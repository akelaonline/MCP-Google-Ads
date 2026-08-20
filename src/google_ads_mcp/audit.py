"""SQLite audit trail and encrypted durable pending-action storage."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path


class AuditLog:
    def __init__(self, db_path: str):
        self._db_path = Path(db_path).expanduser()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._fernet_instance = None
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
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
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_actions (
                action_id TEXT PRIMARY KEY,
                tool_name TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                description TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                invocation_encrypted BLOB,
                risk_level TEXT NOT NULL,
                created_at REAL NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pending_created_at ON pending_actions(created_at)"
        )
        self._conn.commit()
        _chmod_600(self._db_path)

    # ------------------------------------------------------------------
    # Executed mutation audit
    # ------------------------------------------------------------------
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
            return [_decode_audit_row(row) for row in cur.fetchall()]

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
            return [_decode_audit_row(row) for row in cur.fetchall()]

    # ------------------------------------------------------------------
    # Durable pending actions
    # ------------------------------------------------------------------
    def save_pending(
        self,
        *,
        action_id: str,
        tool_name: str,
        customer_id: str,
        description: str,
        payload: dict,
        invocation_arguments: dict | None,
        risk_level: str,
        created_at: float,
        attempts: int = 0,
    ) -> None:
        """Persist one proposed action; original MCP args are encrypted at rest."""
        invocation_encrypted = None
        if invocation_arguments is not None:
            plaintext = json.dumps(
                invocation_arguments,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            invocation_encrypted = self._fernet().encrypt(plaintext)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO pending_actions
                    (action_id, tool_name, customer_id, description, payload_json,
                     invocation_encrypted, risk_level, created_at, attempts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(action_id) DO UPDATE SET
                    tool_name=excluded.tool_name,
                    customer_id=excluded.customer_id,
                    description=excluded.description,
                    payload_json=excluded.payload_json,
                    invocation_encrypted=excluded.invocation_encrypted,
                    risk_level=excluded.risk_level,
                    created_at=excluded.created_at,
                    attempts=excluded.attempts
                """,
                (
                    action_id,
                    tool_name,
                    customer_id,
                    description,
                    json.dumps(payload, default=str),
                    invocation_encrypted,
                    risk_level,
                    float(created_at),
                    int(attempts),
                ),
            )
            self._conn.commit()

    def get_pending(self, action_id: str) -> dict | None:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT action_id, tool_name, customer_id, description,
                       payload_json, invocation_encrypted, risk_level,
                       created_at, attempts
                FROM pending_actions
                WHERE action_id = ?
                """,
                (action_id,),
            )
            row = cur.fetchone()
        return self._decode_pending_row(row) if row else None

    def pending(self) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT action_id, tool_name, customer_id, description,
                       payload_json, invocation_encrypted, risk_level,
                       created_at, attempts
                FROM pending_actions
                ORDER BY created_at ASC
                """
            )
            rows = cur.fetchall()
        return [self._decode_pending_row(row) for row in rows]

    def set_pending_attempts(self, action_id: str, attempts: int) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE pending_actions SET attempts = ? WHERE action_id = ?",
                (int(attempts), action_id),
            )
            self._conn.commit()

    def delete_pending(self, action_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM pending_actions WHERE action_id = ?", (action_id,)
            )
            self._conn.commit()

    def prune_pending_before(self, cutoff: float) -> list[str]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT action_id FROM pending_actions WHERE created_at < ?",
                (float(cutoff),),
            )
            action_ids = [str(row[0]) for row in cur.fetchall()]
            self._conn.execute(
                "DELETE FROM pending_actions WHERE created_at < ?", (float(cutoff),)
            )
            self._conn.commit()
        return action_ids

    def _decode_pending_row(self, row) -> dict:
        (
            action_id,
            tool_name,
            customer_id,
            description,
            payload_json,
            invocation_encrypted,
            risk_level,
            created_at,
            attempts,
        ) = row
        try:
            payload = json.loads(payload_json) if payload_json else {}
        except json.JSONDecodeError:
            payload = {"_raw": payload_json}

        invocation_arguments = None
        invocation_error = None
        if invocation_encrypted is not None:
            try:
                plaintext = self._fernet().decrypt(bytes(invocation_encrypted))
                invocation_arguments = json.loads(plaintext.decode("utf-8"))
            except Exception as ex:  # corrupt/missing key must fail closed, not execute
                invocation_error = f"Unable to decrypt persisted tool arguments: {ex}"

        return {
            "action_id": action_id,
            "tool_name": tool_name,
            "customer_id": customer_id,
            "description": description,
            "payload": payload,
            "invocation_arguments": invocation_arguments,
            "invocation_error": invocation_error,
            "risk_level": risk_level,
            "created_at": float(created_at),
            "attempts": int(attempts),
        }

    def _fernet(self):
        if self._fernet_instance is not None:
            return self._fernet_instance
        from cryptography.fernet import Fernet

        configured = os.environ.get("GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY", "").strip()
        if configured:
            key = configured.encode("ascii")
        else:
            key_path = Path(f"{self._db_path}.pending.key")
            if key_path.exists():
                key = key_path.read_bytes().strip()
            else:
                key = Fernet.generate_key()
                # Exclusive creation avoids accidentally rotating a key used by
                # another process that initialized the same DB concurrently.
                try:
                    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, "wb") as handle:
                        handle.write(key + b"\n")
                except FileExistsError:
                    key = key_path.read_bytes().strip()
            _chmod_600(key_path)
        self._fernet_instance = Fernet(key)
        return self._fernet_instance


def _decode_audit_row(row) -> dict:
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


def _chmod_600(path: Path) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
