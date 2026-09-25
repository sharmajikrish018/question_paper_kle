"""api/routers/questions.py — Question bank endpoints."""
from __future__ import annotations
import tempfile, shutil
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from api.schemas.questions import QuestionOut, QuestionUpdateIn, ImportResultOut, CompletenessOut
from repositories.question_repo import QuestionRepository
from repositories.database import get_session, QuestionDB

router = APIRouter(prefix="/questions", tags=["questions"])


@router.get("", response_model=list[QuestionOut])
def list_questions(
    chapter: int | None = Query(None),
    bloom: str | None = Query(None),
    limit: int = Query(200, le=500),
    offset: int = Query(0),
):
    repo = QuestionRepository()
    questions = repo.get_all(chapter_number=chapter, bloom_level=bloom,
                             limit=limit, offset=offset)
    return [_q_out(q) for q in questions]


@router.get("/completeness", response_model=list[CompletenessOut])
def get_completeness(expected_chapters: int = 7):
    repo = QuestionRepository()
    counts = repo.count_by_chapter_bloom()
    result = []
    for ch in range(1, expected_chapters + 1):
        l2 = counts.get((ch, "L2"), 0)
        l3 = counts.get((ch, "L3"), 0)
        result.append(CompletenessOut(
            chapter_number=ch, l2_count=l2, l3_count=l3,
            total=l2+l3, l2_ok=l2==10, l3_ok=l3==10, complete=l2==10 and l3==10,
        ))
    return result


@router.post("/import", response_model=ImportResultOut)
async def import_question_bank(file: UploadFile = File(...)):
    """Upload a question bank file and import all valid questions."""
    suffix = Path(file.filename or "bank.xlsx").suffix.lower()
    allowed = {".xlsx", ".xls", ".csv", ".json", ".docx", ".pdf"}
    if suffix not in allowed:
        raise HTTPException(400, f"Unsupported format: {suffix}")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        from services.question_bank_service import QuestionBankService
        svc = QuestionBankService()
        result = svc.load_from_file(tmp_path)
        count = 0
        if not result.has_fatal_errors:
            count = svc.import_to_database(result)

        return ImportResultOut(
            total_rows=result.total_rows,
            imported=count,
            warnings=result.warnings[:20],
            errors=[f"Row {e.row} [{e.field}]: {e.message}" for e in result.errors[:20]],
            chapter_completeness={k: dict(v) for k, v in result.chapter_completeness.items()},
        )
    finally:
        tmp_path.unlink(missing_ok=True)


@router.patch("/{question_id}", response_model=QuestionOut)
def update_question(question_id: str, body: QuestionUpdateIn):
    repo = QuestionRepository()
    q = repo.get_by_id(question_id)
    if not q:
        raise HTTPException(404, "Question not found")
    updates = body.model_dump(exclude_none=True)
    q = repo.update(question_id, **updates)
    return _q_out(q)


@router.delete("/{question_id}")
def delete_question(question_id: str):
    repo = QuestionRepository()
    q = repo.get_by_id(question_id)
    if not q:
        raise HTTPException(404, "Question not found")
    repo.delete(question_id)
    return {"ok": True}


def _q_out(q) -> QuestionOut:
    return QuestionOut(
        question_id=q.question_id,
        unit_number=q.unit_number,
        chapter_number=q.chapter_number,
        chapter_name=q.chapter_name or "",
        bloom_level=q.bloom_level.value if hasattr(q.bloom_level, "value") else q.bloom_level,
        question_text=q.question_text,
        marks=q.marks,
        model_answer=q.model_answer,
        difficulty=q.difficulty.value if hasattr(q.difficulty, "value") else (q.difficulty or "medium"),
        source=q.source.value if hasattr(q.source, "value") else (q.source or "QUESTION_BANK"),
        approval_status=q.approval_status.value if hasattr(q.approval_status, "value") else (q.approval_status or "APPROVED"),
    )
