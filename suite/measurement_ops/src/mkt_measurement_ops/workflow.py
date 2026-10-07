from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4


class JobState(StrEnum):
    CREATED = "created"
    AUDITED = "audited"
    PLANNED = "planned"
    PREPARED = "prepared"
    VERIFIED = "verified"
    APPROVED = "approved"
    PUBLISHED = "published"
    FAILED = "failed"


_ALLOWED: dict[JobState, set[JobState]] = {
    JobState.CREATED: {JobState.AUDITED, JobState.FAILED},
    JobState.AUDITED: {JobState.PLANNED, JobState.FAILED},
    JobState.PLANNED: {JobState.PREPARED, JobState.FAILED},
    JobState.PREPARED: {JobState.VERIFIED, JobState.FAILED},
    JobState.VERIFIED: {JobState.APPROVED, JobState.FAILED},
    JobState.APPROVED: {JobState.PUBLISHED, JobState.FAILED},
    JobState.PUBLISHED: set(),
    JobState.FAILED: set(),
}


@dataclass(slots=True)
class MeasurementJob:
    site_key: str
    id: str = field(default_factory=lambda: uuid4().hex)
    state: JobState = JobState.CREATED
    evidence: list[dict] = field(default_factory=list)

    def transition(self, target: JobState, *, evidence: dict | None = None) -> None:
        if target not in _ALLOWED[self.state]:
            raise ValueError(f"invalid transition: {self.state.value} -> {target.value}")
        if target == JobState.APPROVED and not self._has_verification_evidence():
            raise ValueError("approval requires verification evidence")
        self.state = target
        if evidence is not None:
            self.evidence.append(evidence)

    def _has_verification_evidence(self) -> bool:
        return any(item.get("kind") == "verification" and item.get("passed") is True for item in self.evidence)
