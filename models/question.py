"""
models/question.py
Question domain models using Pydantic v2.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from models.enums import (
    BloomLevel,
    QuestionSource,
    ApprovalStatus,
    DifficultyLevel,
    QuestionType,
)
from models.valuation import ValuationPoint


class Question(BaseModel):
    """
    Normalized question record from the approved question bank.
    The faculty-provided Bloom level is treated as authoritative.
    """

    question_id: str
    course_name: str = "Generative AI"
    unit_number: int = Field(ge=1, le=3)
    chapter_number: int = Field(ge=1)
    chapter_name: str
    question_text: str
    bloom_level: BloomLevel
    marks: int = Field(default=10, ge=1, le=100)
    question_type: QuestionType = QuestionType.DESCRIPTIVE
    difficulty: DifficultyLevel = DifficultyLevel.MEDIUM
    model_answer: Optional[str] = None
    valuation_points: list[ValuationPoint] = Field(default_factory=list)
    source: QuestionSource = QuestionSource.QUESTION_BANK
    approval_status: ApprovalStatus = ApprovalStatus.APPROVED
    usage_count: int = Field(default=0, ge=0)
    last_used_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("question_text")
    @classmethod
    def text_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("question_text must not be empty")
        return v.strip()

    @field_validator("question_id")
    @classmethod
    def id_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("question_id must not be empty")
        return v.strip()

    model_config = ConfigDict(use_enum_values=True)



class GeneratedQuestion(BaseModel):
    """
    A question produced by the AI Question Generation Agent.
    Always starts with PENDING approval.
    Validated using Pydantic from LLM structured output.
    """

    question_text: str
    unit_number: int = Field(default=1, ge=1, le=5)
    chapter_number: int = Field(default=1, ge=1)
    chapter_name: str = Field(default="Chapter 1")
    bloom_level: BloomLevel = Field(default=BloomLevel.L2)
    marks: int = Field(default=10, ge=1, le=100)
    question_type: QuestionType = QuestionType.DESCRIPTIVE
    difficulty: DifficultyLevel = DifficultyLevel.MEDIUM
    model_answer: str = Field(default="Model answer provided by generation agent.")
    valuation_points: list[ValuationPoint] = Field(
        default_factory=lambda: [
            ValuationPoint(criterion="Key concept explanation and technical depth", marks=5),
            ValuationPoint(criterion="Illustration with examples and clarity", marks=5),
        ]
    )
    bloom_justification: str = Field(default="Aligned with specified Bloom taxonomy level.")
    syllabus_grounding: list[str] = Field(default_factory=list)
    source: QuestionSource = QuestionSource.AI_GENERATED
    approval_status: ApprovalStatus = ApprovalStatus.PENDING

    @field_validator("question_text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("question_text must not be empty")
        return v.strip()

    @model_validator(mode="after")
    def valuation_must_total_ten(self) -> "GeneratedQuestion":
        if not self.valuation_points:
            self.valuation_points = [
                ValuationPoint(criterion="Key concept explanation and technical depth", marks=5),
                ValuationPoint(criterion="Illustration with examples and clarity", marks=5),
            ]
            return self
        total = sum(vp.marks for vp in self.valuation_points)
        if total != 10:
            diff = 10 - total
            last_vp = self.valuation_points[-1]
            new_marks = last_vp.marks + diff
            if new_marks >= 1:
                self.valuation_points[-1] = ValuationPoint(
                    criterion=last_vp.criterion,
                    marks=new_marks,
                    alternative_acceptable=last_vp.alternative_acceptable,
                )
            else:
                n = len(self.valuation_points)
                base = 10 // n
                rem = 10 % n
                new_vps = []
                for i, vp in enumerate(self.valuation_points):
                    m = base + (1 if i < rem else 0)
                    new_vps.append(
                        ValuationPoint(
                            criterion=vp.criterion,
                            marks=m,
                            alternative_acceptable=vp.alternative_acceptable,
                        )
                    )
                self.valuation_points = new_vps
        return self

    model_config = ConfigDict(use_enum_values=True)



class QuestionRecord(BaseModel):
    """
    A unified record wrapping either a bank question or a generated question,
    plus a local unique ID assigned by the database layer.
    """

    local_id: Optional[int] = None
    generated_id: Optional[str] = None  # e.g. GENAI-GEN-20240101-001
    source: QuestionSource
    bloom_level: BloomLevel
    unit_number: int
    chapter_number: int
    chapter_name: str
    question_text: str
    marks: int = 10
    model_answer: Optional[str] = None
    valuation_points: list[ValuationPoint] = Field(default_factory=list)
    bloom_justification: Optional[str] = None
    syllabus_grounding: list[str] = Field(default_factory=list)
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    difficulty: DifficultyLevel = DifficultyLevel.MEDIUM
    question_id: Optional[str] = None  # original bank ID if from bank

    model_config = ConfigDict(use_enum_values=True)
