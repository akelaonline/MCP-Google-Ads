from __future__ import annotations

import json
import re
from typing import Any


def tpl(key: str, value: str) -> dict[str, Any]:
    return {"type": "template", "key": key, "value": value}


def boolean(key: str, value: bool) -> dict[str, Any]:
    return {"type": "boolean", "key": key, "value": str(value).lower()}


def sanitize_name(name: str) -> str:
    cleaned = re.sub(r"[<>:]", " ", name or "")
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned or "Unnamed"


def condition(
    variable: str,
    operator: str,
    value: str,
    *,
    ignore_case: bool = False,
) -> dict[str, Any]:
    allowed = {"equals", "contains", "startsWith", "endsWith", "matchRegex"}
    if operator not in allowed:
        raise ValueError(f"unsupported GTM condition operator: {operator}")
    params = [tpl("arg0", variable), tpl("arg1", value)]
    if ignore_case:
        params.append(boolean("ignore_case", True))
    return {"type": operator, "parameter": params}


def build_pageview_trigger(name: str = "MKT - All Pages") -> dict:
    return {"name": sanitize_name(name), "type": "pageview"}


def build_link_click_trigger(
    *,
    name: str,
    url_value: str,
    operator: str,
    ignore_case: bool = False,
) -> dict:
    return {
        "name": sanitize_name(name),
        "type": "linkClick",
        "filter": [
            condition("{{Click URL}}", operator, url_value, ignore_case=ignore_case),
        ],
    }


def build_custom_event_trigger(*, name: str, event_name: str) -> dict:
    event_name = event_name.strip()
    if not event_name:
        raise ValueError("event_name is required")
    return {
        "name": sanitize_name(name),
        "type": "customEvent",
        "customEventFilter": [condition("{{_event}}", "equals", event_name)],
    }


def build_form_submit_trigger(
    *,
    name: str,
    form_id: str | None = None,
    page_path: str | None = None,
) -> dict:
    trigger: dict[str, Any] = {
        "name": sanitize_name(name),
        "type": "formSubmission",
        "waitForTags": {"type": "boolean", "value": "false"},
        "checkValidation": {"type": "boolean", "value": "false"},
    }
    filters: list[dict[str, Any]] = []
    if form_id:
        filters.append(condition("{{Form ID}}", "equals", form_id))
    if page_path:
        filters.append(condition("{{Page Path}}", "contains", page_path))
    if filters:
        trigger["filter"] = filters
    return trigger


def build_google_tag(*, name: str, tag_id: str, firing_trigger_id: str) -> dict:
    tag_id = tag_id.strip()
    if not re.match(r"^(G|GT|AW)-[A-Z0-9-]+$", tag_id, re.IGNORECASE):
        raise ValueError("tag_id must be a Google tag ID such as G-XXXX, GT-XXXX or AW-XXXX")
    return {
        "name": sanitize_name(name),
        "type": "googtag",
        "parameter": [tpl("tagId", tag_id)],
        "firingTriggerId": [firing_trigger_id],
    }


def build_ga4_event_tag(
    *,
    name: str,
    measurement_id: str,
    event_name: str,
    firing_trigger_id: str,
    event_parameters: list[dict[str, str]] | None = None,
) -> dict:
    if not re.match(r"^G-[A-Z0-9]+$", measurement_id.strip(), re.IGNORECASE):
        raise ValueError("measurement_id must look like G-XXXXXXXXXX")
    if not event_name.strip():
        raise ValueError("event_name is required")

    parameters: list[dict[str, Any]] = [
        {"type": "tagReference", "key": "measurementId", "value": ""},
        tpl("measurementIdOverride", measurement_id.strip()),
        tpl("eventName", event_name.strip()),
        boolean("sendEcommerceData", False),
    ]
    params = event_parameters or [
        {"name": "page_url", "value": "{{Page URL}}"},
        {"name": "previous_page", "value": "{{Referrer}}"},
    ]
    if params:
        parameters.append(
            {
                "type": "list",
                "key": "eventSettingsTable",
                "list": [
                    {
                        "type": "map",
                        "map": [
                            tpl("parameter", item["name"]),
                            tpl("parameterValue", item["value"]),
                        ],
                    }
                    for item in params
                ],
            }
        )
    return {
        "name": sanitize_name(name),
        "type": "gaawe",
        "parameter": parameters,
        "firingTriggerId": [firing_trigger_id],
    }


def build_custom_html_tag(*, name: str, html: str, firing_trigger_id: str) -> dict:
    if not html.strip():
        raise ValueError("custom HTML cannot be empty")
    return {
        "name": sanitize_name(name),
        "type": "html",
        "parameter": [
            tpl("html", html),
            boolean("supportDocumentWrite", False),
        ],
        "firingTriggerId": [firing_trigger_id],
    }


