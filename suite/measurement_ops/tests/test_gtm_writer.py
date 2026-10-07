import pytest

from mkt_measurement_ops.gtm import GoogleTagManagerWriter


class _Request:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _Versions:
    def __init__(self):
        self.calls = []

    def publish(self, **kwargs):
        self.calls.append(kwargs)
        return _Request({"containerVersion": {"containerVersionId": "7"}})


class _Containers:
    def __init__(self):
        self._versions = _Versions()

    def versions(self):
        return self._versions


class _Accounts:
    def __init__(self):
        self._containers = _Containers()

    def containers(self):
        return self._containers


class _Service:
    def __init__(self):
        self._accounts = _Accounts()

    def accounts(self):
        return self._accounts


def test_workspace_writes_fail_closed() -> None:
    writer = GoogleTagManagerWriter(object(), preview_enabled=False, writes_enabled=False, publish_enabled=False)
    with pytest.raises(PermissionError, match="writes are disabled"):
        writer.create_workspace("1", "2", "MCP Test")


def test_publish_requires_separate_publish_gate() -> None:
    writer = GoogleTagManagerWriter(object(), preview_enabled=False, writes_enabled=True, publish_enabled=False)
    with pytest.raises(PermissionError, match="publish is disabled"):
        writer.publish_version("1", "2", "7", confirm=True)


def test_publish_requires_explicit_confirmation() -> None:
    writer = GoogleTagManagerWriter(object(), preview_enabled=False, writes_enabled=True, publish_enabled=True)
    with pytest.raises(PermissionError, match="confirm=true"):
        writer.publish_version("1", "2", "7", confirm=False)


def test_confirmed_publish_calls_exact_version_path() -> None:
    service = _Service()
    writer = GoogleTagManagerWriter(service, preview_enabled=False, writes_enabled=True, publish_enabled=True)
    result = writer.publish_version("1", "2", "7", confirm=True)

    assert result["containerVersion"]["containerVersionId"] == "7"
    assert service._accounts._containers._versions.calls == [
        {"path": "accounts/1/containers/2/versions/7"}
    ]


def test_preview_requires_preview_gate() -> None:
    writer = GoogleTagManagerWriter(object(), preview_enabled=False, writes_enabled=False, publish_enabled=False)
    with pytest.raises(PermissionError, match="preview is disabled"):
        writer.quick_preview("1", "2", "3")
