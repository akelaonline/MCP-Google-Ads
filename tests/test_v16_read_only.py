from __future__ import annotations

import pytest

from google_ads_mcp.errors import GoogleAdsMcpError
from google_ads_mcp.read_only import ReadOnlySafetyProxy


class _Delegate:
    def __init__(self):
        self.cancelled = []

    def propose(self, **kwargs):
        return {"status": "pending_confirmation"}

    def confirm(self, action_id):
        return {"status": "executed", "action_id": action_id}

    def cancel(self, action_id):
        self.cancelled.append(action_id)
        return {"status": "cancelled", "action_id": action_id}

    def list_pending(self):
        return [{"pending_action_id": "abc123"}]


def test_read_only_blocks_new_write_proposals_before_delegate():
    proxy = ReadOnlySafetyProxy(_Delegate())
    with pytest.raises(GoogleAdsMcpError, match="read-only mode"):
        proxy.propose(
            tool_name="update_campaign_budget",
            customer_id="1111111111",
            description="raise budget",
            payload={"new_daily_amount": 100},
            execute=lambda: None,
        )


def test_read_only_blocks_confirmation_of_existing_pending_action():
    proxy = ReadOnlySafetyProxy(_Delegate())
    with pytest.raises(GoogleAdsMcpError, match="cannot be confirmed"):
        proxy.confirm("abc123")


def test_read_only_still_allows_pending_inspection_and_cancellation():
    delegate = _Delegate()
    proxy = ReadOnlySafetyProxy(delegate)

    assert proxy.list_pending() == [{"pending_action_id": "abc123"}]
    assert proxy.cancel("abc123") == {"status": "cancelled", "action_id": "abc123"}
    assert delegate.cancelled == ["abc123"]
