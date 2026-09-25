"""
repositories/question_repo.py
Repository for question-bank CRUD operations.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from models.enums import BloomLevel, QuestionSource, ApprovalStatus
from models.question import Question
from repositories.database import QuestionDB, get_session


class QuestionRepository:
    """
    Data-access layer for bank questions.
    All DB interactions go through this class.
    """

    def __init__(self, session: Optional[Session] = None):
        self._session = session

    def _get_session(self):
        if self._session:
            return self._session
        raise RuntimeError("No session provided")

    # ── Write operations ──────────────────────────────────────────────────────

    def upsert(self, question: Question) -> QuestionDB:
        """Insert or update a question record."""
        with get_session() as session:
            existing = (
                session.query(QuestionDB)
                .filter(QuestionDB.question_id == question.question_id)
                .first()
            )
            vp_json = json.dumps(
                [vp.model_dump() for vp in question.valuation_points]
            )
            if existing:
                existing.question_text = question.question_text
                existing.bloom_level = question.bloom_level.value if hasattr(question.bloom_level, 'value') else question.bloom_level
                existing.model_answer = question.model_answer
                existing.valuation_points = vp_json
                existing.approval_status = question.approval_status.value if hasattr(question.approval_status, 'value') else question.approval_status
                existing.chapter_name = question.chapter_name
                return existing
            else:
                db_q = QuestionDB(
                    question_id=question.question_id,
                    course_name=question.course_name,
                    unit_number=question.unit_number,
                    chapter_number=question.chapter_number,
                    chapter_name=question.chapter_name,
                    question_text=question.question_text,
                    bloom_level=question.bloom_level.value if hasattr(question.bloom_level, 'value') else question.bloom_level,
                    marks=question.marks,
                    question_type=question.question_type.value if hasattr(question.question_type, 'value') else question.question_type,
                    difficulty=question.difficulty.value if hasattr(question.difficulty, 'value') else question.difficulty,
                    model_answer=question.model_answer,
                    valuation_points=vp_json,
                    source=question.source.value if hasattr(question.source, 'value') else question.source,
                    approval_status=question.approval_status.value if hasattr(question.approval_status, 'value') else question.approval_status,
                    usage_count=question.usage_count,
                    last_used_at=question.last_used_at,
                )
                session.add(db_q)
                return db_q

    def bulk_upsert(self, questions: list[Question]) -> int:
        """Upsert many questions. Returns count inserted/updated."""
        for q in questions:
            self.upsert(q)
        return len(questions)

    def increment_usage(self, question_id: str) -> None:
        """Increment usage count and set last_used_at."""
        with get_session() as session:
            q = session.query(QuestionDB).filter(
                QuestionDB.question_id == question_id
            ).first()
            if q:
                q.usage_count = (q.usage_count or 0) + 1
                q.last_used_at = datetime.utcnow()

    def update_embedding(self, question_id: str, embedding: list[float]) -> None:
        """Store embedding vector for semantic search."""
        with get_session() as session:
            q = session.query(QuestionDB).filter(
                QuestionDB.question_id == question_id
            ).first()
            if q:
                q.embedding = json.dumps(embedding)

    # ── Read operations ───────────────────────────────────────────────────────

    def get_by_id(self, question_id: str) -> Optional[Question]:
        with get_session() as session:
            db = (
                session.query(QuestionDB)
                .filter(QuestionDB.question_id == question_id)
                .first()
            )
            if db is None:
                return None
            return self._db_to_domain(db)

    def get_all(self) -> list[Question]:
        with get_session() as session:
            rows = session.query(QuestionDB).all()
            return [self._db_to_domain(r) for r in rows]

    def get_by_chapter(
        self, chapter_number: int, bloom_level: Optional[str] = None
    ) -> list[Question]:
        with get_session() as session:
            q = session.query(QuestionDB).filter(
                QuestionDB.chapter_number == chapter_number
            )
            if bloom_level:
                q = q.filter(QuestionDB.bloom_level == bloom_level)
            return [self._db_to_domain(r) for r in q.all()]

    def get_by_unit(
        self, unit_number: int, bloom_level: Optional[str] = None
    ) -> list[Question]:
        with get_session() as session:
            q = session.query(QuestionDB).filter(
                QuestionDB.unit_number == unit_number,
                QuestionDB.approval_status == "APPROVED",
            )
            if bloom_level:
                q = q.filter(QuestionDB.bloom_level == bloom_level)
            return [self._db_to_domain(r) for r in q.all()]

    def get_approved(
        self,
        unit_number: Optional[int] = None,
        chapter_number: Optional[int] = None,
        bloom_level: Optional[str] = None,
        exclude_ids: Optional[list[str]] = None,
    ) -> list[Question]:
        with get_session() as session:
            q = session.query(QuestionDB).filter(
                QuestionDB.approval_status == "APPROVED"
            )
            if unit_number is not None:
                q = q.filter(QuestionDB.unit_number == unit_number)
            if chapter_number is not None:
                q = q.filter(QuestionDB.chapter_number == chapter_number)
            if bloom_level:
                q = q.filter(QuestionDB.bloom_level == bloom_level)
            if exclude_ids:
                q = q.filter(QuestionDB.question_id.notin_(exclude_ids))
            return [self._db_to_domain(r) for r in q.all()]

    def _db_to_domain(self, db: QuestionDB) -> Question:
        """Convert ORM instance to domain object while session is still open."""
        return Question(
            question_id=db.question_id,
            course_name=db.course_name or "Generative AI",
            unit_number=db.unit_number,
            chapter_number=db.chapter_number,
            chapter_name=db.chapter_name,
            question_text=db.question_text,
            bloom_level=db.bloom_level,
            marks=db.marks,
            model_answer=db.model_answer,
            source="QUESTION_BANK",
            approval_status=db.approval_status or "APPROVED",
            usage_count=db.usage_count or 0,
        )

    def count_by_chapter_bloom(self) -> dict[tuple[int, str], int]:
        """
        Returns {(chapter_number, bloom_level): count} for completeness checks.
        """
        result: dict[tuple[int, str], int] = {}
        with get_session() as session:
            from sqlalchemy import func
            rows = (
                session.query(
                    QuestionDB.chapter_number,
                    QuestionDB.bloom_level,
                    func.count().label("count"),
                )
                .group_by(QuestionDB.chapter_number, QuestionDB.bloom_level)
                .all()
            )
            for ch, bl, cnt in rows:
                result[(ch, bl)] = cnt
        return result

    def delete_all(self) -> int:
        """Delete all questions. Used only for tests."""
        with get_session() as session:
            count = session.query(QuestionDB).count()
            session.query(QuestionDB).delete()
            return count

    def count_total(self) -> int:
        with get_session() as session:
            return session.query(QuestionDB).count()
