"""
tests/test_question_bank.py
Tests for question bank validation and duplicate detection.
"""

import pytest
from pathlib import Path
from models.question import Question
from models.enums import BloomLevel, QuestionSource, ApprovalStatus
from services.question_bank_service import QuestionBankService, ValidationError


class TestQuestionBankValidation:

    def setup_method(self):
        self.service = QuestionBankService()

    def test_duplicate_id_detection(self):
        """Exact duplicate IDs must be caught."""
        import pandas as pd
        from io import StringIO

        csv_data = """question_id,unit_number,chapter_number,chapter_name,question_text,bloom_level,marks
Q001,1,1,Chapter 1,What is GAN?,L2,10
Q001,1,1,Chapter 1,Explain VAE architecture,L2,10
"""
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_data)
            tmp_path = Path(f.name)

        try:
            result = self.service.load_from_file(tmp_path)
            dup_errors = [e for e in result.errors if "Duplicate ID" in e.message]
            assert len(dup_errors) >= 1
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_exact_text_duplicate_detection(self):
        """Exact duplicate question text must be caught."""
        import tempfile
        csv_data = """question_id,unit_number,chapter_number,chapter_name,question_text,bloom_level,marks
Q001,1,1,Chapter 1,Explain the concept of GAN in detail with examples.,L2,10
Q002,1,1,Chapter 1,Explain the concept of GAN in detail with examples.,L2,10
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_data)
            tmp_path = Path(f.name)

        try:
            result = self.service.load_from_file(tmp_path)
            dup_text_errors = [e for e in result.errors if "duplicate question text" in e.message.lower()]
            assert len(dup_text_errors) >= 1
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_invalid_bloom_level(self):
        """L1 Bloom level must be rejected."""
        import tempfile
        csv_data = """question_id,unit_number,chapter_number,chapter_name,question_text,bloom_level,marks
Q001,1,1,Chapter 1,List the types of generative models.,L1,10
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_data)
            tmp_path = Path(f.name)

        try:
            result = self.service.load_from_file(tmp_path)
            bloom_errors = [e for e in result.errors if "bloom" in e.field.lower() or "L1" in e.message]
            assert len(bloom_errors) >= 1
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_missing_question_text(self):
        """Empty question text must be caught as fatal error."""
        import tempfile
        csv_data = """question_id,unit_number,chapter_number,chapter_name,question_text,bloom_level,marks
Q001,1,1,Chapter 1,,L2,10
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_data)
            tmp_path = Path(f.name)

        try:
            result = self.service.load_from_file(tmp_path)
            text_errors = [e for e in result.errors if "question_text" in e.field or "text" in e.message.lower()]
            assert len(text_errors) >= 1
            assert any(e.is_fatal for e in text_errors)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_marks_not_10(self):
        """Questions with marks ≠ 10 must be flagged."""
        import tempfile
        csv_data = """question_id,unit_number,chapter_number,chapter_name,question_text,bloom_level,marks
Q001,1,1,Chapter 1,Explain GAN.,L2,5
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_data)
            tmp_path = Path(f.name)

        try:
            result = self.service.load_from_file(tmp_path)
            marks_errors = [e for e in result.errors if "marks" in e.field.lower() or "Marks" in e.message]
            assert len(marks_errors) >= 1
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_missing_answer_is_warning_not_fatal(self):
        """Missing model answer should be a warning, not a fatal error."""
        import tempfile
        csv_data = """question_id,unit_number,chapter_number,chapter_name,question_text,bloom_level,marks
Q001,1,1,Chapter 1,Explain GAN architecture with examples.,L2,10
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_data)
            tmp_path = Path(f.name)

        try:
            result = self.service.load_from_file(tmp_path)
            # Should have a warning but no fatal error about answer
            assert not result.has_fatal_errors or result.imported == 1
            assert any("answer" in w.lower() for w in result.warnings)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_valid_import(self):
        """Valid CSV with correct schema imports without errors."""
        import tempfile
        csv_data = """question_id,unit_number,chapter_number,chapter_name,question_text,bloom_level,marks,model_answer
Q001,1,1,Intro to GenAI,Explain the concept of Generative AI and its applications.,L2,10,Generative AI refers to AI that creates new content.
Q002,1,1,Intro to GenAI,Apply GAN concepts to generate realistic images. Describe the training process.,L3,10,The generator creates fake images while the discriminator evaluates them.
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_data)
            tmp_path = Path(f.name)

        try:
            result = self.service.load_from_file(tmp_path)
            assert result.imported == 2
            assert not result.has_fatal_errors
        finally:
            tmp_path.unlink(missing_ok=True)
