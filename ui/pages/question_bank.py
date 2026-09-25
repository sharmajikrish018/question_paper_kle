"""
ui/pages/question_bank.py
Question Bank management page.
"""

import io
import json
import streamlit as st
import pandas as pd
from pathlib import Path

from services.file_service import FileService, FileServiceError
from services.question_bank_service import QuestionBankService, ImportResult
from agents.question_bank_agent import QuestionBankAgent
from models.enums import FileCategory
from repositories.database import get_session, QuestionDB
from config.settings import get_settings

settings = get_settings()


def render():
    st.markdown("## 📋 Question Bank")
    tab1, tab2, tab3, tab4 = st.tabs([
        "📤 Upload & Import", "📊 Browse & Filter", "🔍 Completeness", "✏️ Edit"
    ])

    with tab1:
        _render_upload()
    with tab2:
        _render_browse()
    with tab3:
        _render_completeness()
    with tab4:
        _render_edit()


def _render_upload():
    st.markdown("### Upload Question Bank File")

    # Format guidance
    fmt_tab1, fmt_tab2, fmt_tab3 = st.tabs(["📊 Excel / CSV / JSON", "📄 PDF", "📝 DOCX"])

    with fmt_tab1:
        st.markdown("""
**Required columns:** `question_id`, `unit_number`, `chapter_number`,
`chapter_name`, `question_text`, `bloom_level` (L2/L3), `marks` (10)

**Optional:** `model_answer`, `difficulty`

Download the sample template below for the exact format.
        """)

    with fmt_tab2:
        st.markdown("""
**PDF is supported in two layouts:**

**Layout 1 — Table PDF** *(preferred)*
Create a table in Word/Google Docs, export as PDF. Columns must include:
`question_text`, `bloom_level`, `unit_number`, `chapter_number`, `chapter_name`

**Layout 2 — Text PDF** *(freeform)*
Number questions starting with `Q1.`, `Q2.` etc. Include metadata inline:
```
Unit 1 — Chapter 3: Introduction to GANs

Q1. [L2] Explain the generator-discriminator interaction in a GAN. [10 Marks]
Answer: A GAN consists of two networks...

Q2. [L3] Compare VAE and GAN architectures. [10 Marks]
```

> ⚠️ **Tip:** For best results use a table-based PDF or the Excel template.
> The system auto-detects format and falls back to text parsing.
        """)

    with fmt_tab3:
        st.markdown("""
**DOCX is supported in two layouts:**

**Layout 1 — Table DOCX** *(preferred)*
A Word table where the first row is the header row with column names.

**Layout 2 — Paragraph DOCX**
Numbered questions in the same `Q1.`, `Q2.` format as PDF text mode.
        """)

    st.markdown("---")

    # Sample download
    if st.button("📥 Download Sample Excel Template"):
        sample_path = settings.sample_files_dir / "sample_question_bank.xlsx"
        if sample_path.exists():
            with open(sample_path, "rb") as f:
                st.download_button(
                    "Download sample_question_bank.xlsx",
                    f.read(),
                    "sample_question_bank.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
        else:
            st.warning("Sample file not found. Run setup.ps1 to create sample files.")

    uploaded = st.file_uploader(
        "Upload question bank file",
        type=["xlsx", "xls", "csv", "json", "pdf", "docx"],
        key="qb_upload",
        help="Maximum 50 MB. Supports Excel, CSV, JSON, PDF (table or freeform), DOCX (table or paragraph).",
    )


    if uploaded:
        file_bytes = uploaded.read()
        file_service = FileService()

        col1, col2 = st.columns(2)
        with col1:
            st.metric("File size", f"{len(file_bytes) / 1024:.1f} KB")
        with col2:
            st.metric("File name", uploaded.name)

        # Save uploaded file
        try:
            saved_path = file_service.validate_and_save(
                file_bytes, uploaded.name, FileCategory.QUESTION_BANK
            )
            st.success(f"File saved: {saved_path.name}")
        except FileServiceError as exc:
            st.error(f"File validation failed: {exc}")
            return

        # Parse and validate
        with st.spinner("Parsing and validating..."):
            service = QuestionBankService()
            try:
                result: ImportResult = service.load_from_file(saved_path)
            except Exception as exc:
                st.error(f"Parse error: {exc}")
                return

        # Show import preview
        st.markdown(f"""
        #### Import Preview
        - **Rows processed:** {result.total_rows}
        - **Valid questions:** {result.imported}
        - **Fatal errors:** {sum(1 for e in result.errors if e.is_fatal)}
        - **Warnings:** {len(result.warnings)}
        """)

        # Show errors
        if result.errors:
            with st.expander(f"⚠️ {len(result.errors)} Validation Issues", expanded=True):
                for err in result.errors:
                    icon = "🔴" if err.is_fatal else "🟡"
                    st.markdown(
                        f"{icon} **Row {err.row}** `{err.field}`: {err.message}"
                    )

        if result.warnings:
            with st.expander(f"📋 {len(result.warnings)} Warnings"):
                for w in result.warnings:
                    st.markdown(f"🟡 {w}")

        # Show question preview
        if result.questions:
            st.markdown("#### Question Preview (first 10)")
            preview_data = []
            for q in result.questions[:10]:
                preview_data.append({
                    "ID": q.question_id,
                    "Unit": q.unit_number,
                    "Chapter": q.chapter_number,
                    "Bloom": q.bloom_level.value if hasattr(q.bloom_level, "value") else q.bloom_level,
                    "Marks": q.marks,
                    "Text (80 chars)": q.question_text[:80] + "...",
                })
            st.dataframe(pd.DataFrame(preview_data), use_container_width=True, hide_index=True)

        # Import button
        if result.imported > 0 and not result.has_fatal_errors:
            if st.button(f"✅ Import {result.imported} Questions to Database", type="primary"):
                agent = QuestionBankAgent()
                count = agent.import_to_db(result)
                st.success(f"✅ Imported {count} questions successfully!")
                st.rerun()
        elif result.has_fatal_errors:
            st.error("Cannot import: fix fatal errors first. Edit the file and re-upload.")


def _render_browse():
    st.markdown("### Browse Question Bank")

    with get_session() as session:
        all_qs = session.query(QuestionDB).all()
        # Detach from session
        qs_data = [
            {
                "ID": q.question_id,
                "Unit": q.unit_number,
                "Chapter": q.chapter_number,
                "Ch Name": q.chapter_name[:30],
                "Bloom": q.bloom_level,
                "Marks": q.marks,
                "Difficulty": q.difficulty,
                "Source": q.source,
                "Status": q.approval_status,
                "Used": q.usage_count or 0,
                "Text": q.question_text[:100] + "..." if len(q.question_text) > 100 else q.question_text,
            }
            for q in all_qs
        ]

    if not qs_data:
        st.info("No questions in database. Upload a question bank first.")
        return

    df = pd.DataFrame(qs_data)

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        bloom_filter = st.selectbox("Bloom Level", ["All", "L2", "L3"])
    with col2:
        unit_filter = st.selectbox("Unit", ["All", "1", "2", "3"])
    with col3:
        search = st.text_input("Search text", placeholder="Search question text...")

    filtered = df.copy()
    if bloom_filter != "All":
        filtered = filtered[filtered["Bloom"] == bloom_filter]
    if unit_filter != "All":
        filtered = filtered[filtered["Unit"] == int(unit_filter)]
    if search:
        filtered = filtered[filtered["Text"].str.contains(search, case=False, na=False)]

    st.markdown(f"**{len(filtered)} questions** (of {len(df)} total)")
    st.dataframe(filtered, use_container_width=True, hide_index=True, height=400)

    # Downloads
    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        if st.button("📥 Download as CSV"):
            csv_data = df.to_csv(index=False)
            st.download_button(
                "Download CSV",
                csv_data.encode(),
                "normalized_question_bank.csv",
                mime="text/csv",
            )
    with dl_col2:
        try:
            from services.pdf_service import generate_question_bank_pdf
            pdf_bytes = generate_question_bank_pdf(qs_data)
            st.download_button(
                "📄 Download as PDF",
                data=pdf_bytes,
                file_name="question_bank.pdf",
                mime="application/pdf",
            )
        except Exception as e:
            st.caption(f"PDF error: {e}")



def _render_completeness():
    st.markdown("### Chapter Completeness Matrix")
    st.markdown("""
    Each chapter should have **10 L2** and **10 L3** questions (20 total).
    For 7 chapters: **140 questions** expected.
    """)

    agent = QuestionBankAgent()
    report = agent.get_completeness_report()

    if not report:
        st.info("No questions in database yet.")
        return

    rows = []
    unit_map = {1: [1, 2, 3], 2: [4, 5, 6], 3: [7]}
    total_complete = 0
    for unit, chapters in unit_map.items():
        for ch in chapters:
            data = report.get(ch, {"l2_count": 0, "l3_count": 0, "total": 0})
            l2 = data.get("l2_count", 0)
            l3 = data.get("l3_count", 0)
            complete = l2 >= 10 and l3 >= 10
            if complete:
                total_complete += 1
            rows.append({
                "Unit": f"Unit {unit}",
                "Chapter": ch,
                "L2": l2,
                "L3": l3,
                "Total": l2 + l3,
                "L2 ✓": "✅" if l2 >= 10 else f"⚠️ Need {10-l2} more",
                "L3 ✓": "✅" if l3 >= 10 else f"⚠️ Need {10-l3} more",
                "Ready": "✅ Complete" if complete else "❌ Incomplete",
            })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    pct = total_complete / 7 * 100
    st.progress(pct / 100)
    st.markdown(f"**{total_complete}/7 chapters complete** ({pct:.0f}%)")

    if total_complete < 7:
        st.warning(
            "⚠️ Incomplete question bank. Generation may fail for chapters "
            "with insufficient questions. Add more questions or use a smaller "
            "chapter selection."
        )


def _render_edit():
    st.markdown("### Edit Question")
    st.info("Select a question ID to edit its metadata. Original import is preserved.")

    with get_session() as session:
        ids = [q.question_id for q in session.query(QuestionDB.question_id).all()]

    if not ids:
        st.info("No questions to edit.")
        return

    selected_id = st.selectbox("Select Question ID", ids)

    with get_session() as session:
        q = session.query(QuestionDB).filter(QuestionDB.question_id == selected_id).first()
        if not q:
            st.error("Question not found")
            return
        # Copy values for editing
        q_text = q.question_text
        q_bloom = q.bloom_level
        q_answer = q.model_answer or ""
        q_status = q.approval_status

    st.markdown(f"**Question ID:** `{selected_id}`")

    new_text = st.text_area("Question Text", value=q_text, height=120)
    new_bloom = st.selectbox("Bloom Level", ["L2", "L3"], index=0 if q_bloom == "L2" else 1)
    new_answer = st.text_area("Model Answer", value=q_answer, height=100)
    new_status = st.selectbox(
        "Approval Status",
        ["APPROVED", "PENDING", "UNDER_REVIEW", "REJECTED"],
        index=["APPROVED", "PENDING", "UNDER_REVIEW", "REJECTED"].index(q_status)
        if q_status in ["APPROVED", "PENDING", "UNDER_REVIEW", "REJECTED"] else 0,
    )

    if st.button("💾 Save Changes", type="primary"):
        with get_session() as session:
            q = session.query(QuestionDB).filter(QuestionDB.question_id == selected_id).first()
            if q:
                q.question_text = new_text
                q.bloom_level = new_bloom
                q.model_answer = new_answer if new_answer else None
                q.approval_status = new_status
        st.success("✅ Question updated successfully")
        st.rerun()
