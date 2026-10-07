from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from .settings import MeasurementSettings

READONLY_SCOPE = "https://www.googleapis.com/auth/tagmanager.readonly"
EDIT_CONTAINERS_SCOPE = "https://www.googleapis.com/auth/tagmanager.edit.containers"
EDIT_VERSIONS_SCOPE = "https://www.googleapis.com/auth/tagmanager.edit.containerversions"
PUBLISH_SCOPE = "https://www.googleapis.com/auth/tagmanager.publish"


def account_path(account_id: str) -> str:
    return f"accounts/{account_id}"


def container_path(account_id: str, container_id: str) -> str:
    return f"accounts/{account_id}/containers/{container_id}"


def workspace_path(account_id: str, container_id: str, workspace_id: str) -> str:
    return f"{container_path(account_id, container_id)}/workspaces/{workspace_id}"


def version_path(account_id: str, container_id: str, version_id: str) -> str:
    return f"{container_path(account_id, container_id)}/versions/{version_id}"


def _oauth_service(scopes: list[str]) -> Any:
    client_id = os.getenv("GTM_GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GTM_GOOGLE_CLIENT_SECRET")
    refresh_token = os.getenv("GTM_GOOGLE_REFRESH_TOKEN")
    missing = [
        name
        for name, value in (
            ("GTM_GOOGLE_CLIENT_ID", client_id),
            ("GTM_GOOGLE_CLIENT_SECRET", client_secret),
            ("GTM_GOOGLE_REFRESH_TOKEN", refresh_token),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"missing GTM OAuth configuration: {', '.join(missing)}")

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes,
    )
    return build("tagmanager", "v2", credentials=credentials, cache_discovery=False)


class GoogleTagManagerReadOnly:
    """Thin read-only wrapper over the official Tag Manager API v2."""

    def __init__(self, service: Any) -> None:
        self._service = service

    @classmethod
    def from_env(cls) -> "GoogleTagManagerReadOnly":
        return cls(_oauth_service([READONLY_SCOPE]))

    @staticmethod
    def _paginate(request_factory: Callable[..., Any], response_key: str, **kwargs: Any) -> list[dict]:
        rows: list[dict] = []
        page_token: str | None = None
        while True:
            call_kwargs = dict(kwargs)
            if page_token:
                call_kwargs["pageToken"] = page_token
            response = request_factory(**call_kwargs).execute()
            rows.extend(response.get(response_key, []))
            page_token = response.get("nextPageToken")
            if not page_token:
                return rows

    def list_accounts(self) -> list[dict]:
        return self._paginate(self._service.accounts().list, "account")

    def list_containers(self, account_id: str) -> list[dict]:
        return self._paginate(
            self._service.accounts().containers().list,
            "container",
            parent=account_path(account_id),
        )

    def list_workspaces(self, account_id: str, container_id: str) -> list[dict]:
        return self._paginate(
            self._service.accounts().containers().workspaces().list,
            "workspace",
            parent=container_path(account_id, container_id),
        )

    def list_tags(self, account_id: str, container_id: str, workspace_id: str) -> list[dict]:
        return self._paginate(
            self._service.accounts().containers().workspaces().tags().list,
            "tag",
            parent=workspace_path(account_id, container_id, workspace_id),
        )

    def list_triggers(self, account_id: str, container_id: str, workspace_id: str) -> list[dict]:
        return self._paginate(
            self._service.accounts().containers().workspaces().triggers().list,
            "trigger",
            parent=workspace_path(account_id, container_id, workspace_id),
        )

    def list_variables(self, account_id: str, container_id: str, workspace_id: str) -> list[dict]:
        return self._paginate(
            self._service.accounts().containers().workspaces().variables().list,
            "variable",
            parent=workspace_path(account_id, container_id, workspace_id),
        )

    def list_built_in_variables(self, account_id: str, container_id: str, workspace_id: str) -> list[dict]:
        return self._paginate(
            self._service.accounts().containers().workspaces().built_in_variables().list,
            "builtInVariable",
            parent=workspace_path(account_id, container_id, workspace_id),
        )

    def get_workspace_status(self, account_id: str, container_id: str, workspace_id: str) -> dict:
        return (
            self._service.accounts()
            .containers()
            .workspaces()
            .getStatus(path=workspace_path(account_id, container_id, workspace_id))
            .execute()
        )

    def get_live_version(self, account_id: str, container_id: str) -> dict:
        return (
            self._service.accounts()
            .containers()
            .versions()
            .live(parent=container_path(account_id, container_id))
            .execute()
        )


