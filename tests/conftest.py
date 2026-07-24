"""Shared test fakes for exercising tool modules without a real Google Ads
client: a proto-plus-ish auto-vivifying builder, a minimal MCP registrar,
and an AppContext wired to a mocked mutate().
"""

from __future__ import annotations

import enum
from types import SimpleNamespace

from google_ads_mcp.context import AppContext
from google_ads_mcp.safety import SafetyLayer


class FakeMutateResult:
    """Mimics a MutateXResponse with one or more .results, each carrying a
    .resource_name — enough for every tool in this repo, which only ever
    reads result.results[i].resource_name."""

    def __init__(self, *resource_names: str):
        self.results = [SimpleNamespace(resource_name=rn) for rn in resource_names]


class FakeMcp:
    """Minimal stand-in for FastMCP: @mcp.tool() just registers the function
    under its own name so tests can call it directly."""

    def __init__(self):
        self.registered: dict = {}

    def tool(self):
        def decorator(fn):
            self.registered[fn.__name__] = fn
            return fn

        return decorator


class FakeAuditLog:
    def record(self, *args, **kwargs):
        pass


class AssetFieldTypeEnum(enum.Enum):
    UNSPECIFIED = 0
    SITELINK = 1
    CALL = 2
    MESSAGE = 3
    IMAGE = 4
    PROMOTION = 5
    HEADLINE = 6
    LONG_HEADLINE = 7
    DESCRIPTION = 8
    BUSINESS_NAME = 9
    LOCAL = 10


class ConversionActionStatusEnum(enum.Enum):
    UNSPECIFIED = 0
    ENABLED = 2
    REMOVED = 3
    HIDDEN = 4


class AdGroupCriterionStatusEnum(enum.Enum):
    UNSPECIFIED = 0
    ENABLED = 2
    PAUSED = 3
    REMOVED = 4


class AdGroupAdStatusEnum(enum.Enum):
    UNSPECIFIED = 0
    ENABLED = 2
    PAUSED = 3
    REMOVED = 4


class CampaignStatusEnum(enum.Enum):
    UNSPECIFIED = 0
    ENABLED = 2
    PAUSED = 3
    REMOVED = 4


class AssetGroupStatusEnum(enum.Enum):
    UNSPECIFIED = 0
    ENABLED = 2
    PAUSED = 3
    REMOVED = 4


class AdvertisingChannelTypeEnum(enum.Enum):
    UNSPECIFIED = 0
    SEARCH = 2
    DISPLAY = 3
    SHOPPING = 4
    LOCAL = 10
    PERFORMANCE_MAX = 13


class AdvertisingChannelSubTypeEnum(enum.Enum):
    UNSPECIFIED = 0
    STANDARD_SHOPPING = 8
    SMART_SHOPPING = 12


class CustomerMatchUploadKeyTypeEnum(enum.Enum):
    UNSPECIFIED = 0
    CONTACT_INFO = 2


class OfflineUserDataJobTypeEnum(enum.Enum):
    UNSPECIFIED = 0
    CUSTOMER_MATCH_USER_LIST = 5


class KeywordMatchTypeEnum(enum.Enum):
    UNSPECIFIED = 0
    EXACT = 2
    PHRASE = 3
    BROAD = 4


class DayOfWeekEnum(enum.Enum):
    UNSPECIFIED = 0
    MONDAY = 2
    TUESDAY = 3
    WEDNESDAY = 4
    THURSDAY = 5
    FRIDAY = 6
    SATURDAY = 7
    SUNDAY = 8


class MinuteOfHourEnum(enum.Enum):
    UNSPECIFIED = 0
    ZERO = 1
    FIFTEEN = 2
    THIRTY = 3
    FORTY_FIVE = 4


class DeviceEnum(enum.Enum):
    UNSPECIFIED = 0
    MOBILE = 2
    TABLET = 3
    DESKTOP = 4


