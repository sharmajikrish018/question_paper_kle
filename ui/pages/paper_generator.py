"""
ui/pages/paper_generator.py
Paper Generator page — the core generation workflow.
"""

import streamlit as st
from config.settings import get_settings
from models.enums import ExamType
from agents.coordinator import CoordinatorAgent, GenerationRequest
from repositories.settings_repo import SettingsRepository

settings = get_settings()


def render():
    st.markdown("## ⚡ Paper Generator")
    st.markdown(
        "<div class='confidential-banner'>⚠️ Generated papers are confidential academic documents</div>",
        unsafe_allow_html=True,
    )

    settings_repo = SettingsRepository()
    course_structure = settings_repo.get("course_structure", {})
    chapters = course_structure.get("chapters", [])
    chapter_options = {
        ch["chapter_number"]: f"Ch {ch['chapter_number']}: {ch['title']}"
        for ch in chapters
    } if chapters else {i: f"Chapter {i}" for i in range(1, 8)}

    # ── Configuration panel ───────────────────────────────────────────────────
    with st.form("generator_form"):
        st.markdown("### 1️⃣ Examination Type")
        exam_type_str = st.selectbox(
            "Select examination type",
            ["Minor / Internal Examination", "End-Semester Examination"],
        )
        is_minor = exam_type_str.startswith("Minor")
        exam_type = ExamType.MINOR if is_minor else ExamType.END_SEM

        st.markdown("### 2️⃣ Number of Sets")
        num_sets = st.slider(
            "Number of paper sets to generate",
            min_value=1, max_value=settings.max_paper_sets, value=1,
        )

        st.markdown("### 3️⃣ Chapter Selection")
        if is_minor:
            st.markdown("*Select which chapters may appear in the Minor paper.*")
            selected_chapters = st.multiselect(
                "Select chapters",
                options=list(chapter_options.keys()),
                format_func=lambda x: chapter_options[x],
                default=list(chapter_options.keys())[:3],
            )
        else:
            st.markdown("*End-Semester papers use all chapters from all units.*")
            selected_chapters = list(chapter_options.keys())

        st.markdown("### 4️⃣ Bloom Level Distribution")
        col1, col2 = st.columns(2)
        with col1:
            l2_pct = st.slider("L2 (Understand) %", 0, 100, 50, 5, key="l2_slider")
        with col2:
            l3_pct = 100 - l2_pct
            st.metric("L3 (Apply) %", l3_pct)

        if l2_pct + l3_pct != 100:
            st.error("L2 + L3 must equal 100%")

        st.markdown("### 5️⃣ Advanced Options")
        with st.expander("Advanced Settings"):
            random_seed = st.number_input(
                "Random seed (for reproducibility, 0 = random)",
                min_value=0, max_value=999999, value=0,
            )
            tolerance = st.slider(
                "Bloom allocation tolerance (%)",
                min_value=1, max_value=20, value=5,
            )
            academic_year = st.text_input(
                "Academic Year", value="2024-25"
            )
            department = st.text_input(
                "Department", value="Computer Science & Engineering"
            )
            exclude_used = st.checkbox(
                "Exclude previously used questions",
                value=True,
                help="Prevent questions used in past papers from being selected",
            )

        st.markdown("### 6️⃣ Blueprint Preview")
        _show_blueprint_preview(is_minor, l2_pct, l3_pct, num_sets)

        st.markdown("---")
        confirmed = st.checkbox(
            "✅ I confirm the blueprint above is correct and wish to proceed",
        )

        submitted = st.form_submit_button("🚀 Generate Question Paper(s)", type="primary",
                                           use_container_width=True)

    if submitted:
        if not confirmed:
            st.error("Please confirm the blueprint before generating.")
            return
        if not selected_chapters and is_minor:
            st.error("Please select at least one chapter.")
            return

        seed = random_seed if random_seed > 0 else None
        lesson_plan_text = settings_repo.get("lesson_plan_text", "")
        unit_chapter_map = _build_unit_chapter_map(chapters)

        request = GenerationRequest(
            exam_type=exam_type,
            num_sets=num_sets,
            l2_percent=l2_pct,
            l3_percent=l3_pct,
            selected_chapters=selected_chapters,
            random_seed=seed,
            tolerance_percent=tolerance,
            academic_year=academic_year,
            department=department,
            lesson_plan_text=lesson_plan_text,
            unit_chapter_map=unit_chapter_map,
            exclude_used_question_ids=exclude_used,
        )

        with st.spinner(f"🔄 Generating {num_sets} paper set(s)..."):
            try:
                coordinator = CoordinatorAgent()
                result = coordinator.generate(request)
            except Exception as exc:
                st.error(f"Generation failed: {exc}")
                if settings.debug:
                    st.exception(exc)
                return

        # Persist result so it stays visible across reruns
        st.session_state["last_generation"] = result
        st.session_state["last_generation_done"] = True

    # ── Display generation result (persists across reruns) ────────────────────
    result = st.session_state.get("last_generation")
    if result is not None:
        st.markdown("---")
        if result.success:
            st.success(f"✅ Successfully generated {len(result.complete_paper.sets)} paper set(s)!")

            for i, vr in enumerate(result.validation_reports):
                status_icon = {"PASS": "✅", "PASS_WITH_WARNINGS": "⚠️", "FAIL": "❌"}.get(
                    vr.status.value if hasattr(vr.status, "value") else vr.status, "?"
                )
                st.markdown(
                    f"{status_icon} **{vr.set_id}**: "
                    f"Bank={vr.source_bank_count} AI={vr.source_ai_count} "
                    f"L2={vr.bloom_l2_count} L3={vr.bloom_l3_count}"
                )

            if result.errors:
                st.markdown("#### ⚠️ Generation Warnings")
                for err in result.errors:
                    st.warning(err)

            st.info("👉 Go to **Faculty Review** to approve and export the papers.")
            if st.button("Go to Faculty Review →", type="primary", key="goto_review_btn"):
                st.session_state["last_generation"] = None  # clear so it doesn't persist forever
                st.session_state.current_page = "faculty_review"
                st.rerun()
        else:
            st.error("❌ Generation failed.")
            for err in result.errors:
                st.error(err)
            if result.warnings:
                for w in result.warnings:
                    st.warning(w)



