"""
models/validation.py
Validation finding and report models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

from models.enums import ValidationStatus


class ValidationRule(BaseModel):
    """
    Definition of one validation rule.
    """

    rule_id: str
    description: str
    is_fatal: bool = True  # False → warning only


class ValidationFinding(BaseModel):
    """
    A single validation finding (warning or failure).
    """

    rule_id: str
    severity: str  # "ERROR" | "WARNING"
    message: str
    expected: Optional[Any] = None
    actual: Optional[Any] = None
    affected_questions: list[str] = Field(default_factory=list)
    suggested_action: str = ""


class ValidationReport(BaseModel):
    """
    Complete validation report for one paper set.
    """

    set_id: str
    exam_type: str
    status: ValidationStatus = ValidationStatus.FAIL
    findings: list[ValidationFinding] = Field(default_factory=list)
    validated_at: datetime = Field(default_factory=datetime.utcnow)

    # Summary counts
    source_bank_count: int = 0
    source_ai_count: int = 0
    source_bank_percent: float = 0.0
    source_ai_percent: float = 0.0
    bloom_l2_count: int = 0
    bloom_l3_count: int = 0
    bloom_l2_percent: float = 0.0
    bloom_l3_percent: float = 0.0
    total_printed: int = 0
    marks_total: int = 0

    @property
    def errors(self) -> list[ValidationFinding]:
        return [f for f in self.findings if f.severity == "ERROR"]

    @property
    def warnings(self) -> list[ValidationFinding]:
        return [f for f in self.findings if f.severity == "WARNING"]

    @property
    def passed(self) -> bool:
        return self.status in (
            ValidationStatus.PASS,
            ValidationStatus.PASS_WITH_WARNINGS,
        )
