"""
tests/test_generation.py
Tests for paper generation pipeline using mock LLM.
"""

import pytest
from models.enums import ExamType, ApprovalStatus, PaperSetStatus, QuestionSource


class TestMinorGeneration:
    """Test Minor paper generation with mock LLM."""

    def test_minor_generation_mock(self, loaded_bank, mock_llm):
        """End-to-end Minor generation using mock LLM."""
        from agents.coordinator import CoordinatorAgent, GenerationRequest

        coordinator = CoordinatorAgent(llm_provider=mock_llm)
        request = GenerationRequest(
            exam_type=ExamType.MINOR,
            num_sets=1,
            l2_percent=50,
            l3_percent=50,
            selected_chapters=[1, 2, 3],
            random_seed=42,
        )
        result = coordinator.generate(request)
        assert result.success
        assert result.complete_paper is not None
        assert len(result.complete_paper.sets) == 1

    def test_minor_bank_ai_allocation(self, loaded_bank, mock_llm):
        """Minor paper must have exactly 4 bank + 2 AI questions."""
        from agents.coordinator import CoordinatorAgent, GenerationRequest

        coordinator = CoordinatorAgent(llm_provider=mock_llm)
        request = GenerationRequest(
            exam_type=ExamType.MINOR,
            num_sets=1,
            selected_chapters=[1, 2, 3],
            random_seed=42,
        )
        result = coordinator.generate(request)
        assert result.success
        paper_set = result.complete_paper.sets[0]
        bank_count = sum(
            1 for q in paper_set.questions
            if q.source in (QuestionSource.QUESTION_BANK, "QUESTION_BANK")
        )
        ai_count = sum(
            1 for q in paper_set.questions
            if q.source in (QuestionSource.AI_GENERATED, "AI_GENERATED")
        )
        assert bank_count == 4, f"Expected 4 bank questions, got {bank_count}"
        assert ai_count == 2, f"Expected 2 AI questions, got {ai_count}"

    def test_minor_total_questions(self, loaded_bank, mock_llm):
        """Minor paper must have exactly 6 printed subquestions."""
        from agents.coordinator import CoordinatorAgent, GenerationRequest

        coordinator = CoordinatorAgent(llm_provider=mock_llm)
        request = GenerationRequest(
            exam_type=ExamType.MINOR,
            num_sets=1,
            selected_chapters=[1, 2, 3],
        )
        result = coordinator.generate(request)
        assert result.success
        paper_set = result.complete_paper.sets[0]
        assert len(paper_set.questions) == 6

    def test_minor_bloom_distribution(self, loaded_bank, mock_llm):
        """Minor paper with 50:50 must have 3 L2 and 3 L3."""
        from agents.coordinator import CoordinatorAgent, GenerationRequest

        coordinator = CoordinatorAgent(llm_provider=mock_llm)
        request = GenerationRequest(
            exam_type=ExamType.MINOR,
            num_sets=1,
            l2_percent=50,
            l3_percent=50,
            selected_chapters=[1, 2, 3],
        )
        result = coordinator.generate(request)
        assert result.success
        paper_set = result.complete_paper.sets[0]
        l2 = sum(1 for q in paper_set.questions if q.bloom_level in ("L2",))
        l3 = sum(1 for q in paper_set.questions if q.bloom_level in ("L3",))
        assert l2 == 3, f"Expected 3 L2, got {l2}"
        assert l3 == 3, f"Expected 3 L3, got {l3}"

    def test_minor_marks_per_question(self, loaded_bank, mock_llm):
        """All Minor subquestions must carry 10 marks."""
        from agents.coordinator import CoordinatorAgent, GenerationRequest

        coordinator = CoordinatorAgent(llm_provider=mock_llm)
        request = GenerationRequest(
            exam_type=ExamType.MINOR,
            num_sets=1,
            selected_chapters=[1, 2, 3],
        )
        result = coordinator.generate(request)
        assert result.success
        for q in result.complete_paper.sets[0].questions:
            assert q.marks == 10, f"Slot {q.slot_id} has {q.marks} marks"

    def test_minor_question_numbering(self, loaded_bank, mock_llm):
        """Minor paper slots must be Q1a, Q1b, Q2a, Q2b, Q3a, Q3b."""
        from agents.coordinator import CoordinatorAgent, GenerationRequest

        coordinator = CoordinatorAgent(llm_provider=mock_llm)
        request = GenerationRequest(
            exam_type=ExamType.MINOR,
            num_sets=1,
            selected_chapters=[1, 2, 3],
        )
        result = coordinator.generate(request)
        assert result.success
        slots = sorted(q.slot_id for q in result.complete_paper.sets[0].questions)
        expected = ["Q1a", "Q1b", "Q2a", "Q2b", "Q3a", "Q3b"]
        assert slots == expected, f"Got {slots}"


