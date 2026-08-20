from __future__ import annotations

import os

from google_ads_mcp.audit import AuditLog
from google_ads_mcp.invocation import install_tool_tracking
from google_ads_mcp.safety import SafetyLayer


class _FakeMcp:
    def tool(self, function=None, *args, **kwargs):
        if function is None:
            def decorator(func):
                return func
            return decorator
        return function


def _safety(audit: AuditLog) -> SafetyLayer:
    return SafetyLayer(
        auto_approve=False,
        ttl_minutes=30,
        audit_log=audit,
        allowed_customer_ids={"1234567890"},
    )


def test_pending_action_replays_after_new_safety_instance(tmp_path):
    db_path = tmp_path / "audit.db"
    audit = AuditLog(str(db_path))
    holder = {"safety": _safety(audit)}
    executed: list[str] = []

    mcp = _FakeMcp()
    install_tool_tracking(mcp)

    @mcp.tool()
    def sensitive_change(customer_id: str, secret_value: str) -> dict:
        def execute():
            executed.append(secret_value)
            return {"changed": True}

        return holder["safety"].propose(
            tool_name="sensitive_change",
            customer_id=customer_id,
            description="sensitive change",
            payload={"secret_length": len(secret_value)},
            execute=execute,
        )

    proposed = sensitive_change("1234567890", "never-store-me-in-plaintext")
    action_id = proposed["pending_action_id"]
    assert proposed["durable"] is True
    assert executed == []

    stored = audit.get_pending(action_id)
    assert stored is not None
    assert stored["invocation_arguments"]["secret_value"] == "never-store-me-in-plaintext"

    holder["safety"] = _safety(audit)
    confirmed = holder["safety"].confirm(action_id)

    assert confirmed["status"] == "executed"
    assert confirmed["action_id"] == action_id
    assert confirmed["replayed_after_restart"] is True
    assert executed == ["never-store-me-in-plaintext"]
    assert audit.get_pending(action_id) is None
    entries = audit.by_action_id(action_id)
    assert len(entries) == 1
    assert entries[0]["status"] == "success"


def test_pending_shared_safety_alias_replays_original_public_tool(tmp_path):
    """Public tool name and safety category may differ without breaking replay."""
    db_path = tmp_path / "audit.db"
    audit = AuditLog(str(db_path))
    holder = {"safety": _safety(audit)}
    executed: list[str] = []

    mcp = _FakeMcp()
    install_tool_tracking(mcp)

    @mcp.tool()
    def create_specific_link(customer_id: str, link_id: str) -> dict:
        def execute():
            executed.append(link_id)
            return {"linked": link_id}

        # Mirrors real helpers such as create_merchant_center_link, which share
        # the lower-level create_product_link safety category.
        return holder["safety"].propose(
            tool_name="create_product_link",
            customer_id=customer_id,
            description=f"create link {link_id}",
            payload={"link_id": link_id},
            execute=execute,
        )

    proposed = create_specific_link("1234567890", "merchant-42")
    assert proposed["durable"] is True
    action_id = proposed["pending_action_id"]
    stored = audit.get_pending(action_id)
    assert stored is not None
    assert (
        stored["invocation_arguments"]["__google_ads_mcp_replay_tool_name__"]
        == "create_specific_link"
    )

    holder["safety"] = _safety(audit)
    confirmed = holder["safety"].confirm(action_id)
    assert confirmed["status"] == "executed"
    assert confirmed["action_id"] == action_id
    assert executed == ["merchant-42"]


def test_pending_invocation_is_encrypted_on_disk(tmp_path):
    db_path = tmp_path / "audit.db"
    audit = AuditLog(str(db_path))
    audit.save_pending(
        action_id="abc123",
        tool_name="pii_tool",
        customer_id="1234567890",
        description="redacted payload",
        payload={"identifier_count": 1},
        invocation_arguments={
            "customer_id": "1234567890",
            "raw_identifier": "plain-secret@example.com",
        },
        risk_level="sensitive",
        created_at=1.0,
    )

    disk = b""
    for candidate in (db_path, tmp_path / "audit.db-wal"):
        if candidate.exists():
            disk += candidate.read_bytes()
    assert b"plain-secret@example.com" not in disk

    key_path = tmp_path / "audit.db.pending.key"
    assert key_path.exists()
    if os.name != "nt":
        assert key_path.stat().st_mode & 0o077 == 0
