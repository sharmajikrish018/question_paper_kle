"""
api/schemas/questions.py — Question bank I/O models.
"""
from __future__ import annotations
from pydantic import BaseModel
from typing import Optional


class QuestionOut(BaseModel):
    question_id: str
    unit_number: int
    chapter_number: int
    chapter_name: str
    bloom_level: str
    question_text: str
    marks: int
    model_answer: Optional[str] = None
    difficulty: str = "medium"
    source: str = "QUESTION_BANK"
    approval_status: str = "APPROVED"

    model_config = {"from_attributes": True}


class QuestionUpdateIn(BaseModel):
    question_text: Optional[str] = None
    chapter_number: Optional[int] = None
    unit_number: Optional[int] = None
    bloom_level: Optional[str] = None
    model_answer: Optional[str] = None


class ImportResultOut(BaseModel):
    total_rows: int
    imported: int
    warnings: list[str]
    errors: list[str]
    chapter_completeness: dict[int, dict[str, int]]


class CompletenessOut(BaseModel):
    chapter_number: int
    l2_count: int
    l3_count: int
    total: int
    l2_ok: bool
    l3_ok: bool
    complete: bool
