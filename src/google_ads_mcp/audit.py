"""SQLite audit trail — every executed (confirmed) mutation is logged here."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


class AuditLog:
    def __init__(self, db_path: str):
        db_path = str(Path(db_path).expanduser())
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_id TEXT,
                tool_name TEXT,
                customer_id TEXT,
                description TEXT,
                payload_json TEXT,
                result_json TEXT,
                status TEXT,
                created_at REAL
            )
            """
        )
        self._conn.commit()

    def record(
        self,
        *,
        action_id: str,
        tool_name: str,
        customer_id: str,
        description: str,
        payload: dict,
        result: dict | str | None,
        status: str,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO audit_log
                (action_id, tool_name, customer_id, description,
                 payload_json, result_json, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action_id,
                tool_name,
                customer_id,
                description,
                json.dumps(payload, default=str),
                json.dumps(result, default=str),
                status,
                time.time(),
            ),
        )
        self._conn.commit()

    def recent(self, limit: int = 20) -> list[dict]:
        cur = self._conn.execute(
            "SELECT action_id, tool_name, customer_id, description, status, created_at "
            "FROM audit_log ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
