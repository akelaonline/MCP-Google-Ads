from __future__ import annotations

from collections import Counter
from urllib.parse import urlparse


SUPPORTED_PROVIDER_RECIPES = frozenset(
    {
        "contactform7",
        "gravityforms",
        "wpforms",
        "elementor",
        "hubspot",
        "typeform",
        "calendly",
    }
)

_PURPOSE_EVENT = {
    "lead": "generate_lead",
    "newsletter": "newsletter_signup",
    "signup": "sign_up",
}


def build_installation_steps(opportunities: dict) -> dict:
    """Convert audit opportunities into conservative, typed install steps."""
    steps: list[dict] = [{"kind": "google_tag"}]
    manual: list[dict] = []

    for key, event_name in (
        ("whatsapp_links", "whatsapp_click"),
        ("phone_links", "phone_click"),
        ("email_links", "email_click"),
        ("download_links", "file_download"),
    ):
        if int(opportunities.get(key) or 0) > 0:
            steps.append({"kind": "standard_click", "event_name": event_name})

    forms = list(opportunities.get("form_candidates") or [])
    page_form_counts = Counter(str(item.get("page_url") or "") for item in forms)

    target_forms = [
        item
        for item in forms
        if item.get("purpose") in _PURPOSE_EVENT
    ]
    provider_counts = Counter(
        (str(item.get("provider") or ""), _PURPOSE_EVENT[item["purpose"]])
        for item in target_forms
        if item.get("provider")
    )

    seen_provider_steps: set[tuple[str, str]] = set()
    for form in target_forms:
        purpose = form["purpose"]
        event_name = _PURPOSE_EVENT[purpose]
        provider = str(form.get("provider") or "").strip()
        page_url = str(form.get("page_url") or "")
        form_id = str(form.get("form_id") or "").strip() or None
        page_path = urlparse(page_url).path or "/"

        if provider:
            key = (provider, event_name)
            if provider not in SUPPORTED_PROVIDER_RECIPES:
                manual.append(
                    {
                        "kind": "form",
                        "reason": "provider_recipe_not_supported",
                        "provider": provider,
                        "event_name": event_name,
                        "page_url": page_url,
                        "form_id": form_id,
                    }
                )
                continue
            if provider_counts[key] != 1:
                manual.append(
                    {
                        "kind": "form",
                        "reason": "provider_event_scope_is_ambiguous",
                        "provider": provider,
                        "event_name": event_name,
                        "page_url": page_url,
                        "form_id": form_id,
                    }
                )
                continue
            if key not in seen_provider_steps:
                steps.append(
                    {
                        "kind": "provider_form",
                        "provider": provider,
                        "event_name": event_name,
                    }
                )
                seen_provider_steps.add(key)
            continue

        if form_id:
            steps.append(
                {
                    "kind": "native_form",
                    "event_name": event_name,
                    "form_id": form_id,
                    "page_path": page_path,
                }
            )
            continue

        if page_form_counts[page_url] == 1:
            steps.append(
                {
                    "kind": "native_form",
                    "event_name": event_name,
                    "form_id": None,
                    "page_path": page_path,
                }
            )
            continue

        manual.append(
            {
                "kind": "form",
                "reason": "no_stable_form_id_and_multiple_forms_on_page",
                "event_name": event_name,
                "page_url": page_url,
                "form_id": None,
            }
        )

    return {"steps": steps, "manual_review": manual}
