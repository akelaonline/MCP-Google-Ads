from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4


class JobState(StrEnum):
    CREATED = "created"
    AUDITED = "audited"
    PLANNED = "planned"
    PREPARED = "prepared"
    PREVIEW_VERIFIED = "preview_verified"
    APPROVED = "approved"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    PRODUCTION_VERIFIED = "production_verified"
    FAILED = "failed"


_ALLOWED: dict[JobState, set[JobState]] = {
    JobState.CREATED: {JobState.AUDITED, JobState.FAILED},
    JobState.AUDITED: {JobState.PLANNED, JobState.FAILED},
    JobState.PLANNED: {JobState.PREPARED, JobState.FAILED},
    JobState.PREPARED: {JobState.PREVIEW_VERIFIED, JobState.FAILED},
    JobState.PREVIEW_VERIFIED: {JobState.APPROVED, JobState.FAILED},
    JobState.APPROVED: {JobState.PUBLISHING, JobState.FAILED},
    JobState.PUBLISHING: {JobState.PUBLISHED, JobState.FAILED},
    JobState.PUBLISHED: {JobState.PRODUCTION_VERIFIED, JobState.FAILED},
    JobState.PRODUCTION_VERIFIED: set(),
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
        if target == JobState.APPROVED and not self._has_passed_evidence("preview_verification"):
            raise ValueError("approval requires passed preview-verification evidence")
        # The evidence for this transition must be checked *before* committing
        # either the new state or the evidence. Earlier/replayed evidence must
        # never silently certify a fresh production verification.
        if target == JobState.PRODUCTION_VERIFIED and not (
            isinstance(evidence, dict)
            and evidence.get("kind") == "production_verification"
            and evidence.get("passed") is True
        ):
            raise ValueError("production verification requires passed production-verification evidence")
        self.state = target
        if evidence is not None:
            self.evidence.append(evidence)

    def _has_passed_evidence(self, kind: str) -> bool:
        return any(item.get("kind") == kind and item.get("passed") is True for item in self.evidence)
