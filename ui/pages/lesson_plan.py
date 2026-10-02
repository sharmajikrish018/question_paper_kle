"""
ui/pages/lesson_plan.py
Lesson Plan upload and chapter extraction page.
"""

import streamlit as st
from pathlib import Path

from agents.intake_agent import CourseIntakeAgent, LessonPlanExtraction, ChapterInfo
from services.file_service import FileService, FileServiceError
from models.enums import FileCategory
from config.settings import get_settings
from repositories.settings_repo import SettingsRepository

settings = get_settings()


def render():
    from repositories.subject_repo import SubjectRepository
    active_subject = SubjectRepository().get_active_subject()
    if not active_subject:
        st.info("👉 Please select a subject to continue.")
        return

    st.markdown("## 📖 Lesson Plan")
    tab1, tab2 = st.tabs(["📤 Upload & Extract", "✏️ Edit Structure"])

    with tab1:
        _render_upload()
    with tab2:
        _render_edit()


def _render_upload():
    st.markdown("### Upload Lesson Plan")
    st.markdown("""
    **Supported formats:** `.pdf`, `.docx`, `.txt`, `.md`, `.xlsx`

    The system will extract chapter names and topic coverage using AI.
    You can manually correct the extraction afterward.
    """)

    # Show existing files
    file_service = FileService()
    existing = file_service.list_files(FileCategory.LESSON_PLAN)
    if existing:
        st.markdown("**Currently uploaded lesson plans:**")
        for f in existing:
            cols = st.columns([4, 1])
            with cols[0]:
                st.markdown(f"📄 `{f.name}` ({f.stat().st_size / 1024:.1f} KB)")
            with cols[1]:
                if st.button("🔍 Re-Extract", key=f"extract_{f.name}"):
                    # Clear cache so a fresh LLM call is made
                    cache_key = f"lp_extracted_{f.name}"
                    st.session_state.pop(cache_key, None)
                    _do_extraction(f)

    st.markdown("---")

    uploaded = st.file_uploader(
        "Upload lesson plan",
        type=["pdf", "docx", "txt", "md", "xlsx"],
        key="lp_upload",
    )

    if uploaded:
        file_bytes = uploaded.read()
        try:
            saved_path = file_service.validate_and_save(
                file_bytes, uploaded.name, FileCategory.LESSON_PLAN
            )
            st.success(f"Saved: {saved_path.name}")
            _do_extraction(saved_path)
        except FileServiceError as exc:
            st.error(str(exc))


def _do_extraction(path: Path):
    """Run extraction — result is cached in session_state so Save doesn't re-trigger it."""
    cache_key = f"lp_extracted_{path.name}"

    # Use cached result if available (avoids re-running LLM on every rerun)
    if cache_key not in st.session_state:
        with st.spinner("🤖 Extracting course structure with AI + embeddings…"):
            agent = CourseIntakeAgent()
            result = agent.extract_lesson_plan(path)
        st.session_state[cache_key] = result
        # Keep session state for Edit tab
        st.session_state["extracted_chapters"] = result.chapters
        st.session_state["lesson_plan_text"] = result.raw_text
    else:
        result = st.session_state[cache_key]

    st.markdown(f"### Extraction Results: `{path.name}`")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Chapters detected", len(result.chapters))
    with col2:
        conf_pct = int(result.confidence * 100)
        st.metric("Extraction confidence", f"{conf_pct}%")

    if result.warnings:
        for w in result.warnings:
            st.warning(w)

    if result.chapters:
        st.markdown("#### Detected Chapters")
        import pandas as pd
        rows = [
            {
                "Unit": ch.unit_number,
                "Chapter #": ch.chapter_number,
                "Title": ch.title,
                "Topics": ", ".join(ch.topics[:3]) if ch.topics else "(none extracted)",
            }
            for ch in result.chapters
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        if result.confidence < 0.7:
            st.warning(
                "⚠️ Extraction confidence is low. Please verify and correct the "
                "chapter structure in the Edit tab."
            )
        else:
            st.success("✅ Extraction complete. Review the chapters and click Save.")

        if st.button("💾 Save Extracted Structure", type="primary"):
            _save_structure(result.chapters, result.raw_text)
            # Clear cache after saving so next upload starts fresh
            st.session_state.pop(cache_key, None)
    else:
        st.warning("No chapters detected. Please edit manually in the Edit tab.")

    # Show raw text preview
    if result.raw_text:
        with st.expander("📄 Raw Extracted Text (first 2000 chars)"):
            st.text(result.raw_text[:2000])


def _render_edit():
    st.markdown("### Edit Course Structure")
    st.markdown(
        "Map chapters to units. The system will use this to assign questions correctly."
    )

    settings_repo = SettingsRepository()
    saved = settings_repo.get("course_structure", None)

    if "extracted_chapters" in st.session_state:
        chapters = st.session_state["extracted_chapters"]
    elif saved:
        # Reconstruct from saved
        chapters = [ChapterInfo(**ch) for ch in saved.get("chapters", [])]
    else:
        chapters = [
            ChapterInfo(unit_number=1, chapter_number=i, title=f"Chapter {i}")
            for i in range(1, 8)
        ]

    st.markdown("#### Chapter — Unit Mapping")
    edited_chapters = []
    for ch in chapters:
        with st.container():
            cols = st.columns([1, 1, 3])
            with cols[0]:
                unit_num = st.number_input(
                    "Unit", min_value=1, max_value=3,
                    value=ch.unit_number,
                    key=f"unit_{ch.chapter_number}",
                )
            with cols[1]:
                ch_num = st.number_input(
                    "Chapter #", min_value=1, max_value=20,
                    value=ch.chapter_number,
                    key=f"ch_{ch.chapter_number}",
                )
            with cols[2]:
                title = st.text_input(
                    "Chapter Title",
                    value=ch.title,
                    key=f"title_{ch.chapter_number}",
                )
            edited_chapters.append(
                ChapterInfo(unit_number=unit_num, chapter_number=ch_num, title=title)
            )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ Add Chapter"):
            max_ch = max((c.chapter_number for c in chapters), default=0) + 1
            st.session_state["extracted_chapters"] = chapters + [
                ChapterInfo(unit_number=1, chapter_number=max_ch, title=f"Chapter {max_ch}")
            ]
            st.rerun()

    with col2:
        if st.button("💾 Save Structure", type="primary"):
            _save_structure(
                edited_chapters,
                st.session_state.get("lesson_plan_text", ""),
            )


def _save_structure(chapters: list[ChapterInfo], raw_text: str = "") -> None:
    settings_repo = SettingsRepository()
    settings_repo.set("course_structure", {
        "chapters": [
            {
                "unit_number": ch.unit_number,
                "chapter_number": ch.chapter_number,
                "title": ch.title,
                "topics": ch.topics,
            }
            for ch in chapters
        ],
        "raw_text_length": len(raw_text),
    })
    if raw_text:
        settings_repo.set("lesson_plan_text", raw_text[:50000])

    st.toast(f"✅ Saved structure with {len(chapters)} chapters!", icon="✅")
    st.rerun()
