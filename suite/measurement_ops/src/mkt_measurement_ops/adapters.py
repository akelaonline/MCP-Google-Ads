from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .models import SiteTarget


@dataclass(frozen=True, slots=True)
class AuditFinding:
    code: str
    severity: str
    message: str
    evidence: dict[str, Any]


@dataclass(frozen=True, slots=True)
class VerificationResult:
    passed: bool
    checks: tuple[str, ...]
    evidence: dict[str, Any]


class WebAuditAdapter(Protocol):
    def audit(self, site: SiteTarget) -> list[AuditFinding]: ...


class GTMAdapter(Protocol):
    def audit(self, site: SiteTarget) -> list[AuditFinding]: ...
    def prepare_workspace(self, site: SiteTarget, plan: dict[str, Any]) -> dict[str, Any]: ...
    def publish(self, site: SiteTarget, version_id: str, *, confirm: bool) -> dict[str, Any]: ...


class GA4Adapter(Protocol):
    def audit(self, site: SiteTarget) -> list[AuditFinding]: ...
    def verify(self, site: SiteTarget, expected_events: list[str]) -> VerificationResult: ...


class AdsAdapter(Protocol):
    def audit(self, site: SiteTarget) -> list[AuditFinding]: ...


class SiteDeploymentAdapter(Protocol):
    def plan(self, site: SiteTarget, changes: dict[str, Any]) -> dict[str, Any]: ...
    def deploy(self, site: SiteTarget, changes: dict[str, Any], *, confirm: bool) -> dict[str, Any]: ...
