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
from agents.export_agent import ExportAgent, ExportError, build_meaningful_filename
from agents.validation_agent import ValidationAgent
from services.file_service import FileService
from models.enums import FileCategory

settings = get_settings()
paper_repo = PaperRepository()
audit_repo = AuditRepository()


def render():
    from repositories.subject_repo import SubjectRepository
    subj_repo = SubjectRepository()
    active_subject = subj_repo.get_active_subject()
    if not active_subject:
        st.info("👉 Please select a subject to continue.")
        return

    subject_id = active_subject["subject_id"]

    st.markdown("## 👩‍🏫 Faculty Review")
    st.markdown(
        "<div class='confidential-banner'>⚠️ For faculty use only — Do not distribute</div>",
        unsafe_allow_html=True,
    )

    # Load generated sets from session or DB
    with get_session() as session:
        sets = (
            session.query(PaperSetDB)
            .filter(PaperSetDB.subject_id == subject_id)
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
                "valuation_points": pq.valuation_points,
            }
            for pq in pqs
        ]

    if not pqs_data:
        st.info("No questions found for this set.")
        return

    # Valuation schemes status & missing scheme generator
    missing_val_count = sum(1 for pq in pqs_data if not pq.get("valuation_points"))
    val_status_items = [
        f"{pq['slot_id']} {'✓' if pq.get('valuation_points') else '⚠'}"
        for pq in pqs_data
    ]
    val_status_str = ", ".join(val_status_items)

    v_col1, v_col2 = st.columns([3, 1])
    with v_col1:
        if missing_val_count == 0:
            st.success(f"**Valuation Schemes:** All {len(pqs_data)} questions complete ({val_status_str})")
        else:
            st.warning(f"**Valuation Schemes:** {len(pqs_data) - missing_val_count}/{len(pqs_data)} complete — Missing: {missing_val_count} ({val_status_str})")
    with v_col2:
        if missing_val_count > 0:
            if st.button("⚡ Generate Missing Schemes", key=f"gen_missing_val_{set_id}", use_container_width=True):
                _generate_missing_valuations(set_id, pqs_data)

    # CHANGE 3: Question Paper Layout Preview
    # CHANGE 3: Question Paper Layout Preview
    with st.expander("👁️ Question Paper Layout Preview", expanded=False):
        is_minor = (exam_type == "MINOR")
        if is_minor:
            header_title = "Model Question Paper for Minor Examination (ISA-I)"
            duration_str = "60 mins"
            max_marks_str = "30"
            note_str = "Note: Answer any two full questions. Each full question carries equal marks."
        else:
            header_title = "Model Question Paper for End Semester Assessment (ESA)"
            duration_str = "180 mins"
            max_marks_str = "100"
            note_str = "Note: Answer any two full questions from Unit 1 & 2, and one from Unit 3. Each full question carries equal marks."

        from services.pdf_service import _get_sl_no, _get_q_text, _get_marks, _get_co, _get_bl, _get_po, _get_pi_code

        rows_html = ""
        for pq in sorted(pqs_data, key=lambda q: (q["main_q"], q["part"])):
            sl_no = _get_sl_no(pq)
            qt = _get_q_text(pq).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            marks = _get_marks(pq)
            co = _get_co(pq)
            bl = _get_bl(pq)
            po = _get_po(pq)
            pi_code = _get_pi_code(pq)
            rows_html += f"""
            <tr>
                <td style='border:1px solid #000; padding:6px; text-align:center;'>{sl_no}</td>
                <td style='border:1px solid #000; padding:6px; text-align:left;'>{qt}</td>
                <td style='border:1px solid #000; padding:6px; text-align:center;'>{marks}</td>
                <td style='border:1px solid #000; padding:6px; text-align:center;'>{co}</td>
                <td style='border:1px solid #000; padding:6px; text-align:center;'>{bl}</td>
                <td style='border:1px solid #000; padding:6px; text-align:center;'>{po}</td>
                <td style='border:1px solid #000; padding:6px; text-align:center;'>{pi_code}</td>
            </tr>
            """

        st.markdown(f"""
        <div style='background:#ffffff; color:#000000; padding:15px; border:1px solid #94a3b8;'>
            {f"<div style='text-align:center; color:#dc2626; font-weight:bold; margin-bottom:8px;'>DRAFT — NOT APPROVED — FOR REVIEW ONLY</div>" if status not in ("APPROVED", "EXPORTED") else ""}
            <table style='width:100%; border-collapse:collapse; border:1px solid #000; margin-bottom:12px; font-size:0.9rem;'>
                <tr>
                    <td colspan='2' style='border:1px solid #000; padding:8px; text-align:center; font-weight:bold; font-size:1.05rem;'>{header_title}</td>
                </tr>
                <tr>
                    <td style='border:1px solid #000; padding:6px 10px; width:50%;'><b>Course Code:</b> 26ECAC401</td>
                    <td style='border:1px solid #000; padding:6px 10px; width:50%;'><b>Course Title:</b> Agentic AI</td>
                </tr>
                <tr>
                    <td style='border:1px solid #000; padding:6px 10px;'><b>Duration:</b> {duration_str}</td>
                    <td style='border:1px solid #000; padding:6px 10px;'><b>Max. Marks:</b> {max_marks_str}</td>
                </tr>
                <tr>
                    <td colspan='2' style='border:1px solid #000; padding:6px 10px; font-style:italic;'>{note_str}</td>
                </tr>
            </table>
            <table style='width:100%; border-collapse:collapse; border:1px solid #000; font-size:0.85rem;'>
                <thead>
                    <tr style='background:#f8fafc; font-weight:bold; text-align:center;'>
                        <th style='border:1px solid #000; padding:6px; width:7%;'>Sl.No.</th>
                        <th style='border:1px solid #000; padding:6px; width:57%; text-align:left;'>Questions</th>
                        <th style='border:1px solid #000; padding:6px; width:7%;'>Marks</th>
                        <th style='border:1px solid #000; padding:6px; width:7%;'>CO</th>
                        <th style='border:1px solid #000; padding:6px; width:7%;'>BL</th>
                        <th style='border:1px solid #000; padding:6px; width:7%;'>PO</th>
                        <th style='border:1px solid #000; padding:6px; width:8%;'>PI Code</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
        """, unsafe_allow_html=True)

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

    val_has = bool(pq.get("valuation_points"))
    val_badge = (
        "<span class='badge' style='background:#065f46; color:white;'>Scheme ✓</span>"
        if val_has
        else "<span class='badge' style='background:#b45309; color:white;'>Scheme ⚠ Missing</span>"
    )

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
            {val_badge}
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
                is_regen_running = st.session_state.get(f"is_regenerating_{set_id}_{slot_id}", False)
                btn_label = "⏳ Regenerating..." if is_regen_running else "🔄 Regenerate Question"
                if st.button(btn_label, key=f"regen_{set_id}_{slot_id}", disabled=is_regen_running):
                    st.session_state[f"is_regenerating_{set_id}_{slot_id}"] = True
                    _regenerate_question(set_id, pq)
                    st.session_state[f"is_regenerating_{set_id}_{slot_id}"] = False

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


