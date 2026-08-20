from __future__ import annotations

import threading
import time
from types import SimpleNamespace

from google_ads_mcp import server


class _FakeMcp:
    def __init__(self):
        self.tools = {}

    def tool(self, function=None, *args, **kwargs):
        def register(func):
            self.tools[kwargs.get("name") or func.__name__] = func
            return func

        if function is None:
            return register
        return register(function)


class _FakeSafety:
    def list_pending(self):
        return []

    def confirm(self, action_id: str):
        return {"confirmed": action_id}

    def cancel(self, action_id: str):
        return {"cancelled": action_id}


class _FakeAudit:
    def recent(self, limit=20):
        return []

    def by_action_id(self, action_id):
        return []


def test_confirm_waits_for_pending_action_control_lock():
    mcp = _FakeMcp()
    ctx = SimpleNamespace(safety=_FakeSafety(), audit=_FakeAudit())
    server._register_safety_tools(mcp, ctx)

    completed = threading.Event()
    result = {}

    def run_confirm():
        result.update(mcp.tools["confirm_pending_action"]("abc123"))
        completed.set()

    server._PENDING_ACTION_CONTROL_LOCK.acquire()
    try:
        thread = threading.Thread(target=run_confirm)
        thread.start()
        time.sleep(0.03)
        assert completed.is_set() is False
    finally:
        server._PENDING_ACTION_CONTROL_LOCK.release()

    thread.join(timeout=1)
    assert completed.is_set() is True
    assert result == {"confirmed": "abc123"}


def test_cancel_and_list_use_same_control_lock():
    mcp = _FakeMcp()
    ctx = SimpleNamespace(safety=_FakeSafety(), audit=_FakeAudit())
    server._register_safety_tools(mcp, ctx)

    assert mcp.tools["cancel_pending_action"]("abc123") == {"cancelled": "abc123"}
    assert mcp.tools["list_pending_actions"]() == {"pending_actions": []}
