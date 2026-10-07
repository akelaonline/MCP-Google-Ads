from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict
from pathlib import Path

from .workflow import JobState, MeasurementJob


class JobStore:
    """Durable workflow state. Stores evidence metadata, never provider credentials."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @classmethod
    def from_env(cls) -> "JobStore":
        return cls(os.getenv("MEASUREMENT_OPS_DB", "./measurement_ops.db"))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS measurement_jobs (
                    id TEXT PRIMARY KEY,
                    site_key TEXT NOT NULL,
                    state TEXT NOT NULL,
                    evidence_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def create(self, site_key: str) -> MeasurementJob:
        job = MeasurementJob(site_key=site_key)
        with self._connect() as db:
            db.execute(
                "INSERT INTO measurement_jobs (id, site_key, state, evidence_json) VALUES (?, ?, ?, ?)",
                (job.id, job.site_key, job.state.value, json.dumps(job.evidence)),
            )
        return job

    def get(self, job_id: str) -> MeasurementJob:
        with self._connect() as db:
            row = db.execute(
                "SELECT id, site_key, state, evidence_json FROM measurement_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown measurement job: {job_id}")
        return MeasurementJob(
            id=row["id"],
            site_key=row["site_key"],
            state=JobState(row["state"]),
            evidence=json.loads(row["evidence_json"]),
        )

    def save(self, job: MeasurementJob) -> None:
        with self._connect() as db:
            cursor = db.execute(
                """
                UPDATE measurement_jobs
                SET state = ?, evidence_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (job.state.value, json.dumps(job.evidence), job.id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"unknown measurement job: {job.id}")

    def transition(self, job_id: str, target: JobState, *, evidence: dict | None = None) -> MeasurementJob:
        job = self.get(job_id)
        job.transition(target, evidence=evidence)
        self.save(job)
        return job

    @staticmethod
    def serialize(job: MeasurementJob) -> dict:
        payload = asdict(job)
        payload["state"] = job.state.value
        return payload
