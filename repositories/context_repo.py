"""
repositories/context_repo.py
Repository for per-subject UI context (last page, filters, drafts, etc.).
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from repositories.database import SubjectContextDB, get_session

MAX_CONTEXT_BYTES = 64 * 1024  # 64 KB cap


class SubjectContextRepository:

    def get(self, subject_id: str) -> dict:
        """Return the stored context dict for subject_id, or empty dict."""
        with get_session() as session:
            row = session.query(SubjectContextDB).filter(
                SubjectContextDB.subject_id == subject_id
            ).first()
            if row is None or not row.context_json:
                return {}
            try:
                return json.loads(row.context_json)
            except Exception:
                return {}

    def put(self, subject_id: str, context: dict) -> None:
        """
        Persist the context dict for subject_id.
        Raises ValueError if serialized size exceeds MAX_CONTEXT_BYTES.
        """
        raw = json.dumps(context, ensure_ascii=False)
        if len(raw.encode("utf-8")) > MAX_CONTEXT_BYTES:
            raise ValueError(
                f"Context blob too large ({len(raw.encode())} bytes > {MAX_CONTEXT_BYTES} limit)"
            )
        with get_session() as session:
            row = session.query(SubjectContextDB).filter(
                SubjectContextDB.subject_id == subject_id
            ).first()
            if row:
                row.context_json = raw
                row.updated_at = datetime.utcnow()
            else:
                session.add(SubjectContextDB(
                    subject_id=subject_id,
                    context_json=raw,
                    updated_at=datetime.utcnow(),
                ))
