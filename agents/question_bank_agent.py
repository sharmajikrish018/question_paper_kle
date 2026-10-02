"""
agents/question_bank_agent.py
Validates, normalizes, and reports on question bank quality.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from models.enums import BloomLevel
from models.question import Question
from repositories.question_repo import QuestionRepository
from services.question_bank_service import QuestionBankService, ImportResult
from services.similarity_service import SimilarityService

logger = logging.getLogger(__name__)

EXPECTED_PER_LEVEL = 10
EXPECTED_CHAPTERS = 7


@dataclass
class BankValidationReport:
    total_questions: int = 0
    import_result: Optional[ImportResult] = None
    chapter_completeness: dict = None  # type: ignore
    duplicate_findings: list = None  # type: ignore
    is_usable: bool = False
    summary: str = ""

    def __post_init__(self):
        if self.chapter_completeness is None:
            self.chapter_completeness = {}
        if self.duplicate_findings is None:
            self.duplicate_findings = []


class QuestionBankAgent:
    """
    Agent node 9.3: Question Bank Agent.
    Loads, validates, and prepares the question bank.
    """

    def __init__(self):
        self._service = QuestionBankService()
        self._repo = QuestionRepository()
        self._sim = SimilarityService()

    def load_and_validate(self, file_path: Path) -> BankValidationReport:
        """
        Full pipeline: load file → validate → detect duplicates → report.
        Does NOT automatically import; caller decides.
        """
        report = BankValidationReport()

        # Parse and validate
        import_result = self._service.load_from_file(file_path)
        report.import_result = import_result
        report.total_questions = import_result.imported

        # Duplicate detection within the loaded batch
        texts = [q.question_text for q in import_result.questions]
        dup_findings = self._sim.find_duplicates_in_list(texts)
        report.duplicate_findings = [
            {
                "index_a": i,
                "index_b": j,
                "status": r.status,
                "score": r.max_score,
                "explanation": r.explanation,
                "text_a": texts[i][:80],
                "text_b": texts[j][:80],
            }
            for i, j, r in dup_findings
        ]

        # Chapter completeness
        report.chapter_completeness = import_result.chapter_completeness

        report.is_usable = (
            not import_result.has_fatal_errors and import_result.imported > 0
        )
        report.summary = self._build_summary(report)
        return report

    def import_to_db(self, import_result: ImportResult) -> int:
        """Persist validated questions."""
        return self._service.import_to_database(import_result)

    def get_completeness_report(self) -> dict:
        """Chapter-wise completeness from the database."""
        return self._service.chapter_completeness_report(EXPECTED_CHAPTERS)

    def get_available_questions(
        self,
        subject_id: Optional[str] = None,
        unit_number: Optional[int] = None,
        chapter_number: Optional[int] = None,
        bloom_level: Optional[str] = None,
        exclude_ids: Optional[list[str]] = None,
    ) -> list[Question]:
        """
        Return approved questions filtered by criteria.
        Used by the selection agent.
        Receives domain Question objects directly from the repo.
        """
        if not subject_id:
            from repositories.subject_repo import SubjectRepository
            subject_id = SubjectRepository().get_active_subject_id() or "genai-001"
        questions = self._repo.get_approved(
            subject_id=subject_id,
            unit_number=unit_number,
            chapter_number=chapter_number,
            bloom_level=bloom_level,
            exclude_ids=exclude_ids,
        )
        if not questions and subject_id != "genai-001":
            questions = self._repo.get_approved(
                subject_id="genai-001",
                unit_number=unit_number,
                chapter_number=chapter_number,
                bloom_level=bloom_level,
                exclude_ids=exclude_ids,
            )
        return questions


    def _build_summary(self, report: BankValidationReport) -> str:
        lines = [
            f"Questions loaded: {report.total_questions}",
            f"Fatal errors: {sum(1 for e in report.import_result.errors if e.is_fatal)}",
            f"Warnings: {len(report.import_result.warnings)}",
            f"Duplicate findings: {len(report.duplicate_findings)}",
        ]
        incomplete = [
            ch for ch, data in report.chapter_completeness.items()
            if data.get("L2", 0) != EXPECTED_PER_LEVEL
            or data.get("L3", 0) != EXPECTED_PER_LEVEL
        ]
        if incomplete:
            lines.append(f"Chapters with incomplete banks: {incomplete}")
        return "\n".join(lines)
