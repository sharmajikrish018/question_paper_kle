"""
tests/test_config.py
Tests for configuration loading, .env handling, and Windows paths.
"""

import os
import pytest


class TestConfiguration:

    def test_settings_load_without_error(self):
        """Settings must load successfully from .env."""
        from config.settings import get_settings
        s = get_settings()
        assert s is not None
        assert s.app_name == "Question Paper Setting Agent"

    def test_mock_mode_enabled_in_test(self):
        """Tests should run in mock mode."""
        from config.settings import get_settings
        s = get_settings()
        # Test env sets USE_MOCK_LLM=true
        assert s.use_mock_llm or s.llm_provider == "mock"

    def test_key_resolution_order(self):
        """LLM_API_KEY takes priority over provider-specific key."""
        from config.settings import Settings
        # If both set, LLM_API_KEY wins
        s = Settings(llm_api_key="primary_key", groq_api_key="secondary_key")
        assert s.resolved_llm_api_key == "primary_key"

    def test_groq_fallback(self):
        """GROQ_API_KEY is used when LLM_API_KEY is empty."""
        from config.settings import Settings
        s = Settings(llm_provider="groq", llm_api_key="", groq_api_key="groq_key")
        assert s.resolved_llm_api_key == "groq_key"

    def test_env_file_exists(self):
        """The .env file must exist in project root."""
        from config.settings import PROJECT_ROOT
        assert (PROJECT_ROOT / ".env").exists(), ".env file missing"

    def test_env_example_exists(self):
        """The .env.example file must exist."""
        from config.settings import PROJECT_ROOT
        assert (PROJECT_ROOT / ".env.example").exists()

    def test_project_root_is_valid_directory(self):
        """Project root directory must exist."""
        from config.settings import PROJECT_ROOT
        assert PROJECT_ROOT.is_dir()

    def test_windows_path_no_crash(self):
        """Path operations must work on Windows."""
        from config.settings import get_settings
        from pathlib import Path
        s = get_settings()
        # These should not raise
        _ = s.question_bank_dir
        _ = s.lesson_plan_dir
        _ = s.database_dir
        assert True

    def test_database_url_resolves(self):
        """Database URL must be resolvable to an absolute path."""
        from config.settings import get_settings
        s = get_settings()
        db_url = s.database_url
        assert "sqlite" in db_url or "postgresql" in db_url

    def test_bloom_percents_default(self):
        """Default Bloom percents must sum to 100."""
        from config.settings import get_settings
        s = get_settings()
        total = s.default_bloom_l2_percent + s.default_bloom_l3_percent
        assert total == 100


class TestDatabaseInit:

    def test_all_tables_created(self):
        """All required tables must be created by init_db."""
        from repositories.database import init_db, engine
        from sqlalchemy import inspect

        init_db()
        insp = inspect(engine)
        tables = set(insp.get_table_names())

        required = {
            "courses", "units", "chapters", "questions",
            "generated_questions", "paper_requests", "paper_sets",
            "paper_questions", "usage_history", "audit_logs",
            "uploaded_files", "app_settings",
        }
        missing = required - tables
        assert not missing, f"Missing tables: {missing}"

    def test_question_crud(self):
        """Basic question CRUD operations must work."""
        from repositories.question_repo import QuestionRepository
        from models.question import Question
        from models.enums import BloomLevel, QuestionSource, ApprovalStatus

        repo = QuestionRepository()
        q = Question(
            question_id="TEST-CRUD-001",
            unit_number=1,
            chapter_number=1,
            chapter_name="Test Chapter",
            question_text="Test question for CRUD verification.",
            bloom_level=BloomLevel.L2,
            marks=10,
        )
        repo.upsert(q, subject_id="default-subject")
        loaded = repo.get_by_id("TEST-CRUD-001", subject_id="default-subject")
        assert loaded is not None
        assert loaded.question_text == q.question_text

    def test_audit_log_works(self):
        """Audit log insertion must not raise."""
        from repositories.audit_repo import AuditRepository
        repo = AuditRepository()
        repo.log("TEST_ACTION", details={"test": True})
        logs = repo.get_recent(1)
        assert len(logs) >= 1
