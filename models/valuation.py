"""
models/valuation.py
Valuation scheme models.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class ValuationPoint(BaseModel):
    """
    A single grading criterion within a 10-mark scheme.
    """

    criterion: str
    marks: int = Field(ge=1)
    alternative_acceptable: Optional[str] = None


class ValuationScheme(BaseModel):
    """
    Complete valuation scheme for one question.
    Total of all ValuationPoints must equal exactly 10.
    """

    question_ref: str  # question_id or generated_id
    expected_answer: str
    key_points: list[str] = Field(default_factory=list)
    valuation_points: list[ValuationPoint] = Field(min_length=1)
    alternative_answers: list[str] = Field(default_factory=list)
    faculty_notes: Optional[str] = None
    approval_status: str = "PENDING"
    total_marks: int = 10

    @property
    def computed_total(self) -> int:
        return sum(vp.marks for vp in self.valuation_points)

    def validate_total(self) -> bool:
        return self.computed_total == self.total_marks
