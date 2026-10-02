"""
ui/pages/settings_page.py
Application settings configuration page.
"""

import streamlit as st
from config.settings import get_settings
from repositories.settings_repo import SettingsRepository

settings = get_settings()
settings_repo = SettingsRepository()


def render():
    st.markdown("## ⚙️ Settings")

    tab1, tab2, tab3 = st.tabs(["🤖 LLM Provider", "📐 Paper Rules", "🔧 System"])

    with tab1:
        _render_llm_settings()
    with tab2:
        _render_paper_rules()
    with tab3:
        _render_system_settings()


def _render_llm_settings():
    st.markdown("### LLM Provider Configuration")
    st.info("Changes here update session state only. Edit `.env` for permanent changes.")

    providers = ["groq", "openrouter", "nvidia_nim", "ollama", "custom_openai_compatible", "mock"]
    provider = st.selectbox(
        "LLM Provider",
        providers,
        index=providers.index(settings.llm_provider) if settings.llm_provider in providers else 0,
    )

    model = st.text_input("Model Name", value=settings.resolved_llm_model)
    base_url = st.text_input("API Base URL", value=settings.resolved_llm_base_url)

    # API key — show only first 4 chars
    api_key_display = settings.resolved_llm_api_key
    if api_key_display:
        api_key_display = api_key_display[:4] + "*" * (len(api_key_display) - 4)
    st.text_input("API Key (masked)", value=api_key_display, disabled=True)

    mock_mode = st.checkbox("Use Mock LLM (offline demo)", value=settings.is_mock_mode)

    # Connectivity test
    if st.button("🔌 Test API Connectivity"):
        if mock_mode or provider == "mock":
            st.success("✅ Mock mode active — no API calls needed")
        else:
            with st.spinner("Testing..."):
                try:
                    from services.llm_provider import get_llm_provider
                    from models.question import GeneratedQuestion
                    llm = get_llm_provider()
                    # Simple ping
                    from pydantic import BaseModel
                    class Ping(BaseModel):
                        message: str
                    result = llm.generate_structured(
                        [{"role": "user", "content": "Say OK"}],
                        Ping,
                        temperature=0.1,
                    )
                    st.success(f"✅ Connected! Response: {result.message[:50]}")
                except Exception as exc:
                    st.error(f"❌ Connection failed: {exc}")

    col1, col2 = st.columns(2)
    with col1:
        temp_gen = st.slider(
            "Generation Temperature", 0.0, 1.0,
            float(settings.llm_temperature_generation), 0.05,
        )
    with col2:
        temp_val = st.slider(
            "Validation Temperature", 0.0, 1.0,
            float(settings.llm_temperature_validation), 0.05,
        )

    max_tokens = st.number_input("Max Tokens", value=settings.llm_max_tokens, min_value=512)
    timeout = st.number_input("Timeout (seconds)", value=settings.llm_timeout_seconds, min_value=10)
    retries = st.number_input("Max Retries", value=settings.llm_max_retries, min_value=1, max_value=10)

    if st.button("💾 Save Provider Settings"):
        settings_repo.set("llm_provider", provider)
        settings_repo.set("llm_model", model)
        settings_repo.set("llm_base_url", base_url)
        settings_repo.set("use_mock_llm", mock_mode)
        settings_repo.set("llm_temperature_generation", temp_gen)
        settings_repo.set("llm_temperature_validation", temp_val)
        st.success("Settings saved (session). Edit .env for permanent changes.")


def _render_paper_rules():
    st.markdown("### Paper Generation Rules")

    dup_threshold = st.slider(
        "Semantic Duplicate Threshold",
        0.5, 1.0, float(settings.semantic_duplicate_threshold), 0.01,
    )
    warn_threshold = st.slider(
        "Similarity Warning Threshold",
        0.5, 1.0, float(settings.semantic_warning_threshold), 0.01,
    )

    tolerance = st.slider(
        "Bloom Allocation Tolerance (%)",
        1, 20, int(settings.default_ratio_tolerance_percent),
    )

    max_sets = st.number_input(
        "Maximum Paper Sets per Request",
        value=int(settings.max_paper_sets), min_value=1, max_value=10,
    )

    st.markdown("#### Default Bloom Distribution")
    l2_default = st.slider("Default L2 %", 0, 100, 50, 5)
    st.caption(f"L3 will be {100 - l2_default}%")

    if st.button("💾 Save Paper Rules"):
        settings_repo.set("semantic_duplicate_threshold", dup_threshold)
        settings_repo.set("semantic_warning_threshold", warn_threshold)
        settings_repo.set("default_ratio_tolerance_percent", tolerance)
        settings_repo.set("max_paper_sets", max_sets)
        settings_repo.set("default_bloom_l2_percent", l2_default)
        settings_repo.set("default_bloom_l3_percent", 100 - l2_default)
        st.success("Paper rules saved")


def _render_system_settings():
    st.markdown("### System Settings")

    st.markdown("#### Environment Configuration")
    st.markdown(f"- **Project Root:** `{settings.project_root}`")
    st.markdown(f"- **Database:** `{settings.database_url}`")
    st.markdown(f"- **Log Level:** `{settings.log_level}`")
    st.markdown(f"- **Debug Mode:** `{settings.debug}`")
    st.markdown(f"- **Embedding Model:** `{settings.embedding_model}`")

    st.markdown("#### Data Directories")
    for label, path in [
        ("Question Bank", settings.question_bank_dir),
        ("Lesson Plan", settings.lesson_plan_dir),
        ("Templates", settings.university_templates_dir),
        ("Drafts", settings.drafts_dir),
        ("Approved", settings.approved_dir),
    ]:
        exists = "✅" if path.exists() else "❌"
        st.markdown(f"- {exists} **{label}:** `{path}`")

    if st.button("🔧 Re-initialize Directories"):
        settings.ensure_directories()
        st.success("Directories re-created")

    if st.button("🗃️ Re-initialize Database"):
        from repositories.database import init_db
        init_db()
        st.success("Database tables re-created (existing data preserved)")

    st.markdown("#### Privacy Settings")
    log_prompts = st.checkbox(
        "Log prompt content (⚠️ security risk)", value=settings.log_prompt_content
    )
    store_raw = st.checkbox(
        "Store raw LLM responses", value=settings.store_llm_raw_responses
    )
    if st.button("💾 Save Privacy Settings"):
        settings_repo.set("log_prompt_content", log_prompts)
        settings_repo.set("store_llm_raw_responses", store_raw)
        st.success("Privacy settings saved")
