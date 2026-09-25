"""
agents/validation_agent.py
Validates a composed paper set against all required rules.
Returns ValidationReport with PASS / PASS_WITH_WARNINGS / FAIL.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from models.enums import ExamType, ValidationStatus, QuestionSource, ApprovalStatus
from models.paper import PaperSet
from models.validation import ValidationFinding, ValidationReport
from models.blueprint import MinorBlueprint, EndSemBlueprint

logger = logging.getLogger(__name__)


class ValidationAgent:
    """
    Agent node 9.10: Validation and Audit Agent.
    Every rule has a unique ID. Never silently relaxes failed rules.
    """

    # ── Minor constants ────────────────────────────────────────────────────────
    MINOR_TOTAL_PRINTED = 6
    MINOR_BANK = 4
    MINOR_AI = 2
    MINOR_MARKS = 40

    # ── End-Sem constants ──────────────────────────────────────────────────────
    ENDSEM_TOTAL_PRINTED = 16
    ENDSEM_BANK = 11
    ENDSEM_AI = 5
    ENDSEM_MARKS = 100

    def validate(
        self,
        paper_set: PaperSet,
        blueprint: MinorBlueprint | EndSemBlueprint,
        tolerance_pct: int = 5,
    ) -> ValidationReport:
        """Run all validation rules and return the report."""
        is_minor = paper_set.exam_type in (ExamType.MINOR, "MINOR")
        findings: list[ValidationFinding] = []

        qs = paper_set.questions
        total = len(qs)
        bank_qs = [q for q in qs if q.source in (QuestionSource.QUESTION_BANK, "QUESTION_BANK")]
        ai_qs = [q for q in qs if q.source in (QuestionSource.AI_GENERATED, "AI_GENERATED")]
        l2_qs = [q for q in qs if q.bloom_level in ("L2",)]
        l3_qs = [q for q in qs if q.bloom_level in ("L3",)]

        expected_total = self.MINOR_TOTAL_PRINTED if is_minor else self.ENDSEM_TOTAL_PRINTED
        expected_bank = self.MINOR_BANK if is_minor else self.ENDSEM_BANK
        expected_ai = self.MINOR_AI if is_minor else self.ENDSEM_AI

        # ── RULE V001: Total printed questions ────────────────────────────────
        if total != expected_total:
            findings.append(ValidationFinding(
                rule_id="V001",
                severity="ERROR",
                message="Total printed question count mismatch",
                expected=expected_total,
                actual=total,
                suggested_action="Ensure all slots are filled",
            ))

        # ── RULE V002: Bank question count ────────────────────────────────────
        if len(bank_qs) != expected_bank:
            findings.append(ValidationFinding(
                rule_id="V002",
                severity="ERROR",
                message="Bank question count mismatch",
                expected=expected_bank,
                actual=len(bank_qs),
                suggested_action="Check selection agent output",
            ))

        # ── RULE V003: AI question count ──────────────────────────────────────
        if len(ai_qs) != expected_ai:
            findings.append(ValidationFinding(
                rule_id="V003",
                severity="ERROR",
                message="AI generated question count mismatch",
                expected=expected_ai,
                actual=len(ai_qs),
                suggested_action="Check generation agent output",
            ))

        # ── RULE V004: Marks per subquestion ──────────────────────────────────
        wrong_marks = [q.slot_id for q in qs if q.marks != 10]
        if wrong_marks:
            findings.append(ValidationFinding(
                rule_id="V004",
                severity="ERROR",
                message="Subquestion(s) do not carry 10 marks",
                expected=10,
                actual=f"{wrong_marks}",
                affected_questions=wrong_marks,
                suggested_action="All subquestions must be 10 marks",
            ))

        # ── RULE V005: Bloom L2 count ─────────────────────────────────────────
        bp_l2 = blueprint.bloom.l2_count
        if abs(len(l2_qs) - bp_l2) > 0:
            findings.append(ValidationFinding(
                rule_id="V005",
                severity="ERROR",
                message="L2 Bloom count does not match blueprint",
                expected=bp_l2,
                actual=len(l2_qs),
                suggested_action="Check Bloom level assignments",
            ))

        # ── RULE V006: Bloom L3 count ─────────────────────────────────────────
        bp_l3 = blueprint.bloom.l3_count
        if abs(len(l3_qs) - bp_l3) > 0:
            findings.append(ValidationFinding(
                rule_id="V006",
                severity="ERROR",
                message="L3 Bloom count does not match blueprint",
                expected=bp_l3,
                actual=len(l3_qs),
                suggested_action="Check Bloom level assignments",
            ))

        # ── RULE V007: Pending AI question approval ────────────────────────────
        # WARNING (not ERROR): AI questions are always PENDING on first generation.
        # Faculty will approve them in the Faculty Review page.
        pending_ai = [
            q.slot_id for q in ai_qs
            if q.approval_status in (ApprovalStatus.PENDING, "PENDING")
        ]
        if pending_ai:
            findings.append(ValidationFinding(
                rule_id="V007",
                severity="WARNING",
                message="AI generated questions awaiting faculty approval",
                expected="APPROVED",
                actual="PENDING",
                affected_questions=pending_ai,
                suggested_action="Go to Faculty Review to approve AI questions before export",
            ))

        # ── RULE V008: Valuation total check ──────────────────────────────────
        for q in qs:
            if q.valuation_scheme:
                total_marks = sum(vp.marks for vp in q.valuation_scheme.valuation_points)
                if total_marks != 10:
                    findings.append(ValidationFinding(
                        rule_id="V008",
                        severity="ERROR",
                        message=f"Valuation scheme total ≠ 10 for slot {q.slot_id}",
                        expected=10,
                        actual=total_marks,
                        affected_questions=[q.slot_id],
                        suggested_action="Correct valuation points to sum to 10",
                    ))

        # ── RULE V009: Missing valuation schemes ──────────────────────────────
        no_valuation = [q.slot_id for q in qs if q.valuation_scheme is None]
        if no_valuation:
            findings.append(ValidationFinding(
                rule_id="V009",
                severity="WARNING",
                message="Some questions have no valuation scheme",
                affected_questions=no_valuation,
                suggested_action="Generate valuation schemes before export",
            ))

        # ── RULE V010: Numbering integrity ────────────────────────────────────
        expected_slots = self._expected_slots(is_minor)
        actual_slots = {q.slot_id for q in qs}
        missing_slots = expected_slots - actual_slots
        if missing_slots:
            findings.append(ValidationFinding(
                rule_id="V010",
                severity="ERROR",
                message="Missing question slots",
                expected=str(sorted(expected_slots)),
                actual=str(sorted(actual_slots)),
                suggested_action=f"Fill missing slots: {sorted(missing_slots)}",
            ))

        # ── RULE V011: Source percentage within tolerance ─────────────────────
        if total > 0:
            bank_pct = len(bank_qs) / total * 100
            ai_pct = len(ai_qs) / total * 100
            target_bank_pct = expected_bank / expected_total * 100
            if abs(bank_pct - target_bank_pct) > tolerance_pct:
                findings.append(ValidationFinding(
                    rule_id="V011",
                    severity="WARNING",
                    message="Source distribution outside tolerance",
                    expected=f"~{target_bank_pct:.1f}% bank",
                    actual=f"{bank_pct:.1f}% bank",
                ))

        # ── Determine overall status ───────────────────────────────────────────
        has_errors = any(f.severity == "ERROR" for f in findings)
        has_warnings = any(f.severity == "WARNING" for f in findings)

        if has_errors:
            status = ValidationStatus.FAIL
        elif has_warnings:
            status = ValidationStatus.PASS_WITH_WARNINGS
        else:
            status = ValidationStatus.PASS

        report = ValidationReport(
            set_id=paper_set.set_id,
            exam_type=paper_set.exam_type if isinstance(paper_set.exam_type, str) else paper_set.exam_type.value,
            status=status,
            findings=findings,
            source_bank_count=len(bank_qs),
            source_ai_count=len(ai_qs),
            source_bank_percent=round(len(bank_qs) / max(total, 1) * 100, 2),
            source_ai_percent=round(len(ai_qs) / max(total, 1) * 100, 2),
            bloom_l2_count=len(l2_qs),
            bloom_l3_count=len(l3_qs),
            bloom_l2_percent=round(len(l2_qs) / max(total, 1) * 100, 2),
            bloom_l3_percent=round(len(l3_qs) / max(total, 1) * 100, 2),
            total_printed=total,
            marks_total=sum(q.marks for q in qs),
        )
        logger.info(
            f"Validation {paper_set.set_id}: {status} "
            f"({len(findings)} findings)"
        )
        return report

    def _expected_slots(self, is_minor: bool) -> set[str]:
        if is_minor:
            return {f"Q{q}{p}" for q in range(1, 4) for p in ("a", "b")}
        else:
            return {f"Q{q}{p}" for q in range(1, 9) for p in ("a", "b")}