class GoogleTagManagerWriter(GoogleTagManagerReadOnly):
    """Workspace writer with independent write and publish kill switches."""

    def __init__(
        self,
        service: Any,
        *,
        preview_enabled: bool,
        writes_enabled: bool,
        publish_enabled: bool,
    ) -> None:
        super().__init__(service)
        self._preview_enabled = preview_enabled
        self._writes_enabled = writes_enabled
        self._publish_enabled = publish_enabled

    @classmethod
    def from_env(cls) -> "GoogleTagManagerWriter":
        settings = MeasurementSettings.from_env()
        scopes = [READONLY_SCOPE, EDIT_CONTAINERS_SCOPE, EDIT_VERSIONS_SCOPE]
        if settings.gtm_enable_publish:
            scopes.append(PUBLISH_SCOPE)
        return cls(
            _oauth_service(scopes),
            preview_enabled=settings.gtm_enable_preview,
            writes_enabled=settings.gtm_enable_writes,
            publish_enabled=settings.gtm_enable_publish,
        )

    def _ensure_preview(self) -> None:
        if not self._preview_enabled:
            raise PermissionError("GTM preview is disabled; set GTM_ENABLE_PREVIEW=true to enable quick preview")

    def _ensure_writes(self) -> None:
        if not self._writes_enabled:
            raise PermissionError("GTM writes are disabled; set GTM_ENABLE_WRITES=true to enable workspace mutations")

    def _ensure_publish(self, confirm: bool) -> None:
        self._ensure_writes()
        if not self._publish_enabled:
            raise PermissionError("GTM publish is disabled; set GTM_ENABLE_PUBLISH=true to enable production publish")
        if confirm is not True:
            raise PermissionError("GTM publish requires confirm=true")

    def quick_preview(self, account_id: str, container_id: str, workspace_id: str) -> dict:
        self._ensure_preview()
        return (
            self._service.accounts()
            .containers()
            .workspaces()
            .quick_preview(path=workspace_path(account_id, container_id, workspace_id))
            .execute()
        )

    def create_workspace(self, account_id: str, container_id: str, name: str, description: str = "") -> dict:
        self._ensure_writes()
        body = {"name": name}
        if description:
            body["description"] = description
        return (
            self._service.accounts()
            .containers()
            .workspaces()
            .create(parent=container_path(account_id, container_id), body=body)
            .execute()
        )

    def create_tag(self, account_id: str, container_id: str, workspace_id: str, body: dict) -> dict:
        self._ensure_writes()
        return (
            self._service.accounts()
            .containers()
            .workspaces()
            .tags()
            .create(parent=workspace_path(account_id, container_id, workspace_id), body=body)
            .execute()
        )

    def create_trigger(self, account_id: str, container_id: str, workspace_id: str, body: dict) -> dict:
        self._ensure_writes()
        return (
            self._service.accounts()
            .containers()
            .workspaces()
            .triggers()
            .create(parent=workspace_path(account_id, container_id, workspace_id), body=body)
            .execute()
        )

    def enable_built_in_variables(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        variable_types: list[str],
    ) -> dict:
        self._ensure_writes()
        requested = list(dict.fromkeys(item for item in variable_types if item))
        if not requested:
            return {"builtInVariable": []}
        existing = self.list_built_in_variables(account_id, container_id, workspace_id)
        enabled = {item.get("type") for item in existing}
        missing = [item for item in requested if item not in enabled]
        if not missing:
            return {"builtInVariable": [], "alreadyEnabled": requested}
        return (
            self._service.accounts()
            .containers()
            .workspaces()
            .built_in_variables()
            .create(
                parent=workspace_path(account_id, container_id, workspace_id),
                type=missing,
            )
            .execute()
        )

    def create_variable(self, account_id: str, container_id: str, workspace_id: str, body: dict) -> dict:
        self._ensure_writes()
        return (
            self._service.accounts()
            .containers()
            .workspaces()
            .variables()
            .create(parent=workspace_path(account_id, container_id, workspace_id), body=body)
            .execute()
        )

    def create_version(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        *,
        name: str,
        notes: str = "",
    ) -> dict:
        self._ensure_writes()
        body = {"name": name}
        if notes:
            body["notes"] = notes
        return (
            self._service.accounts()
            .containers()
            .workspaces()
            .create_version(path=workspace_path(account_id, container_id, workspace_id), body=body)
            .execute()
        )

    def publish_version(
        self,
        account_id: str,
        container_id: str,
        version_id: str,
        *,
        confirm: bool,
    ) -> dict:
        self._ensure_publish(confirm)
        return (
            self._service.accounts()
            .containers()
            .versions()
            .publish(path=version_path(account_id, container_id, version_id))
            .execute()
        )
