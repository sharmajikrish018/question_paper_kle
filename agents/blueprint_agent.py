"""
agents/blueprint_agent.py
Converts UI criteria into a validated Blueprint object.
"""

from __future__ import annotations

import logging
from typing import Optional

from models.blueprint import MinorBlueprint, EndSemBlueprint
from models.enums import ExamType
from services.blueprint_service import BlueprintService

logger = logging.getLogger(__name__)


class BlueprintAgent:
    """
    Agent node 9.4: Blueprint Agent.
    Accepts faculty parameters and returns an immutable blueprint.
    """

    def __init__(self):
        self._service = BlueprintService()

    def build(
        self,
        exam_type: ExamType,
        l2_percent: int = 50,
        l3_percent: int = 50,
        selected_chapters: Optional[list[int]] = None,
        unit_allocations: Optional[list[dict]] = None,
        random_seed: Optional[int] = None,
        tolerance_percent: int = 5,
    ) -> MinorBlueprint | EndSemBlueprint:
        """
        Build and return the appropriate blueprint.
        """
        logger.info(
            f"Building {exam_type} blueprint: L2={l2_percent}% L3={l3_percent}% "
            f"seed={random_seed}"
        )
        if exam_type in (ExamType.MINOR, "MINOR"):
            return self._service.build_minor(
                l2_percent=l2_percent,
                l3_percent=l3_percent,
                selected_chapters=selected_chapters,
                random_seed=random_seed,
                tolerance_percent=tolerance_percent,
            )
        else:
            return self._service.build_end_sem(
                l2_percent=l2_percent,
                l3_percent=l3_percent,
                unit_allocations=unit_allocations,
                random_seed=random_seed,
                tolerance_percent=tolerance_percent,
            )
