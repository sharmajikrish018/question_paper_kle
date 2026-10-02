"""
tests/test_subject_isolation.py
Verifies strict per-subject data isolation: questions, papers, audit logs, context.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def clean_db():
    """Wipe and recreate all tables between tests."""
    from repositories.database import Base, engine, get_session
    from repositories.database import (
        QuestionDB, PaperSetDB, PaperRequestDB, PaperQuestionDB,
        AuditLogDB, UsageHistoryDB, SubjectContextDB, CourseDB,
    )
    Base.metadata.drop_all(bind=engine)
    from repositories.database import init_db
    init_db()
    yield


def _make_subject(name: str, code: str) -> str:
    """Helper: create a subject and return its subject_id slug."""
    from repositories.subject_repo import SubjectRepository
    result = SubjectRepository().create_subject(
        course_name=name,
        course_code=code,
        units=[{
            "unit_number": 1,
            "title": "Unit 1",
            "chapters": [{"chapter_number": 1, "title": "Chapter 1", "topics": ["Topic A"]}],
        }],
    )
    return result["subject_id"]


def _make_question(q_id: str, subject_id: str) -> None:
    from models.question import Question
    from models.enums import BloomLevel, QuestionSource, ApprovalStatus
    from repositories.question_repo import QuestionRepository
    QuestionRepository().upsert(
        Question(
            question_id=q_id,
            unit_number=1,
            chapter_number=1,
            chapter_name="Ch1",
            question_text=f"Question {q_id} text",
            bloom_level=BloomLevel.L2,
            marks=10,
            source=QuestionSource.QUESTION_BANK,
            approval_status=ApprovalStatus.APPROVED,
        ),
        subject_id=subject_id,
    )


class TestQuestionIsolation:

    def test_questions_isolated_between_subjects(self):
        """Questions added to A must not appear in B's listing."""
        sid_a = _make_subject("Subject A", "SUBA")
        sid_b = _make_subject("Subject B", "SUBB")
        _make_question("Q-A-001", sid_a)
        _make_question("Q-A-002", sid_a)

        from repositories.question_repo import QuestionRepository
        repo = QuestionRepository()
        assert len(repo.get_all(subject_id=sid_a)) == 2
        assert len(repo.get_all(subject_id=sid_b)) == 0

    def test_cross_subject_get_by_id_returns_none(self):
        """Getting A's question using B's subject_id must return None."""
        sid_a = _make_subject("Subject A", "SUBA")
        sid_b = _make_subject("Subject B", "SUBB")
        _make_question("Q-A-001", sid_a)

        from repositories.question_repo import QuestionRepository
        repo = QuestionRepository()
        assert repo.get_by_id("Q-A-001", subject_id=sid_b) is None
        assert repo.get_by_id("Q-A-001", subject_id=sid_a) is not None

    def test_delete_only_affects_own_subject(self):
        """Deleting A's question must not touch B's questions."""
        sid_a = _make_subject("Subject A", "SUBA")
        sid_b = _make_subject("Subject B", "SUBB")
        _make_question("Q-A-001", sid_a)
        _make_question("Q-B-001", sid_b)

        from repositories.question_repo import QuestionRepository
        repo = QuestionRepository()
        repo.delete("Q-A-001", subject_id=sid_a)

        assert repo.get_all(subject_id=sid_a) == []
        assert len(repo.get_all(subject_id=sid_b)) == 1

    def test_update_respects_subject_scope(self):
        """Updating a question via B's subject_id when it belongs to A → no-op."""
        sid_a = _make_subject("Subject A", "SUBA")
        sid_b = _make_subject("Subject B", "SUBB")
        _make_question("Q-A-001", sid_a)

        from repositories.question_repo import QuestionRepository
        repo = QuestionRepository()
        result = repo.update("Q-A-001", subject_id=sid_b, question_text="hacked")
        assert result is None

        # Original text unchanged
        q = repo.get_by_id("Q-A-001", subject_id=sid_a)
        assert q.question_text == "Question Q-A-001 text"


