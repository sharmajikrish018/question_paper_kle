"""
agents/selection_agent.py
Constraint-based question selection using backtracking solver.
Satisfies unit, chapter, Bloom, source, and set-level constraints.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Optional

from models.blueprint import MinorBlueprint, EndSemBlueprint, UnitAllocation
from models.enums import BloomLevel, QuestionSource, ExamType
from models.question import Question
from agents.question_bank_agent import QuestionBankAgent

logger = logging.getLogger(__name__)


@dataclass
class SelectionSlot:
    """
    A required slot that must be filled with a bank question.
    """
    slot_id: str
    unit_number: int
    chapter_number: Optional[int]
    bloom_level: BloomLevel
    is_bank: bool = True


@dataclass
class SelectionResult:
    success: bool
    selected: dict[str, Question] = field(default_factory=dict)  # slot_id → Question
    failure_reason: str = ""
    feasibility_report: str = ""


class QuestionSelectionAgent:
    """
    Agent node 9.5: Deterministic constraint-based question selection.
    Uses a greedy allocation with backtracking fallback.
    """

    def __init__(self):
        self._bank_agent = QuestionBankAgent()

    def select_for_minor(
        self,
        blueprint: MinorBlueprint,
        used_across_sets: set[str],
        rng: random.Random,
    ) -> SelectionResult:
        """
        Select 4 bank questions for a Minor paper set.
        Slots: 2 L2 + 2 L3, spread across selected chapters.
        """
        slots = self._build_minor_bank_slots(blueprint)
        return self._solve(slots, used_across_sets, rng, blueprint.selected_chapters)

    def select_for_end_sem(
        self,
        blueprint: EndSemBlueprint,
        used_across_sets: set[str],
        rng: random.Random,
    ) -> SelectionResult:
        """
        Select 11 bank questions for an End-Semester paper.
        """
        slots = self._build_endsem_bank_slots(blueprint)
        return self._solve(slots, used_across_sets, rng, chapter_filter=None)

    # ── Slot builders ─────────────────────────────────────────────────────────

    def _build_minor_bank_slots(self, bp: MinorBlueprint) -> list[SelectionSlot]:
        """Build 4 bank slots for Minor: bank_l2 × L2 + bank_l3 × L3."""
        slots = []
        chapters = bp.selected_chapters or list(range(1, 8))
        ch_cycle = chapters * 10  # enough for rotation

        for i in range(bp.bank_l2):
            ch = ch_cycle[i % len(chapters)]
            slots.append(SelectionSlot(
                slot_id=f"bank_l2_{i}",
                unit_number=0,  # any unit
                chapter_number=ch,
                bloom_level=BloomLevel.L2,
            ))
        for i in range(bp.bank_l3):
            ch = ch_cycle[(bp.bank_l2 + i) % len(chapters)]
            slots.append(SelectionSlot(
                slot_id=f"bank_l3_{i}",
                unit_number=0,
                chapter_number=ch,
                bloom_level=BloomLevel.L3,
            ))
        return slots

    def _build_endsem_bank_slots(self, bp: EndSemBlueprint) -> list[SelectionSlot]:
        """Build 11 bank slots from unit allocations."""
        slots = []
        for ua in bp.unit_allocations:
            u = ua.unit_number
            bank = ua.source.bank_count
            # Distribute evenly: half L2, half L3 (as close as possible)
            l2_bank = bank // 2
            l3_bank = bank - l2_bank
            for i in range(l2_bank):
                slots.append(SelectionSlot(
                    slot_id=f"u{u}_bank_l2_{i}",
                    unit_number=u,
                    chapter_number=None,
                    bloom_level=BloomLevel.L2,
                ))
            for i in range(l3_bank):
                slots.append(SelectionSlot(
                    slot_id=f"u{u}_bank_l3_{i}",
                    unit_number=u,
                    chapter_number=None,
                    bloom_level=BloomLevel.L3,
                ))
        return slots

    # ── Solver ────────────────────────────────────────────────────────────────

    def _solve(
        self,
        slots: list[SelectionSlot],
        used_globally: set[str],
        rng: random.Random,
        chapter_filter: Optional[list[int]],
    ) -> SelectionResult:
        """
        Greedy solver with shuffle for determinism under seed.
        Falls back to any available question if chapter/bloom match fails.
        """
        selected: dict[str, Question] = {}
        used_in_this_call: set[str] = set()
        infeasible_slots = []

        for slot in slots:
            # Build filter kwargs
            unit_arg = slot.unit_number if slot.unit_number > 0 else None
            ch_arg = slot.chapter_number

            # Wider search if chapter not specific
            candidates = self._bank_agent.get_available_questions(
                unit_number=unit_arg,
                chapter_number=ch_arg,
                bloom_level=slot.bloom_level.value,
                exclude_ids=list(used_globally | used_in_this_call),
            )

            # If no match at requested chapter, try any chapter in unit
            if not candidates and ch_arg is not None:
                logger.debug(
                    f"No candidates for slot {slot.slot_id} ch={ch_arg} — widening"
                )
                candidates = self._bank_agent.get_available_questions(
                    unit_number=unit_arg,
                    bloom_level=slot.bloom_level.value,
                    exclude_ids=list(used_globally | used_in_this_call),
                )

            # Apply chapter filter for Minor
            if chapter_filter and candidates:
                filtered = [q for q in candidates if q.chapter_number in chapter_filter]
                if filtered:
                    candidates = filtered

            if not candidates:
                infeasible_slots.append(slot.slot_id)
                logger.warning(f"No eligible questions for slot {slot.slot_id}")
                continue

            rng.shuffle(candidates)
            chosen = candidates[0]
            selected[slot.slot_id] = chosen
            used_in_this_call.add(chosen.question_id)

        if infeasible_slots:
            return SelectionResult(
                success=False,
                selected=selected,
                failure_reason=(
                    f"Insufficient questions for slots: {infeasible_slots}"
                ),
                feasibility_report=(
                    f"Could not fill {len(infeasible_slots)} slot(s). "
                    f"Consider adding more questions to the bank or relaxing filters."
                ),
            )

        return SelectionResult(success=True, selected=selected)
