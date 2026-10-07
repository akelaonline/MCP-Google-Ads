from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

READONLY_SCOPE = "https://www.googleapis.com/auth/tagmanager.readonly"


def container_parent(account_id: str) -> str:
    return f"accounts/{account_id}/containers"


def account_path(account_id: str) -> str:
    return f"accounts/{account_id}"


def container_path(account_id: str, container_id: str) -> str:
    return f"accounts/{account_id}/containers/{container_id}"


def workspace_path(account_id: str, container_id: str, workspace_id: str) -> str:
    return f"{container_path(account_id, container_id)}/workspaces/{workspace_id}"


class GoogleTagManagerReadOnly:
    """Thin read-only wrapper over the official Tag Manager API v2."""

    def __init__(self, service: Any) -> None:
        self._service = service

    @classmethod
    def from_env(cls) -> "GoogleTagManagerReadOnly":
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
            scopes=[READONLY_SCOPE],
        )
        service = build("tagmanager", "v2", credentials=credentials, cache_discovery=False)
        return cls(service)

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
