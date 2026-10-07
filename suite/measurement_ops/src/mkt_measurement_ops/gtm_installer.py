from __future__ import annotations

from typing import Any

from .gtm import GoogleTagManagerWriter
from .gtm_builders import (
    build_ga4_event_tag,
    build_google_tag,
    build_pageview_trigger,
    build_standard_click_bundle,
)


class GTMDriftError(RuntimeError):
    pass


def _named(rows: list[dict], name: str) -> dict | None:
    return next((row for row in rows if row.get("name") == name), None)


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