class FakeEnums:
    AssetFieldTypeEnum = AssetFieldTypeEnum
    ConversionActionStatusEnum = ConversionActionStatusEnum
    AdGroupCriterionStatusEnum = AdGroupCriterionStatusEnum
    AdGroupAdStatusEnum = AdGroupAdStatusEnum
    CampaignStatusEnum = CampaignStatusEnum
    AssetGroupStatusEnum = AssetGroupStatusEnum
    AdvertisingChannelTypeEnum = AdvertisingChannelTypeEnum
    AdvertisingChannelSubTypeEnum = AdvertisingChannelSubTypeEnum
    DayOfWeekEnum = DayOfWeekEnum
    MinuteOfHourEnum = MinuteOfHourEnum
    DeviceEnum = DeviceEnum
    CustomerMatchUploadKeyTypeEnum = CustomerMatchUploadKeyTypeEnum
    OfflineUserDataJobTypeEnum = OfflineUserDataJobTypeEnum
    KeywordMatchTypeEnum = KeywordMatchTypeEnum


class AutoVivify:
    """A nested attribute sandbox: reading an unset attribute creates and
    caches a fresh AutoVivify, so arbitrarily deep proto-style attribute
    chains (asset.sitelink_asset.link_text = ...) just work in a fake."""

    def __init__(self):
        object.__setattr__(self, "_children", {})
        object.__setattr__(self, "_list", [])

    def __getattr__(self, name):
        children = object.__getattribute__(self, "_children")
        if name not in children:
            children[name] = AutoVivify()
        return children[name]

    def __setattr__(self, name, value):
        object.__getattribute__(self, "_children")[name] = value

    def append(self, value):
        object.__getattribute__(self, "_list").append(value)

    def extend(self, values):
        object.__getattribute__(self, "_list").extend(values)

    def __iter__(self):
        return iter(object.__getattribute__(self, "_list"))

    def __len__(self):
        return len(object.__getattribute__(self, "_list"))

    def CopyFrom(self, value):
        # field_mask_pb2.FieldMask(...).CopyFrom target — no-op is fine, the
        # tests only assert on which services/mutations get called, not on
        # the exact field mask contents.
        pass

    def SetInParent(self):
        pass

    @property
    def create(self):
        return self.__getattr__("create")

    @property
    def update(self):
        return self.__getattr__("update")

    @property
    def remove(self):
        return self.__getattr__("remove")


class FakePathService:
    def __init__(self, name):
        self._name = name

    def __getattr__(self, name):
        # e.g. campaign_path(...), asset_path(...), campaign_asset_path(...)
        def _path(*args):
            return f"customers/{args[0]}/{self._name}Path/{'/'.join(str(a) for a in args[1:])}"

        return _path


class FakeRawClient:
    """Fakes the bits of google.ads.googleads.client.GoogleAdsClient that
    tool modules touch: get_type, get_service, enums."""

    enums = FakeEnums

    def __init__(self, extra_services: dict | None = None):
        self._extra_services = extra_services or {}

    def get_type(self, name):
        return AutoVivify()

    def get_service(self, name):
        if name in self._extra_services:
            return self._extra_services[name]
        return FakePathService(name)


def build_ctx(mutate_side_effect, extra_services: dict | None = None):
    """AppContext with a real SafetyLayer (auto-approve, so propose() runs
    execute() immediately) and a client whose .mutate() is fully mocked."""
    fake_client = SimpleNamespace(
        raw=FakeRawClient(extra_services=extra_services),
        mutate=mutate_side_effect,
    )
    safety = SafetyLayer(auto_approve=True, ttl_minutes=30, audit_log=FakeAuditLog())
    return AppContext(settings=None, client=fake_client, safety=safety, audit=FakeAuditLog())


def register_module(module, ctx):
    mcp = FakeMcp()
    module.register(mcp, ctx)
    return mcp.registered