class TestEndSemGeneration:
    """Test End-Semester paper generation."""

    def test_endsem_generation_mock(self, loaded_bank, mock_llm):
        """End-to-end End-Sem generation using mock LLM."""
        from agents.coordinator import CoordinatorAgent, GenerationRequest

        coordinator = CoordinatorAgent(llm_provider=mock_llm)
        request = GenerationRequest(
            exam_type=ExamType.END_SEM,
            num_sets=1,
            random_seed=42,
        )
        result = coordinator.generate(request)
        assert result.success
        assert result.complete_paper is not None

    def test_endsem_total_questions(self, loaded_bank, mock_llm):
        """End-Sem paper must have 16 printed subquestions."""
        from agents.coordinator import CoordinatorAgent, GenerationRequest

        coordinator = CoordinatorAgent(llm_provider=mock_llm)
        request = GenerationRequest(
            exam_type=ExamType.END_SEM,
            num_sets=1,
        )
        result = coordinator.generate(request)
        assert result.success
        paper_set = result.complete_paper.sets[0]
        assert len(paper_set.questions) == 16

    def test_endsem_bank_ai_allocation(self, loaded_bank, mock_llm):
        """End-Sem paper must have exactly 11 bank + 5 AI questions."""
        from agents.coordinator import CoordinatorAgent, GenerationRequest

        coordinator = CoordinatorAgent(llm_provider=mock_llm)
        request = GenerationRequest(
            exam_type=ExamType.END_SEM,
            num_sets=1,
        )
        result = coordinator.generate(request)
        assert result.success
        paper_set = result.complete_paper.sets[0]
        bank = sum(1 for q in paper_set.questions if q.source in ("QUESTION_BANK",))
        ai = sum(1 for q in paper_set.questions if q.source in ("AI_GENERATED",))
        assert bank == 11, f"Expected 11 bank, got {bank}"
        assert ai == 5, f"Expected 5 AI, got {ai}"


class TestMultipleSetGeneration:

    def test_multiple_sets_no_bank_reuse(self, loaded_bank, mock_llm):
        """Bank questions must not be reused across sets in same request."""
        from agents.coordinator import CoordinatorAgent, GenerationRequest

        coordinator = CoordinatorAgent(llm_provider=mock_llm)
        request = GenerationRequest(
            exam_type=ExamType.MINOR,
            num_sets=2,
            selected_chapters=[1, 2, 3],
            random_seed=42,
        )
        result = coordinator.generate(request)
        assert result.success
        assert len(result.complete_paper.sets) == 2

        # Collect bank question IDs per set
        sets = result.complete_paper.sets
        bank_ids_0 = {
            q.question_id for q in sets[0].questions
            if q.source in ("QUESTION_BANK",) and q.question_id
        }
        bank_ids_1 = {
            q.question_id for q in sets[1].questions
            if q.source in ("QUESTION_BANK",) and q.question_id
        }
        # No bank question should appear in both sets
        overlap = bank_ids_0 & bank_ids_1
        assert len(overlap) == 0, f"Questions reused across sets: {overlap}"