def _show_blueprint_preview(is_minor: bool, l2_pct: int, l3_pct: int, num_sets: int):
    """Display a summary of the paper blueprint before generation."""
    if is_minor:
        st.markdown(f"""
        | Parameter | Value |
        |-----------|-------|
        | Exam Type | Minor / Internal Examination |
        | Duration | 75 minutes |
        | Total Attempted Marks | 40 |
        | Total Printed Questions | 6 |
        | Bank Questions | 4 (66.67% — nearest feasible to 70%) |
        | AI Questions | 2 (33.33% — nearest feasible to 30%) |
        | L2 Questions | {round(6 * l2_pct / 100)} |
        | L3 Questions | {6 - round(6 * l2_pct / 100)} |
        | Sets | {num_sets} |
        | Choice Instruction | Answer any TWO full questions |
        """)
        st.caption(
            "Note: 4 bank + 2 AI is the nearest feasible integer allocation to 70:30 "
            "(actual: 66.67%/33.33%). This is clearly documented and not claimed as exact 70:30."
        )
    else:
        l2_q = round(16 * l2_pct / 100)
        l3_q = 16 - l2_q
        st.markdown(f"""
        | Parameter | Value |
        |-----------|-------|
        | Exam Type | End-Semester Examination |
        | Duration | 180 minutes |
        | Total Attempted Marks | 100 |
        | Total Printed Questions | 16 |
        | Bank Questions | 11 (68.75% — nearest feasible to 70%) |
        | AI Questions | 5 (31.25% — nearest feasible to 30%) |
        | L2 Questions | {l2_q} |
        | L3 Questions | {l3_q} |
        | Sets | {num_sets} |
        | Unit 1 | 3 questions × 2 parts, answer any 2 (40 marks) |
        | Unit 2 | 3 questions × 2 parts, answer any 2 (40 marks) |
        | Unit 3 | 2 questions × 2 parts, answer any 1 (20 marks) |
        """)
        st.caption(
            "Note: 11 bank + 5 AI is the nearest feasible integer allocation to 70:30 "
            "(actual: 68.75%/31.25%). This is clearly documented."
        )


def _build_unit_chapter_map(chapters: list[dict]) -> dict:
    """Build {unit_number: [{chapter_number, title}]} map."""
    ucm = {}
    for ch in chapters:
        u = ch.get("unit_number", 1)
        ucm.setdefault(u, []).append(ch)
    return ucm
