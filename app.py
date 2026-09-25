"""
app.py
Main Streamlit application entry point for Question Paper Setting Agent.
"""

import logging
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

# Configure page first
st.set_page_config(
    page_title="Question Paper Setting Agent",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "Question Paper Setting Agent — Generative AI Course",
    },
)

# Initialize DB and settings
from config.settings import get_settings
from repositories.database import init_db
from utils.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

@st.cache_resource
def initialize_app():
    """One-time initialization."""
    settings = get_settings()
    settings.ensure_directories()
    init_db()
    logger.info("Application initialized")
    return settings

settings = initialize_app()

# ── Global Design System ─────────────────────────────────────────────────────
st.markdown("""
<style>
  /* ── Fonts ── */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  html, body, [class*="css"], .stApp {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display",
                 "SF Pro Text", "Inter", "Helvetica Neue", Arial, sans-serif;
    background-color: #f5f5f7 !important;
    color: #1d1d1f;
    -webkit-font-smoothing: antialiased;
  }

  /* ── Hide Streamlit chrome ── */
  #MainMenu, footer, header, [data-testid="stToolbar"] { display: none !important; }
  [data-testid="stDecoration"] { display: none !important; }

  /* ── Main content area ── */
  .main .block-container {
    padding: 2.5rem 3rem 3rem 3rem;
    max-width: 1200px;
    background: transparent;
  }

  /* ── Sidebar ── */
  [data-testid="stSidebar"] {
    background: rgba(255,255,255,0.92) !important;
    backdrop-filter: saturate(180%) blur(20px);
    -webkit-backdrop-filter: saturate(180%) blur(20px);
    border-right: 1px solid rgba(0,0,0,0.08) !important;
    box-shadow: 2px 0 16px rgba(0,0,0,0.04);
  }
  [data-testid="stSidebar"] * { color: #1d1d1f !important; }
  [data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    border: none !important;
    border-radius: 10px !important;
    color: #1d1d1f !important;
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    padding: 0.55rem 1rem !important;
    text-align: left !important;
    width: 100%;
    transition: background 0.15s ease;
    box-shadow: none !important;
  }
  [data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(0,113,227,0.08) !important;
    color: #0071e3 !important;
    transform: none !important;
    box-shadow: none !important;
  }
  [data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: rgba(0,113,227,0.1) !important;
    color: #0071e3 !important;
    font-weight: 600 !important;
  }

  /* ── Page headings ── */
  h1, h2, h3 {
    color: #1d1d1f !important;
    letter-spacing: -0.02em;
    font-weight: 700;
  }
  h2 { font-size: 2rem !important; font-weight: 700; margin-bottom: 0.25rem !important; }
  h3 { font-size: 1.2rem !important; font-weight: 600; margin-top: 2rem !important; }

  /* ── Card ── */
  .apple-card {
    background: #ffffff;
    border-radius: 18px;
    padding: 1.5rem 1.75rem;
    box-shadow: 0 2px 20px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.04);
    margin-bottom: 1.25rem;
    transition: box-shadow 0.2s ease;
  }
  .apple-card:hover {
    box-shadow: 0 8px 32px rgba(0,0,0,0.1), 0 0 0 1px rgba(0,0,0,0.04);
  }

  /* ── Stat card ── */
  .stat-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 1.4rem 1.2rem;
    box-shadow: 0 2px 16px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.04);
    text-align: center;
    transition: box-shadow 0.2s ease, transform 0.15s ease;
  }
  .stat-card:hover {
    box-shadow: 0 8px 28px rgba(0,0,0,0.1);
    transform: translateY(-2px);
  }
  .stat-card .metric-value {
    font-size: 2.2rem;
    font-weight: 700;
    color: #0071e3;
    letter-spacing: -0.04em;
    line-height: 1;
    margin: 0.4rem 0 0.2rem;
  }
  .stat-card .metric-label {
    font-size: 0.78rem;
    color: #86868b;
    font-weight: 500;
    letter-spacing: 0.02em;
    text-transform: uppercase;
  }
  .stat-card .metric-icon {
    font-size: 1.3rem;
    margin-bottom: 0.2rem;
  }

  /* ── Hero banner ── */
  .hero-banner {
    background: linear-gradient(135deg, #0071e3 0%, #6e40c9 100%);
    border-radius: 20px;
    padding: 2rem 2.5rem;
    color: white;
    margin-bottom: 2rem;
    position: relative;
    overflow: hidden;
  }
  .hero-banner::before {
    content: '';
    position: absolute;
    top: -50%;
    right: -20%;
    width: 60%;
    height: 200%;
    background: radial-gradient(circle, rgba(255,255,255,0.12) 0%, transparent 70%);
    pointer-events: none;
  }
  .hero-banner .hero-label {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    opacity: 0.75;
  }
  .hero-banner .hero-title {
    font-size: 1.8rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    margin: 0.4rem 0 0.3rem;
  }
  .hero-banner .hero-sub {
    font-size: 0.9rem;
    opacity: 0.82;
    font-weight: 400;
  }

  /* ── Status pill ── */
  .pill {
    display: inline-block;
    padding: 0.2rem 0.75rem;
    border-radius: 100px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.02em;
  }
  .pill-blue   { background: rgba(0,113,227,0.1);  color: #0071e3; }
  .pill-green  { background: rgba(52,199,89,0.12);  color: #1a7f37; }
  .pill-orange { background: rgba(255,149,0,0.12);  color: #b35c00; }
  .pill-red    { background: rgba(255,59,48,0.1);   color: #d70015; }
  .pill-gray   { background: rgba(60,60,67,0.08);   color: #3c3c43; }
  .pill-purple { background: rgba(110,64,201,0.1);  color: #6e40c9; }

  /* ── Badge (legacy compat) ── */
  .badge { display: inline-block; padding: 0.18rem 0.6rem; border-radius: 100px;
           font-size: 0.72rem; font-weight: 600; margin: 0.1rem; }
  .badge-bank   { background: rgba(0,113,227,0.1);  color: #0071e3; }
  .badge-ai     { background: rgba(110,64,201,0.1); color: #6e40c9; }
  .badge-l2     { background: rgba(52,199,89,0.12); color: #1a7f37; }
  .badge-l3     { background: rgba(255,149,0,0.12); color: #b35c00; }
  .badge-approved { background: rgba(52,199,89,0.12); color: #1a7f37; }
  .badge-pending  { background: rgba(255,149,0,0.12); color: #b35c00; }
  .badge-rejected { background: rgba(255,59,48,0.1);  color: #d70015; }
  .badge-draft    { background: rgba(60,60,67,0.08);  color: #3c3c43; }

  /* ── Confidential banner ── */
  .confidential-banner {
    background: rgba(255,59,48,0.06);
    border: 1px solid rgba(255,59,48,0.2);
    color: #d70015;
    padding: 0.45rem 1rem;
    border-radius: 10px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-bottom: 1.5rem;
    text-align: center;
    letter-spacing: 0.06em;
  }
  .draft-watermark {
    background: rgba(255,149,0,0.06);
    border: 1px solid rgba(255,149,0,0.25);
    color: #b35c00;
    padding: 0.5rem 1rem;
    border-radius: 10px;
    font-weight: 600;
    text-align: center;
    margin-bottom: 1rem;
  }

  /* ── Buttons ── */
  .stButton > button {
    border-radius: 980px !important;
    font-weight: 500 !important;
    font-size: 0.9rem !important;
    padding: 0.55rem 1.4rem !important;
    transition: all 0.2s ease !important;
    border: none !important;
    letter-spacing: -0.01em;
  }
  .stButton > button[kind="primary"] {
    background: #0071e3 !important;
    color: white !important;
    box-shadow: 0 2px 8px rgba(0,113,227,0.3) !important;
  }
  .stButton > button[kind="primary"]:hover {
    background: #0077ed !important;
    box-shadow: 0 4px 16px rgba(0,113,227,0.4) !important;
    transform: translateY(-1px) !important;
  }
  .stButton > button[kind="secondary"] {
    background: rgba(0,0,0,0.05) !important;
    color: #1d1d1f !important;
    border: 1px solid rgba(0,0,0,0.1) !important;
  }
  .stButton > button[kind="secondary"]:hover {
    background: rgba(0,0,0,0.08) !important;
    transform: translateY(-1px) !important;
  }

  /* ── Inputs ── */
  .stTextInput > div > div > input,
  .stSelectbox > div > div > div,
  .stTextArea > div > div > textarea,
  .stNumberInput > div > div > input {
    border-radius: 10px !important;
    border: 1px solid rgba(0,0,0,0.12) !important;
    background: #ffffff !important;
    font-size: 0.9rem !important;
    color: #1d1d1f !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
  }
  .stTextInput > div > div > input:focus,
  .stTextArea > div > div > textarea:focus {
    border-color: #0071e3 !important;
    box-shadow: 0 0 0 3px rgba(0,113,227,0.15) !important;
    outline: none !important;
  }

  /* ── Tabs ── */
  .stTabs [data-baseweb="tab-list"] {
    background: rgba(0,0,0,0.04);
    border-radius: 12px;
    padding: 4px;
    border: none;
    gap: 2px;
  }
  .stTabs [data-baseweb="tab"] {
    border-radius: 9px;
    font-weight: 500;
    font-size: 0.88rem;
    color: #86868b;
    padding: 0.45rem 1.1rem;
    border: none;
    transition: all 0.2s ease;
    background: transparent;
  }
  .stTabs [aria-selected="true"] {
    background: #ffffff !important;
    color: #1d1d1f !important;
    font-weight: 600 !important;
    box-shadow: 0 1px 6px rgba(0,0,0,0.1) !important;
  }
  .stTabs [data-baseweb="tab-panel"] {
    padding-top: 1.5rem;
  }

  /* ── Dataframe / Table ── */
  .stDataFrame { border-radius: 14px; overflow: hidden; }
  .stDataFrame table { border: none; }
  .stDataFrame th {
    background: rgba(0,0,0,0.03) !important;
    color: #86868b !important;
    font-weight: 600 !important;
    font-size: 0.75rem !important;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    border: none !important;
  }
  .stDataFrame td {
    font-size: 0.88rem !important;
    color: #1d1d1f !important;
    border-color: rgba(0,0,0,0.05) !important;
  }

  /* ── Alerts ── */
  .stAlert {
    border-radius: 12px !important;
    border: none !important;
    font-size: 0.9rem;
  }
  div[data-testid="stNotification"] { border-radius: 14px !important; }

  /* ── Spinner ── */
  .stSpinner { color: #0071e3 !important; }

  /* ── Expander ── */
  .streamlit-expanderHeader {
    border-radius: 12px !important;
    background: rgba(0,0,0,0.03) !important;
    font-weight: 500 !important;
    color: #1d1d1f !important;
  }

  /* ── Metrics (native st.metric) ── */
  [data-testid="metric-container"] {
    background: #ffffff;
    border-radius: 16px;
    padding: 1.2rem 1rem !important;
    box-shadow: 0 2px 16px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.04);
  }
  [data-testid="metric-container"] label {
    color: #86868b !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  [data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #1d1d1f !important;
    font-weight: 700 !important;
    font-size: 1.8rem !important;
    letter-spacing: -0.03em !important;
  }

  /* ── File uploader ── */
  [data-testid="stFileUploader"] {
    border-radius: 14px !important;
    border: 1.5px dashed rgba(0,113,227,0.3) !important;
    background: rgba(0,113,227,0.02) !important;
    transition: border-color 0.2s, background 0.2s;
  }
  [data-testid="stFileUploader"]:hover {
    border-color: #0071e3 !important;
    background: rgba(0,113,227,0.04) !important;
  }

  /* ── Sidebar divider ── */
  [data-testid="stSidebar"] hr {
    border-color: rgba(0,0,0,0.07) !important;
    margin: 0.75rem 0 !important;
  }

  /* ── Progress bar ── */
  .stProgress > div > div > div {
    background: linear-gradient(90deg, #0071e3, #6e40c9) !important;
    border-radius: 100px;
  }
  .stProgress > div > div {
    background: rgba(0,0,0,0.06) !important;
    border-radius: 100px;
  }

  /* ── Slider ── */
  [data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
    background: #0071e3 !important;
    border: 2px solid white !important;
    box-shadow: 0 2px 8px rgba(0,113,227,0.4) !important;
  }

  /* ── Section divider ── */
  hr { border-color: rgba(0,0,0,0.07) !important; }

  /* ── Toast notifications ── */
  [data-testid="stToast"] {
    border-radius: 14px !important;
    backdrop-filter: blur(20px) !important;
    box-shadow: 0 8px 32px rgba(0,0,0,0.12) !important;
    border: 1px solid rgba(0,0,0,0.06) !important;
  }

  /* ── Activity row ── */
  .activity-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.65rem 0;
    border-bottom: 1px solid rgba(0,0,0,0.05);
    font-size: 0.875rem;
    color: #1d1d1f;
  }
  .activity-row:last-child { border-bottom: none; }
  .activity-time {
    font-size: 0.78rem;
    color: #86868b;
    min-width: 120px;
    font-variant-numeric: tabular-nums;
  }
  .activity-action {
    font-weight: 500;
    flex: 1;
  }

  /* ── Section label ── */
  .section-label {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #86868b;
    margin-bottom: 0.75rem;
    margin-top: 0.25rem;
  }

  /* ── Quick action button ── */
  .quick-action {
    background: #ffffff;
    border-radius: 14px;
    padding: 1.2rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.04);
    text-align: center;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .quick-action:hover {
    box-shadow: 0 6px 24px rgba(0,0,0,0.1);
    transform: translateY(-2px);
  }
  .quick-action .qa-icon { font-size: 1.6rem; margin-bottom: 0.4rem; }
  .quick-action .qa-label { font-size: 0.85rem; font-weight: 600; color: #1d1d1f; }

  /* ── Checkbox / Radio ── */
  [data-testid="stCheckbox"] label, [data-testid="stRadio"] label {
    font-size: 0.9rem !important;
    color: #1d1d1f !important;
  }
</style>
""", unsafe_allow_html=True)


