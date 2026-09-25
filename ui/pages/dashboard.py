"""
ui/pages/dashboard.py
Dashboard — Apple-level clean design.
"""

import streamlit as st
from datetime import datetime
from repositories.database import get_session
from repositories.database import QuestionDB, PaperSetDB, AuditLogDB
from config.settings import get_settings


def render():
    settings = get_settings()

    # ── Fetch data ─────────────────────────────────────────────────────────────
    with get_session() as session:
        total_questions = session.query(QuestionDB).count()
        l2_count = session.query(QuestionDB).filter(QuestionDB.bloom_level == "L2").count()
        l3_count = session.query(QuestionDB).filter(QuestionDB.bloom_level == "L3").count()
        total_sets  = session.query(PaperSetDB).count()
        pending_sets = session.query(PaperSetDB).filter(
            PaperSetDB.status.in_(["GENERATED", "UNDER_REVIEW", "CHANGES_REQUESTED"])
        ).count()
        approved_sets = session.query(PaperSetDB).filter(PaperSetDB.status == "APPROVED").count()
        exported_sets = session.query(PaperSetDB).filter(PaperSetDB.status == "EXPORTED").count()

        logs = [
            {"action": log.action, "timestamp": log.timestamp, "paper_set_id": log.paper_set_id}
            for log in session.query(AuditLogDB).order_by(AuditLogDB.timestamp.desc()).limit(8).all()
        ]
        qs_raw = session.query(QuestionDB.chapter_number, QuestionDB.bloom_level).all()

    # ── Hero banner ────────────────────────────────────────────────────────────
    mode_label = "Mock Mode" if settings.is_mock_mode else "Live"
    mode_color = "rgba(255,149,0,0.85)" if settings.is_mock_mode else "rgba(52,199,89,0.85)"

    st.markdown(f"""
    <div class="hero-banner">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:1rem;">
            <div>
                <div class="hero-label">Active Course</div>
                <div class="hero-title">Generative AI</div>
                <div class="hero-sub">3 Units · 7 Chapters · Bloom L2 &amp; L3</div>
            </div>
            <div style="text-align:right;">
                <div style="background:{mode_color}; border-radius:100px; padding:0.3rem 0.9rem;
                            font-size:0.75rem; font-weight:600; color:white; display:inline-block;">
                    {mode_label}
                </div>
                <div style="font-size:0.72rem; opacity:0.7; margin-top:0.4rem;">
                    {settings.llm_provider.upper()} · {settings.resolved_llm_model[:30]}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Confidential notice ────────────────────────────────────────────────────
    st.markdown(
        "<div class='confidential-banner'>⚠ CONFIDENTIAL — Question papers are restricted academic documents</div>",
        unsafe_allow_html=True,
    )

    # ── Question bank stats ────────────────────────────────────────────────────
    st.markdown("<div class='section-label'>Question Bank</div>", unsafe_allow_html=True)
    completeness_pct = min(100, round(total_questions / 140 * 100)) if total_questions > 0 else 0
    cols = st.columns(4)
    _stat(cols[0], total_questions, "Total Questions", "📋")
    _stat(cols[1], l2_count, "L2 Understand", "🔵")
    _stat(cols[2], l3_count, "L3 Apply", "🟣")
    _stat(cols[3], f"{completeness_pct}%", "Bank Complete", "✅")

    # ── Paper generation stats ─────────────────────────────────────────────────
    st.markdown("<div class='section-label' style='margin-top:1.5rem;'>Paper Sets</div>", unsafe_allow_html=True)
    cols2 = st.columns(4)
    _stat(cols2[0], total_sets, "Total Sets", "📄")
    _stat(cols2[1], pending_sets, "In Review", "⏳")
    _stat(cols2[2], approved_sets, "Approved", "✅")
    _stat(cols2[3], exported_sets, "Exported", "📤")

    # ── Chapter completeness + Activity (side by side) ─────────────────────────
    left, right = st.columns([3, 2], gap="large")

    with left:
        st.markdown("<div class='section-label' style='margin-top:1.5rem;'>Chapter Completeness</div>",
                    unsafe_allow_html=True)
        completeness: dict[int, dict[str, int]] = {}
        for ch, bl in qs_raw:
            completeness.setdefault(ch, {"L2": 0, "L3": 0})
            completeness[ch][bl] = completeness[ch].get(bl, 0) + 1

        if completeness:
            import pandas as pd
            unit_map = {1: [1, 2], 2: [3, 4, 5], 3: [6, 7]}
            rows = []
            for unit, chapters in unit_map.items():
                for ch in chapters:
                    l2 = completeness.get(ch, {}).get("L2", 0)
                    l3 = completeness.get(ch, {}).get("L3", 0)
                    rows.append({
                        "Unit": f"Unit {unit}",
                        "Ch": ch,
                        "L2": l2,
                        "L3": l3,
                        "L2 ✓": "✅" if l2 >= 10 else f"⚠ {l2}/10",
                        "L3 ✓": "✅" if l3 >= 10 else f"⚠ {l3}/10",
                        "Status": "✅ Ready" if l2 >= 10 and l3 >= 10 else "⚠ Incomplete",
                    })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.markdown("""
            <div class='apple-card' style='text-align:center; padding: 2.5rem;'>
                <div style='font-size:2rem; margin-bottom:0.75rem;'>📭</div>
                <div style='font-weight:600; color:#1d1d1f; margin-bottom:0.3rem;'>No question bank yet</div>
                <div style='font-size:0.85rem; color:#86868b;'>Upload a question bank to get started</div>
            </div>
            """, unsafe_allow_html=True)

    with right:
        st.markdown("<div class='section-label' style='margin-top:1.5rem;'>Recent Activity</div>",
                    unsafe_allow_html=True)
        if logs:
            action_icons = {
                "GENERATE": "⚡", "APPROVE": "✅", "REJECT": "❌",
                "EXPORT": "📤", "SAVE_DRAFT": "💾", "IMPORT": "📥",
            }
            rows_html = ""
            for log in logs:
                ts = log["timestamp"].strftime("%b %d, %H:%M") if log["timestamp"] else "—"
                action = log["action"]
                icon = next((v for k, v in action_icons.items() if k in action.upper()), "•")
                set_id = f" · {log['paper_set_id']}" if log["paper_set_id"] else ""
                rows_html += f"""
                <div class="activity-row">
                    <span style="font-size:1rem;">{icon}</span>
                    <span class="activity-action">{action.replace('_', ' ').title()}{set_id}</span>
                    <span class="activity-time">{ts}</span>
                </div>"""
            st.markdown(f"<div class='apple-card' style='padding:0.75rem 1.25rem;'>{rows_html}</div>",
                        unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class='apple-card' style='text-align:center; padding: 2rem;'>
                <div style='font-size:1.5rem; margin-bottom:0.5rem;'>🕐</div>
                <div style='font-size:0.85rem; color:#86868b;'>No activity yet</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Quick start ────────────────────────────────────────────────────────────
    st.markdown("<div class='section-label' style='margin-top:1.5rem;'>Quick Actions</div>",
                unsafe_allow_html=True)
    qa_cols = st.columns(4)

    with qa_cols[0]:
        if st.button("📋  Upload Question Bank", use_container_width=True, type="secondary"):
            st.session_state.current_page = "question_bank"
            st.rerun()

    with qa_cols[1]:
        if st.button("📖  Upload Lesson Plan", use_container_width=True, type="secondary"):
            st.session_state.current_page = "lesson_plan"
            st.rerun()

    with qa_cols[2]:
        if st.button("⚡  Generate Paper", use_container_width=True, type="primary"):
            st.session_state.current_page = "paper_generator"
            st.rerun()

    with qa_cols[3]:
        try:
            from services.pdf_service import generate_dashboard_pdf
            comp: dict[int, dict[str, int]] = {}
            for ch, bl in qs_raw:
                comp.setdefault(ch, {"L2": 0, "L3": 0})
                comp[ch][bl] = comp[ch].get(bl, 0) + 1
            unit_map2 = {1: [1, 2], 2: [3, 4, 5], 3: [6, 7]}
            completeness_rows = []
            for unit, chapters in unit_map2.items():
                for ch in chapters:
                    l2 = comp.get(ch, {}).get("L2", 0)
                    l3 = comp.get(ch, {}).get("L3", 0)
                    completeness_rows.append({
                        "Unit": f"Unit {unit}", "Chapter": ch,
                        "L2": l2, "L3": l3, "Total": l2 + l3,
                        "Ready": "✅ Complete" if l2 >= 10 and l3 >= 10 else "❌ Incomplete",
                    })
            pdf_bytes = generate_dashboard_pdf(
                total_questions=total_questions, l2_count=l2_count, l3_count=l3_count,
                total_sets=total_sets, pending_sets=pending_sets,
                approved_sets=approved_sets, exported_sets=exported_sets,
                completeness_rows=completeness_rows,
            )
            st.download_button(
                "📄  Export Summary",
                data=pdf_bytes,
                file_name=f"dashboard_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception:
            if st.button("📄  Export Summary", use_container_width=True, type="secondary", disabled=True):
                pass


def _stat(col, value, label: str, icon: str):
    with col:
        st.markdown(f"""
        <div class="stat-card">
            <div class="metric-icon">{icon}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-label">{label}</div>
        </div>
        """, unsafe_allow_html=True)
