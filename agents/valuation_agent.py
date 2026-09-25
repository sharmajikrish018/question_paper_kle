"""
agents/valuation_agent.py
Generates scheme of valuation for each question.
"""

from __future__ import annotations

import logging
from typing import Optional

from models.paper import PaperQuestion
from models.valuation import ValuationPoint, ValuationScheme
from models.enums import QuestionSource
from services.llm_provider import LLMProviderProtocol
from models.question import GeneratedQuestion

logger = logging.getLogger(__name__)


class ValuationAgent:
    """
    Agent node 9.9: Scheme of Valuation Agent.
    For bank questions: uses stored model answers or generates draft.
    For AI questions: generates full scheme.
    All schemes must total exactly 10 marks.
    """

    def __init__(self, llm_provider: LLMProviderProtocol):
        self._llm = llm_provider

    def generate_scheme(
        self, pq: PaperQuestion, stored_answer: Optional[str] = None
    ) -> ValuationScheme:
        """
        Generate or retrieve valuation scheme for one paper question.
        """
        if (
            pq.source == QuestionSource.QUESTION_BANK
            and stored_answer
        ):
            # Use faculty-provided answer if available
            return self._scheme_from_stored(pq, stored_answer)

        # Generate draft scheme using LLM
        return self._generate_draft_scheme(pq)

    def _scheme_from_stored(
        self, pq: PaperQuestion, answer: str
    ) -> ValuationScheme:
        """
        Build a scheme from a stored faculty model answer.
        Splits evenly if no valuation_points stored.
        """
        # Create default 5×2 scheme
        vp = [
            ValuationPoint(criterion=f"Key point {i+1}", marks=2)
            for i in range(5)
        ]
        return ValuationScheme(
            question_ref=pq.question_id or pq.generated_id or pq.slot_id,
            expected_answer=answer,
            key_points=[answer],
            valuation_points=vp,
            approval_status="APPROVED",
        )

    def _generate_draft_scheme(self, pq: PaperQuestion) -> ValuationScheme:
        """Use the LLM to generate a draft valuation scheme."""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a university marking scheme writer. "
                    "Generate a precise, complete valuation scheme for a 10-mark question. "
                    "The total marks across all valuation points must equal exactly 10."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Generate a complete valuation scheme for:\n\n"
                    f"Question: {pq.question_text}\n"
                    f"Bloom Level: {pq.bloom_level}\n"
                    f"Marks: 10\n\n"
                    f"Return JSON with:\n"
                    f"- expected_answer: string (2-3 paragraphs)\n"
                    f"- key_points: list of strings\n"
                    f"- valuation_points: list of {{criterion, marks}} summing to 10\n"
                    f"- alternative_answers: list of strings (optional)"
                ),
            },
        ]

        # Build a simple internal model
        from pydantic import BaseModel, model_validator
        from typing import List

        class ValuationDraft(BaseModel):
            expected_answer: str
            key_points: list[str] = []
            valuation_points: list[ValuationPoint]
            alternative_answers: list[str] = []

            @model_validator(mode="after")
            def check_total(self):
                total = sum(vp.marks for vp in self.valuation_points)
                if total != 10:
                    # Auto-adjust last point
                    if self.valuation_points:
                        deficit = 10 - sum(vp.marks for vp in self.valuation_points[:-1])
                        self.valuation_points[-1] = ValuationPoint(
                            criterion=self.valuation_points[-1].criterion,
                            marks=max(1, deficit),
                        )
                return self

        try:
            draft = self._llm.generate_structured(
                messages=messages,
                response_model=ValuationDraft,
                temperature=0.2,
                max_tokens=1500,
            )
            return ValuationScheme(
                question_ref=pq.question_id or pq.generated_id or pq.slot_id,
                expected_answer=draft.expected_answer,
                key_points=draft.key_points,
                valuation_points=draft.valuation_points,
                alternative_answers=draft.alternative_answers,
                approval_status="PENDING",
            )
        except Exception as exc:
            logger.error(f"Valuation generation failed: {exc}")
            # Return minimal draft
            return ValuationScheme(
                question_ref=pq.question_id or pq.generated_id or pq.slot_id,
                expected_answer="[Draft — faculty review required]",
                valuation_points=[
                    ValuationPoint(criterion=f"Key aspect {i+1}", marks=2)
                    for i in range(5)
                ],
                approval_status="PENDING",
            )
