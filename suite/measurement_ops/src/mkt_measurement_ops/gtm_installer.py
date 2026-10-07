from __future__ import annotations

from typing import Any

from .gtm import GoogleTagManagerWriter
from .gtm_builders import (
    build_ga4_event_tag,
    build_custom_event_trigger,
    build_custom_html_tag,
    build_form_submit_trigger,
    build_google_tag,
    build_pageview_trigger,
    build_standard_click_bundle,
    provider_listener_html,
)


class GTMDriftError(RuntimeError):
    pass


def _named(rows: list[dict], name: str) -> dict | None:
    return next((row for row in rows if row.get("name") == name), None)


def _scope_label(*parts: str | None) -> str:
    values = [str(part).strip().replace("/", " ") for part in parts if part and str(part).strip()]
    return " - ".join(values) if values else "All Native Forms"


class GTMTrackingInstaller:
    """Typed, idempotent installer for the v1 standard measurement set."""

    def __init__(self, client: GoogleTagManagerWriter) -> None:
        self.client = client

    def _ensure_trigger(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        body: dict[str, Any],
    ) -> tuple[dict, bool]:
        existing = _named(self.client.list_triggers(account_id, container_id, workspace_id), body["name"])
        if existing is not None:
            if existing.get("type") != body.get("type"):
                raise GTMDriftError(
                    f"trigger {body['name']!r} exists with type {existing.get('type')!r}, expected {body.get('type')!r}"
                )
            for field in ("filter", "customEventFilter", "waitForTags", "checkValidation"):
                if field in body and existing.get(field) != body.get(field):
                    raise GTMDriftError(f"trigger {body['name']!r} has configuration drift in {field}")
            if not existing.get("triggerId"):
                raise GTMDriftError(f"trigger {body['name']!r} has no triggerId")
            return existing, False
        created = self.client.create_trigger(account_id, container_id, workspace_id, body)
        if not created.get("triggerId"):
            raise GTMDriftError(f"created trigger {body['name']!r} returned no triggerId")
        return created, True

    def _ensure_tag(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        body: dict[str, Any],
    ) -> tuple[dict, bool]:
        existing = _named(self.client.list_tags(account_id, container_id, workspace_id), body["name"])
        if existing is not None:
            if existing.get("type") != body.get("type"):
                raise GTMDriftError(
                    f"tag {body['name']!r} exists with type {existing.get('type')!r}, expected {body.get('type')!r}"
                )
            expected_triggers = set(body.get("firingTriggerId", []))
            actual_triggers = set(existing.get("firingTriggerId", []))
            if expected_triggers and expected_triggers != actual_triggers:
                raise GTMDriftError(
                    f"tag {body['name']!r} trigger linkage drift: {sorted(actual_triggers)} != {sorted(expected_triggers)}"
                )
            if "parameter" in body and existing.get("parameter") != body.get("parameter"):
                raise GTMDriftError(f"tag {body['name']!r} has parameter drift")
            return existing, False
        return self.client.create_tag(account_id, container_id, workspace_id, body), True

    def install_google_tag(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        *,
        tag_id: str,
    ) -> dict:
        trigger_body = build_pageview_trigger()
        trigger, trigger_created = self._ensure_trigger(account_id, container_id, workspace_id, trigger_body)
        tag_body = build_google_tag(
            name=f"Google tag - {tag_id}",
            tag_id=tag_id,
            firing_trigger_id=trigger["triggerId"],
        )
        tag, tag_created = self._ensure_tag(account_id, container_id, workspace_id, tag_body)
        return {
            "trigger": trigger,
            "tag": tag,
            "created": {"trigger": trigger_created, "tag": tag_created},
        }

    def install_standard_click_event(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        *,
        event_name: str,
        measurement_id: str,
    ) -> dict:
        bundle = build_standard_click_bundle(event_name, measurement_id)
        builtins = self.client.enable_built_in_variables(
            account_id,
            container_id,
            workspace_id,
            bundle["required_built_in_variables"],
        )
        trigger, trigger_created = self._ensure_trigger(
            account_id,
            container_id,
            workspace_id,
            bundle["trigger"],
        )
        tag_factory = bundle["tag_factory"]
        tag_body = build_ga4_event_tag(
            name=tag_factory["name"],
            measurement_id=tag_factory["measurement_id"],
            event_name=tag_factory["event_name"],
            firing_trigger_id=trigger["triggerId"],
            event_parameters=tag_factory["event_parameters"],
        )
        tag, tag_created = self._ensure_tag(account_id, container_id, workspace_id, tag_body)
        return {
            "event_name": event_name,
            "built_in_variables": builtins,
            "trigger": trigger,
            "tag": tag,
            "created": {"trigger": trigger_created, "tag": tag_created},
        }


    def install_native_form_event(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        *,
        measurement_id: str,
        event_name: str = "generate_lead",
        form_id: str | None = None,
        page_path: str | None = None,
    ) -> dict:
        builtins = {"builtInVariable": []}
        if form_id:
            builtins = self.client.enable_built_in_variables(
                account_id,
                container_id,
                workspace_id,
                ["formId"],
            )
        scope = _scope_label(form_id, page_path)
        trigger_body = build_form_submit_trigger(
            name=f"MKT - {event_name} - {scope}",
            form_id=form_id,
            page_path=page_path,
        )
        trigger, trigger_created = self._ensure_trigger(account_id, container_id, workspace_id, trigger_body)
        tag_body = build_ga4_event_tag(
            name=f"GA4 - Event - {event_name} - Native - {scope}",
            measurement_id=measurement_id,
            event_name=event_name,
            firing_trigger_id=trigger["triggerId"],
        )
        tag, tag_created = self._ensure_tag(account_id, container_id, workspace_id, tag_body)
        return {
            "event_name": event_name,
            "built_in_variables": builtins,
            "trigger": trigger,
            "tag": tag,
            "created": {"trigger": trigger_created, "tag": tag_created},
        }

    def install_custom_event(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        *,
        measurement_id: str,
        data_layer_event: str,
        ga4_event_name: str,
    ) -> dict:
        trigger_body = build_custom_event_trigger(
            name=f"MKT - Custom Event - {data_layer_event}",
            event_name=data_layer_event,
        )
        trigger, trigger_created = self._ensure_trigger(account_id, container_id, workspace_id, trigger_body)
        tag_body = build_ga4_event_tag(
            name=f"GA4 - Event - {ga4_event_name} - Source - {data_layer_event}",
            measurement_id=measurement_id,
            event_name=ga4_event_name,
            firing_trigger_id=trigger["triggerId"],
        )
        tag, tag_created = self._ensure_tag(account_id, container_id, workspace_id, tag_body)
        return {
            "data_layer_event": data_layer_event,
            "ga4_event_name": ga4_event_name,
            "trigger": trigger,
            "tag": tag,
            "created": {"trigger": trigger_created, "tag": tag_created},
        }

    def install_provider_form_event(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        *,
        provider: str,
        measurement_id: str,
        event_name: str = "generate_lead",
    ) -> dict:
        all_pages, all_pages_created = self._ensure_trigger(
            account_id,
            container_id,
            workspace_id,
            build_pageview_trigger(),
        )
        listener_body = build_custom_html_tag(
            name=f"MKT - Listener - {provider} - {event_name}",
            html=provider_listener_html(provider, event_name),
            firing_trigger_id=all_pages["triggerId"],
        )
        listener, listener_created = self._ensure_tag(
            account_id,
            container_id,
            workspace_id,
            listener_body,
        )
        event_result = self.install_custom_event(
            account_id,
            container_id,
            workspace_id,
            measurement_id=measurement_id,
            data_layer_event=event_name,
            ga4_event_name=event_name,
        )
        return {
            "provider": provider,
            "listener": listener,
            "event": event_result,
            "created": {
                "all_pages_trigger": all_pages_created,
                "listener": listener_created,
                "event_trigger": event_result["created"]["trigger"],
                "event_tag": event_result["created"]["tag"],
            },
        }
