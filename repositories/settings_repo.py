"""
repositories/settings_repo.py
App settings key-value store in database.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from repositories.database import AppSettingDB, get_session


class SettingsRepository:

    def set(self, key: str, value: Any) -> None:
        with get_session() as session:
            existing = session.query(AppSettingDB).filter(
                AppSettingDB.key == key
            ).first()
            val_str = json.dumps(value) if not isinstance(value, str) else value
            if existing:
                existing.value = val_str
            else:
                session.add(AppSettingDB(key=key, value=val_str))

    def get(self, key: str, default: Any = None) -> Any:
        with get_session() as session:
            row = session.query(AppSettingDB).filter(
                AppSettingDB.key == key
            ).first()
            if row is None:
                return default
            try:
                return json.loads(row.value)
            except (json.JSONDecodeError, TypeError):
                return row.value

    def get_all(self) -> dict[str, Any]:
        with get_session() as session:
            rows = session.query(AppSettingDB).all()
            result = {}
            for row in rows:
                try:
                    result[row.key] = json.loads(row.value)
                except (json.JSONDecodeError, TypeError):
                    result[row.key] = row.value
            return result
