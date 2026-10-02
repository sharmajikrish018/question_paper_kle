"""
repositories/database.py
SQLAlchemy engine, session factory, and base model.
Also defines all ORM table models.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

from config.settings import get_settings


# ── ORM Base ─────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── ORM Models ───────────────────────────────────────────────────────────────

class CourseDB(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True)
    # Stable, URL-safe slug used as the external subject identifier
    # e.g. "agentic-ai-26ECAC401"
    subject_id = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False, default="")
    code = Column(String, nullable=True)
    department = Column(String, nullable=True)
    semester = Column(String, nullable=True)
    academic_year = Column(String, nullable=True)
    # JSON blob: {"minor1": [unit_ids…], "minor2": [unit_ids…]}
    minor_configuration = Column(Text, nullable=True)
    # JSON blob: {"confidence": float, "warnings": [], "source_filename": str, "raw_text_length": int}
    lp_metadata = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    units = relationship("UnitDB", back_populates="course", cascade="all, delete-orphan")


class UnitDB(Base):
    __tablename__ = "units"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    unit_number = Column(Integer, nullable=False)
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    course = relationship("CourseDB", back_populates="units")
    chapters = relationship("ChapterDB", back_populates="unit", cascade="all, delete-orphan")


class ChapterDB(Base):
    __tablename__ = "chapters"
    id = Column(Integer, primary_key=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)
    chapter_number = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    topics = Column(Text, nullable=True)  # JSON list of topic strings
    created_at = Column(DateTime, default=datetime.utcnow)

    unit = relationship("UnitDB", back_populates="chapters")


class QuestionDB(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True)
    question_id = Column(String, unique=True, nullable=False, index=True)
    subject_id = Column(String, nullable=True, index=True)
    course_name = Column(String, default="Generative AI")
    unit_number = Column(Integer, nullable=False)
    chapter_number = Column(Integer, nullable=False)
    chapter_name = Column(String, nullable=False)
    question_text = Column(Text, nullable=False)
    bloom_level = Column(String, nullable=False)  # L2 | L3
    marks = Column(Integer, default=10)
    question_type = Column(String, default="descriptive")
    difficulty = Column(String, default="medium")
    model_answer = Column(Text, nullable=True)
    valuation_points = Column(Text, nullable=True)  # JSON
    source = Column(String, default="QUESTION_BANK")
    approval_status = Column(String, default="APPROVED")
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Embedding stored as JSON float list
    embedding = Column(Text, nullable=True)


class GeneratedQuestionDB(Base):
    __tablename__ = "generated_questions"
    id = Column(Integer, primary_key=True)
    generated_id = Column(String, unique=True, nullable=False, index=True)
    subject_id = Column(String, nullable=True, index=True)
    paper_set_id = Column(String, nullable=True, index=True)
    unit_number = Column(Integer, nullable=False)
    chapter_number = Column(Integer, nullable=False)
    chapter_name = Column(String, nullable=False)
    question_text = Column(Text, nullable=False)
    bloom_level = Column(String, nullable=False)
    marks = Column(Integer, default=10)
    model_answer = Column(Text, nullable=True)
    valuation_points = Column(Text, nullable=True)  # JSON
    bloom_justification = Column(Text, nullable=True)
    syllabus_grounding = Column(Text, nullable=True)  # JSON
    approval_status = Column(String, default="PENDING")
    added_to_bank = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    embedding = Column(Text, nullable=True)


class PaperRequestDB(Base):
    __tablename__ = "paper_requests"
    id = Column(Integer, primary_key=True)
    request_id = Column(String, unique=True, nullable=False)
    subject_id = Column(String, nullable=True, index=True)
    exam_type = Column(String, nullable=False)
    course_name = Column(String, default="Generative AI")
    academic_year = Column(String, nullable=True)
    num_sets = Column(Integer, default=1)
    random_seed = Column(Integer, nullable=True)
    l2_percent = Column(Integer, default=50)
    l3_percent = Column(Integer, default=50)
    selected_chapters = Column(Text, nullable=True)  # JSON
    model_provider = Column(String, nullable=True)
    model_name = Column(String, nullable=True)
    status = Column(String, default="DRAFT")
    created_at = Column(DateTime, default=datetime.utcnow)

    sets = relationship("PaperSetDB", back_populates="request", cascade="all, delete-orphan")


class PaperSetDB(Base):
    __tablename__ = "paper_sets"
    id = Column(Integer, primary_key=True)
    subject_id = Column(String, nullable=True, index=True)
    request_id = Column(String, ForeignKey("paper_requests.request_id"), nullable=False)
    set_id = Column(String, unique=True, nullable=False)
    set_index = Column(Integer, nullable=False)
    exam_type = Column(String, nullable=False)
    status = Column(String, default="GENERATED")
    generated_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
    exported_at = Column(DateTime, nullable=True)
    faculty_notes = Column(Text, nullable=True)
    validation_status = Column(String, nullable=True)
    validation_findings = Column(Text, nullable=True)  # JSON

    request = relationship("PaperRequestDB", back_populates="sets")
    paper_questions = relationship(
        "PaperQuestionDB", back_populates="paper_set", cascade="all, delete-orphan"
    )


class PaperQuestionDB(Base):
    __tablename__ = "paper_questions"
    id = Column(Integer, primary_key=True)
    subject_id = Column(String, nullable=True, index=True)
    paper_set_id = Column(String, ForeignKey("paper_sets.set_id"), nullable=False)
    slot_id = Column(String, nullable=False)  # Q1a, Q2b …
    main_question_number = Column(Integer, nullable=False)
    part = Column(String, nullable=False)  # a | b
    unit_number = Column(Integer, nullable=False)
    chapter_number = Column(Integer, nullable=False)
    chapter_name = Column(String, nullable=False)
    question_text = Column(Text, nullable=False)
    bloom_level = Column(String, nullable=False)
    marks = Column(Integer, default=10)
    source = Column(String, nullable=False)
    approval_status = Column(String, default="PENDING")
    question_id = Column(String, nullable=True)  # bank ID
    generated_id = Column(String, nullable=True)  # AI ID
    valuation_points = Column(Text, nullable=True)  # JSON
    bloom_justification = Column(Text, nullable=True)
    similarity_status = Column(String, nullable=True)

    paper_set = relationship("PaperSetDB", back_populates="paper_questions")


class UsageHistoryDB(Base):
    __tablename__ = "usage_history"
    id = Column(Integer, primary_key=True)
    subject_id = Column(String, nullable=True, index=True)
    question_id = Column(String, nullable=False, index=True)
    source = Column(String, nullable=False)
    paper_set_id = Column(String, nullable=False)
    exam_type = Column(String, nullable=False)
    academic_year = Column(String, nullable=True)
    used_at = Column(DateTime, default=datetime.utcnow)


class AuditLogDB(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    subject_id = Column(String, nullable=True, index=True)
    request_id = Column(String, nullable=True)
    paper_set_id = Column(String, nullable=True)
    action = Column(String, nullable=False)
    actor = Column(String, default="FACULTY")
    details = Column(Text, nullable=True)  # JSON
    timestamp = Column(DateTime, default=datetime.utcnow)


class UploadedFileDB(Base):
    __tablename__ = "uploaded_files"
    id = Column(Integer, primary_key=True)
    subject_id = Column(String, nullable=True, index=True)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    category = Column(String, nullable=False)  # question_bank | lesson_plan | university_template
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class AppSettingDB(Base):
    __tablename__ = "app_settings"
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SubjectContextDB(Base):
    __tablename__ = "subject_context"
    id = Column(Integer, primary_key=True)
    subject_id = Column(String, unique=True, nullable=False, index=True)
    context_json = Column(Text, nullable=True)  # JSON blob
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── Engine and session factory ────────────────────────────────────────────────

def _build_db_url() -> str:
    settings = get_settings()
    db_url = settings.database_url
    # Resolve relative sqlite path to absolute
    if db_url.startswith("sqlite:///./"):
        rel_path = db_url[len("sqlite:///./"):]
        abs_path = settings.project_root / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{abs_path.as_posix()}"
    return db_url


_DB_URL = _build_db_url()

engine = create_engine(
    _DB_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

# Enable WAL mode for better concurrent access on SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create all tables. Safe to call multiple times.
    Also applies lightweight column-level migrations for existing tables.
    """
    Base.metadata.create_all(bind=engine)
    _migrate_columns()