# ── Navigation ────────────────────────────────────────────────────────────────

def render_sidebar():
    with st.sidebar:
        # ── Brand ──────────────────────────────────────────────────────────────
        st.markdown("""
        <div style='padding: 1.5rem 0.5rem 1rem; border-bottom: 1px solid rgba(0,0,0,0.07); margin-bottom: 0.5rem;'>
            <div style='font-size: 1.15rem; font-weight: 700; color: #1d1d1f; letter-spacing: -0.02em;'>
                Prashnopatra
            </div>
            <div style='font-size: 0.75rem; color: #86868b; margin-top: 0.15rem; font-weight: 400;'>
                AI Question Paper Agent
            </div>
        </div>
        """, unsafe_allow_html=True)

        pages = {
            "🏠  Dashboard":          "dashboard",
            "📚  Course Setup":       "course_setup",
            "📋  Question Bank":      "question_bank",
            "📖  Lesson Plan":        "lesson_plan",
            "⚡  Generate Paper":     "paper_generator",
            "👩‍🏫  Faculty Review":    "faculty_review",
            "✅  Validation":         "validation_reports",
            "📊  Usage History":      "usage_history",
            "⚙️  Settings":           "settings_page",
        }

        if "current_page" not in st.session_state:
            st.session_state.current_page = "dashboard"

        st.markdown("<div style='padding: 0.25rem 0;'>", unsafe_allow_html=True)
        for label, page_key in pages.items():
            is_active = st.session_state.current_page == page_key
            if st.sidebar.button(
                label,
                key=f"nav_{page_key}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state.current_page = page_key
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        # ── Status pill at bottom ───────────────────────────────────────────────
        st.markdown("<div style='flex: 1;'></div>", unsafe_allow_html=True)
        st.markdown("---")
        is_mock = settings.is_mock_mode
        pill_color = "rgba(255,149,0,0.12)"
        text_color = "#b35c00"
        dot = "🟡"
        if not is_mock:
            pill_color = "rgba(52,199,89,0.12)"
            text_color = "#1a7f37"
            dot = "🟢"

        st.markdown(f"""
        <div style='padding: 0 0.5rem 1rem;'>
            <div style='background: {pill_color}; border-radius: 10px; padding: 0.5rem 0.75rem;'>
                <div style='font-size: 0.72rem; font-weight: 600; color: {text_color};'>
                    {dot} {'Mock Mode' if is_mock else 'Live API'}
                </div>
                <div style='font-size: 0.68rem; color: #86868b; margin-top: 0.1rem;'>
                    {settings.llm_provider.upper()} · {settings.resolved_llm_model[:22]}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)



def render_page(page_key: str):
    """Dynamically load and render the selected page."""
    page_module_map = {
        "dashboard": "ui.pages.dashboard",
        "course_setup": "ui.pages.course_setup",
        "question_bank": "ui.pages.question_bank",
        "lesson_plan": "ui.pages.lesson_plan",
        "paper_generator": "ui.pages.paper_generator",
        "faculty_review": "ui.pages.faculty_review",
        "validation_reports": "ui.pages.validation_reports",
        "usage_history": "ui.pages.usage_history",
        "settings_page": "ui.pages.settings_page",
    }
    module_name = page_module_map.get(page_key, "ui.pages.dashboard")
    import importlib
    try:
        module = importlib.import_module(module_name)
        module.render()
    except Exception as exc:
        st.error(f"Page error: {exc}")
        if settings.debug:
            st.exception(exc)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    render_sidebar()
    render_page(st.session_state.get("current_page", "dashboard"))


if __name__ == "__main__":
    main()
