from mkt_measurement_ops.planner import ImplementationMode, build_plan


def test_standard_lead_plan_is_hybrid_and_deduplicated() -> None:
    plan = build_plan("cambridge", ["lead_form", "whatsapp_click", "lead_form"])
    assert [event.event_name for event in plan.events] == ["generate_lead", "whatsapp_click"]
    assert plan.events[0].implementation == ImplementationMode.HYBRID
    assert plan.require_consent_audit is True
