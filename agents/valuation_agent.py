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
    For bank questions: uses stored model answers or generates draft once and persists to bank.
    For AI questions: generated in single call (reused from PaperQuestion).
    All schemes must total exactly 10 marks.
    """

    def __init__(self, llm_provider: LLMProviderProtocol):
        self._llm = llm_provider

    def generate_scheme(
        self, pq: PaperQuestion, stored_answer: Optional[str] = None, subject_id: str = "default-subject"
    ) -> ValuationScheme:
        """
        Generate or retrieve valuation scheme for one paper question.
        """
        # 1. Return pre-populated scheme if already present (e.g. from single-call AI generation)
        if pq.valuation_scheme is not None:
            return pq.valuation_scheme

        is_bank = pq.source == QuestionSource.QUESTION_BANK or str(pq.source) == "QUESTION_BANK"

        # 2. For Bank questions: try stored answer / repo first
        if is_bank:
            if stored_answer:
                return self._scheme_from_stored(pq, stored_answer)

            if pq.question_id:
                try:
                    from repositories.question_repo import QuestionRepository
                    repo = QuestionRepository()
                    stored_q = repo.get_by_id(pq.question_id, subject_id=subject_id)
                    if stored_q and (stored_q.model_answer or stored_q.valuation_points):
                        vp = stored_q.valuation_points or [
                            ValuationPoint(criterion=f"Key point {i+1}", marks=2) for i in range(5)
                        ]
                        return ValuationScheme(
                            question_ref=pq.question_id,
                            expected_answer=stored_q.model_answer or "[Stored Answer]",
                            key_points=[stored_q.model_answer] if stored_q.model_answer else [],
                            valuation_points=vp,
                            approval_status="APPROVED",
                        )
                except Exception as exc:
                    logger.debug(f"Bank question lookup failed: {exc}")

        # 3. Call LLM only if missing
        scheme = self._generate_draft_scheme(pq)

        # 4. If bank question was missing valuation, persist generated valuation back to DB
        if is_bank and pq.question_id:
            try:
                from repositories.question_repo import QuestionRepository
                repo = QuestionRepository()
                repo.update(
                    pq.question_id,
                    subject_id=subject_id,
                    model_answer=scheme.expected_answer,
                )
            except Exception as exc:
                logger.warning(f"Could not persist bank valuation to DB: {exc}")

        return scheme

    def _scheme_from_stored(
        self, pq: PaperQuestion, answer: str
    ) -> ValuationScheme:
        """
        Build a scheme from a stored faculty model answer.
        Splits evenly if no valuation_points stored.
        """
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

        from pydantic import BaseModel, model_validator

        class ValuationDraft(BaseModel):
            expected_answer: str
            key_points: list[str] = []
            valuation_points: list[ValuationPoint]
            alternative_answers: list[str] = []

            @model_validator(mode="after")
            def check_total(self):
                total = sum(vp.marks for vp in self.valuation_points)
                if total != 10:
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
            return ValuationScheme(
                question_ref=pq.question_id or pq.generated_id or pq.slot_id,
                expected_answer="[Draft — faculty review required]",
                valuation_points=[
                    ValuationPoint(criterion=f"Key aspect {i+1}", marks=2)
                    for i in range(5)
                ],
                approval_status="PENDING",
            )

