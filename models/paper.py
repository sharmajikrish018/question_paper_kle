"""
models/paper.py
Paper composition models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from models.enums import (
    BloomLevel,
    ExamType,
    QuestionSource,
    ApprovalStatus,
    PaperSetStatus,
)
from models.question import QuestionRecord
from models.valuation import ValuationScheme


class PaperQuestion(BaseModel):
    """
    One placed subquestion in a composed paper.
    Carries internal metadata for review but does NOT appear on the student copy.
    """

    slot_id: str  # e.g. "Q1a", "Q2b", "Q7a"
    main_question_number: int  # 1, 2, 3 …
    part: str  # "a" or "b"
    unit_number: int
    chapter_number: int
    chapter_name: str
    question_text: str
    bloom_level: BloomLevel
    marks: int = 10
    source: QuestionSource
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    question_id: Optional[str] = None  # bank original ID
    generated_id: Optional[str] = None  # AI question ID
    valuation_scheme: Optional[ValuationScheme] = None
    bloom_justification: Optional[str] = None
    similarity_status: Optional[str] = None  # e.g. "OK", "WARNING 0.82"

    model_config = ConfigDict(use_enum_values=True)



class PaperSet(BaseModel):
    """
    One complete generated paper set.
    """

    set_id: str  # e.g. "SET-A", "SET-B"
    set_index: int  # 0-based
    exam_type: ExamType
    status: PaperSetStatus = PaperSetStatus.GENERATED
    questions: list[PaperQuestion] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    exported_at: Optional[datetime] = None
    faculty_notes: str = ""
    exam_title: Optional[str] = None
    duration: Optional[str] = None
    max_marks: Optional[int] = None
    instructions: Optional[str] = None

    # Validation result summary
    validation_status: Optional[str] = None
    validation_findings: list[dict] = Field(default_factory=list)

    model_config = ConfigDict(use_enum_values=True)


    @property
    def is_approved(self) -> bool:
        return self.status == PaperSetStatus.APPROVED

    @property
    def is_exported(self) -> bool:
        return self.status == PaperSetStatus.EXPORTED

    @property
    def all_questions_approved(self) -> bool:
        return all(
            q.approval_status == ApprovalStatus.APPROVED
            for q in self.questions
        )


class CompletePaper(BaseModel):
    """
    Wrapper for a complete generation request containing multiple sets.
    """

    request_id: str
    exam_type: ExamType
    course_name: str = "Generative AI"
    academic_year: str = ""
    sets: list[PaperSet] = Field(default_factory=list)
    random_seed: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(use_enum_values=True)

