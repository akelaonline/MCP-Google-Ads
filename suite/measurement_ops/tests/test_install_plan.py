from mkt_measurement_ops.install_plan import build_installation_steps


def test_standard_clicks_become_typed_steps() -> None:
    plan = build_installation_steps(
        {
            "whatsapp_links": 2,
            "phone_links": 1,
            "email_links": 0,
            "download_links": 3,
            "form_candidates": [],
        }
    )

    events = [step.get("event_name") for step in plan["steps"]]
    assert "whatsapp_click" in events
    assert "phone_click" in events
    assert "file_download" in events
    assert plan["manual_review"] == []


def test_lead_form_with_stable_id_is_safe_native_step() -> None:
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

    step = next(item for item in plan["steps"] if item["kind"] == "native_form")
    assert step["event_name"] == "generate_lead"
    assert step["form_id"] == "contact-form"


def test_unscoped_form_on_multi_form_page_requires_manual_review() -> None:
    plan = build_installation_steps(
        {
            "form_candidates": [
                {
                    "page_url": "https://example.com/",
                    "form_id": None,
                    "purpose": "lead",
                    "provider": None,
                },
                {
                    "page_url": "https://example.com/",
                    "form_id": None,
                    "purpose": "search",
                    "provider": None,
                },
            ]
        }
    )

    assert not any(step["kind"] == "native_form" for step in plan["steps"])
    assert plan["manual_review"][0]["reason"] == "no_stable_form_id_and_multiple_forms_on_page"


def test_ambiguous_provider_forms_do_not_auto_install() -> None:
    plan = build_installation_steps(
        {
            "form_candidates": [
                {
                    "page_url": "https://example.com/a",
                    "form_id": "1",
                    "purpose": "lead",
                    "provider": "contactform7",
                },
                {
                    "page_url": "https://example.com/b",
                    "form_id": "2",
                    "purpose": "lead",
                    "provider": "contactform7",
                },
            ]
        }
    )

    assert not any(step["kind"] == "provider_form" for step in plan["steps"])
    assert len(plan["manual_review"]) == 2
