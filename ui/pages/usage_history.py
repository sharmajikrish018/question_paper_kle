"""
ui/pages/usage_history.py
Question usage history page.
"""

import streamlit as st
import pandas as pd
from repositories.database import get_session, UsageHistoryDB


def render():
    from repositories.subject_repo import SubjectRepository
    active_subject = SubjectRepository().get_active_subject()
    if not active_subject:
        st.info("👉 Please select a subject to continue.")
        return

    st.markdown("## 📊 Usage History")
    st.markdown("Track which questions have been used in previously generated papers.")

    with get_session() as session:
        history_data = [
            {
                "Question ID": h.question_id,
                "Source": h.source,
                "Paper Set": h.paper_set_id,
                "Exam Type": h.exam_type,
                "Academic Year": h.academic_year or "—",
                "Used At": h.used_at.strftime("%Y-%m-%d %H:%M") if h.used_at else "—",
            }
            for h in (
                session.query(UsageHistoryDB)
                .order_by(UsageHistoryDB.used_at.desc())
                .all()
            )
        ]

    if not history_data:
        st.info("No usage history yet. Generate and export papers to record usage.")

        st.markdown("### 📌 How question usage is recorded")
        st.markdown("""
        - **Draft export** records usage in the usage history table
        - **Final export** also marks the question with `last_used_at`
        - Usage history helps you avoid reusing questions across exam cycles
        - Cross-set uniqueness within a single request is enforced automatically
        """)
        return

    df = pd.DataFrame(history_data)

    # Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Usage Records", len(df))
    with col2:
        st.metric("Unique Questions Used", df["Question ID"].nunique())
    with col3:
        bank_count = len(df[df["Source"] == "QUESTION_BANK"])
        st.metric("Bank Questions Used", bank_count)

    st.markdown("---")

    # Filters
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        source_filter = st.selectbox("Filter by Source", ["All", "QUESTION_BANK", "AI_GENERATED"])
    with col_b:
        exam_filter = st.selectbox("Filter by Exam Type", ["All", "MINOR", "END_SEM"])
    with col_c:
        year_opts = ["All"] + sorted(df["Academic Year"].unique().tolist())
        year_filter = st.selectbox("Filter by Academic Year", year_opts)

    if source_filter != "All":
        df = df[df["Source"] == source_filter]
    if exam_filter != "All":
        df = df[df["Exam Type"] == exam_filter]
    if year_filter != "All":
        df = df[df["Academic Year"] == year_filter]

    st.dataframe(df, use_container_width=True, hide_index=True)

    # Downloads
    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        csv_data = df.to_csv(index=False)
        st.download_button(
            "📥 Download CSV",
            data=csv_data.encode(),
            file_name="usage_history.csv",
            mime="text/csv",
        )
    with dl_col2:
        try:
            from services.pdf_service import generate_usage_history_pdf
            pdf_bytes = generate_usage_history_pdf(df.to_dict("records"))
            st.download_button(
                "📄 Download PDF",
                data=pdf_bytes,
                file_name="usage_history.pdf",
                mime="application/pdf",
            )
        except Exception as e:
            st.caption(f"PDF error: {e}")

    if len(df) > 0:
        freq = df["Question ID"].value_counts().reset_index()
        freq.columns = ["Question ID", "Times Used"]
        st.markdown("### Most Frequently Used")
        st.dataframe(freq.head(15), use_container_width=True, hide_index=True)