def provider_listener_html(provider: str, event_name: str) -> str:
    event = json.dumps(event_name)
    scripts = {
        "contactform7": (
            f'<script>(function(){{window.dataLayer=window.dataLayer||[];'
            f'document.addEventListener("wpcf7mailsent",function(e){{'
            f'window.dataLayer.push({{event:{event},form_id:e.detail&&e.detail.contactFormId}});'
            f'}},false);}})();</script>'
        ),
        "gravityforms": (
            f'<script>(function(){{window.dataLayer=window.dataLayer||[];if(!window.jQuery)return;'
            f'jQuery(document).on("gform_confirmation_loaded",function(e,formId){{'
            f'window.dataLayer.push({{event:{event},form_id:formId}});}});}})();</script>'
        ),
        "wpforms": (
            f'<script>(function(){{window.dataLayer=window.dataLayer||[];var fired=0;'
            f'var push=function(el){{if(fired)return;fired=1;setTimeout(function(){{fired=0;}},50);'
            f'window.dataLayer.push({{event:{event},form_id:el&&el.getAttribute&&el.getAttribute("data-formid")}});}};'
            f'if(window.jQuery){{jQuery(document).on("wpformsAjaxSubmitSuccess",function(e){{push(e&&e.target);}});}}'
            f'document.addEventListener("wpformsAjaxSubmitSuccess",function(e){{push(e&&e.target);}},false);}})();</script>'
        ),
        "elementor": (
            f'<script>(function(){{window.dataLayer=window.dataLayer||[];if(!window.jQuery)return;'
            f'jQuery(document).on("submit_success",function(){{window.dataLayer.push({{event:{event}}});}});}})();</script>'
        ),
        "hubspot": (
            f'<script>(function(){{window.dataLayer=window.dataLayer||[];'
            f'window.addEventListener("message",function(e){{var d=e&&e.data;'
            f'var u;try{{u=new URL(e.origin);}}catch(_){{return;}}'
            f'if(u.protocol!=="https:"||!(u.hostname==="calendly.com"||u.hostname.endsWith(".calendly.com")))return;'
            f'var u;try{{u=new URL(e.origin);}}catch(_){{return;}}'
            f'if(u.protocol!=="https:"||!(u.hostname==="typeform.com"||u.hostname.endsWith(".typeform.com")))return;'
            f'var u;try{{u=new URL(e.origin);}}catch(_){{return;}}'
            f'if(u.protocol!=="https:"||!(u.hostname==="hsforms.com"||u.hostname.endsWith(".hsforms.com")||u.hostname==="hubspot.com"||u.hostname.endsWith(".hubspot.com")))return;'
            f'if(d&&d.type==="hsFormCallback"&&d.eventName==="onFormSubmitted"){{'
            f'window.dataLayer.push({{event:{event},hs_form_id:d.id}});}}}});}})();</script>'
        ),
        "typeform": (
            f'<script>(function(){{window.dataLayer=window.dataLayer||[];'
            f'window.addEventListener("message",function(e){{var d=e&&e.data;'
            f'if(d&&d.type==="form-submit"){{window.dataLayer.push({{event:{event},typeform_id:d.formId}});}}}});}})();</script>'
        ),
        "calendly": (
            f'<script>(function(){{window.dataLayer=window.dataLayer||[];'
            f'window.addEventListener("message",function(e){{var d=e&&e.data;'
            f'if(d&&d.event==="calendly.event_scheduled"){{window.dataLayer.push({{event:{event}}});}}}});}})();</script>'
        ),
    }
    try:
        return scripts[provider]
    except KeyError as exc:
        raise ValueError(f"unsupported form provider listener: {provider}") from exc


STANDARD_CLICK_EVENTS: dict[str, dict[str, Any]] = {
    "whatsapp_click": {
        "trigger_name": "MKT - WhatsApp Click",
        "tag_name": "GA4 - Event - WhatsApp Click",
        "operator": "matchRegex",
        "value": r"(wa\.me|api\.whatsapp\.com)",
        "ignore_case": True,
    },
    "phone_click": {
        "trigger_name": "MKT - Phone Click",
        "tag_name": "GA4 - Event - Phone Click",
        "operator": "startsWith",
        "value": "tel:",
        "ignore_case": True,
    },
    "email_click": {
        "trigger_name": "MKT - Email Click",
        "tag_name": "GA4 - Event - Email Click",
        "operator": "startsWith",
        "value": "mailto:",
        "ignore_case": True,
    },
    "file_download": {
        "trigger_name": "MKT - File Download",
        "tag_name": "GA4 - Event - File Download",
        "operator": "matchRegex",
        "value": r"\.(pdf|zip|docx?|xlsx?|pptx?|csv|rar|7z|mp4|mp3)(?:[?#]|$)",
        "ignore_case": True,
    },
}


def build_standard_click_bundle(event_name: str, measurement_id: str) -> dict:
    try:
        spec = STANDARD_CLICK_EVENTS[event_name]
    except KeyError as exc:
        raise ValueError(f"unsupported standard click event: {event_name}") from exc

    trigger = build_link_click_trigger(
        name=spec["trigger_name"],
        url_value=spec["value"],
        operator=spec["operator"],
        ignore_case=spec["ignore_case"],
    )
    return {
        "event_name": event_name,
        "required_built_in_variables": ["clickUrl"],
        "trigger": trigger,
        "tag_factory": {
            "name": spec["tag_name"],
            "measurement_id": measurement_id,
            "event_name": event_name,
            "event_parameters": [
                {"name": "click_url", "value": "{{Click URL}}"},
                {"name": "page_url", "value": "{{Page URL}}"},
                {"name": "previous_page", "value": "{{Referrer}}"},
            ],
        },
    }
