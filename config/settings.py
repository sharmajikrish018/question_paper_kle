"""
config/settings.py
Centralised configuration using pydantic-settings.
Reads from .env and environment variables.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root is the directory that contains this config/ package
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """
    Application-wide settings.
    All values come from .env → environment variables → defaults.
    """

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "Question Paper Setting Agent"
    app_env: Literal["development", "production", "test"] = "development"
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = 8501
    secret_key: str = "replace-with-a-long-random-local-secret"

    # ── LLM provider ─────────────────────────────────────────────────────────
    llm_provider: Literal[
        "groq", "openrouter", "nvidia_nim", "ollama", "custom_openai_compatible", "mock"
    ] = "groq"
    llm_model: str = "openai/gpt-oss-120b"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: str = ""
    llm_temperature_generation: float = 0.4
    llm_temperature_validation: float = 0.1
    llm_max_tokens: int = 4096
    llm_timeout_seconds: int = 120
    llm_max_retries: int = 3

    # Provider-specific keys
    groq_api_key: str = ""
    openrouter_api_key: str = ""
    nvidia_nim_api_key: str = ""
    ollama_api_key: str = "ollama"

    # OpenRouter extras
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = ""
    openrouter_site_url: str = "http://localhost:8501"
    openrouter_app_name: str = "Question Paper Setting Agent"

    # NVIDIA NIM extras
    nvidia_nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_nim_model: str = ""

    # Ollama & Qwen extras
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen3:8b"

    # Mock mode
    use_mock_llm: bool = False

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "sqlite:///./data/database/qp_agent.db"

    # ── Similarity ───────────────────────────────────────────────────────────
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_duplicate_threshold: float = 0.88
    semantic_warning_threshold: float = 0.80

    # ── Paper rules ──────────────────────────────────────────────────────────
    default_bloom_l2_percent: int = 50
    default_bloom_l3_percent: int = 50
    default_ratio_tolerance_percent: int = 5
    max_paper_sets: int = 5

    # ── Security / logging ───────────────────────────────────────────────────
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_prompt_content: bool = False
    store_llm_raw_responses: bool = False

    # ── Derived paths (computed properties) ──────────────────────────────────
    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    @property
    def data_dir(self) -> Path:
        return PROJECT_ROOT / "data"

    @property
    def question_bank_dir(self) -> Path:
        return self.data_dir / "question_bank"

    @property
    def lesson_plan_dir(self) -> Path:
        return self.data_dir / "lesson_plan"

    @property
    def university_templates_dir(self) -> Path:
        return self.data_dir / "university_templates"

    @property
    def generated_outputs_dir(self) -> Path:
        return self.data_dir / "generated_outputs"

    @property
    def drafts_dir(self) -> Path:
        return self.generated_outputs_dir / "drafts"

    @property
    def approved_dir(self) -> Path:
        return self.generated_outputs_dir / "approved"

    @property
    def schemes_dir(self) -> Path:
        return self.generated_outputs_dir / "schemes"

    @property
    def validation_reports_dir(self) -> Path:
        return self.generated_outputs_dir / "validation_reports"

    @property
    def database_dir(self) -> Path:
        return self.data_dir / "database"

    @property
    def sample_files_dir(self) -> Path:
        return self.data_dir / "sample_files"

    @property
    def logs_dir(self) -> Path:
        return PROJECT_ROOT / "logs"

    @property
    def resolved_llm_api_key(self) -> str:
        """
        Key resolution order:
        1. LLM_API_KEY
        2. Provider-specific key (GROQ_API_KEY etc.)
        """
        if self.llm_api_key:
            return self.llm_api_key
        provider = self.llm_provider
        if provider == "groq":
            return self.groq_api_key
        if provider == "openrouter":
            return self.openrouter_api_key
        if provider == "nvidia_nim":
            return self.nvidia_nim_api_key
        if provider == "ollama":
            return self.ollama_api_key or "ollama"
        return ""

    @property
    def resolved_llm_base_url(self) -> str:
        """Return provider-specific base URL."""
        provider = self.llm_provider
        if provider == "openrouter":
            return self.openrouter_base_url
        if provider == "nvidia_nim":
            return self.nvidia_nim_base_url
        if provider == "ollama":
            return self.ollama_base_url
        return self.llm_base_url

    @property
    def resolved_llm_model(self) -> str:
        """Return provider-specific model override if set."""
        provider = self.llm_provider
        if provider == "openrouter" and self.openrouter_model:
            return self.openrouter_model
        if provider == "nvidia_nim" and self.nvidia_nim_model:
            return self.nvidia_nim_model
        if provider == "ollama" and self.ollama_model:
            return self.ollama_model
        return self.llm_model

    @property
    def is_mock_mode(self) -> bool:
        return self.use_mock_llm or self.llm_provider == "mock"

    def ensure_directories(self) -> None:
        """Create all required directories if they do not exist."""
        dirs = [
            self.question_bank_dir,
            self.lesson_plan_dir,
            self.university_templates_dir,
            self.drafts_dir,
            self.approved_dir,
            self.schemes_dir,
            self.validation_reports_dir,
            self.database_dir,
            self.sample_files_dir,
            self.logs_dir,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
            gitkeep = d / ".gitkeep"
            if not gitkeep.exists():
                gitkeep.touch()


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton Settings instance."""
    s = Settings()
    s.ensure_directories()
    return s
