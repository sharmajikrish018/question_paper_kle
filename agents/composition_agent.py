"""
agents/composition_agent.py
Places selected and generated questions into correctly numbered paper slots.
"""

from __future__ import annotations

import logging
from typing import Optional

from models.blueprint import MinorBlueprint, EndSemBlueprint
from models.enums import BloomLevel, ExamType, QuestionSource, ApprovalStatus
from models.paper import PaperSet, PaperQuestion
from models.question import Question, GeneratedQuestion, QuestionRecord
from models.valuation import ValuationPoint, ValuationScheme

logger = logging.getLogger(__name__)


class PaperCompositionAgent:
    """
    Agent node 9.8: Paper Composition Agent.
    Assembles questions into correct Q#(a)/(b) slots.
    """


    def compose_minor(
        self,
        set_id: str,
        set_index: int,
        blueprint: MinorBlueprint,
        bank_questions: list[Question],
        ai_questions: list[GeneratedQuestion],
    ) -> PaperSet:
        """
        Compose a Minor paper set with layout:
        Q1(a), Q1(b), Q2(a), Q2(b), Q3(a), Q3(b)
        Bank: 4 questions, AI: 2 questions.
        AI questions must be spread (not both in same main-question).
        """
        exam_subtype = getattr(blueprint, "exam_subtype", "ISA-I")
        paper_set = PaperSet(
            set_id=set_id,
            set_index=set_index,
            exam_type=ExamType.MINOR,
            max_marks=blueprint.total_attempted_marks,
            duration=f"{blueprint.duration_minutes} mins",
            instructions=blueprint.choice_instruction,
            exam_title=f"Question Paper for Minor Examination ({exam_subtype})",
        )

        sub_marks = getattr(blueprint, "sub_question_marks", []) or [blueprint.marks_per_part]
        part_marks = {"a": sub_marks[0] if len(sub_marks) > 0 else 10,
                      "b": sub_marks[1] if len(sub_marks) > 1 else sub_marks[0]}

        # Assign slots: 6 total
        # Preferred: Q1a=bank, Q1b=bank, Q2a=bank, Q2b=AI, Q3a=bank, Q3b=AI
        # This spreads AI across Q2 and Q3 (2 different main questions)
        slots = [
            (1, "a"), (1, "b"),
            (2, "a"), (2, "b"),
            (3, "a"), (3, "b"),
        ]
        # Assign sources per slot
        # Bank at indices 0,1,2,4 → AI at 3,5
        ai_slots = {(2, "b"), (3, "b")}

        bank_iter = iter(bank_questions)
        ai_iter = iter(ai_questions)

        for main_q, part in slots:
            slot_id = f"Q{main_q}{part}"
            is_ai = (main_q, part) in ai_slots
            assigned_m = part_marks.get(part, 10)

            if is_ai:
                q = next(ai_iter, None)
                if q is None:
                    # Fallback: use another bank question
                    q_bank = next(bank_iter, None)
                    if q_bank:
                        pq = self._bank_to_paper_question(q_bank, slot_id, main_q, part, assigned_m)
                    else:
                        logger.warning(f"No question available for slot {slot_id}")
                        continue
                else:
                    pq = self._generated_to_paper_question(q, slot_id, main_q, part, assigned_m)
            else:
                q_bank = next(bank_iter, None)
                if q_bank is None:
                    # Fallback: use AI question
                    q = next(ai_iter, None)
                    if q:
                        pq = self._generated_to_paper_question(q, slot_id, main_q, part, assigned_m)
                    else:
                        logger.warning(f"No question available for slot {slot_id}")
                        continue
                else:
                    pq = self._bank_to_paper_question(q_bank, slot_id, main_q, part, assigned_m)

            paper_set.questions.append(pq)

        return paper_set

    def compose_end_sem(
        self,
        set_id: str,
        set_index: int,
        blueprint: EndSemBlueprint,
        bank_questions_by_unit: dict[int, list[Question]],
        ai_questions_by_unit: dict[int, list[GeneratedQuestion]],
    ) -> PaperSet:
        """
        Compose an End-Sem paper set with layout:
        Unit 1: Q1-Q3 (6 subquestions)
        Unit 2: Q4-Q6 (6 subquestions)
        Unit 3: Q7-Q8 (4 subquestions)
        AI preferred: U1=2, U2=2, U3=1
        """
        exam_subtype = getattr(blueprint, "exam_subtype", "ESA")
        paper_set = PaperSet(
            set_id=set_id,
            set_index=set_index,
            exam_type=ExamType.END_SEM,
            max_marks=blueprint.total_attempted_marks,
            duration=f"{blueprint.duration_minutes} mins",
            instructions=blueprint.choice_instruction,
            exam_title=f"Question Paper for End Semester Assessment ({exam_subtype})",
        )

        sub_marks = getattr(blueprint, "sub_question_marks", []) or [10, 10]
        part_marks = {"a": sub_marks[0] if len(sub_marks) > 0 else 10,
                      "b": sub_marks[1] if len(sub_marks) > 1 else sub_marks[0]}

        # Unit 1: Q1-Q3, each (a)(b)
        # Unit 2: Q4-Q6, each (a)(b)
        # Unit 3: Q7-Q8, each (a)(b)
        unit_q_ranges = {1: range(1, 4), 2: range(4, 7), 3: range(7, 9)}
        # AI placement: last part(s) of unit
        ai_placement_per_unit = {1: {(3, "a"), (3, "b")},
                                  2: {(6, "a"), (6, "b")},
                                  3: {(8, "a")}}

        for ua in blueprint.unit_allocations:
            u = ua.unit_number
            bank_iter = iter(bank_questions_by_unit.get(u, []))
            ai_iter = iter(ai_questions_by_unit.get(u, []))
            ai_slots = ai_placement_per_unit.get(u, set())

            for main_q in unit_q_ranges[u]:
                for part in ("a", "b"):
                    slot_id = f"Q{main_q}{part}"
                    is_ai = (main_q, part) in ai_slots
                    assigned_m = part_marks.get(part, 10)

                    if is_ai:
                        q = next(ai_iter, None)
                        if q:
                            pq = self._generated_to_paper_question(q, slot_id, main_q, part, assigned_m)
                        else:
                            qb = next(bank_iter, None)
                            pq = (self._bank_to_paper_question(qb, slot_id, main_q, part, assigned_m)
                                  if qb else None)
                    else:
                        qb = next(bank_iter, None)
                        if qb:
                            pq = self._bank_to_paper_question(qb, slot_id, main_q, part, assigned_m)
                        else:
                            q = next(ai_iter, None)
                            pq = (self._generated_to_paper_question(q, slot_id, main_q, part, assigned_m)
                                  if q else None)

                    if pq:
                        paper_set.questions.append(pq)
                    else:
                        logger.warning(f"No question available for slot {slot_id}")

        return paper_set

    # ── Converters ────────────────────────────────────────────────────────────

    def _bank_to_paper_question(
        self, q: Question, slot_id: str, main_q: int, part: str, assigned_marks: Optional[int] = None
    ) -> PaperQuestion:
        final_marks = assigned_marks if assigned_marks is not None else int(q.marks)
        vp = q.valuation_points or [
            ValuationPoint(criterion="Complete and correct answer", marks=final_marks)
        ]
        # Re-scale valuation points if assigned_marks differs
        vp_total = sum(p.marks for p in vp)
        if vp_total != final_marks and vp_total > 0:
            scale = final_marks / vp_total
            vp = [ValuationPoint(criterion=p.criterion, marks=max(1, round(p.marks * scale))) for p in vp]
            # Ensure exact sum
            diff = final_marks - sum(p.marks for p in vp)
            if diff != 0 and vp:
                vp[0] = ValuationPoint(criterion=vp[0].criterion, marks=vp[0].marks + diff)

        scheme = ValuationScheme(
            question_ref=q.question_id,
            expected_answer=q.model_answer or "[Faculty answer]",
            key_points=[q.model_answer] if q.model_answer else [],
            valuation_points=vp,
            approval_status="APPROVED",
        )
        return PaperQuestion(
            slot_id=slot_id,
            main_question_number=main_q,
            part=part,
            unit_number=q.unit_number,
            chapter_number=q.chapter_number,
            chapter_name=q.chapter_name,
            question_text=q.question_text,
            bloom_level=q.bloom_level,
            marks=final_marks,
            source=QuestionSource.QUESTION_BANK,
            approval_status=ApprovalStatus.APPROVED,  # bank questions pre-approved
            question_id=q.question_id,
            valuation_scheme=scheme,
        )

    def _generated_to_paper_question(
        self, q: GeneratedQuestion, slot_id: str, main_q: int, part: str, assigned_marks: Optional[int] = None
    ) -> PaperQuestion:
        final_marks = assigned_marks if assigned_marks is not None else int(q.marks)
        gen_id = f"GENAI-GEN-{id(q)}"
        vp = q.valuation_points or [
            ValuationPoint(criterion="Key concept explanation and technical depth", marks=max(1, final_marks // 2)),
            ValuationPoint(criterion="Illustration with examples and clarity", marks=max(1, final_marks - (final_marks // 2))),
        ]
        vp_total = sum(p.marks for p in vp)
        if vp_total != final_marks and vp_total > 0:
            scale = final_marks / vp_total
            vp = [ValuationPoint(criterion=p.criterion, marks=max(1, round(p.marks * scale))) for p in vp]
            diff = final_marks - sum(p.marks for p in vp)
            if diff != 0 and vp:
                vp[0] = ValuationPoint(criterion=vp[0].criterion, marks=vp[0].marks + diff)

        scheme = ValuationScheme(
            question_ref=gen_id,
            expected_answer=q.model_answer,
            key_points=[q.model_answer],
            valuation_points=vp,
            approval_status="PENDING",
        )
        return PaperQuestion(
            slot_id=slot_id,
            main_question_number=main_q,
            part=part,
            unit_number=q.unit_number,
            chapter_number=q.chapter_number,
            chapter_name=q.chapter_name,
            question_text=q.question_text,
            bloom_level=q.bloom_level,
            marks=final_marks,
            source=QuestionSource.AI_GENERATED,
            approval_status=ApprovalStatus.PENDING,
            generated_id=gen_id,
            valuation_scheme=scheme,
            bloom_justification=q.bloom_justification,
        )

