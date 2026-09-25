"""
ui/pages/faculty_review.py
Faculty review page with per-question actions and paper approval workflow.
"""

import json
import streamlit as st
from datetime import datetime
from pathlib import Path

from config.settings import get_settings
from models.enums import PaperSetStatus, ApprovalStatus, ExamType
from repositories.database import get_session, PaperSetDB, PaperQuestionDB
from repositories.paper_repo import PaperRepository
from repositories.audit_repo import AuditRepository
from agents.coordinator import CoordinatorAgent
from agents.export_agent import ExportAgent, ExportError
from agents.validation_agent import ValidationAgent
from services.file_service import FileService
from models.enums import FileCategory

settings = get_settings()
paper_repo = PaperRepository()
audit_repo = AuditRepository()


def render():
    st.markdown("## 👩‍🏫 Faculty Review")
    st.markdown(
        "<div class='confidential-banner'>⚠️ For faculty use only — Do not distribute</div>",
        unsafe_allow_html=True,
    )

    # Load generated sets from session or DB
    with get_session() as session:
        sets = (
            session.query(PaperSetDB)
            .order_by(PaperSetDB.generated_at.desc())
            .limit(20)
            .all()
        )
        # Collect basic info (avoid detached session issues)
        sets_info = [
            {
                "set_id": s.set_id,
                "exam_type": s.exam_type,
                "status": s.status,
                "generated_at": s.generated_at,
                "validation_status": s.validation_status,
                "faculty_notes": s.faculty_notes,
            }
            for s in sets
        ]

    if not sets_info:
        st.info("No paper sets generated yet. Go to ⚡ Paper Generator to create papers.")
        return

    # Tab per set
    set_ids = [s["set_id"] for s in sets_info]
    tabs = st.tabs(set_ids)

    for i, (tab, set_info) in enumerate(zip(tabs, sets_info)):
        with tab:
            _render_set_review(set_info)


