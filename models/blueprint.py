"""
models/blueprint.py
Blueprint models that encode the immutable generation contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from pydantic import BaseModel, Field

from models.enums import BloomLevel, ExamType, QuestionSource


class SourceAllocation(BaseModel):
    """
    Source breakdown for one unit or for the full paper.
    """

    bank_count: int
    ai_count: int
    total: int

    @property
    def bank_percent(self) -> float:
        if self.total == 0:
            return 0.0
        return round(self.bank_count / self.total * 100, 2)

    @property
    def ai_percent(self) -> float:
        if self.total == 0:
            return 0.0
        return round(self.ai_count / self.total * 100, 2)


class BloomAllocation(BaseModel):
    """
    Bloom-level breakdown.
    """

    l2_count: int
    l3_count: int
    total: int

    @property
    def l2_percent(self) -> float:
        if self.total == 0:
            return 0.0
        return round(self.l2_count / self.total * 100, 2)

    @property
    def l3_percent(self) -> float:
        if self.total == 0:
            return 0.0
        return round(self.l3_count / self.total * 100, 2)


class UnitAllocation(BaseModel):
    """
    Per-unit source and Bloom allocation.
    """

    unit_number: int
    source: SourceAllocation
    bloom: BloomAllocation
    chapter_numbers: list[int] = Field(default_factory=list)
    questions_to_print: int = 0
    questions_to_attempt: int = 0
    marks_to_attempt: int = 0
    main_questions: int = 0  # e.g. 3 for Unit 1 End-Sem
    choice_instruction: str = ""


class MinorBlueprint(BaseModel):
    """
    Immutable blueprint for a Minor / Internal Examination paper.

    Fixed structure:
    - 3 main questions (Q1-Q3), each with (a) and (b)
    - 6 printed subquestions × 10 marks each
    - Student answers any 2 complete questions → 4 subquestions
    - Source: 4 bank + 2 AI (nearest feasible to 70:30)
    """

    exam_type: ExamType = ExamType.MINOR
    exam_subtype: str = "ISA-I"  # "ISA-I" | "ISA-II"
    total_printed_questions: int = 6
    total_attempted_marks: int = 40
    duration_minutes: int = 75
    main_question_count: int = 3
    parts_per_question: int = 2
    marks_per_part: int = 10
    sub_question_marks: list[int] = Field(default_factory=list)  # e.g. [10, 5] from saved scheme
    choice_instruction: str = "Answer any TWO full questions."

    # Source allocation
    source: SourceAllocation = Field(
        default_factory=lambda: SourceAllocation(
            bank_count=4, ai_count=2, total=6
        )
    )
    source_note: str = (
        "Nearest feasible integer allocation to 70:30 "
        "(actual: 66.67% bank, 33.33% AI)"
    )

    # Bloom allocation (default 50:50)
    bloom: BloomAllocation = Field(
        default_factory=lambda: BloomAllocation(
            l2_count=3, l3_count=3, total=6
        )
    )

    # Bank source/Bloom matrix
    bank_l2: int = 2
    bank_l3: int = 2
    ai_l2: int = 1
    ai_l3: int = 1

    # Faculty-selected chapters for this paper
    selected_chapters: list[int] = Field(default_factory=list)

    # Configuration
    l2_percent_target: int = 50
    l3_percent_target: int = 50
    tolerance_percent: int = 5
    random_seed: Optional[int] = None


class EndSemBlueprint(BaseModel):
    """
    Immutable blueprint for an End-Semester Examination.

    Fixed structure:
    - Unit 1: Q1-Q3, each (a)+(b), answer any 2 → 6 printed / 4 attempted
    - Unit 2: Q4-Q6, each (a)+(b), answer any 2 → 6 printed / 4 attempted
    - Unit 3: Q7-Q8, each (a)+(b), answer any 1 → 4 printed / 2 attempted
    - Total: 16 printed subquestions, 100 attempted marks
    - Source: 11 bank + 5 AI (nearest feasible to 70:30)
    """

    exam_type: ExamType = ExamType.END_SEM
    exam_subtype: str = "ESA"
    total_printed_questions: int = 16
    total_attempted_marks: int = 100
    duration_minutes: int = 180
    sub_question_marks: list[int] = Field(default_factory=list)  # e.g. [10, 10]
    choice_instruction: str = "Answer any TWO full questions from Unit 1 & 2, and one from Unit 3."

    # Source allocation
    source: SourceAllocation = Field(
        default_factory=lambda: SourceAllocation(
            bank_count=11, ai_count=5, total=16
        )
    )
    source_note: str = (
        "Nearest feasible integer allocation to 70:30 "
        "(actual: 68.75% bank, 31.25% AI)"
    )

    # Bloom allocation (default 50:50)
    bloom: BloomAllocation = Field(
        default_factory=lambda: BloomAllocation(
            l2_count=8, l3_count=8, total=16
        )
    )

    # Unit allocations (default preferred distribution)
    unit_allocations: list[UnitAllocation] = Field(default_factory=list)

    # Configuration
    l2_percent_target: int = 50
    l3_percent_target: int = 50
    tolerance_percent: int = 5
    random_seed: Optional[int] = None

    @classmethod
    def default_unit_allocations(cls) -> list[UnitAllocation]:
        """Return the preferred default per-unit allocation."""
        return [
            UnitAllocation(
                unit_number=1,
                source=SourceAllocation(bank_count=4, ai_count=2, total=6),
                bloom=BloomAllocation(l2_count=3, l3_count=3, total=6),
                questions_to_print=6,
                questions_to_attempt=4,
                marks_to_attempt=40,
                main_questions=3,
                choice_instruction="Answer any TWO full questions.",
            ),
            UnitAllocation(
                unit_number=2,
                source=SourceAllocation(bank_count=4, ai_count=2, total=6),
                bloom=BloomAllocation(l2_count=3, l3_count=3, total=6),
                questions_to_print=6,
                questions_to_attempt=4,
                marks_to_attempt=40,
                main_questions=3,
                choice_instruction="Answer any TWO full questions.",
            ),
            UnitAllocation(
                unit_number=3,
                source=SourceAllocation(bank_count=3, ai_count=1, total=4),
                bloom=BloomAllocation(l2_count=2, l3_count=2, total=4),
                questions_to_print=4,
                questions_to_attempt=2,
                marks_to_attempt=20,
                main_questions=2,
                choice_instruction="Answer any ONE full question.",
            ),
        ]
