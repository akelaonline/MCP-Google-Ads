"""SQLite audit trail for every executed Google Ads mutation."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path


class AuditLog:
    def __init__(self, db_path: str):
        db_path = str(Path(db_path).expanduser())
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
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
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_action_id ON audit_log(action_id)"
        )
        self._conn.commit()
        try:
            os.chmod(db_path, 0o600)
        except OSError:
            pass

    def record(
        self,
        *,
        action_id: str,
        tool_name: str,
        customer_id: str,
        description: str,
        payload: dict,
        result: dict | list | str | None,
        status: str,
    ) -> None:
        with self._lock:
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
        limit = max(1, min(int(limit), 200))
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT action_id, tool_name, customer_id, description,
                       payload_json, result_json, status, created_at
                FROM audit_log
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [_decode_row(row) for row in cur.fetchall()]

    def by_action_id(self, action_id: str) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT action_id, tool_name, customer_id, description,
                       payload_json, result_json, status, created_at
                FROM audit_log
                WHERE action_id = ?
                ORDER BY id ASC
                """,
                (action_id,),
            )
            return [_decode_row(row) for row in cur.fetchall()]


def _decode_row(row) -> dict:
    (
        action_id,
        tool_name,
        customer_id,
        description,
        payload_json,
        result_json,
        status,
        created_at,
    ) = row
    try:
        payload = json.loads(payload_json) if payload_json else None
    except json.JSONDecodeError:
        payload = payload_json
    try:
        result = json.loads(result_json) if result_json else None
    except json.JSONDecodeError:
        result = result_json
    return {
        "action_id": action_id,
        "tool_name": tool_name,
        "customer_id": customer_id,
        "description": description,
        "payload": payload,
        "result": result,
        "status": status,
        "created_at": created_at,
    }
