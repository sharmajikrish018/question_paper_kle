"""api/routers/papers.py — Generation, review & export endpoints."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import io
from api.schemas.papers import (
    GenerateRequest, GenerateResponse, PaperSetOut, PaperListItem,
    PaperQuestionOut, QuestionStatusUpdate, ValidationReportOut, ValidationFindingOut,
)
from repositories.database import get_session, PaperSetDB, PaperQuestionDB
from repositories.settings_repo import SettingsRepository

router = APIRouter(prefix="/papers", tags=["papers"])


@router.get("", response_model=list[PaperListItem])
def list_papers():
    with get_session() as session:
        rows = session.query(PaperSetDB).order_by(PaperSetDB.generated_at.desc()).limit(50).all()
        return [
            PaperListItem(
                set_id=r.set_id,
                exam_type=r.exam_type,
                status=r.status,
                created_at=r.generated_at,
                question_count=session.query(PaperQuestionDB)
                    .filter(PaperQuestionDB.paper_set_id == r.set_id).count(),
            )
            for r in rows
        ]


@router.post("/generate", response_model=GenerateResponse)
def generate_papers(body: GenerateRequest):
    from agents.coordinator import CoordinatorAgent, GenerationRequest
    from models.enums import ExamType
    from repositories.settings_repo import SettingsRepository

    repo = SettingsRepository()
    lesson_plan_text = repo.get("lesson_plan_text", "")
    course_structure = repo.get("course_structure", {})
    chapters = course_structure.get("chapters", [])

    ucm: dict = {}
    for ch in chapters:
        u = ch.get("unit_number", 1)
        ucm.setdefault(u, []).append(ch)

    exam_type = ExamType.MINOR if body.exam_type == "MINOR" else ExamType.END_SEM
    request = GenerationRequest(
        exam_type=exam_type,
        num_sets=body.num_sets,
        l2_percent=body.l2_percent,
        l3_percent=body.l3_percent,
        selected_chapters=body.selected_chapters,
        random_seed=body.random_seed,
        tolerance_percent=body.tolerance_percent,
        academic_year=body.academic_year,
        department=body.department,
        lesson_plan_text=lesson_plan_text,
        unit_chapter_map=ucm,
        exclude_used_question_ids=body.exclude_used_question_ids,
    )

    coordinator = CoordinatorAgent()
    result = coordinator.generate(request)

    set_ids = [s.set_id for s in result.complete_paper.sets] if result.success else []
    reports = [_vr_out(vr) for vr in result.validation_reports]

    return GenerateResponse(
        success=result.success,
        paper_set_ids=set_ids,
        validation_reports=reports,
        errors=result.errors or [],
        warnings=result.warnings or [],
    )


@router.get("/{set_id}", response_model=PaperSetOut)
def get_paper(set_id: str):
    with get_session() as session:
        row = session.query(PaperSetDB).filter(PaperSetDB.set_id == set_id).first()
        if not row:
            raise HTTPException(404, "Paper set not found")
        qs = session.query(PaperQuestionDB)\
            .filter(PaperQuestionDB.paper_set_id == set_id).all()
        questions = [_pq_out(q) for q in qs]
        return PaperSetOut(
            set_id=row.set_id,
            exam_type=row.exam_type,
            status=row.status,
            created_at=row.generated_at,
            question_count=len(questions),
            questions=questions,
        )


@router.patch("/{set_id}/questions/{slot_id}", response_model=PaperQuestionOut)
def update_question_status(set_id: str, slot_id: str, body: QuestionStatusUpdate):
    from repositories.paper_repo import PaperRepository
    from repositories.audit_repo import AuditRepository

    paper_repo = PaperRepository()
    audit_repo = AuditRepository()

    if body.edited_text:
        paper_repo.update_question_text(set_id, slot_id, body.edited_text)
        audit_repo.log("EDIT_QUESTION", paper_set_id=set_id,
                       details={"slot_id": slot_id})

    paper_repo.update_question_status(set_id, slot_id, body.status)
    audit_repo.log(f"QUESTION_{body.status}", paper_set_id=set_id,
                   details={"slot_id": slot_id})

    with get_session() as session:
        q = session.query(PaperQuestionDB).filter(
            PaperQuestionDB.paper_set_id == set_id,
            PaperQuestionDB.slot_id == slot_id
        ).first()
        if not q:
            raise HTTPException(404, "Question slot not found")
        return _pq_out(q)


@router.post("/{set_id}/approve")
def approve_paper(set_id: str):
    from agents.coordinator import CoordinatorAgent
    from repositories.audit_repo import AuditRepository
    coordinator = CoordinatorAgent()
    coordinator.approve_set(set_id)
    AuditRepository().log("APPROVE_SET", paper_set_id=set_id)
    return {"ok": True, "set_id": set_id, "status": "APPROVED"}


@router.get("/{set_id}/validation", response_model=ValidationReportOut)
def get_validation(set_id: str):
    from repositories.paper_repo import PaperRepository
    from agents.validation_agent import ValidationAgent
    from agents.blueprint_agent import BlueprintAgent
    from models.enums import ExamType

    paper_repo = PaperRepository()
    paper_set = paper_repo.get_paper_set(set_id)
    if not paper_set:
        raise HTTPException(404, "Paper set not found")

    blueprint_agent = BlueprintAgent()
    exam_type = ExamType.MINOR if paper_set.exam_type in ("MINOR", ExamType.MINOR) else ExamType.END_SEM
    blueprint = blueprint_agent.build(exam_type)
    report = ValidationAgent().validate(paper_set, blueprint)
    return _vr_out(report)


@router.get("/{set_id}/export/docx")
def export_docx(set_id: str):
    from agents.export_agent import ExportAgent

    paper_set = _build_paper_set(set_id)
    if not paper_set:
        raise HTTPException(404, "Paper set not found")

    export_agent = ExportAgent()
    docx_bytes = export_agent.export_docx_bytes(paper_set)
    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{set_id}.docx"'},
    )


@router.get("/{set_id}/export/pdf")
def export_pdf(set_id: str):
    from services.pdf_service import generate_paper_pdf

    paper_set = _build_paper_set(set_id)
    if not paper_set:
        raise HTTPException(404, "Paper set not found")

    pdf_bytes = generate_paper_pdf(paper_set)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{set_id}.pdf"'},
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_paper_set(set_id: str):
    """Reconstruct a PaperSet domain object from DB rows for export."""
    from repositories.paper_repo import PaperRepository
    from models.paper import PaperSet, PaperQuestion
    from models.enums import ExamType, PaperSetStatus, BloomLevel, QuestionSource, ApprovalStatus

    paper_repo = PaperRepository()
    meta = paper_repo.get_set(set_id)
    if not meta:
        return None

    q_rows = paper_repo.get_questions_for_set(set_id)
    questions = []
    for i, r in enumerate(q_rows):
        # Derive main_question_number and part from slot_id (e.g. "Q1a") or fallback
        slot = r.get("slot_id", "")
        try:
            import re
            m = re.match(r'Q(\d+)([a-z])', slot, re.IGNORECASE)
            main_q = int(m.group(1)) if m else (i // 2 + 1)
            part = m.group(2).lower() if m else ("a" if i % 2 == 0 else "b")
        except Exception:
            main_q = i // 2 + 1
            part = "a" if i % 2 == 0 else "b"

        bloom_raw = r.get("bloom_level", "L2")
        source_raw = r.get("source", "QUESTION_BANK")
        status_raw = r.get("approval_status", "PENDING")

        try:
            bloom = BloomLevel(bloom_raw)
        except ValueError:
            bloom = BloomLevel.L2
        try:
            source = QuestionSource(source_raw)
        except ValueError:
            source = QuestionSource.QUESTION_BANK
        try:
            approval = ApprovalStatus(status_raw)
        except ValueError:
            approval = ApprovalStatus.PENDING

        questions.append(PaperQuestion(
            slot_id=slot or f"Q{main_q}{part}",
            main_question_number=main_q,
            part=part,
            unit_number=r.get("unit_number") or 1,
            chapter_number=r.get("chapter_number") or 0,
            chapter_name=r.get("chapter_name") or "",
            question_text=r.get("question_text") or "",
            bloom_level=bloom,
            marks=r.get("marks") or 10,
            source=source,
            approval_status=approval,
            question_id=r.get("question_id"),
            generated_id=r.get("generated_id"),
        ))

    exam_raw = meta.get("exam_type", "MINOR")
    try:
        exam_type = ExamType(exam_raw)
    except ValueError:
        exam_type = ExamType.MINOR

    status_raw = meta.get("status", "GENERATED")
    try:
        status = PaperSetStatus(status_raw)
    except ValueError:
        status = PaperSetStatus.GENERATED

    return PaperSet(
        set_id=set_id,
        set_index=0,
        exam_type=exam_type,
        status=status,
        questions=questions,
        generated_at=meta.get("generated_at"),
        approved_at=meta.get("approved_at"),
        exported_at=meta.get("exported_at"),
        faculty_notes=meta.get("faculty_notes") or "",
    )

def _pq_out(q) -> PaperQuestionOut:
    return PaperQuestionOut(
        slot_id=q.slot_id,
        question_text=q.question_text,
        bloom_level=q.bloom_level.value if hasattr(q.bloom_level, "value") else q.bloom_level,
        marks=q.marks,
        source=q.source.value if hasattr(q.source, "value") else (q.source or ""),
        chapter_number=q.chapter_number or 0,
        chapter_name=q.chapter_name or "",
        unit_number=q.unit_number or 1,
        approval_status=q.approval_status.value if hasattr(q.approval_status, "value") else (q.approval_status or "PENDING"),
        model_answer=getattr(q, "model_answer", None),
    )


def _vr_out(vr) -> ValidationReportOut:
    findings = []
    for f in (vr.findings or []):
        findings.append(ValidationFindingOut(
            rule_id=f.rule_id,
            severity=f.severity,
            message=f.message,
            expected=str(f.expected) if f.expected is not None else None,
            actual=str(f.actual) if f.actual is not None else None,
            suggested_action=f.suggested_action,
            affected_questions=f.affected_questions or [],
        ))
    status = vr.status.value if hasattr(vr.status, "value") else str(vr.status)
    exam_type = vr.exam_type.value if hasattr(vr.exam_type, "value") else str(vr.exam_type)
    return ValidationReportOut(
        set_id=vr.set_id,
        exam_type=exam_type,
        status=status,
        findings=findings,
        source_bank_count=vr.source_bank_count,
        source_ai_count=vr.source_ai_count,
        source_bank_percent=vr.source_bank_percent,
        source_ai_percent=vr.source_ai_percent,
        bloom_l2_count=vr.bloom_l2_count,
        bloom_l3_count=vr.bloom_l3_count,
        bloom_l2_percent=vr.bloom_l2_percent,
        bloom_l3_percent=vr.bloom_l3_percent,
        total_printed=vr.total_printed,
        marks_total=vr.marks_total,
    )