@st.dialog("View Question Paper", width="large")
def _show_view_paper_dialog(set_id: str, exam_type: str, status: str, pqs_data: list):
    pset_obj = _build_paper_set_from_db(set_id, exam_type, status, pqs_data)
    if pset_obj:
        try:
            from services.pdf_service import generate_paper_pdf
            pdf_bytes = generate_paper_pdf(pset_obj, is_draft=(status not in ("APPROVED", "EXPORTED")))
            import base64
            base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="520px" type="application/pdf" style="border:none; border-radius:8px;"></iframe>',
                unsafe_allow_html=True,
            )
        except Exception as exc:
            st.error(f"Could not render PDF preview: {exc}")

    st.markdown("<div style='display:flex; justify-content:center; margin-top:1rem;'>", unsafe_allow_html=True)
    all_dlg_approved = all(pq.get("approval_status") == "APPROVED" for pq in pqs_data) or status in ("APPROVED", "EXPORTED")
    if pset_obj and all_dlg_approved:
        try:
            from services.pdf_service import generate_paper_pdf
            is_draft = (status not in ("APPROVED", "EXPORTED"))
            pdf_bytes = generate_paper_pdf(pset_obj, is_draft=is_draft)
            fn = build_meaningful_filename("Paper", exam_type, set_id, "pdf", is_draft=is_draft)
            st.download_button(
                "📥 Download QP",
                data=pdf_bytes,
                file_name=fn,
                mime="application/pdf",
                type="primary",
                key=f"dlg_dl_qp_btn_{set_id}",
            )
        except Exception:
            pass
    elif pset_obj and not all_dlg_approved:
        st.caption("🔒 Question paper download is locked until all questions are approved by faculty.")
    st.markdown("</div>", unsafe_allow_html=True)


