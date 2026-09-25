"""
ui/pages/validation_reports.py
Validation reports display page.
"""

import json
import streamlit as st
import pandas as pd
from repositories.database import get_session, PaperSetDB
from config.settings import get_settings

settings = get_settings()


def render():
    st.markdown("## ✅ Validation Reports")

    with get_session() as session:
        sets = (
            session.query(PaperSetDB)
            .order_by(PaperSetDB.generated_at.desc())
            .limit(20)
            .all()
        )
        sets_data = [
            {
                "set_id": s.set_id,
                "exam_type": s.exam_type,
                "status": s.status,
                "validation_status": s.validation_status or "—",
                "generated_at": s.generated_at,
                "findings_json": s.validation_findings or "[]",
            }
            for s in sets
        ]

    if not sets_data:
        st.info("No paper sets found. Generate papers first.")
        return

    # Summary table
    summary = pd.DataFrame([
        {
            "Set ID": s["set_id"],
            "Exam Type": s["exam_type"],
            "Status": s["status"],
            "Validation": s["validation_status"],
            "Generated": s["generated_at"].strftime("%Y-%m-%d %H:%M") if s["generated_at"] else "—",
        }
        for s in sets_data
    ])
    st.dataframe(summary, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Detailed view
    selected = st.selectbox(
        "Select set for detailed report",
        [s["set_id"] for s in sets_data],
    )
    set_detail = next(s for s in sets_data if s["set_id"] == selected)

    try:
        findings = json.loads(set_detail["findings_json"])
    except Exception:
        findings = []

    val_status = set_detail["validation_status"]
    status_icon = {"PASS": "✅", "PASS_WITH_WARNINGS": "⚠️", "FAIL": "❌"}.get(val_status, "❓")
    st.markdown(f"### {status_icon} {selected} — {val_status}")

    if not findings:
        if val_status == "PASS":
            st.success("All validation rules passed.")
        else:
            st.info("No detailed findings recorded.")
        return

    errors = [f for f in findings if f.get("severity") == "ERROR"]
    warnings = [f for f in findings if f.get("severity") == "WARNING"]

    col1, col2 = st.columns(2)
    with col1:
        st.metric("🔴 Errors", len(errors))
    with col2:
        st.metric("🟡 Warnings", len(warnings))

    for finding in findings:
        severity = finding.get("severity", "INFO")
        icon = "🔴" if severity == "ERROR" else "🟡"
        rule_id = finding.get("rule_id", "—")
        message = finding.get("message", "")
        expected = finding.get("expected")
        actual = finding.get("actual")
        action = finding.get("suggested_action", "")
        affected = finding.get("affected_questions", [])

        with st.expander(f"{icon} [{rule_id}] {message}"):
            if expected is not None:
                st.markdown(f"**Expected:** `{expected}`")
            if actual is not None:
                st.markdown(f"**Actual:** `{actual}`")
            if affected:
                st.markdown(f"**Affected slots:** {', '.join(str(a) for a in affected)}")
            if action:
                st.markdown(f"**Action:** {action}")

    # Download buttons
    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        if st.button("📥 Download Validation Report (JSON)"):
            report_json = json.dumps(
                {
                    "set_id": selected,
                    "validation_status": val_status,
                    "findings": findings,
                },
                indent=2,
            )
            st.download_button(
                "Download JSON",
                report_json.encode(),
                f"validation_{selected}.json",
                mime="application/json",
            )
    with dl_col2:
        try:
            from services.pdf_service import generate_validation_report_pdf
            pdf_bytes = generate_validation_report_pdf(
                set_id=selected,
                exam_type=set_detail["exam_type"],
                validation_status=val_status,
                findings=findings,
            )
            st.download_button(
                "📄 Download Validation Report (PDF)",
                data=pdf_bytes,
                file_name=f"validation_{selected}.pdf",
                mime="application/pdf",
            )
        except Exception as e:
            st.caption(f"PDF error: {e}")


    # Distribution charts
    _render_distribution_charts(set_detail)


def _render_distribution_charts(set_info: dict):
    """Show source and Bloom distribution for the selected set."""
    from repositories.database import PaperQuestionDB

    with get_session() as session:
        pqs = (
            session.query(PaperQuestionDB)
            .filter(PaperQuestionDB.paper_set_id == set_info["set_id"])
            .all()
        )
        pqs_data = [{"source": pq.source, "bloom": pq.bloom_level} for pq in pqs]

    if not pqs_data:
        return

    df = pd.DataFrame(pqs_data)

    st.markdown("### Distribution Summary")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Source Distribution**")
        src_counts = df["source"].value_counts()
        total = len(df)
        for src, cnt in src_counts.items():
            pct = cnt / total * 100
            label = "Bank" if src == "QUESTION_BANK" else "AI Generated"
            target_pct = 68.75 if set_info["exam_type"] == "END_SEM" else 66.67
            target = target_pct if label == "Bank" else (100 - target_pct)
            diff = abs(pct - target)
            icon = "✅" if diff <= 5 else "⚠️"
            st.markdown(
                f"{icon} **{label}:** {cnt}/{total} ({pct:.1f}%) "
                f"— Target ~{target:.1f}%"
            )

    with col2:
        st.markdown("**Bloom Distribution**")
        bloom_counts = df["bloom"].value_counts()
        for bloom, cnt in bloom_counts.items():
            pct = cnt / total * 100
            target_pct = 50  # default
            diff = abs(pct - target_pct)
            icon = "✅" if diff <= 5 else "⚠️"
            st.markdown(f"{icon} **{bloom}:** {cnt}/{total} ({pct:.1f}%)")
