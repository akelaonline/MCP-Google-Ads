from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum


class MeasurementGoal(StrEnum):
    LEAD_FORM = "lead_form"
    WHATSAPP_CLICK = "whatsapp_click"
    PHONE_CLICK = "phone_click"
    EMAIL_CLICK = "email_click"
    FILE_DOWNLOAD = "file_download"
    CTA_CLICK = "cta_click"
    PURCHASE = "purchase"


class ImplementationMode(StrEnum):
    GTM = "gtm"
    SITE_CODE = "site_code"
    HYBRID = "hybrid"


@dataclass(frozen=True, slots=True)
class EventSpec:
    goal: MeasurementGoal
    event_name: str
    implementation: ImplementationMode
    verify: tuple[str, ...]
    notes: str


@dataclass(frozen=True, slots=True)
class MeasurementPlan:
    site_key: str
    events: tuple[EventSpec, ...]
    require_consent_audit: bool = True

    def to_dict(self) -> dict:
        return {
            "site_key": self.site_key,
            "require_consent_audit": self.require_consent_audit,
            "events": [asdict(event) for event in self.events],
        }


STANDARD_EVENTS: dict[MeasurementGoal, EventSpec] = {
    MeasurementGoal.LEAD_FORM: EventSpec(
        goal=MeasurementGoal.LEAD_FORM,
        event_name="generate_lead",
        implementation=ImplementationMode.HYBRID,
        verify=("dataLayer", "ga4_hit"),
        notes="Prefer GTM-native/provider listener. Use site code only when the success state is not observable reliably.",
    ),
    MeasurementGoal.WHATSAPP_CLICK: EventSpec(
        goal=MeasurementGoal.WHATSAPP_CLICK,
        event_name="whatsapp_click",
        implementation=ImplementationMode.GTM,
        verify=("dataLayer", "ga4_hit"),
        notes="Match wa.me, api.whatsapp.com and configured WhatsApp links.",
    ),
    MeasurementGoal.PHONE_CLICK: EventSpec(
        goal=MeasurementGoal.PHONE_CLICK,
        event_name="phone_click",
        implementation=ImplementationMode.GTM,
        verify=("dataLayer", "ga4_hit"),
        notes="Match tel: links.",
    ),
    MeasurementGoal.EMAIL_CLICK: EventSpec(
        goal=MeasurementGoal.EMAIL_CLICK,
        event_name="email_click",
        implementation=ImplementationMode.GTM,
        verify=("dataLayer", "ga4_hit"),
        notes="Match mailto: links.",
    ),
    MeasurementGoal.FILE_DOWNLOAD: EventSpec(
        goal=MeasurementGoal.FILE_DOWNLOAD,
        event_name="file_download",
        implementation=ImplementationMode.GTM,
        verify=("ga4_hit",),
        notes="Avoid duplication when GA4 Enhanced Measurement already tracks the same downloads.",
    ),
    MeasurementGoal.CTA_CLICK: EventSpec(
        goal=MeasurementGoal.CTA_CLICK,
        event_name="cta_click",
        implementation=ImplementationMode.GTM,
        verify=("dataLayer", "ga4_hit"),
        notes="Only create explicit CTA events for business-significant actions.",
    ),
    MeasurementGoal.PURCHASE: EventSpec(
        goal=MeasurementGoal.PURCHASE,
        event_name="purchase",
        implementation=ImplementationMode.HYBRID,
        verify=("dataLayer", "ga4_hit", "transaction_id"),
        notes="Requires deterministic transaction/value/currency data; site/backend instrumentation may be required.",
    ),
}


def build_plan(site_key: str, goals: list[str], *, require_consent_audit: bool = True) -> MeasurementPlan:
    normalized: list[MeasurementGoal] = []
    seen: set[MeasurementGoal] = set()
    for raw in goals:
        goal = MeasurementGoal(raw)
        if goal not in seen:
            normalized.append(goal)
            seen.add(goal)

    events = tuple(STANDARD_EVENTS[goal] for goal in normalized)
    return MeasurementPlan(site_key=site_key, events=events, require_consent_audit=require_consent_audit)
