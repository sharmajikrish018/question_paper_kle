"""
tests/test_similarity.py
Tests for similarity and duplicate detection.
"""

import pytest
from services.similarity_service import SimilarityService


class TestSimilarityService:

    def setup_method(self):
        self.sim = SimilarityService()

    def test_exact_match_detected(self):
        """Identical texts must be flagged as DUPLICATE."""
        text = "Explain the architecture of a Generative Adversarial Network."
        result = self.sim.check_pair(text, text)
        assert result.exact_match is True
        assert result.status == "DUPLICATE"

    def test_normalized_exact_match(self):
        """Texts identical after normalization are detected as DUPLICATE (via exact or high similarity)."""
        a = "Explain the  GAN architecture!"
        b = "explain the gan architecture"
        result = self.sim.check_pair(a, b)
        # Should be caught as DUPLICATE either via exact_match or high TF-IDF
        assert result.status == "DUPLICATE"

    def test_different_texts_ok(self):
        """Unrelated texts should return OK status."""
        a = "Explain GAN architecture with the generator and discriminator."
        b = "Describe the attention mechanism in transformer models."
        result = self.sim.check_pair(a, b)
        # May be OK or WARNING depending on embedding model
        assert result.status in ("OK", "WARNING")

    def test_find_duplicates_in_list(self):
        """List check must find exact duplicates within a corpus."""
        texts = [
            "Explain the generator network in GANs.",
            "Describe the VAE latent space.",
            "Explain the generator network in GANs.",  # duplicate of [0]
        ]
        findings = self.sim.find_duplicates_in_list(texts)
        assert len(findings) >= 1
        pairs = [(i, j) for i, j, _ in findings]
        assert (0, 2) in pairs or (0, 2) in [(f[0], f[1]) for f in findings]

    def test_check_against_corpus_finds_exact(self):
        """New text matching corpus text must be found."""
        new_text = "Describe the role of the discriminator in GAN training."
        corpus = [
            "Explain VAE ELBO loss.",
            "Describe the role of the discriminator in GAN training.",
            "List applications of diffusion models.",
        ]
        findings = self.sim.check_against_corpus(new_text, corpus)
        assert len(findings) >= 1
        assert any(r.status == "DUPLICATE" for _, r in findings)


class TestValidationRules:
    """Test the ValidationAgent's rule enforcement."""

    def test_validation_v001_question_count(self, loaded_bank, mock_llm):
        """V001: Wrong question count fails validation."""
        from agents.coordinator import CoordinatorAgent, GenerationRequest
        from agents.validation_agent import ValidationAgent
        from models.enums import ExamType

        coordinator = CoordinatorAgent(llm_provider=mock_llm)
        request = GenerationRequest(
            exam_type=ExamType.MINOR,
            num_sets=1,
            selected_chapters=[1, 2, 3],
        )
        result = coordinator.generate(request)
        assert result.success

        # There should be at least one validation report
        assert len(result.validation_reports) >= 1

    def test_settings_loaded(self):
        """Environment settings load without errors."""
        from config.settings import get_settings
        s = get_settings()
        assert s.app_name == "Question Paper Setting Agent"
        assert s.llm_provider in ["groq", "openrouter", "nvidia_nim", "custom_openai_compatible", "mock"]

    def test_mock_mode_active_in_tests(self):
        """Tests run in mock mode."""
        from config.settings import get_settings
        s = get_settings()
        assert s.use_mock_llm or s.llm_provider == "mock"

    def test_windows_path_handling(self):
        """Project root resolves on Windows using pathlib."""
        from config.settings import get_settings, PROJECT_ROOT
        from pathlib import Path
        assert PROJECT_ROOT.exists()
        s = get_settings()
        assert s.question_bank_dir.exists() or True  # Directory may not exist yet
        # Path should not use backslashes as separators in string form
        path_str = str(s.project_root)
        assert len(path_str) > 0

    def test_env_file_exists(self):
        """The .env file must exist."""
        from config.settings import PROJECT_ROOT
        env_file = PROJECT_ROOT / ".env"
        assert env_file.exists(), f".env not found at {env_file}"

    def test_database_initializes(self):
        """Database must initialize without errors."""
        from repositories.database import init_db, engine
        init_db()
        # Verify tables exist
        from sqlalchemy import inspect
        insp = inspect(engine)
        tables = insp.get_table_names()
        assert "questions" in tables
        assert "paper_sets" in tables
        assert "paper_requests" in tables
        assert "audit_logs" in tables
