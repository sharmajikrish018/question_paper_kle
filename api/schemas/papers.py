"""
api/schemas/papers.py — Paper generation, review & export I/O models.
"""
from __future__ import annotations
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class GenerateRequest(BaseModel):
    exam_type: str = "MINOR"          # "MINOR" | "END_SEM"
    num_sets: int = 1
    l2_percent: int = 50
    l3_percent: int = 50
    selected_chapters: list[int] = []
    random_seed: Optional[int] = None
    tolerance_percent: int = 5
    academic_year: str = "2024-25"
    department: str = "Computer Science & Engineering"
    exclude_used_question_ids: bool = True


class ValidationFindingOut(BaseModel):
    rule_id: str
    severity: str
    message: str
    expected: Optional[str] = None
    actual: Optional[str] = None
    suggested_action: Optional[str] = None
    affected_questions: list[str] = []


class ValidationReportOut(BaseModel):
    set_id: str
    exam_type: str
    status: str
    findings: list[ValidationFindingOut]
    source_bank_count: int
    source_ai_count: int
    source_bank_percent: float
    source_ai_percent: float
    bloom_l2_count: int
    bloom_l3_count: int
    bloom_l2_percent: float
    bloom_l3_percent: float
    total_printed: int
    marks_total: int


class PaperQuestionOut(BaseModel):
    slot_id: str
    question_text: str
    bloom_level: str
    marks: int
    source: str
    chapter_number: int
    chapter_name: str
    unit_number: int
    approval_status: str
    model_answer: Optional[str] = None

    model_config = {"from_attributes": True}


class PaperSetOut(BaseModel):
    set_id: str
    exam_type: str
    status: str
    created_at: Optional[datetime] = None
    question_count: int
    questions: list[PaperQuestionOut] = []

    model_config = {"from_attributes": True}


class GenerateResponse(BaseModel):
    success: bool
    paper_set_ids: list[str]
    validation_reports: list[ValidationReportOut]
    errors: list[str]
    warnings: list[str]


class QuestionStatusUpdate(BaseModel):
    status: str          # "APPROVED" | "REJECTED"
    edited_text: Optional[str] = None


class PaperListItem(BaseModel):
    set_id: str
    exam_type: str
    status: str
    created_at: Optional[datetime] = None
    question_count: int

    model_config = {"from_attributes": True}
