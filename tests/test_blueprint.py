"""
tests/test_blueprint.py
Tests for Minor and End-Semester blueprint generation.
"""

import pytest
from services.blueprint_service import BlueprintService, BlueprintError
from models.blueprint import MinorBlueprint, EndSemBlueprint
from models.enums import ExamType


class TestMinorBlueprint:
    """Test Minor / Internal Examination blueprint."""

    def setup_method(self):
        self.service = BlueprintService()

    def test_minor_default_structure(self):
        """Test that Minor blueprint has correct default counts."""
        bp = self.service.build_minor()
        assert bp.source.total == 6
        assert bp.source.bank_count == 4
        assert bp.source.ai_count == 2
        assert bp.bloom.total == 6
        assert bp.main_question_count == 3
        assert bp.parts_per_question == 2
        assert bp.marks_per_part == 10
        assert bp.total_attempted_marks == 40

    def test_minor_50_50_bloom(self):
        """Test default 50:50 Bloom allocation."""
        bp = self.service.build_minor(l2_percent=50, l3_percent=50)
        assert bp.bloom.l2_count == 3
        assert bp.bloom.l3_count == 3
        assert bp.bloom.l2_count + bp.bloom.l3_count == 6

    def test_minor_70_30_bloom_allocation(self):
        """Test 70:30 Bloom allocation — nearest feasible integer."""
        bp = self.service.build_minor(l2_percent=70, l3_percent=30)
        total = bp.bloom.l2_count + bp.bloom.l3_count
        assert total == 6
        # Nearest to 70%: 4 L2, 2 L3 (66.67%) OR 5 L2, 1 L3 (83.33%)
        # Round(6 * 0.70) = Round(4.2) = 4 → 4 L2, 2 L3
        assert bp.bloom.l2_count == 4
        assert bp.bloom.l3_count == 2

    def test_minor_source_note_displayed(self):
        """Source note must state this is nearest feasible, not exact 70:30."""
        bp = self.service.build_minor()
        assert "nearest feasible" in bp.source_note.lower()
        assert "66.67" in bp.source_note or "integer" in bp.source_note.lower()

    def test_minor_bloom_invalid(self):
        """Bloom percents not summing to 100 must fail."""
        with pytest.raises(BlueprintError):
            self.service.build_minor(l2_percent=60, l3_percent=50)

    def test_minor_bank_ai_matrix(self):
        """Source/Bloom matrix must sum correctly."""
        bp = self.service.build_minor()
        assert bp.bank_l2 + bp.bank_l3 == bp.source.bank_count
        assert bp.ai_l2 + bp.ai_l3 == bp.source.ai_count
        assert bp.bank_l2 + bp.ai_l2 == bp.bloom.l2_count
        assert bp.bank_l3 + bp.ai_l3 == bp.bloom.l3_count

    def test_minor_selected_chapters(self):
        """Selected chapters are preserved in blueprint."""
        chapters = [1, 2, 3]
        bp = self.service.build_minor(selected_chapters=chapters)
        assert bp.selected_chapters == chapters


class TestEndSemBlueprint:
    """Test End-Semester Examination blueprint."""

    def setup_method(self):
        self.service = BlueprintService()

    def test_endsem_default_structure(self):
        """Test End-Sem blueprint has correct totals."""
        bp = self.service.build_end_sem()
        assert bp.source.total == 16
        assert bp.source.bank_count == 11
        assert bp.source.ai_count == 5
        assert bp.bloom.total == 16
        assert bp.total_attempted_marks == 100

    def test_endsem_50_50_bloom(self):
        """Test default 50:50 Bloom for End-Sem."""
        bp = self.service.build_end_sem(l2_percent=50, l3_percent=50)
        assert bp.bloom.l2_count == 8
        assert bp.bloom.l3_count == 8
        assert bp.bloom.l2_count + bp.bloom.l3_count == 16

    def test_endsem_unit_allocations(self):
        """Test default unit allocations total correctly."""
        bp = self.service.build_end_sem()
        # Default: U1=4+2=6, U2=4+2=6, U3=3+1=4
        assert len(bp.unit_allocations) == 3
        total_bank = sum(ua.source.bank_count for ua in bp.unit_allocations)
        total_ai = sum(ua.source.ai_count for ua in bp.unit_allocations)
        assert total_bank == 11
        assert total_ai == 5
        total_printed = sum(ua.source.total for ua in bp.unit_allocations)
        assert total_printed == 16

    def test_endsem_custom_unit_alloc_valid(self):
        """Valid custom unit allocation passes validation."""
        custom = [
            {"unit": 1, "bank": 5, "ai": 1, "total": 6},
            {"unit": 2, "bank": 4, "ai": 2, "total": 6},
            {"unit": 3, "bank": 2, "ai": 2, "total": 4},
        ]
        bp = self.service.build_end_sem(unit_allocations=custom)
        assert bp.source.bank_count == 11
        assert bp.source.ai_count == 5

    def test_endsem_custom_unit_alloc_invalid(self):
        """Custom unit allocation that doesn't sum to 11/5 fails."""
        bad_alloc = [
            {"unit": 1, "bank": 4, "ai": 2, "total": 6},
            {"unit": 2, "bank": 4, "ai": 2, "total": 6},
            {"unit": 3, "bank": 4, "ai": 1, "total": 4},  # bank=12 ≠ 11
        ]
        with pytest.raises(BlueprintError):
            self.service.build_end_sem(unit_allocations=bad_alloc)

    def test_endsem_source_note(self):
        """End-Sem source note must acknowledge 68.75% not exact 70%."""
        bp = self.service.build_end_sem()
        assert "nearest feasible" in bp.source_note.lower()
        assert "68.75" in bp.source_note or "integer" in bp.source_note.lower()

    def test_endsem_unit_questions_to_attempt(self):
        """Unit attempt counts must be correct."""
        bp = self.service.build_end_sem()
        ua = bp.unit_allocations
        assert ua[0].questions_to_attempt == 4  # U1: answer any 2 → 4 subq
        assert ua[1].questions_to_attempt == 4  # U2
        assert ua[2].questions_to_attempt == 2  # U3: answer any 1 → 2 subq

    def test_endsem_marks_to_attempt(self):
        """Marks to attempt per unit must be correct."""
        bp = self.service.build_end_sem()
        ua = bp.unit_allocations
        assert ua[0].marks_to_attempt == 40
        assert ua[1].marks_to_attempt == 40
        assert ua[2].marks_to_attempt == 20
