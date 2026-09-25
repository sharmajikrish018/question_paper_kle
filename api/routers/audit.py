"""api/routers/audit.py — Audit logs & dashboard stats."""
from fastapi import APIRouter, Query
from repositories.database import get_session, AuditLogDB, QuestionDB, PaperSetDB

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/stats")
def get_stats():
    with get_session() as session:
        total_questions = session.query(QuestionDB).count()
        l2_count = session.query(QuestionDB).filter(QuestionDB.bloom_level == "L2").count()
        l3_count = session.query(QuestionDB).filter(QuestionDB.bloom_level == "L3").count()
        total_sets = session.query(PaperSetDB).count()
        pending_sets = session.query(PaperSetDB).filter(
            PaperSetDB.status.in_(["GENERATED", "UNDER_REVIEW", "CHANGES_REQUESTED"])
        ).count()
        approved_sets = session.query(PaperSetDB).filter(PaperSetDB.status == "APPROVED").count()
        exported_sets = session.query(PaperSetDB).filter(PaperSetDB.status == "EXPORTED").count()

        qs = session.query(QuestionDB.chapter_number, QuestionDB.bloom_level).all()

    completeness: dict = {}
    for ch, bl in qs:
        completeness.setdefault(ch, {"L2": 0, "L3": 0})
        completeness[ch][bl] = completeness[ch].get(bl, 0) + 1

    return {
        "question_bank": {
            "total": total_questions,
            "l2": l2_count,
            "l3": l3_count,
            "completeness_pct": min(100, round(total_questions / 140 * 100)) if total_questions else 0,
        },
        "papers": {
            "total": total_sets,
            "pending": pending_sets,
            "approved": approved_sets,
            "exported": exported_sets,
        },
        "chapter_completeness": completeness,
    }


@router.get("/logs")
def get_logs(limit: int = Query(20, le=100)):
    with get_session() as session:
        logs = (
            session.query(AuditLogDB)
            .order_by(AuditLogDB.timestamp.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": log.id,
                "action": log.action,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "paper_set_id": log.paper_set_id,
                "details": log.details,
            }
            for log in logs
        ]
