"""
services/blueprint_service.py
Converts faculty UI criteria into immutable Blueprint objects.
Pure deterministic Python — no LLM involvement.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

from models.blueprint import (
    MinorBlueprint,
    EndSemBlueprint,
    UnitAllocation,
    BloomAllocation,
    SourceAllocation,
)
from models.enums import ExamType

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

MINOR_TOTAL_PRINTED = 6
MINOR_BANK = 4
MINOR_AI = 2
MINOR_MARKS = 40

ENDSEM_TOTAL_PRINTED = 16
ENDSEM_BANK = 11
ENDSEM_AI = 5
ENDSEM_MARKS = 100

# Default unit allocations for End-Sem
DEFAULT_ENDSEM_UNITS = [
    {"unit": 1, "bank": 4, "ai": 2, "total": 6},
    {"unit": 2, "bank": 4, "ai": 2, "total": 6},
    {"unit": 3, "bank": 3, "ai": 1, "total": 4},
]


class BlueprintError(Exception):
    pass


class BlueprintService:
    """
    Builds blueprint objects from faculty parameters.
    Validates integer feasibility.
    """

    def build_minor(
        self,
        l2_percent: int = 50,
        l3_percent: int = 50,
        selected_chapters: Optional[list[int]] = None,
        random_seed: Optional[int] = None,
        tolerance_percent: int = 5,
    ) -> MinorBlueprint:
        """
        Build a validated MinorBlueprint.
        """
        self._validate_bloom_percents(l2_percent, l3_percent)
        l2_count, l3_count = self._allocate_bloom(
            MINOR_TOTAL_PRINTED, l2_percent, l3_percent, tolerance_percent
        )

        # Source/bloom matrix for bank and AI subsets
        bank_l2, bank_l3 = self._allocate_bloom(MINOR_BANK, l2_percent, l3_percent, tolerance_percent)
        ai_l2, ai_l3 = l2_count - bank_l2, l3_count - bank_l3

        bp = MinorBlueprint(
            source=SourceAllocation(bank_count=MINOR_BANK, ai_count=MINOR_AI, total=MINOR_TOTAL_PRINTED),
            bloom=BloomAllocation(l2_count=l2_count, l3_count=l3_count, total=MINOR_TOTAL_PRINTED),
            bank_l2=bank_l2,
            bank_l3=bank_l3,
            ai_l2=ai_l2,
            ai_l3=ai_l3,
            selected_chapters=selected_chapters or [],
            l2_percent_target=l2_percent,
            l3_percent_target=l3_percent,
            tolerance_percent=tolerance_percent,
            random_seed=random_seed,
        )
        logger.info(
            f"MinorBlueprint: bank={MINOR_BANK} AI={MINOR_AI} "
            f"L2={l2_count} L3={l3_count}"
        )
        return bp

    def build_end_sem(
        self,
        l2_percent: int = 50,
        l3_percent: int = 50,
        unit_allocations: Optional[list[dict]] = None,
        random_seed: Optional[int] = None,
        tolerance_percent: int = 5,
    ) -> EndSemBlueprint:
        """
        Build a validated EndSemBlueprint.
        unit_allocations: list of {unit, bank, ai, total}
        """
        self._validate_bloom_percents(l2_percent, l3_percent)

        unit_allocs_cfg = unit_allocations or DEFAULT_ENDSEM_UNITS
        self._validate_unit_alloc(unit_allocs_cfg)

        l2_count, l3_count = self._allocate_bloom(
            ENDSEM_TOTAL_PRINTED, l2_percent, l3_percent, tolerance_percent
        )

        unit_objs: list[UnitAllocation] = []
        for cfg in unit_allocs_cfg:
            u = cfg["unit"]
            total = cfg["total"]
            bank = cfg["bank"]
            ai = cfg["ai"]
            u_l2, u_l3 = self._allocate_bloom(total, l2_percent, l3_percent, tolerance_percent)
            choice_map = {1: "Answer any TWO full questions.",
                          2: "Answer any TWO full questions.",
                          3: "Answer any ONE full question."}
            marks_map = {1: 40, 2: 40, 3: 20}
            attempt_map = {1: 4, 2: 4, 3: 2}
            unit_objs.append(UnitAllocation(
                unit_number=u,
                source=SourceAllocation(bank_count=bank, ai_count=ai, total=total),
                bloom=BloomAllocation(l2_count=u_l2, l3_count=u_l3, total=total),
                questions_to_print=total,
                questions_to_attempt=attempt_map.get(u, 4),
                marks_to_attempt=marks_map.get(u, 40),
                main_questions=3 if u in (1, 2) else 2,
                choice_instruction=choice_map.get(u, "Answer as instructed."),
            ))

        bp = EndSemBlueprint(
            source=SourceAllocation(bank_count=ENDSEM_BANK, ai_count=ENDSEM_AI, total=ENDSEM_TOTAL_PRINTED),
            bloom=BloomAllocation(l2_count=l2_count, l3_count=l3_count, total=ENDSEM_TOTAL_PRINTED),
            unit_allocations=unit_objs,
            l2_percent_target=l2_percent,
            l3_percent_target=l3_percent,
            tolerance_percent=tolerance_percent,
            random_seed=random_seed,
        )
        logger.info(
            f"EndSemBlueprint: bank={ENDSEM_BANK} AI={ENDSEM_AI} "
            f"L2={l2_count} L3={l3_count}"
        )
        return bp

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _validate_bloom_percents(self, l2: int, l3: int) -> None:
        if l2 + l3 != 100:
            raise BlueprintError(
                f"L2% + L3% must equal 100, got {l2} + {l3} = {l2 + l3}"
            )
        if not (0 <= l2 <= 100) or not (0 <= l3 <= 100):
            raise BlueprintError("Bloom percentages must be between 0 and 100")

    def _allocate_bloom(
        self, total: int, l2_pct: int, l3_pct: int, tolerance: int
    ) -> tuple[int, int]:
        """
        Compute nearest feasible integer Bloom allocation.
        Returns (l2_count, l3_count) that sum to total.
        Validates within tolerance.
        """
        l2_exact = total * l2_pct / 100
        l2_count = round(l2_exact)
        l3_count = total - l2_count

        if l2_count < 0 or l3_count < 0:
            raise BlueprintError(
                f"Cannot allocate negative counts: L2={l2_count} L3={l3_count}"
            )

        # Check within tolerance
        achieved_l2_pct = l2_count / total * 100
        achieved_l3_pct = l3_count / total * 100
        if abs(achieved_l2_pct - l2_pct) > tolerance:
            raise BlueprintError(
                f"Cannot achieve L2={l2_pct}% within ±{tolerance}% tolerance "
                f"with {total} questions. Achieved L2={achieved_l2_pct:.1f}%."
            )
        return l2_count, l3_count

    def _validate_unit_alloc(self, unit_allocs: list[dict]) -> None:
        """Validate custom unit allocation sums."""
        total_bank = sum(u["bank"] for u in unit_allocs)
        total_ai = sum(u["ai"] for u in unit_allocs)
        if total_bank != ENDSEM_BANK:
            raise BlueprintError(
                f"Unit bank allocations must sum to {ENDSEM_BANK}, got {total_bank}"
            )
        if total_ai != ENDSEM_AI:
            raise BlueprintError(
                f"Unit AI allocations must sum to {ENDSEM_AI}, got {total_ai}"
            )
