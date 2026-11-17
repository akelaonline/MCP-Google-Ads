"""READ_ONLY must reject write tools before building a client or authenticating.

Before this change a write tool such as ``create_campaign_budget`` built the
GoogleAdsClient (which refreshes the OAuth token at construction) *before*
``ctx.safety.propose`` blocked it, so a read-only rejection still talked to Google
OAuth. These tests build the real server and prove the early gate.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gen_write_tools

from google_ads_mcp import invocation
from google_ads_mcp.errors import GoogleAdsMcpError
from google_ads_mcp.write_tools import WRITE_TOOLS

# Verb-named tools reviewed by hand: they never reach SafetyLayer.propose.
_REVIEWED_NON_WRITE_VERB_TOOLS = {
    "create_local_campaign",  # retired by Google: returns guidance
    "create_smart_campaign",  # retired by Google: returns guidance
    "create_video_ad",  # legacy compatibility endpoint: never mutates
    "fetch_google_ads_incentives",  # read
    "fetch_google_ads_incentives_full",  # read
    "cancel_pending_action",  # cleanup stays available in read-only mode
}
_WRITE_VERBS = (
    "create_",
    "update_",
    "remove_",
    "add_",
    "set_",
    "attach_",
    "apply_",
    "upload_",
    "submit_",
    "bulk_",
    "cancel_",
    "accept_",
    "decline_",
    "dismiss_",
    "invite_",
    "enable_",
    "end_",
    "graduate_",
    "promote_",
    "schedule_",
    "move_",
    "unlink",
    "reject_",
    "revoke_",
    "resolve_",
    "retract_",
    "restate_",
    "rename_",
    "regenerate_",
    "replace_",
    "append_",
    "assign_",
    "exclude_",
    "insert_",
    "provide_",
    "start_",
    "delete_",
    "request_",
    "fetch_",
)


def test_manifest_matches_sources():
    write, _ = gen_write_tools.classify()
    assert gen_write_tools.render(write) == (
        Path(gen_write_tools.PKG / "write_tools.py").read_text(encoding="utf-8")
    ), "write_tools.py drifted: run python scripts/gen_write_tools.py"
    assert set(WRITE_TOOLS) == write


def test_every_verb_named_tool_is_classified_or_reviewed():
    write, allt = gen_write_tools.classify()
    unclassified = {
        n for n in allt if n.startswith(_WRITE_VERBS) and n not in write
    } - _REVIEWED_NON_WRITE_VERB_TOOLS
    assert not unclassified, (
        f"verb-named tools not reaching propose: {sorted(unclassified)}"
    )
    assert "confirm_pending_action" in WRITE_TOOLS
    assert "cancel_pending_action" not in WRITE_TOOLS
    assert "list_pending_actions" not in WRITE_TOOLS


def _build(monkeypatch, tmp_path, read_only: bool):
    for key, value in {
        "GOOGLE_ADS_MCP_READ_ONLY": "true" if read_only else "false",
        "GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS": "1234567890",
        "GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST": "true",
        "GOOGLE_ADS_MCP_AUDIT_DB": str(tmp_path / "audit.db"),
        "GOOGLE_ADS_CLIENT_ID": "decoy.apps.googleusercontent.com",
        "GOOGLE_ADS_CLIENT_SECRET": "decoy",
        "GOOGLE_ADS_REFRESH_TOKEN": "decoy",
    }.items():
        monkeypatch.setenv(key, value)
    from google_ads_mcp.server import build_server

    return build_server()


def _tripwires():
    """Patch every way a client could be built or a token refreshed."""
    import google.auth.transport.requests  # noqa: F401
    from google.ads.googleads.client import GoogleAdsClient
    from google.oauth2 import credentials as oauth_credentials

    return (
        mock.patch.object(
            GoogleAdsClient,
            "load_from_dict",
            side_effect=AssertionError("client built"),
        ),
        mock.patch.object(
            oauth_credentials.Credentials,
            "refresh",
            side_effect=AssertionError("oauth refresh attempted"),
        ),
    )


def test_all_write_tools_rejected_before_client_or_auth(monkeypatch, tmp_path):
    _build(monkeypatch, tmp_path, read_only=True)
    build, refresh = _tripwires()
    with build as load, refresh as refresh_mock:
        for name in sorted(WRITE_TOOLS):
            function = invocation._TOOL_REGISTRY[name]
            with pytest.raises(GoogleAdsMcpError, match="read-only"):
                function()  # rejected before argument binding or the tool body
        assert load.call_count == 0
        assert refresh_mock.call_count == 0


def _call(server, name, arguments):
    """Call one tool through the real FastMCP server (sync wrapper)."""
    from fastmcp import Client

    async def go():
        async with Client(server) as client:
            return await client.call_tool(name, arguments)

    return asyncio.run(go())


_BUDGET = {"customer_id": "1234567890", "name": "x", "daily_amount": 1.0}


def test_write_rejected_through_real_fastmcp_without_client(monkeypatch, tmp_path):
    from fastmcp.exceptions import ToolError

    server = _build(monkeypatch, tmp_path, read_only=True)
    build, refresh = _tripwires()
    with build as load, refresh as refresh_mock:
        with pytest.raises(ToolError, match="read-only"):
            _call(server, "create_campaign_budget", _BUDGET)
        with pytest.raises(ToolError, match="read-only"):
            _call(server, "confirm_pending_action", {"action_id": "abc"})
        assert load.call_count == 0
        assert refresh_mock.call_count == 0


def test_read_and_cleanup_tools_still_work_in_read_only(monkeypatch, tmp_path):
    server = _build(monkeypatch, tmp_path, read_only=True)
    build, refresh = _tripwires()
    with build as load, refresh:
        result = _call(server, "list_pending_actions", {})
        assert "pending_actions" in str(result)
        _call(server, "get_recent_audit_log", {"limit": 1})
        assert load.call_count == 0


def test_read_tools_still_reach_the_client_in_read_only(monkeypatch, tmp_path):
    """The early gate must not over-block reads: they still build the client."""
    from fastmcp.exceptions import ToolError

    server = _build(monkeypatch, tmp_path, read_only=True)
    build, refresh = _tripwires()
    with build as load, refresh:
        with pytest.raises(ToolError, match="client built"):
            _call(server, "get_account_summary", {"customer_id": "1234567890"})
        assert load.call_count >= 1


def test_write_not_early_rejected_when_not_read_only(monkeypatch, tmp_path):
    """Outside READ_ONLY the behaviour is unchanged: the tool body runs."""
    from fastmcp.exceptions import ToolError

    server = _build(monkeypatch, tmp_path, read_only=False)
    build, refresh = _tripwires()
    with build as load, refresh:
        with pytest.raises(ToolError, match="client built"):
            _call(server, "create_campaign_budget", _BUDGET)
        assert load.call_count >= 1