def _migrate_columns() -> None:
    """
    Idempotent column migrations for tables that may already exist.
    Uses SQLite PRAGMA to check existing columns before attempting ALTER TABLE.
    Also ensures every subject-owned row has a subject_id (assigns to 'default-subject').
    """
    import sqlalchemy as _sa

    migrations = [
        # (table_name, column_name, column_definition)
        ("courses", "subject_id",          "TEXT"),
        ("courses", "minor_configuration", "TEXT"),
        ("courses", "lp_metadata",         "TEXT"),
        ("questions",           "subject_id", "TEXT"),
        ("generated_questions", "subject_id", "TEXT"),
        ("paper_requests",      "subject_id", "TEXT"),
        ("paper_sets",          "subject_id", "TEXT"),
        ("paper_questions",     "subject_id", "TEXT"),
        ("usage_history",       "subject_id", "TEXT"),
        ("audit_logs",          "subject_id", "TEXT"),
        ("uploaded_files",      "subject_id", "TEXT"),
    ]

    with engine.connect() as conn:
        for table, col, col_def in migrations:
            try:
                result = conn.execute(_sa.text(f"PRAGMA table_info({table})"))
                existing = {row[1] for row in result}
                if col not in existing:
                    conn.execute(_sa.text(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}"))
                    conn.commit()
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning(
                    f"[init_db] migration {table}.{col} skipped: {exc}"
                )

    # Ensure a default subject exists and assign orphan rows to it
    _ensure_default_subject()


def _ensure_default_subject() -> None:
    """Create 'default-subject' if no subjects exist; assign all NULL subject_id rows to it."""
    import sqlalchemy as _sa
    import logging
    log = logging.getLogger(__name__)

    with engine.connect() as conn:
        # Check if any course rows exist
        result = conn.execute(_sa.text("SELECT subject_id FROM courses LIMIT 1"))
        first = result.fetchone()
        default_slug = first[0] if first else None

        # If no courses at all, create the default subject row
        if first is None:
            conn.execute(_sa.text(
                "INSERT INTO courses (subject_id, name, code, created_at, updated_at) "
                "VALUES ('default-subject', 'Default Subject', 'DEFAULT', datetime('now'), datetime('now'))"
            ))
            conn.commit()
            default_slug = "default-subject"
            log.info("[init_db] Created 'default-subject' course.")

        if not default_slug:
            return

        # Assign NULL subject_id rows in all subject-owned tables to default_slug
        owned_tables = [
            "questions", "generated_questions", "paper_requests",
            "paper_sets", "paper_questions", "usage_history",
            "audit_logs", "uploaded_files",
        ]
        for tbl in owned_tables:
            try:
                conn.execute(_sa.text(
                    f"UPDATE {tbl} SET subject_id = :slug WHERE subject_id IS NULL"
                ), {"slug": default_slug})
            except Exception as exc:
                log.warning(f"[init_db] could not update {tbl}.subject_id: {exc}")
        conn.commit()
        log.info(f"[init_db] Orphan rows assigned to '{default_slug}'.")



@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Provide a transactional database session."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
