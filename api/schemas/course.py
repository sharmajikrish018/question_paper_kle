"""
api/schemas/course.py — Course & lesson plan I/O models.
Extended to support multi-subject management.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Any


# ── Legacy flat schemas (kept for backward compat) ─────────────────────────────

class ChapterOut(BaseModel):
    unit_number: int
    chapter_number: int
    title: str
    topics: list[str] = []


class CourseStructureOut(BaseModel):
    chapters: list[ChapterOut]
    raw_text_length: int = 0


class CourseStructureIn(BaseModel):
    chapters: list[ChapterOut]


class CourseInfoOut(BaseModel):
    course_name: str = ""
    course_code: str = ""
    department: str = ""
    semester: str = ""
    academic_year: str = ""


class CourseInfoIn(BaseModel):
    course_name: str = ""
    course_code: str = ""
    department: str = ""
    semester: str = ""
    academic_year: str = ""


class LessonPlanExtractionOut(BaseModel):
    chapters: list[ChapterOut]
    confidence: float
    warnings: list[str]
    raw_text_preview: str = ""


# ── Multi-subject schemas ──────────────────────────────────────────────────────

class ChapterIn(BaseModel):
    chapter_number: int = 1
    title: str = ""
    topics: list[str] = []


class ChapterDetail(BaseModel):
    id: Optional[int] = None
    chapter_number: int
    title: str
    topics: list[str] = []


class UnitIn(BaseModel):
    unit_number: int = 1
    title: str = ""
    chapters: list[ChapterIn] = []


class UnitDetail(BaseModel):
    id: Optional[int] = None
    unit_number: int
    title: str
    chapters: list[ChapterDetail] = []


class MinorConfigSchema(BaseModel):
    """
    Maps Minor 1 / Minor 2 to specific unit numbers.
    Each list contains unit_numbers (integers) covered by that minor exam.
    """
    minor1: list[int] = Field(default_factory=list, description="Unit numbers covered by Minor 1")
    minor2: list[int] = Field(default_factory=list, description="Unit numbers covered by Minor 2")


class LpMetadataSchema(BaseModel):
    confidence: float = 0.0
    warnings: list[str] = []
    source_filename: str = ""
    raw_text_length: int = 0


class SubjectIn(BaseModel):
    """Payload to create or update a subject."""
    course_name: str = ""
    course_code: str = ""
    department: str = ""
    semester: str = ""
    academic_year: str = ""
    units: list[UnitIn] = []
    minor_configuration: MinorConfigSchema = Field(default_factory=MinorConfigSchema)
    lp_metadata: Optional[LpMetadataSchema] = None


class SubjectOut(BaseModel):
    """Full subject detail including units and chapters."""
    id: Optional[int] = None
    subject_id: str
    course_name: str = ""
    course_code: str = ""
    department: str = ""
    semester: str = ""
    academic_year: str = ""
    units: list[UnitDetail] = []
    minor_configuration: dict = {}
    lp_metadata: dict = {}
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SubjectListItem(BaseModel):
    """Lightweight summary for the subject selector dropdown."""
    id: Optional[int] = None
    subject_id: str
    course_name: str = ""
    course_code: str = ""
    department: str = ""
    semester: str = ""
    academic_year: str = ""
    minor_configuration: dict = {}
    lp_metadata: dict = {}


class ActiveSubjectResponse(BaseModel):
    active_subject_id: Optional[str] = None


class SetActiveSubjectIn(BaseModel):
    subject_id: str


# ── LP parse response (richer than old LessonPlanExtractionOut) ────────────────

class ParsedUnitSchema(BaseModel):
    unit_number: int
    unit_name: str = ""
    chapters: list[ChapterIn] = []


class LpParseOut(BaseModel):
    """
    Returned by POST /api/subjects/lp-parse.
    Data is NOT saved yet — frontend shows a review/edit screen first.
    Fields that could not be extracted are left as empty strings / null.
    """
    # Course info — may be empty if not found
    course_name: Optional[str] = None
    course_code: Optional[str] = None
    department: Optional[str] = None
    semester: Optional[str] = None   # e.g. "7" or "7th"
    academic_year: Optional[str] = None

    # Structure
    units: list[ParsedUnitSchema] = []

    # Minor config (may be empty if LP doesn't specify assessment mapping)
    minor_configuration: MinorConfigSchema = Field(default_factory=MinorConfigSchema)

    # Parse quality metadata
    confidence: float = 0.0
    warnings: list[str] = []
    raw_text_preview: str = ""