def _render_paper_actions(set_id: str, status: str, exam_type: str, pqs_data: list):
    st.markdown("### Paper Actions")
    col1, col2, col3, col4 = st.columns(4)

    all_approved = all(pq["approval_status"] == "APPROVED" for pq in pqs_data)
    pending_count = sum(1 for pq in pqs_data if pq["approval_status"] == "PENDING")

    is_draft = (status not in ("APPROVED", "EXPORTED"))
    fn_docx = build_meaningful_filename("Paper", exam_type, set_id, "docx", is_draft=is_draft)
    fn_pdf = build_meaningful_filename("Paper", exam_type, set_id, "pdf", is_draft=is_draft)
    fn_scheme_pdf = f"SCHEME_{fn_pdf}"

    with col1:
        if st.button("👁 View Paper", use_container_width=True, key=f"btn_view_paper_{set_id}"):
            _show_view_paper_dialog(set_id, exam_type, status, pqs_data)

    can_download = all_approved or status in ("APPROVED", "EXPORTED")

    with col2:
        if can_download:
            try:
                docx_bytes = _generate_docx_bytes(set_id, exam_type, status, pqs_data, is_draft=is_draft)
                st.download_button(
                    "📥 DOCX",
                    data=docx_bytes,
                    file_name=fn_docx,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    key=f"action_btn_docx_{set_id}",
                )
            except Exception as e:
                st.button("📥 DOCX", disabled=True, use_container_width=True, key=f"action_btn_docx_dis_{set_id}")
        else:
            st.button("🔒 📥 DOCX", disabled=True, use_container_width=True, help="Approve all questions to unlock DOCX download", key=f"action_btn_docx_lock_{set_id}")

    with col3:
        if can_download:
            try:
                pset_obj = _build_paper_set_from_db(set_id, exam_type, status, pqs_data)
                if pset_obj:
                    from services.pdf_service import generate_paper_pdf
                    pdf_bytes = generate_paper_pdf(pset_obj, is_draft=is_draft)
                    st.download_button(
                        "📄 PDF",
                        data=pdf_bytes,
                        file_name=fn_pdf,
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"action_btn_pdf_{set_id}",
                    )
                else:
                    st.button("📄 PDF", disabled=True, use_container_width=True, key=f"action_btn_pdf_dis_{set_id}")
            except Exception as e:
                st.button("📄 PDF", disabled=True, use_container_width=True, key=f"action_btn_pdf_err_{set_id}")
        else:
            st.button("🔒 📄 PDF", disabled=True, use_container_width=True, help="Approve all questions to unlock PDF download", key=f"action_btn_pdf_lock_{set_id}")

    with col4:
        approve_disabled = not all_approved or status in ("APPROVED", "EXPORTED")
        if st.button(
            "Approve All",
            type="primary",
            use_container_width=True,
            disabled=approve_disabled,
            key=f"action_btn_approve_all_{set_id}",
        ):
            coordinator = CoordinatorAgent()
            coordinator.approve_set(set_id)
            st.toast(f"✅ {set_id} APPROVED!", icon="✅")
            st.rerun()
        if pending_count > 0 and status not in ("APPROVED", "EXPORTED"):
            st.caption(f"⚠️ {pending_count} question(s) still pending approval")

    st.markdown("---")
    st.markdown("**⬇ Downloads & Export**")
    dl1, dl2, dl3, dl4 = st.columns(4)

    pset_obj = _build_paper_set_from_db(set_id, exam_type, status, pqs_data)

    with dl1:
        try:
            docx_bytes = _generate_docx_bytes(set_id, exam_type, status, pqs_data, is_draft=True)
            st.download_button(
                "📥 Draft DOCX",
                data=docx_bytes,
                file_name=fn_draft_docx,
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
                    file_name=fn_draft_pdf,
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
                        file_name=fn_final_pdf,
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
                    file_name=fn_scheme_pdf,
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
    from agents.export_agent import _render_tabular_docx

    pset_obj = _build_paper_set_from_db(set_id, exam_type, status, pqs_data)
    doc = Document()
    if pset_obj:
        _render_tabular_docx(doc, pset_obj, is_draft=is_draft, course_name="Agentic AI")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _regenerate_question(set_id: str, pq: dict):
    """Regenerate a single question with identical constraints avoiding old text."""
    st.info(f"Regenerating question {pq['slot_id']} with Ollama...")
    try:
        from services.llm_provider import LLMProvider
        from agents.generation_agent import AIQuestionGenerationAgent
        from models.enums import BloomLevel

        llm = LLMProvider()
        agent = AIQuestionGenerationAgent(llm)

        b_level = BloomLevel.L3 if str(pq["bloom_level"]).endswith("L3") else BloomLevel.L2

        new_q = agent.regenerate_question(
            bloom_level=b_level,
            unit_number=pq["unit_number"],
            chapter_number=pq["chapter_number"],
            chapter_name=pq["chapter_name"],
            old_question_text=pq["question_text"],
        )

        if new_q and new_q.question_text:
            val_json = json.dumps([vp.model_dump() for vp in new_q.valuation_points]) if new_q.valuation_points else None
            with get_session() as session:
                db_pq = session.query(PaperQuestionDB).filter(
                    PaperQuestionDB.paper_set_id == set_id,
                    PaperQuestionDB.slot_id == pq["slot_id"]
                ).first()
                if db_pq:
                    db_pq.question_text = new_q.question_text
                    db_pq.bloom_justification = new_q.bloom_justification
                    db_pq.approval_status = "PENDING"
                    if val_json:
                        db_pq.valuation_points = val_json
                    session.commit()

            audit_repo.log(
                "QUESTION_REGENERATED",
                paper_set_id=set_id,
                details={"slot_id": pq["slot_id"], "old_text": pq["question_text"][:50], "new_text": new_q.question_text[:50]},
            )
            st.toast(f"✅ Question {pq['slot_id']} regenerated!", icon="⚡")
            st.rerun()
        else:
            st.error("Failed to regenerate question.")
    except Exception as exc:
        st.error(f"Regeneration error: {exc}")


def _generate_missing_valuations(set_id: str, pqs_data: list):
    """Generate valuation schemes for any questions missing them."""
    st.info("Generating missing valuation schemes with Ollama...")
    try:
        from services.llm_provider import LLMProvider
        from agents.valuation_agent import ValuationAgent
        from models.paper import PaperQuestion
        from models.enums import BloomLevel, QuestionSource, ApprovalStatus

        llm = LLMProvider()
        val_agent = ValuationAgent(llm)
        count = 0

        for pq in pqs_data:
            if not pq.get("valuation_points"):
                b_level = BloomLevel.L3 if str(pq["bloom_level"]).endswith("L3") else BloomLevel.L2
                src = QuestionSource.QUESTION_BANK if pq["source"] == "QUESTION_BANK" else QuestionSource.AI_GENERATED
                app_str = pq.get("approval_status", "PENDING")
                app = ApprovalStatus.APPROVED if app_str == "APPROVED" else (ApprovalStatus.REJECTED if app_str == "REJECTED" else ApprovalStatus.PENDING)

                pq_obj = PaperQuestion(
                    slot_id=pq["slot_id"],
                    main_question_number=pq["main_q"],
                    part=pq["part"],
                    unit_number=pq["unit_number"],
                    chapter_number=pq["chapter_number"],
                    chapter_name=pq["chapter_name"],
                    question_text=pq["question_text"],
                    bloom_level=b_level,
                    marks=pq["marks"],
                    source=src,
                    approval_status=app,
                    question_id=pq.get("question_id"),
                    generated_id=pq.get("generated_id"),
                )

                scheme = val_agent.generate_scheme(pq_obj)
                if scheme and scheme.valuation_points:
                    val_json = json.dumps([vp.model_dump() for vp in scheme.valuation_points])
                    with get_session() as session:
                        db_pq = session.query(PaperQuestionDB).filter(
                            PaperQuestionDB.paper_set_id == set_id,
                            PaperQuestionDB.slot_id == pq["slot_id"]
                        ).first()
                        if db_pq:
                            db_pq.valuation_points = val_json
                            session.commit()
                    count += 1

        st.toast(f"✅ Generated valuation schemes for {count} question(s)!", icon="✅")
        st.rerun()
    except Exception as exc:
        st.error(f"Valuation generation error: {exc}")
