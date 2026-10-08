from mkt_measurement_ops.install_plan import build_installation_steps


def test_only_standard_non_download_clicks_auto_install() -> None:
    plan = build_installation_steps(
        {
            "whatsapp_links": 2,
            "phone_links": 1,
            "email_links": 1,
            "download_links": 3,
            "form_candidates": [],
        }
    )
    events = [step.get("event_name") for step in plan["steps"]]
    assert "whatsapp_click" in events
    assert "phone_click" in events
    assert "email_click" in events
    assert "file_download" not in events
    assert plan["manual_review"][0]["reason"] == (
        "verify_ga4_enhanced_measurement_to_avoid_duplicate_events"
    )


def test_lead_with_stable_id_still_requires_success_validation() -> None:
    plan = build_installation_steps(
        {
            "form_candidates": [
                {
                    "page_url": "https://example.com/contact",
                    "form_id": "contact-form",
                    "purpose": "lead",
                    "provider": None,
                }
            ]
        }
    )
    assert not any(step["kind"] == "native_form" for step in plan["steps"])
    assert plan["manual_review"][0]["event_name"] == "generate_lead"
    assert plan["manual_review"][0]["reason"] == (
        "success_signal_must_be_verified_before_install"
    )


def test_search_and_login_forms_never_become_auto_conversions() -> None:
    plan = build_installation_steps(
        {
            "form_candidates": [
                {"purpose": "login", "page_url": "https://example.com/login"},
                {"purpose": "search", "page_url": "https://example.com"},
            ]
        }
    )
    assert plan["steps"] == [{"kind": "google_tag"}]
    assert plan["manual_review"] == []


def test_provider_forms_require_success_signal_validation() -> None:
    plan = build_installation_steps(
        {
            "form_candidates": [
                {
                    "page_url": "https://example.com/contact",
                    "form_id": "1",
                    "purpose": "lead",
                    "provider": "contactform7",
                }
            ]
        }
    )
    assert not any(step["kind"] == "provider_form" for step in plan["steps"])
    assert plan["manual_review"][0]["provider"] == "contactform7"
    assert plan["manual_review"][0]["reason"] == (
        "success_signal_must_be_verified_before_install"
    )



def test_existing_ga4_page_tag_blocks_automatic_base_google_tag() -> None:
    plan = build_installation_steps(
        {"whatsapp_links": 1, "form_candidates": []},
        tracking={"ga4_ids": ["G-ABC123"]},
    )
    assert not any(step["kind"] == "google_tag" for step in plan["steps"])
    assert any(step.get("event_name") == "whatsapp_click" for step in plan["steps"])
    assert plan["manual_review"][0]["reason"] == (
        "existing_ga4_page_installation_may_duplicate_base_tag"
    )
