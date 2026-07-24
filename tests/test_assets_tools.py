"""Tests for the campaign-asset tools (sitelinks, call, message assets) and
the conversion-action management tools added alongside them.

These exercise the two-step create-then-link flow that create_sitelink_asset
/ create_call_asset / create_message_asset all share: create the Asset via
AssetService, then link it to the campaign via CampaignAssetService, both
inside the single execute() the safety layer confirms.
"""

from __future__ import annotations

import enum
from types import SimpleNamespace

import pytest

from google_ads_mcp import tools
from google_ads_mcp.context import AppContext
from google_ads_mcp.safety import SafetyLayer


class _FakeMutateResult:
    def __init__(self, resource_name: str):
        self.results = [SimpleNamespace(resource_name=resource_name)]


class _FakeMcp:
    """Minimal stand-in for FastMCP: @mcp.tool() just registers the function
    under its own name so tests can call it directly."""

    def __init__(self):
        self.registered = {}

    def tool(self):
        def decorator(fn):
            self.registered[fn.__name__] = fn
            return fn

        return decorator


class _FakeAuditLog:
    def record(self, *args, **kwargs):
        pass


def _build_ctx(mutate_side_effect):
    """AppContext with a real SafetyLayer (auto-approve, so propose() runs
    execute() immediately) and a client whose .mutate() is fully mocked."""
    fake_client = SimpleNamespace(
        raw=_FakeRawClient(),
        mutate=mutate_side_effect,
    )
    safety = SafetyLayer(auto_approve=True, ttl_minutes=30, audit_log=_FakeAuditLog())
    return AppContext(settings=None, client=fake_client, safety=safety, audit=_FakeAuditLog())


class _AssetFieldTypeEnum(enum.Enum):
    SITELINK = 1
    CALL = 2
    MESSAGE = 3


class _ConversionActionStatusEnum(enum.Enum):
    ENABLED = 2
    REMOVED = 3
    HIDDEN = 4


class _FakeEnums:
    AssetFieldTypeEnum = _AssetFieldTypeEnum
    ConversionActionStatusEnum = _ConversionActionStatusEnum


class _FakeRawClient:
    """Fakes the bits of google.ads.googleads.client.GoogleAdsClient that
    assets.py / conversions.py touch: get_type, get_service, enums."""

    enums = _FakeEnums

    def get_type(self, name):
        # Returns an object whose .create / .update act like proto-plus
        # message builders: any attribute access auto-vivifies a nested
        # namespace, and list-like fields support .append.
        return _AutoVivify()

    def get_service(self, name):
        return _FakePathService(name)


class _AutoVivify:
    """A nested attribute sandbox: reading an unset attribute creates and
    caches a fresh _AutoVivify, so arbitrarily deep proto-style attribute
    chains (asset.sitelink_asset.link_text = ...) just work in a fake."""

    def __init__(self):
        object.__setattr__(self, "_children", {})
        object.__setattr__(self, "_list", [])

    def __getattr__(self, name):
        children = object.__getattribute__(self, "_children")
        if name not in children:
            children[name] = _AutoVivify()
        return children[name]

    def __setattr__(self, name, value):
        object.__getattribute__(self, "_children")[name] = value

    def append(self, value):
        object.__getattribute__(self, "_list").append(value)

    def CopyFrom(self, value):
        # field_mask_pb2.FieldMask(...).CopyFrom target — no-op is fine, the
        # tests only assert on which services/mutations get called, not on
        # the exact field mask contents.
        pass

    @property
    def create(self):
        return self.__getattr__("create")

    @property
    def update(self):
        return self.__getattr__("update")


class _FakePathService:
    def __init__(self, name):
        self._name = name

    def __getattr__(self, name):
        # e.g. campaign_path(...), asset_path(...), campaign_asset_path(...)
        def _path(*args):
            return f"customers/{args[0]}/{self._name}Path/{'/'.join(str(a) for a in args[1:])}"

        return _path


def _register_module(module, ctx):
    mcp = _FakeMcp()
    module.register(mcp, ctx)
    return mcp.registered


# ---- create_message_asset: the WhatsApp-critical path ----------------------


def test_create_message_asset_creates_then_links():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        if service_name == "AssetService":
            return _FakeMutateResult("customers/123/assets/999")
        if service_name == "CampaignAssetService":
            return _FakeMutateResult("customers/123/campaignAssets/456~999~MESSAGE")
        raise AssertionError(f"unexpected service {service_name}")

    ctx = _build_ctx(fake_mutate)
    tool_fns = _register_module(tools.assets, ctx)

    result = tool_fns["create_message_asset"](
        customer_id="123",
        campaign_id="456",
        phone_number="1112345678",
        country_code="AR",
        business_name="Instituto Cambridge",
        message_text="Hola! Quiero info de los cursos",
        call_to_action_text="Escribinos por WhatsApp",
    )

    # AssetService must be called before CampaignAssetService (link needs the
    # asset's resource name from the first call).
    assert calls == ["AssetService", "CampaignAssetService"]
    assert result["status"] == "executed"
    assert result["result"]["asset_resource_name"] == "customers/123/assets/999"


def test_create_message_asset_rejects_long_text():
    ctx = _build_ctx(lambda *a, **k: None)
    tool_fns = _register_module(tools.assets, ctx)

    with pytest.raises(ValueError, match="35 characters"):
        tool_fns["create_message_asset"](
            customer_id="123",
            campaign_id="456",
            phone_number="1112345678",
            country_code="AR",
            business_name="Instituto Cambridge",
            message_text="x" * 36,
        )


def test_create_sitelink_asset_rejects_long_link_text():
    ctx = _build_ctx(lambda *a, **k: None)
    tool_fns = _register_module(tools.assets, ctx)

    with pytest.raises(ValueError, match="25 characters"):
        tool_fns["create_sitelink_asset"](
            customer_id="123",
            campaign_id="456",
            link_text="x" * 26,
            final_url="https://example.com",
        )


def test_create_call_asset_creates_then_links():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        if service_name == "AssetService":
            return _FakeMutateResult("customers/123/assets/111")
        return _FakeMutateResult("customers/123/campaignAssets/456~111~CALL")

    ctx = _build_ctx(fake_mutate)
    tool_fns = _register_module(tools.assets, ctx)

    result = tool_fns["create_call_asset"](
        customer_id="123", campaign_id="456", phone_number="+541112345678"
    )

    assert calls == ["AssetService", "CampaignAssetService"]
    assert result["status"] == "executed"


# ---- conversion action management ------------------------------------------


def test_update_conversion_action_status():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        return _FakeMutateResult("customers/123/conversionActions/789")

    ctx = _build_ctx(fake_mutate)
    tool_fns = _register_module(tools.conversions, ctx)

    result = tool_fns["update_conversion_action_status"](
        customer_id="123", conversion_action_id="789", status="REMOVED"
    )

    assert calls == ["ConversionActionService"]
    assert result["status"] == "executed"


def test_set_conversion_action_counting_excludes_from_bidding():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        return _FakeMutateResult("customers/123/conversionActions/789")

    ctx = _build_ctx(fake_mutate)
    tool_fns = _register_module(tools.conversions, ctx)

    result = tool_fns["set_conversion_action_counting"](
        customer_id="123",
        conversion_action_id="789",
        include_in_conversions_metric=False,
    )

    assert calls == ["ConversionActionService"]
    assert result["status"] == "executed"
    assert "Exclude" in result["description"]
