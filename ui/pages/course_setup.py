"""
ui/pages/course_setup.py
Course setup page for managing course metadata and unit/chapter structure.
"""

import streamlit as st
from repositories.database import get_session, CourseDB, UnitDB, ChapterDB
from repositories.settings_repo import SettingsRepository


def render():
    st.markdown("## 📚 Course Setup")
    st.markdown("Configure the course details and unit/chapter structure.")

    settings_repo = SettingsRepository()

    tab1, tab2 = st.tabs(["🎓 Course Info", "🗂️ Unit Structure"])

    with tab1:
        _render_course_info(settings_repo)
    with tab2:
        _render_unit_structure(settings_repo)


def _render_course_info(settings_repo):
    st.markdown("### Course Information")

    saved = settings_repo.get("course_info", {})

    with st.form("course_info_form"):
        course_name = st.text_input(
            "Course Name", value=saved.get("course_name", "Generative AI")
        )
        course_code = st.text_input(
            "Course Code", value=saved.get("course_code", "GEN-AI-601")
        )
        department = st.text_input(
            "Department", value=saved.get("department", "Computer Science & Engineering")
        )
        semester = st.text_input(
            "Semester", value=saved.get("semester", "VI")
        )
        academic_year = st.text_input(
            "Academic Year", value=saved.get("academic_year", "2024-25")
        )

        submitted = st.form_submit_button("💾 Save Course Info", type="primary")

    if submitted:
        settings_repo.set("course_info", {
            "course_name": course_name,
            "course_code": course_code,
            "department": department,
            "semester": semester,
            "academic_year": academic_year,
        })
        st.toast("✅ Course information saved!", icon="✅")


def _render_unit_structure(settings_repo):
    st.markdown("### Unit and Chapter Structure")
    st.markdown("""
    The Generative AI course has **3 units** and **7 chapters**:
    - **Unit 1:** 3 chapters
    - **Unit 2:** 3 chapters
    - **Unit 3:** 1 chapter

    Chapter names are extracted from the lesson plan.
    Confirm them here before generating papers.
    """)

    course_structure = settings_repo.get("course_structure", {})
    chapters = course_structure.get("chapters", [])

    if not chapters:
        st.warning(
            "No chapter structure found. Upload a lesson plan first, or add chapters manually below."
        )
        # Default 7 chapters
        chapters = [
            {"unit_number": 1, "chapter_number": i, "title": f"Chapter {i}", "topics": []}
            for i in range(1, 8)
        ]
        chapters[3]["unit_number"] = 2
        chapters[4]["unit_number"] = 2
        chapters[5]["unit_number"] = 2
        chapters[6]["unit_number"] = 3

    # Display and edit
    st.markdown("#### Confirm Chapter–Unit Mapping")

    import pandas as pd
    df_data = [
        {
            "Unit": ch.get("unit_number", 1),
            "Chapter #": ch.get("chapter_number", 1),
            "Title": ch.get("title", ""),
        }
        for ch in chapters
    ]

    edited = st.data_editor(
        pd.DataFrame(df_data),
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Unit": st.column_config.NumberColumn(min_value=1, max_value=3, step=1),
            "Chapter #": st.column_config.NumberColumn(min_value=1, max_value=20, step=1),
            "Title": st.column_config.TextColumn(max_chars=200),
        },
    )

    if st.button("💾 Save Unit Structure", type="primary"):
        updated_chapters = [
            {
                "unit_number": int(row["Unit"]),
                "chapter_number": int(row["Chapter #"]),
                "title": str(row["Title"]),
                "topics": [],
            }
            for _, row in edited.iterrows()
            if row["Title"]
        ]
        settings_repo.set("course_structure", {
            "chapters": updated_chapters,
            "raw_text_length": course_structure.get("raw_text_length", 0),
        })
        st.toast(f"✅ Saved {len(updated_chapters)} chapters!", icon="✅")
        st.rerun()
