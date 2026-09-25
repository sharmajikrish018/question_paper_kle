"""
agents/similarity_agent.py
Layered duplicate and near-duplicate detection across questions and sets.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from services.similarity_service import SimilarityService, SimilarityResult

logger = logging.getLogger(__name__)


@dataclass
class DuplicateReport:
    within_set: list[dict] = field(default_factory=list)
    cross_set: list[dict] = field(default_factory=list)
    bank_vs_generated: list[dict] = field(default_factory=list)
    has_blocking_duplicates: bool = False


class SimilarityDuplicateAgent:
    """
    Agent node 9.7: Similarity and Duplicate Agent.
    Checks within-set, cross-set, and bank vs generated duplicates.
    """

    def __init__(self):
        self._sim = SimilarityService()

    def check_within_set(
        self, question_texts: list[str], question_ids: list[str]
    ) -> list[dict]:
        """Check for duplicates within one paper set."""
        findings = []
        for i, j, result in self._sim.find_duplicates_in_list(question_texts):
            findings.append({
                "id_a": question_ids[i] if i < len(question_ids) else str(i),
                "id_b": question_ids[j] if j < len(question_ids) else str(j),
                "status": result.status,
                "score": result.max_score,
                "explanation": result.explanation,
            })
        return findings

    def check_cross_set(
        self,
        set_questions: list[tuple[str, list[str]]],  # [(set_id, [texts])]
    ) -> list[dict]:
        """Check for duplicates across multiple paper sets."""
        findings = []
        for i in range(len(set_questions)):
            set_id_a, texts_a = set_questions[i]
            for j in range(i + 1, len(set_questions)):
                set_id_b, texts_b = set_questions[j]
                for ta in texts_a:
                    pairs = self._sim.check_against_corpus(ta, texts_b)
                    for idx, result in pairs:
                        if result.status != "OK":
                            findings.append({
                                "set_a": set_id_a,
                                "set_b": set_id_b,
                                "text_a": ta[:80],
                                "text_b": texts_b[idx][:80],
                                "status": result.status,
                                "score": result.max_score,
                                "explanation": result.explanation,
                            })
        return findings

    def check_generated_vs_bank(
        self, generated_texts: list[str], bank_texts: list[str]
    ) -> list[dict]:
        """Ensure AI questions don't copy/paraphrase bank questions."""
        findings = []
        for gen_text in generated_texts:
            pairs = self._sim.check_against_corpus(gen_text, bank_texts)
            for idx, result in pairs:
                if result.status != "OK":
                    findings.append({
                        "generated": gen_text[:80],
                        "bank": bank_texts[idx][:80],
                        "status": result.status,
                        "score": result.max_score,
                        "explanation": result.explanation,
                    })
        return findings

    def full_report(
        self,
        set_id: str,
        question_texts: list[str],
        question_ids: list[str],
        generated_texts: list[str],
        bank_texts: list[str],
        other_sets: Optional[list[tuple[str, list[str]]]] = None,
    ) -> DuplicateReport:
        report = DuplicateReport()
        report.within_set = self.check_within_set(question_texts, question_ids)
        if generated_texts and bank_texts:
            report.bank_vs_generated = self.check_generated_vs_bank(
                generated_texts, bank_texts
            )
        if other_sets:
            current = [(set_id, question_texts)]
            report.cross_set = self.check_cross_set(current + other_sets)

        # Flag blocking duplicates (status == DUPLICATE)
        all_findings = (
            report.within_set + report.cross_set + report.bank_vs_generated
        )
        report.has_blocking_duplicates = any(
            f.get("status") == "DUPLICATE" for f in all_findings
        )
        return report
