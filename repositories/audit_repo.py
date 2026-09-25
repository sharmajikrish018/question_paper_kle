"""
repositories/audit_repo.py
Audit log repository.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from repositories.database import AuditLogDB, get_session


class AuditRepository:

    def log(
        self,
        action: str,
        details: Optional[dict[str, Any]] = None,
        request_id: Optional[str] = None,
        paper_set_id: Optional[str] = None,
        actor: str = "FACULTY",
    ) -> None:
        with get_session() as session:
            session.add(AuditLogDB(
                request_id=request_id,
                paper_set_id=paper_set_id,
                action=action,
                actor=actor,
                details=json.dumps(details) if details else None,
                timestamp=datetime.utcnow(),
            ))

    def get_recent(self, limit: int = 50) -> list[dict]:
        with get_session() as session:
            rows = (
                session.query(AuditLogDB)
                .order_by(AuditLogDB.timestamp.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": r.id,
                    "action": r.action,
                    "actor": r.actor,
                    "request_id": r.request_id,
                    "paper_set_id": r.paper_set_id,
                    "details": r.details,
                    "timestamp": r.timestamp,
                }
                for r in rows
            ]

