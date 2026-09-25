"""
repositories/paper_repo.py
Repository for paper sets and related records.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from repositories.database import (
    PaperRequestDB,
    PaperSetDB,
    PaperQuestionDB,
    GeneratedQuestionDB,
    UsageHistoryDB,
    get_session,
)
from models.paper import PaperSet, PaperQuestion, CompletePaper


class PaperRepository:

    def save_request(self, paper: CompletePaper, num_sets: int,
                     l2_pct: int, l3_pct: int, selected_chapters: list[int],
                     model_provider: str, model_name: str) -> None:
        with get_session() as session:
            req = PaperRequestDB(
                request_id=paper.request_id,
                exam_type=paper.exam_type if isinstance(paper.exam_type, str) else paper.exam_type.value,
                course_name=paper.course_name,
                academic_year=paper.academic_year,
                num_sets=num_sets,
                random_seed=paper.random_seed,
                l2_percent=l2_pct,
                l3_percent=l3_pct,
                selected_chapters=json.dumps(selected_chapters),
                model_provider=model_provider,
                model_name=model_name,
                status="GENERATED",
            )
            session.add(req)

    def save_set(self, paper_set: PaperSet, request_id: str) -> None:
        with get_session() as session:
            # Remove existing if any
            session.query(PaperSetDB).filter(
                PaperSetDB.set_id == paper_set.set_id
            ).delete()
            db_set = PaperSetDB(
                request_id=request_id,
                set_id=paper_set.set_id,
                set_index=paper_set.set_index,
                exam_type=paper_set.exam_type if isinstance(paper_set.exam_type, str) else paper_set.exam_type.value,
                status=paper_set.status if isinstance(paper_set.status, str) else paper_set.status.value,
                generated_at=paper_set.generated_at,
                faculty_notes=paper_set.faculty_notes,
                validation_status=paper_set.validation_status,
                validation_findings=json.dumps(paper_set.validation_findings),
            )
            session.add(db_set)
            for pq in paper_set.questions:
                db_pq = PaperQuestionDB(
                    paper_set_id=paper_set.set_id,
                    slot_id=pq.slot_id,
                    main_question_number=pq.main_question_number,
                    part=pq.part,
                    unit_number=pq.unit_number,
                    chapter_number=pq.chapter_number,
                    chapter_name=pq.chapter_name,
                    question_text=pq.question_text,
                    bloom_level=pq.bloom_level if isinstance(pq.bloom_level, str) else pq.bloom_level.value,
                    marks=pq.marks,
                    source=pq.source if isinstance(pq.source, str) else pq.source.value,
                    approval_status=pq.approval_status if isinstance(pq.approval_status, str) else pq.approval_status.value,
                    question_id=pq.question_id,
                    generated_id=pq.generated_id,
                    valuation_points=json.dumps(
                        [vp.model_dump() for vp in pq.valuation_scheme.valuation_points]
                        if pq.valuation_scheme else []
                    ),
                    bloom_justification=pq.bloom_justification,
                    similarity_status=pq.similarity_status,
                )
                session.add(db_pq)

    def update_set_status(self, set_id: str, status: str,
                          approved_at: Optional[datetime] = None,
                          exported_at: Optional[datetime] = None,
                          notes: Optional[str] = None) -> None:
        with get_session() as session:
            db_set = session.query(PaperSetDB).filter(
                PaperSetDB.set_id == set_id
            ).first()
            if db_set:
                db_set.status = status
                if approved_at:
                    db_set.approved_at = approved_at
                if exported_at:
                    db_set.exported_at = exported_at
                if notes is not None:
                    db_set.faculty_notes = notes

    def update_question_text(self, paper_set_id: str, slot_id: str, new_text: str) -> None:
        with get_session() as session:
            pq = session.query(PaperQuestionDB).filter(
                PaperQuestionDB.paper_set_id == paper_set_id,
                PaperQuestionDB.slot_id == slot_id,
            ).first()
            if pq:
                pq.question_text = new_text

    def update_question_status(self, paper_set_id: str, slot_id: str,
                               status: str, new_text: Optional[str] = None) -> None:
        with get_session() as session:
            pq = session.query(PaperQuestionDB).filter(
                PaperQuestionDB.paper_set_id == paper_set_id,
                PaperQuestionDB.slot_id == slot_id,
            ).first()
            if pq:
                pq.approval_status = status
                if new_text:
                    pq.question_text = new_text

    def get_set(self, set_id: str) -> Optional[dict]:
        with get_session() as session:
            db = session.query(PaperSetDB).filter(
                PaperSetDB.set_id == set_id
            ).first()
            if db is None:
                return None
            return {
                "set_id": db.set_id,
                "exam_type": db.exam_type,
                "status": db.status,
                "validation_status": db.validation_status,
                "validation_findings": db.validation_findings or "[]",
                "faculty_notes": db.faculty_notes,
                "generated_at": db.generated_at,
                "approved_at": db.approved_at,
                "exported_at": db.exported_at,
            }

    def get_all_sets(self) -> list[dict]:
        with get_session() as session:
            rows = (
                session.query(PaperSetDB)
                .order_by(PaperSetDB.generated_at.desc())
                .all()
            )
            return [
                {
                    "set_id": r.set_id,
                    "exam_type": r.exam_type,
                    "status": r.status,
                    "validation_status": r.validation_status,
                    "generated_at": r.generated_at,
                }
                for r in rows
            ]

    def get_questions_for_set(self, set_id: str) -> list[dict]:
        with get_session() as session:
            rows = (
                session.query(PaperQuestionDB)
                .filter(PaperQuestionDB.paper_set_id == set_id)
                .order_by(PaperQuestionDB.main_question_number, PaperQuestionDB.part)
                .all()
            )
            return [
                {
                    "id": r.id,
                    "slot_id": r.slot_id,
                    "main_question_number": r.main_question_number,
                    "part": r.part,
                    "unit_number": r.unit_number,
                    "chapter_number": r.chapter_number,
                    "chapter_name": r.chapter_name,
                    "question_text": r.question_text,
                    "bloom_level": r.bloom_level,
                    "marks": r.marks,
                    "source": r.source,
                    "approval_status": r.approval_status,
                    "question_id": r.question_id,
                    "generated_id": r.generated_id,
                    "bloom_justification": r.bloom_justification,
                    "similarity_status": r.similarity_status,
                }
                for r in rows
            ]

    def save_generated_question(
        self,
        generated_id: str,
        paper_set_id: str,
        unit_number: int,
        chapter_number: int,
        chapter_name: str,
        question_text: str,
        bloom_level: str,
        model_answer: str,
        valuation_points: list[dict],
        bloom_justification: str,
        syllabus_grounding: list[str],
    ) -> None:
        with get_session() as session:
            existing = session.query(GeneratedQuestionDB).filter(
                GeneratedQuestionDB.generated_id == generated_id
            ).first()
            if existing:
                return
            db_gq = GeneratedQuestionDB(
                generated_id=generated_id,
                paper_set_id=paper_set_id,
                unit_number=unit_number,
                chapter_number=chapter_number,
                chapter_name=chapter_name,
                question_text=question_text,
                bloom_level=bloom_level,
                model_answer=model_answer,
                valuation_points=json.dumps(valuation_points),
                bloom_justification=bloom_justification,
                syllabus_grounding=json.dumps(syllabus_grounding),
                approval_status="PENDING",
            )
            session.add(db_gq)

    def record_usage(self, question_id: str, source: str,
                     paper_set_id: str, exam_type: str,
                     academic_year: str = "") -> None:
        with get_session() as session:
            session.add(UsageHistoryDB(
                question_id=question_id,
                source=source,
                paper_set_id=paper_set_id,
                exam_type=exam_type,
                academic_year=academic_year,
            ))

    def get_usage_history(self) -> list[dict]:
        with get_session() as session:
            rows = (
                session.query(UsageHistoryDB)
                .order_by(UsageHistoryDB.used_at.desc())
                .all()
            )
            return [
                {
                    "question_id": r.question_id,
                    "source": r.source,
                    "paper_set_id": r.paper_set_id,
                    "exam_type": r.exam_type,
                    "academic_year": r.academic_year,
                    "used_at": r.used_at,
                }
                for r in rows
            ]

    def get_used_question_ids(self, exclude_paper_set_ids: Optional[list[str]] = None) -> set[str]:
        """Return set of question IDs used in previous papers."""
        with get_session() as session:
            q = session.query(UsageHistoryDB.question_id)
            if exclude_paper_set_ids:
                q = q.filter(UsageHistoryDB.paper_set_id.notin_(exclude_paper_set_ids))
            return {row.question_id for row in q.all()}
