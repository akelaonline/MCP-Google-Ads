from __future__ import annotations

from enum import StrEnum


class RiskLevel(StrEnum):
    READ = "read"
    STANDARD = "standard"
    SENSITIVE = "sensitive"
    DESTRUCTIVE = "destructive"


READ_ACTIONS = {
    "audit_site",
    "audit_gtm",
    "audit_ga4",
    "audit_ads",
    "verify_measurement",
    "list_sites",
    "get_site",
}

SENSITIVE_ACTIONS = {
    "publish_gtm_version",
    "deploy_site",
    "change_consent_configuration",
    "create_ads_conversion_action",
}

DESTRUCTIVE_ACTIONS = {
    "delete_gtm_tag",
    "delete_gtm_trigger",
    "delete_gtm_variable",
    "delete_gtm_container",
    "rollback_site",
}


def classify_action(action: str) -> RiskLevel:
    normalized = action.strip().lower()
    if normalized in READ_ACTIONS:
        return RiskLevel.READ
    if normalized in DESTRUCTIVE_ACTIONS:
        return RiskLevel.DESTRUCTIVE
    if normalized in SENSITIVE_ACTIONS:
        return RiskLevel.SENSITIVE
    return RiskLevel.STANDARD


def requires_confirmation(action: str) -> bool:
    return classify_action(action) in {RiskLevel.SENSITIVE, RiskLevel.DESTRUCTIVE}