class TestAuditIsolation:

    def test_audit_logs_scoped_by_subject(self):
        sid_a = _make_subject("Subject A", "SUBA")
        sid_b = _make_subject("Subject B", "SUBB")

        from repositories.audit_repo import AuditRepository
        audit = AuditRepository()
        audit.log("ACTION_A1", subject_id=sid_a)
        audit.log("ACTION_A2", subject_id=sid_a)
        audit.log("ACTION_B1", subject_id=sid_b)

        logs_a = audit.get_recent(subject_id=sid_a)
        logs_b = audit.get_recent(subject_id=sid_b)

        assert len(logs_a) == 2
        assert len(logs_b) == 1
        assert all(l["action"].startswith("ACTION_A") for l in logs_a)
        assert logs_b[0]["action"] == "ACTION_B1"


class TestContextSaveRestore:

    def test_context_save_restore_per_subject(self):
        sid_a = _make_subject("Subject A", "SUBA")
        sid_b = _make_subject("Subject B", "SUBB")

        from repositories.context_repo import SubjectContextRepository
        ctx_repo = SubjectContextRepository()

        ctx_a = {"page": "/questions", "filter": {"bloom": "L2"}, "page_num": 3}
        ctx_b = {"page": "/generate", "wizard_step": 2}

        ctx_repo.put(sid_a, ctx_a)
        ctx_repo.put(sid_b, ctx_b)

        assert ctx_repo.get(sid_a) == ctx_a
        assert ctx_repo.get(sid_b) == ctx_b

    def test_context_restore_after_switch(self):
        """A → B → A: A's context must be exactly restored."""
        sid_a = _make_subject("Subject A", "SUBA")
        sid_b = _make_subject("Subject B", "SUBB")

        from repositories.context_repo import SubjectContextRepository
        ctx_repo = SubjectContextRepository()

        original_a = {"page": "/review", "selected_set": "SET-001", "zoom": 1.5}
        ctx_repo.put(sid_a, original_a)
        ctx_repo.put(sid_b, {"page": "/dashboard"})

        # Simulate switch A → B → A
        _ = ctx_repo.get(sid_b)
        ctx_repo.put(sid_b, {"page": "/questions", "edited": True})

        # A's context must be unchanged
        assert ctx_repo.get(sid_a) == original_a
        assert ctx_repo.get(sid_b)["edited"] is True

    def test_context_size_cap(self):
        sid_a = _make_subject("Subject A", "SUBA")
        from repositories.context_repo import SubjectContextRepository, MAX_CONTEXT_BYTES
        huge_ctx = {"data": "x" * (MAX_CONTEXT_BYTES + 5000)}
        with pytest.raises(ValueError, match="too large"):
            SubjectContextRepository().put(sid_a, huge_ctx)


class TestMigration:

    def test_orphan_rows_assigned_to_default_subject(self):
        """Questions with NULL subject_id (legacy rows) must be assigned after init_db."""
        from repositories.database import QuestionDB, get_session, init_db
        import sqlalchemy as sa

        with get_session() as session:
            session.execute(sa.text(
                "INSERT INTO questions "
                "(question_id, unit_number, chapter_number, chapter_name, question_text, "
                "bloom_level, marks, source, approval_status) "
                "VALUES ('LEGACY-001', 1, 1, 'Ch1', 'Legacy question', 'L2', 10, "
                "'QUESTION_BANK', 'APPROVED')"
            ))

        init_db()

        with get_session() as session:
            q = session.query(QuestionDB).filter(
                QuestionDB.question_id == "LEGACY-001"
            ).first()
            # Read attribute inside session to avoid DetachedInstanceError
            assert q is not None
            sid_val = q.subject_id
        assert sid_val is not None and sid_val != ""


class TestDeleteCascade:

    def test_delete_subject_cascades_questions(self):
        """Deleting subject A removes its questions; B untouched."""
        sid_a = _make_subject("Subject A", "SUBA")
        sid_b = _make_subject("Subject B", "SUBB")
        _make_question("Q-A-001", sid_a)
        _make_question("Q-B-001", sid_b)

        from repositories.question_repo import QuestionRepository
        repo = QuestionRepository()
        repo.delete_by_subject(sid_a)

        assert repo.get_all(subject_id=sid_a) == []
        assert len(repo.get_all(subject_id=sid_b)) == 1
