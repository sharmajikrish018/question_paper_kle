"""
agents/generation_agent.py
AI Question Generation Agent.
Generates L2/L3 questions using the LLM, grounded in the lesson plan.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from models.enums import BloomLevel, ExamType
from models.question import GeneratedQuestion
from models.valuation import ValuationPoint
from services.llm_provider import LLMProviderProtocol

logger = logging.getLogger(__name__)


class AIQuestionGenerationAgent:
    """
    Agent node 9.6: AI Question Generation Agent.
    - Generates exactly 2 questions for Minor, 5 for End-Sem (per set).
    - Only calls the LLM.
    - Validates output with Pydantic.
    """

    def __init__(self, llm_provider: LLMProviderProtocol):
        self._llm = llm_provider

    def generate_for_minor(
        self,
        blueprint_bloom: dict,  # {l2: count, l3: count}
        selected_chapters: list[int],
        lesson_plan_text: str,
        question_bank_sample: list[str],
        used_texts: list[str],
        unit_chapter_map: dict[int, list[dict]],
    ) -> list[GeneratedQuestion]:
        """
        Generate exactly 2 AI questions for a Minor paper.
        blueprint_bloom: {"l2": ai_l2, "l3": ai_l3}
        """
        questions = []
        l2_needed = blueprint_bloom.get("l2", 1)
        l3_needed = blueprint_bloom.get("l3", 1)

        # Determine unit/chapter for each generated question
        slots = (
            [(BloomLevel.L2, 1)] * l2_needed +
            [(BloomLevel.L3, 1)] * l3_needed
        )

        for bloom, _ in slots:
            chapter = self._pick_chapter(selected_chapters, unit_chapter_map, questions)
            chapter_name = self._get_chapter_name(chapter, unit_chapter_map)
            unit_num = self._get_unit_for_chapter(chapter, unit_chapter_map)
            topic_extract = self._extract_relevant_topics(lesson_plan_text, chapter_name)
            q = self._generate_one(
                bloom_level=bloom,
                unit_number=unit_num,
                chapter_number=chapter,
                chapter_name=chapter_name,
                lesson_plan_excerpt=topic_extract,
                bank_samples=question_bank_sample[:5],
                avoid_texts=used_texts,
            )
            if q:
                questions.append(q)

        return questions

    def generate_for_end_sem(
        self,
        unit_ai_bloom: list[dict],  # [{unit, chapter, bloom}]
        lesson_plan_text: str,
        question_bank_sample: list[str],
        used_texts: list[str],
        unit_chapter_map: dict[int, list[dict]],
    ) -> list[GeneratedQuestion]:
        """
        Generate exactly 5 AI questions for an End-Sem paper.
        unit_ai_bloom: list of {unit_number, chapter_number, bloom_level}
        """
        questions = []
        for slot in unit_ai_bloom:
            unit_num = slot["unit_number"]
            chapter_num = slot["chapter_number"]
            chapter_name = slot.get("chapter_name", f"Chapter {chapter_num}")
            bloom = BloomLevel(slot["bloom_level"])
            topic_extract = self._extract_relevant_topics(lesson_plan_text, chapter_name)
            q = self._generate_one(
                bloom_level=bloom,
                unit_number=unit_num,
                chapter_number=chapter_num,
                chapter_name=chapter_name,
                lesson_plan_excerpt=topic_extract,
                bank_samples=question_bank_sample[:5],
                avoid_texts=[qq.question_text for qq in questions] + used_texts,
            )
            if q:
                questions.append(q)
        return questions

    def _generate_one(
        self,
        bloom_level: BloomLevel,
        unit_number: int,
        chapter_number: int,
        chapter_name: str,
        lesson_plan_excerpt: str,
        bank_samples: list[str],
        avoid_texts: list[str],
    ) -> Optional[GeneratedQuestion]:
        """Call the LLM to generate one question with validation."""
        bloom_label = "L2 (Understand)" if bloom_level == BloomLevel.L2 else "L3 (Apply)"

        avoid_section = ""
        if avoid_texts:
            avoid_section = (
                "\n\nAVOID generating questions similar to:\n"
                + "\n".join(f"- {t[:120]}" for t in avoid_texts[:5])
            )

        bank_section = ""
        if bank_samples:
            bank_section = (
                "\n\nQuestion bank style examples (do NOT copy or paraphrase):\n"
                + "\n".join(f"- {t[:120]}" for t in bank_samples)
            )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert university question paper setter for the course "
                    "'Generative AI'. You generate high-quality descriptive questions "
                    "worth exactly 10 marks. Each question must be grounded only in the "
                    "provided syllabus topics. Do NOT use external knowledge beyond the "
                    "provided context."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Generate ONE descriptive question for:\n"
                    f"- Course: Generative AI\n"
                    f"- Unit: {unit_number}\n"
                    f"- Chapter: {chapter_number} — {chapter_name}\n"
                    f"- Bloom Level: {bloom_label}\n"
                    f"- Marks: 10\n"
                    f"- Type: Descriptive (long answer)\n\n"
                    f"Syllabus topics for this chapter:\n{lesson_plan_excerpt or '(not available)'}\n"
                    f"{bank_section}"
                    f"{avoid_section}\n\n"
                    f"Requirements:\n"
                    f"1. Question must match Bloom level {bloom_label} — not just recall.\n"
                    f"2. Valuation points must sum to exactly 10 marks.\n"
                    f"3. Provide a complete model answer.\n"
                    f"4. Provide Bloom justification (explain WHY this is {bloom_label}).\n"
                    f"5. Mark unit_number={unit_number}, chapter_number={chapter_number}.\n"
                    f"6. Set approval_status='PENDING'.\n"
                    f"7. Set source='AI_GENERATED'."
                ),
            },
        ]

        try:
            result = self._llm.generate_structured(
                messages=messages,
                response_model=GeneratedQuestion,
                temperature=0.4,
                max_tokens=2048,
            )
            # Override with correct metadata
            result = result.model_copy(update={
                "unit_number": unit_number,
                "chapter_number": chapter_number,
                "chapter_name": chapter_name,
                "bloom_level": bloom_level,
                "marks": 10,
                "source": "AI_GENERATED",
                "approval_status": "PENDING",
            })
            logger.info(
                f"Generated question for ch={chapter_number} bloom={bloom_level.value}"
            )
            return result
        except Exception as exc:
            logger.error(f"Question generation failed: {exc}")
            fallback_text = (
                f"Explain the core concepts and underlying mechanism of {chapter_name}. "
                f"Discuss its key architectural components, workflow, and applications."
            )
            return GeneratedQuestion(
                question_text=fallback_text,
                unit_number=unit_number,
                chapter_number=chapter_number,
                chapter_name=chapter_name,
                bloom_level=bloom_level,
                marks=10,
                model_answer=f"Detailed explanation of {chapter_name} covering foundational principles, architecture, and practical use cases.",
                valuation_points=[
                    ValuationPoint(criterion="Core concepts and theoretical background", marks=5),
                    ValuationPoint(criterion="Architecture, workflow, and applications", marks=5),
                ],
                bloom_justification=f"Requires clear explanation and contextual understanding of {chapter_name}.",
                syllabus_grounding=[chapter_name],
                source="AI_GENERATED",
                approval_status="PENDING",
            )

    def _pick_chapter(
        self,
        selected_chapters: list[int],
        unit_chapter_map: dict,
        already_generated: list[GeneratedQuestion],
    ) -> int:
        """Pick a chapter for the next generated question, spreading across chapters."""
        used_chapters = [q.chapter_number for q in already_generated]
        for ch in selected_chapters:
            if ch not in used_chapters:
                return ch
        return selected_chapters[0] if selected_chapters else 1

    def _get_chapter_name(self, chapter_number: int, unit_chapter_map: dict) -> str:
        for unit_chapters in unit_chapter_map.values():
            for ch in unit_chapters:
                if ch.get("chapter_number") == chapter_number:
                    return ch.get("title", f"Chapter {chapter_number}")
        return f"Chapter {chapter_number}"

    def _get_unit_for_chapter(self, chapter_number: int, unit_chapter_map: dict) -> int:
        for unit_num, chapters in unit_chapter_map.items():
            for ch in chapters:
                if ch.get("chapter_number") == chapter_number:
                    return unit_num
        return 1

    def _extract_relevant_topics(self, lesson_plan_text: str, chapter_name: str) -> str:
        """
        Extract the most relevant paragraph(s) for the given chapter.
        Simple heuristic: find lines near the chapter heading.
        """
        if not lesson_plan_text:
            return ""
        lines = lesson_plan_text.split("\n")
        ch_lower = chapter_name.lower()
        snippet_lines = []
        in_section = False
        for line in lines:
            ll = line.lower()
            if ch_lower in ll or any(word in ll for word in ch_lower.split() if len(word) > 3):
                in_section = True
            if in_section:
                snippet_lines.append(line)
                if len(snippet_lines) > 20:
                    break
        return "\n".join(snippet_lines[:20]) or lesson_plan_text[:500]