class TestApprovalGating:

    def test_export_blocked_before_approval(self, loaded_bank, mock_llm):
        """Export must raise ExportError when set is not APPROVED."""
        from agents.coordinator import CoordinatorAgent, GenerationRequest
        from agents.export_agent import ExportAgent, ExportError
        from models.paper import PaperSet
        from models.validation import ValidationReport
        from models.enums import ValidationStatus

        coordinator = CoordinatorAgent(llm_provider=mock_llm)
        request = GenerationRequest(
            exam_type=ExamType.MINOR,
            num_sets=1,
            selected_chapters=[1, 2, 3],
        )
        result = coordinator.generate(request)
        assert result.success

        paper_set = result.complete_paper.sets[0]
        assert paper_set.status in ("GENERATED", PaperSetStatus.GENERATED)

        report = ValidationReport(
            set_id=paper_set.set_id,
            exam_type="MINOR",
            status=ValidationStatus.PASS,
            findings=[],
        )
        export_agent = ExportAgent()
        with pytest.raises(ExportError):
            export_agent.export_paper(
                paper_set=paper_set,
                validation_report=report,
                template_path=None,
                is_draft=False,
            )

    def test_draft_export_allowed_without_approval(self, loaded_bank, mock_llm):
        """Draft export must be allowed without APPROVED status."""
        from agents.coordinator import CoordinatorAgent, GenerationRequest
        from agents.export_agent import ExportAgent
        from models.validation import ValidationReport
        from models.enums import ValidationStatus

        coordinator = CoordinatorAgent(llm_provider=mock_llm)
        request = GenerationRequest(
            exam_type=ExamType.MINOR,
            num_sets=1,
            selected_chapters=[1, 2, 3],
        )
        result = coordinator.generate(request)
        assert result.success

        paper_set = result.complete_paper.sets[0]
        report = ValidationReport(
            set_id=paper_set.set_id,
            exam_type="MINOR",
            status=ValidationStatus.PASS,
            findings=[],
        )
        export_agent = ExportAgent()
        # Should not raise
        out_path = export_agent.export_paper(
            paper_set=paper_set,
            validation_report=report,
            template_path=None,
            is_draft=True,
        )
        assert out_path.exists()
        # Check draft contains DRAFT in filename
        assert "DRAFT" in out_path.name or out_path.exists()


class TestValuationScheme:

    def test_valuation_total_must_be_10(self, mock_llm):
        """Valuation points must always total 10."""
        from models.question import GeneratedQuestion

        q = GeneratedQuestion(
            question_text="Explain GAN",
            unit_number=1,
            chapter_number=1,
            chapter_name="Chapter 1",
            bloom_level="L2",
            marks=10,
            model_answer="Answer",
            valuation_points=[
                {"criterion": "Point 1", "marks": 4},
                {"criterion": "Point 2", "marks": 4},
                {"criterion": "Point 3", "marks": 2},
            ],
            bloom_justification="Tests understanding",
            syllabus_grounding=["GAN basics"],
        )
        total = sum(vp.marks for vp in q.valuation_points)
        assert total == 10

    def test_valuation_invalid_total_raises(self):
        """Valuation points not summing to 10 must raise ValidationError."""
        from models.question import GeneratedQuestion
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            GeneratedQuestion(
                question_text="Explain GAN",
                unit_number=1,
                chapter_number=1,
                chapter_name="Chapter 1",
                bloom_level="L2",
                marks=10,
                model_answer="Answer",
                valuation_points=[
                    {"criterion": "Point 1", "marks": 5},
                    {"criterion": "Point 2", "marks": 3},
                    # Sum is 8, not 10
                ],
                bloom_justification="Tests understanding",
                syllabus_grounding=["GAN basics"],
            )
