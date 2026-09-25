"""
models/enums.py
All application-wide enumeration types.
"""
from enum import Enum


class BloomLevel(str, Enum):
    L2 = "L2"
    L3 = "L3"

    @property
    def label(self) -> str:
        labels = {
            "L2": "L2 — Understand",
            "L3": "L3 — Apply",
        }
        return labels[self.value]


class ExamType(str, Enum):
    MINOR = "MINOR"
    END_SEM = "END_SEM"

    @property
    def label(self) -> str:
        labels = {
            "MINOR": "Minor / Internal Examination",
            "END_SEM": "End-Semester Examination",
        }
        return labels[self.value]


class QuestionSource(str, Enum):
    QUESTION_BANK = "QUESTION_BANK"
    AI_GENERATED = "AI_GENERATED"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    UNDER_REVIEW = "UNDER_REVIEW"


class PaperSetStatus(str, Enum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    UNDER_REVIEW = "UNDER_REVIEW"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    APPROVED = "APPROVED"
    EXPORTED = "EXPORTED"


class ValidationStatus(str, Enum):
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    FAIL = "FAIL"


class DifficultyLevel(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionType(str, Enum):
    DESCRIPTIVE = "descriptive"
    SHORT_ANSWER = "short_answer"
    ESSAY = "essay"


class FileCategory(str, Enum):
    QUESTION_BANK = "question_bank"
    LESSON_PLAN = "lesson_plan"
    UNIVERSITY_TEMPLATE = "university_template"