def _render_set_review(set_info: dict):
    set_id = set_info["set_id"]
    status = set_info["status"]
    exam_type = set_info["exam_type"]
    val_status = set_info["validation_status"] or "—"

    # Status header
    status_colors = {
        "GENERATED": "#1d4ed8",
        "UNDER_REVIEW": "#b45309",
        "CHANGES_REQUESTED": "#7f1d1d",
        "APPROVED": "#065f46",
        "EXPORTED": "#374151",
    }
    color = status_colors.get(status, "#374151")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown(f"""
        <div style='background:{color}; color:white; padding:0.5rem 1rem;
                    border-radius:8px; display:inline-block; font-weight:600;'>
            {set_id} — {status}
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"**Exam:** {exam_type}")
    with col3:
        gen_at = set_info.get("generated_at")
        st.markdown(f"**Generated:** {gen_at.strftime('%Y-%m-%d %H:%M') if gen_at else '—'}")

    st.markdown(f"**Validation Status:** {val_status}")

    # Draft watermark if not approved
    if status not in ("APPROVED", "EXPORTED"):
        st.markdown(
            "<div class='draft-watermark'>⚠️ DRAFT — NOT APPROVED — DO NOT DISTRIBUTE</div>",
            unsafe_allow_html=True,
        )

    # Load questions
    with get_session() as session:
        pqs = (
            session.query(PaperQuestionDB)
            .filter(PaperQuestionDB.paper_set_id == set_id)
            .order_by(PaperQuestionDB.main_question_number, PaperQuestionDB.part)
            .all()
        )
        pqs_data = [
            {
                "id": pq.id,
                "slot_id": pq.slot_id,
                "main_q": pq.main_question_number,
                "part": pq.part,
                "unit_number": pq.unit_number,
                "chapter_number": pq.chapter_number,
                "chapter_name": pq.chapter_name,
                "question_text": pq.question_text,
                "bloom_level": pq.bloom_level,
                "marks": pq.marks,
                "source": pq.source,
                "approval_status": pq.approval_status,
                "question_id": pq.question_id,
                "generated_id": pq.generated_id,
                "bloom_justification": pq.bloom_justification,
                "similarity_status": pq.similarity_status,
            }
            for pq in pqs
        ]

    if not pqs_data:
        st.info("No questions found for this set.")
        return

    st.markdown(f"**{len(pqs_data)} questions in this paper**")
    st.markdown("---")

    # Render each question
    current_main = None
    for pq in pqs_data:
        if pq["main_q"] != current_main:
            current_main = pq["main_q"]
            unit_lbl = f"(Unit {pq['unit_number']})" if exam_type == "END_SEM" else ""
            st.markdown(f"#### Q{pq['main_q']} {unit_lbl}")

        _render_question_card(pq, set_id, status)

    st.markdown("---")

    # Paper-level actions
    _render_paper_actions(set_id, status, exam_type, pqs_data)


def _render_question_card(pq: dict, set_id: str, paper_status: str):
    slot_id = pq["slot_id"]
    source = pq["source"]
    bloom = pq["bloom_level"]
    approval = pq["approval_status"]

    # Source badge
    src_badge = (
        "<span class='badge badge-bank'>QUESTION BANK</span>"
        if source == "QUESTION_BANK"
        else "<span class='badge badge-ai'>AI GENERATED</span>"
    )
    bloom_badge = (
        f"<span class='badge badge-l2'>{bloom}</span>"
        if bloom == "L2"
        else f"<span class='badge badge-l3'>{bloom}</span>"
    )
    approval_class = {
        "APPROVED": "badge-approved",
        "PENDING": "badge-pending",
        "REJECTED": "badge-rejected",
    }.get(approval, "badge-draft")
    approval_badge = f"<span class='badge {approval_class}'>{approval}</span>"
    sim_badge = ""
    if pq.get("similarity_status") and pq["similarity_status"] != "OK":
        sim_badge = f"<span class='badge' style='background:#7f1d1d; color:white;'>⚠️ {pq['similarity_status']}</span>"

    with st.container():
        st.markdown(
            f"""
            <div class='question-card'>
            <b>({pq['part']})</b>&nbsp;
            {src_badge} {bloom_badge}
            <span class='badge' style='background:#374151; color:white;'>
                Ch {pq['chapter_number']}
            </span>
            <span class='badge' style='background:#374151; color:white;'>10 MARKS</span>
            {approval_badge} {sim_badge}
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(f"**{pq['question_text']}**")

        if pq.get("bloom_justification"):
            with st.expander("Bloom Justification"):
                st.markdown(pq["bloom_justification"])

        if paper_status not in ("APPROVED", "EXPORTED"):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button(
                    "✅ Approve", key=f"approve_{set_id}_{slot_id}",
                    disabled=(approval == "APPROVED"),
                ):
                    _update_question_status(set_id, slot_id, "APPROVED")
            with col2:
                if st.button("❌ Reject", key=f"reject_{set_id}_{slot_id}"):
                    _update_question_status(set_id, slot_id, "REJECTED")
            with col3:
                if st.button("✏️ Edit", key=f"edit_{set_id}_{slot_id}"):
                    st.session_state[f"editing_{set_id}_{slot_id}"] = True
            with col4:
                if source == "AI_GENERATED":
                    if st.button("🔄 Regenerate", key=f"regen_{set_id}_{slot_id}"):
                        st.info("Regenerate: Click Save Draft and re-generate from Paper Generator.")

            # Edit mode
            if st.session_state.get(f"editing_{set_id}_{slot_id}"):
                new_text = st.text_area(
                    "Edit question text",
                    value=pq["question_text"],
                    key=f"text_{set_id}_{slot_id}",
                )
                if st.button("💾 Save Edit", key=f"save_{set_id}_{slot_id}"):
                    _update_question_text(set_id, slot_id, new_text)
                    st.session_state[f"editing_{set_id}_{slot_id}"] = False

        st.markdown("")


def _render_paper_actions(set_id: str, status: str, exam_type: str, pqs_data: list):
    st.markdown("### Paper Actions")
    col1, col2, col3, col4 = st.columns(4)

    all_approved = all(pq["approval_status"] == "APPROVED" for pq in pqs_data)
    pending_count = sum(1 for pq in pqs_data if pq["approval_status"] == "PENDING")

    with col1:
        if st.button("💾 Save Draft", use_container_width=True):
            paper_repo.update_set_status(set_id, "UNDER_REVIEW")
            audit_repo.log("SAVE_DRAFT", paper_set_id=set_id)
            st.toast("✅ Draft saved!", icon="💾")
            st.rerun()

    with col2:
        if st.button("📋 Request Changes", use_container_width=True):
            paper_repo.update_set_status(set_id, "CHANGES_REQUESTED")
            audit_repo.log("CHANGES_REQUESTED", paper_set_id=set_id)
            st.info("Marked for changes")
            st.rerun()

    with col3:
        approve_disabled = not all_approved or status in ("APPROVED", "EXPORTED")
        if st.button(
            "✅ Approve Set" + (f" ({pending_count} pending)" if pending_count else ""),
            type="primary",
            use_container_width=True,
            disabled=approve_disabled,
        ):
            coordinator = CoordinatorAgent()
            coordinator.approve_set(set_id)
            st.toast(f"✅ {set_id} APPROVED!", icon="✅")
            st.rerun()
        if pending_count > 0:
            st.caption(f"⚠️ {pending_count} question(s) still pending approval")

    with col4:
        if status in ("APPROVED", "EXPORTED"):
            try:
                final_docx = _generate_docx_bytes(set_id, exam_type, status, pqs_data, is_draft=False)
                st.download_button(
                    "📤 Final DOCX",
                    data=final_docx,
                    file_name=f"{set_id}_FINAL.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    key=f"final_docx_action_{set_id}",
                )
            except Exception as e:
                st.caption(f"DOCX error: {e}")
        else:
            st.button("📤 Final DOCX", disabled=True, use_container_width=True, key=f"final_docx_dis_{set_id}")
            st.caption("Approve set first")

    st.markdown("---")
    st.markdown("**⬇ Downloads**")
    dl1, dl2, dl3, dl4 = st.columns(4)

    pset_obj = _build_paper_set_from_db(set_id, exam_type, status, pqs_data)

    with dl1:
        # Draft DOCX — generated in-memory so download_button works immediately
        try:
            docx_bytes = _generate_docx_bytes(set_id, exam_type, status, pqs_data, is_draft=True)
            st.download_button(
                "📥 Draft DOCX",
                data=docx_bytes,
                file_name=f"DRAFT_{set_id}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key=f"draft_docx_{set_id}",
            )
        except Exception as e:
            st.caption(f"DOCX error: {e}")

    with dl2:
        try:
            from services.pdf_service import generate_paper_pdf
            if pset_obj:
                pdf_bytes = generate_paper_pdf(pset_obj, is_draft=True)
                st.download_button(
                    "📄 Draft PDF",
                    data=pdf_bytes,
                    file_name=f"DRAFT_{set_id}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"draft_pdf_{set_id}",
                )
        except Exception as e:
            st.caption(f"PDF error: {e}")

    with dl3:
        if status in ("APPROVED", "EXPORTED"):
            try:
                from services.pdf_service import generate_paper_pdf
                if pset_obj:
                    pdf_bytes = generate_paper_pdf(pset_obj, is_draft=False)
                    st.download_button(
                        "✅ Final PDF",
                        data=pdf_bytes,
                        file_name=f"{set_id}_FINAL.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"final_pdf_{set_id}",
                    )
            except Exception as e:
                st.caption(f"PDF error: {e}")
        else:
            st.button("✅ Final PDF", disabled=True, use_container_width=True, key=f"final_pdf_dis_{set_id}")
            st.caption("Approve set first")

    with dl4:
        try:
            from services.pdf_service import generate_scheme_pdf
            if pset_obj:
                is_draft_scheme = status not in ("APPROVED", "EXPORTED")
                scheme_bytes = generate_scheme_pdf(pset_obj, is_draft=is_draft_scheme)
                st.download_button(
                    "📋 Scheme PDF",
                    data=scheme_bytes,
                    file_name=f"SCHEME_{set_id}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"scheme_pdf_{set_id}",
                )
        except Exception as e:
            st.caption(f"Scheme error: {e}")


def _update_question_status(set_id: str, slot_id: str, status: str):
    paper_repo.update_question_status(set_id, slot_id, status)
    audit_repo.log(
        f"QUESTION_{status}",
        paper_set_id=set_id,
        details={"slot_id": slot_id},
    )
    st.toast(f"Question {slot_id} → {status}", icon="✅")
    st.rerun()


def _update_question_text(set_id: str, slot_id: str, new_text: str):
    paper_repo.update_question_status(set_id, slot_id, "PENDING", new_text=new_text)
    audit_repo.log(
        "QUESTION_EDITED",
        paper_set_id=set_id,
        details={"slot_id": slot_id, "new_text_preview": new_text[:80]},
    )
    st.toast("✅ Question text updated. Approval reset to PENDING.", icon="✅")
    st.rerun()


def _do_export(set_id: str, exam_type: str, is_draft: bool):
    """Perform DOCX export."""
    from models.paper import PaperSet, PaperQuestion
    from models.validation import ValidationReport, ValidationFinding
    from models.enums import ValidationStatus

    # Build minimal paper set object for export
    with get_session() as session:
        db_set = session.query(PaperSetDB).filter(PaperSetDB.set_id == set_id).first()
        pqs_db = (
            session.query(PaperQuestionDB)
            .filter(PaperQuestionDB.paper_set_id == set_id)
            .order_by(PaperQuestionDB.main_question_number, PaperQuestionDB.part)
            .all()
        )
        status = db_set.status if db_set else "GENERATED"
        val_findings = json.loads(db_set.validation_findings or "[]") if db_set else []

        pqs = []
        for pq in pqs_db:
            from models.paper import PaperQuestion as PQ
            pqs.append(PQ(
                slot_id=pq.slot_id,
                main_question_number=pq.main_question_number,
                part=pq.part,
                unit_number=pq.unit_number,
                chapter_number=pq.chapter_number,
                chapter_name=pq.chapter_name,
                question_text=pq.question_text,
                bloom_level=pq.bloom_level,
                marks=pq.marks,
                source=pq.source,
                approval_status=pq.approval_status,
                question_id=pq.question_id,
                generated_id=pq.generated_id,
            ))

    paper_set = PaperSet(
        set_id=set_id,
        set_index=0,
        exam_type=exam_type,
        status=status,
        questions=pqs,
    )

    report = ValidationReport(
        set_id=set_id,
        exam_type=exam_type,
        status=ValidationStatus.PASS,
        findings=[],
    )

    file_service = FileService()
    template_path = file_service.get_active_template()

    try:
        export_agent = ExportAgent()
        out_path = export_agent.export_paper(
            paper_set=paper_set,
            validation_report=report,
            template_path=template_path,
            is_draft=is_draft,
        )
        with open(out_path, "rb") as f:
            st.download_button(
                f"📥 Download {'Draft' if is_draft else 'Final'} Paper ({set_id}.docx)",
                f.read(),
                file_name=out_path.name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        if not is_draft:
            st.success(f"✅ Final paper exported: {out_path.name}")
    except ExportError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"Export error: {exc}")
        if settings.debug:
            st.exception(exc)


def _build_paper_set_from_db(set_id: str, exam_type: str, status: str, pqs_data: list):
    """Reconstruct a PaperSet domain object from pre-fetched question dicts."""
    try:
        from models.paper import PaperSet, PaperQuestion
        pqs = []
        for pq in pqs_data:
            pqs.append(PaperQuestion(
                slot_id=pq["slot_id"],
                main_question_number=pq["main_q"],
                part=pq["part"],
                unit_number=pq["unit_number"],
                chapter_number=pq["chapter_number"],
                chapter_name=pq["chapter_name"],
                question_text=pq["question_text"],
                bloom_level=pq["bloom_level"],
                marks=pq["marks"],
                source=pq["source"],
                approval_status=pq["approval_status"],
                question_id=pq.get("question_id"),
                generated_id=pq.get("generated_id"),
                bloom_justification=pq.get("bloom_justification"),
                similarity_status=pq.get("similarity_status"),
            ))
        return PaperSet(
            set_id=set_id,
            set_index=0,
            exam_type=exam_type,
            status=status,
            questions=pqs,
        )
    except Exception as exc:
        logger.warning(f"Could not build PaperSet from DB: {exc}")
        return None


def _generate_docx_bytes(set_id: str, exam_type: str, status: str, pqs_data: list, is_draft: bool) -> bytes:
    """Generate DOCX in-memory and return raw bytes for st.download_button."""
    import io
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from models.enums import ExamType

    DRAFT_WATERMARK = "DRAFT — NOT APPROVED — FOR REVIEW ONLY"
    is_minor = exam_type in ("MINOR", ExamType.MINOR)
    duration = "75 minutes" if is_minor else "180 minutes"
    max_marks = "40" if is_minor else "100"
    exam_label = "Minor / Internal Examination" if is_minor else "End-Semester Examination"

    doc = Document()

    if is_draft:
        p = doc.add_paragraph(DRAFT_WATERMARK)
        p.runs[0].bold = True
        p.runs[0].font.color.rgb = RGBColor(0xFF, 0x00, 0x00)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    dept_p = doc.add_paragraph("Department of Computer Science & Engineering (AI)")
    dept_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    title_p = doc.add_paragraph(f"Generative AI — {exam_label}")
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_p.runs[0].bold = True

    meta_p = doc.add_paragraph(
        f"Set: {set_id}   |   Time: {duration}   |   Max Marks: {max_marks}"
    )
    meta_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    instr = (
        "Answer any TWO complete questions. Each complete question carries 20 marks."
        if is_minor else
        "Unit 1 & 2: Answer any TWO complete questions from each unit. "
        "Unit 3: Answer any ONE complete question. Each complete question carries 20 marks."
    )
    doc.add_paragraph(instr)
    doc.add_paragraph("")

    sorted_pqs = sorted(pqs_data, key=lambda q: (q["main_q"], q["part"]))
    current_main = None
    for pq in sorted_pqs:
        if pq["main_q"] != current_main:
            current_main = pq["main_q"]
            h = doc.add_paragraph(f"Q{pq['main_q']}.")
            h.runs[0].bold = True
        para = doc.add_paragraph()
        part_run = para.add_run(f"  ({pq['part']}) ")
        part_run.bold = True
        para.add_run(pq["question_text"])
        marks_run = para.add_run(f"  [{pq['marks']} Marks]")
        marks_run.bold = True

    if is_minor:
        doc.add_paragraph("\nAnswer any TWO full questions.")
    else:
        doc.add_paragraph("\n[See unit-wise instructions above]")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
