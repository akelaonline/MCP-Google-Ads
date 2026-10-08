from __future__ import annotations


_PURPOSE_EVENT = {
    "lead": "generate_lead",
    "newsletter": "newsletter_signup",
    "signup": "sign_up",
}


def build_installation_steps(opportunities: dict, *, tracking: dict | None = None) -> dict:
    """Conservative install planner: never auto-report unverified conversions."""
    steps: list[dict] = []
    manual: list[dict] = []

    if (tracking or {}).get("ga4_ids"):
        manual.append(
            {
                "kind": "google_tag",
                "reason": "existing_ga4_page_installation_may_duplicate_base_tag",
                "observed_measurement_ids": sorted(set(tracking["ga4_ids"])),
            }
        )
    else:
        steps.append({"kind": "google_tag"})

    for key, event_name in (
        ("whatsapp_links", "whatsapp_click"),
        ("phone_links", "phone_click"),
        ("email_links", "email_click"),
    ):
        if int(opportunities.get(key) or 0) > 0:
            steps.append({"kind": "standard_click", "event_name": event_name})

    # GA4 Enhanced Measurement may already emit file_download.
    if int(opportunities.get("download_links") or 0) > 0:
        manual.append(
            {
                "kind": "file_download",
                "event_name": "file_download",
                "reason": "verify_ga4_enhanced_measurement_to_avoid_duplicate_events",
            }
        )

    # Seeing an HTML form does not prove a successful conversion.
    # Provider callbacks, AJAX completion and backend acceptance differ.
    for form in opportunities.get("form_candidates") or []:
        purpose = form.get("purpose")
        if purpose not in _PURPOSE_EVENT:
            continue
        manual.append(
            {
                "kind": "form_success",
                "event_name": _PURPOSE_EVENT[purpose],
                "provider": form.get("provider"),
                "form_id": form.get("form_id"),
                "page_url": form.get("page_url"),
                "reason": "success_signal_must_be_verified_before_install",
            }
        )

    return {"steps": steps, "manual_review": manual}
