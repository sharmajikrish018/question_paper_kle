"""
repositories/subject_repo.py
Full CRUD repository for multi-subject (CourseDB → UnitDB → ChapterDB) management.

Each "subject" is one CourseDB row with its own tree of UnitDB → ChapterDB rows.
A stable slug (subject_id) is the external identifier, e.g. "agentic-ai-26ECAC401".
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Optional

from repositories.database import (
    AppSettingDB, ChapterDB, CourseDB, UnitDB, get_session
)


# ── Slug helper ────────────────────────────────────────────────────────────────

def _make_slug(name: str, code: str) -> str:
    """Produce a stable, URL-safe slug from course name + code."""
    base = f"{name}-{code}" if code else name
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", base).strip("-").lower()
    return slug or str(uuid.uuid4())[:8]


# ── Public data shapes (plain dicts — no Pydantic to avoid circular deps) ──────

def _chapter_to_dict(ch: ChapterDB) -> dict:
    return {
        "id": ch.id,
        "chapter_number": ch.chapter_number,
        "title": ch.title,
        "topics": json.loads(ch.topics) if ch.topics else [],
    }


def _unit_to_dict(unit: UnitDB, include_chapters: bool = True) -> dict:
    d: dict = {
        "id": unit.id,
        "unit_number": unit.unit_number,
        "title": unit.title or f"Unit {unit.unit_number}",
    }
    if include_chapters:
        d["chapters"] = [_chapter_to_dict(ch) for ch in sorted(unit.chapters, key=lambda c: c.chapter_number)]
    return d


def _course_to_dict(course: CourseDB, include_units: bool = True) -> dict:
    d: dict = {
        "id": course.id,
        "subject_id": course.subject_id,
        "course_name": course.name,
        "course_code": course.code or "",
        "department": course.department or "",
        "semester": course.semester or "",
        "academic_year": course.academic_year or "",
        "minor_configuration": json.loads(course.minor_configuration) if course.minor_configuration else {},
        "lp_metadata": json.loads(course.lp_metadata) if course.lp_metadata else {},
        "created_at": course.created_at.isoformat() if course.created_at else None,
        "updated_at": course.updated_at.isoformat() if course.updated_at else None,
    }
    if include_units:
        d["units"] = [_unit_to_dict(u) for u in sorted(course.units, key=lambda u: u.unit_number)]
    return d


# ── Repository ──────────────────────────────────────────────────────────────────

class SubjectRepository:

    # ── Active subject tracking ────────────────────────────────────────────────

    def get_active_subject_id(self) -> Optional[str]:
        """Return the slug of the currently active subject, or None."""
        with get_session() as session:
            row = session.query(AppSettingDB).filter(
                AppSettingDB.key == "active_subject_id"
            ).first()
            return row.value if row else None

    def set_active_subject_id(self, subject_id: str) -> None:
        with get_session() as session:
            row = session.query(AppSettingDB).filter(
                AppSettingDB.key == "active_subject_id"
            ).first()
            if row:
                row.value = subject_id
            else:
                session.add(AppSettingDB(key="active_subject_id", value=subject_id))

    # ── List ───────────────────────────────────────────────────────────────────

    def list_subjects(self) -> list[dict]:
        """Return summary list (no chapters) for all subjects."""
        with get_session() as session:
            courses = session.query(CourseDB).order_by(CourseDB.created_at).all()
            return [_course_to_dict(c, include_units=False) for c in courses]

    # ── Get ────────────────────────────────────────────────────────────────────

    def get_subject_by_slug(self, subject_id: str) -> Optional[dict]:
        with get_session() as session:
            course = session.query(CourseDB).filter(
                CourseDB.subject_id == subject_id
            ).first()
            if not course:
                return None
            return _course_to_dict(course)

    def get_subject_by_db_id(self, db_id: int) -> Optional[dict]:
        with get_session() as session:
            course = session.query(CourseDB).filter(CourseDB.id == db_id).first()
            if not course:
                return None
            return _course_to_dict(course)

    # ── Create ─────────────────────────────────────────────────────────────────

    def create_subject(
        self,
        course_name: str,
        course_code: str = "",
        department: str = "",
        semester: str = "",
        academic_year: str = "",
        units: Optional[list[dict]] = None,
        minor_configuration: Optional[dict] = None,
        lp_metadata: Optional[dict] = None,
        subject_id: Optional[str] = None,  # pass to avoid collision
    ) -> dict:
        """
        Create a new subject with its unit/chapter tree.
        `units` format:
          [{"unit_number": 1, "title": "...", "chapters": [
              {"chapter_number": 1, "title": "...", "topics": [...]}
          ]}]
        """
        slug = subject_id or _make_slug(course_name, course_code)

        # Ensure slug uniqueness
        with get_session() as session:
            existing = session.query(CourseDB).filter(CourseDB.subject_id == slug).first()
            if existing:
                slug = f"{slug}-{str(uuid.uuid4())[:4]}"

        with get_session() as session:
            course = CourseDB(
                subject_id=slug,
                name=course_name,
                code=course_code,
                department=department,
                semester=semester,
                academic_year=academic_year,
                minor_configuration=json.dumps(minor_configuration or {}),
                lp_metadata=json.dumps(lp_metadata or {}),
            )
            session.add(course)
            session.flush()  # get course.id

            for unit_data in (units or []):
                unit = UnitDB(
                    course_id=course.id,
                    unit_number=unit_data.get("unit_number", 1),
                    title=unit_data.get("title") or f"Unit {unit_data.get('unit_number', 1)}",
                )
                session.add(unit)
                session.flush()

                for ch_data in unit_data.get("chapters", []):
                    chapter = ChapterDB(
                        unit_id=unit.id,
                        chapter_number=ch_data.get("chapter_number", 1),
                        title=ch_data.get("title", ""),
                        topics=json.dumps(ch_data.get("topics", [])),
                    )
                    session.add(chapter)

            session.flush()
            # Need to reload after commit – return slug for lookup
            result_slug = course.subject_id

        # Re-query after session closes to get full populated object
        return self.get_subject_by_slug(result_slug)  # type: ignore[return-value]

    # ── Update ─────────────────────────────────────────────────────────────────

    def update_subject(
        self,
        subject_id: str,
        course_name: Optional[str] = None,
        course_code: Optional[str] = None,
        department: Optional[str] = None,
        semester: Optional[str] = None,
        academic_year: Optional[str] = None,
        units: Optional[list[dict]] = None,
        minor_configuration: Optional[dict] = None,
        lp_metadata: Optional[dict] = None,
    ) -> Optional[dict]:
        with get_session() as session:
            course = session.query(CourseDB).filter(
                CourseDB.subject_id == subject_id
            ).first()
            if not course:
                return None

            if course_name is not None:
                course.name = course_name
            if course_code is not None:
                course.code = course_code
            if department is not None:
                course.department = department
            if semester is not None:
                course.semester = semester
            if academic_year is not None:
                course.academic_year = academic_year
            if minor_configuration is not None:
                course.minor_configuration = json.dumps(minor_configuration)
            if lp_metadata is not None:
                course.lp_metadata = json.dumps(lp_metadata)

            # Replace units/chapters if provided
            if units is not None:
                # delete-orphan cascade handles cleanup
                for old_unit in list(course.units):
                    session.delete(old_unit)
                session.flush()

                for unit_data in units:
                    unit = UnitDB(
                        course_id=course.id,
                        unit_number=unit_data.get("unit_number", 1),
                        title=unit_data.get("title") or f"Unit {unit_data.get('unit_number', 1)}",
                    )
                    session.add(unit)
                    session.flush()

                    for ch_data in unit_data.get("chapters", []):
                        chapter = ChapterDB(
                            unit_id=unit.id,
                            chapter_number=ch_data.get("chapter_number", 1),
                            title=ch_data.get("title", ""),
                            topics=json.dumps(ch_data.get("topics", [])),
                        )
                        session.add(chapter)

        return self.get_subject_by_slug(subject_id)

    # ── Delete ─────────────────────────────────────────────────────────────────

    def delete_subject(self, subject_id: str) -> bool:
        with get_session() as session:
            course = session.query(CourseDB).filter(
                CourseDB.subject_id == subject_id
            ).first()
            if not course:
                return False
            session.delete(course)
        return True

    # ── Active subject convenience (returns full dict or None) ─────────────────

    def get_active_subject(self) -> Optional[dict]:
        slug = self.get_active_subject_id()
        if not slug:
            return None
        return self.get_subject_by_slug(slug)
