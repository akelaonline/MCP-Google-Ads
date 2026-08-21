"""Shared test fakes for tool-level unit tests.

These fakes intentionally remain lightweight. API-contract correctness is
covered separately by tests that instantiate Google's real v25 protobuf types.
"""

from __future__ import annotations

import enum
from types import SimpleNamespace

from google_ads_mcp.context import AppContext
from google_ads_mcp.safety import SafetyLayer


class FakeMutateResult:
    def __init__(self, *resource_names: str):
        self.results = [SimpleNamespace(resource_name=rn) for rn in resource_names]


class FakeMcp:
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
    UNKNOWN = 1
    HEADLINE = 2
    DESCRIPTION = 3
    MANDATORY_AD_TEXT = 4
    MARKETING_IMAGE = 5
    MEDIA_BUNDLE = 6
    YOUTUBE_VIDEO = 7
    BOOK_ON_GOOGLE = 8
    LEAD_FORM = 9
    PROMOTION = 10
    CALLOUT = 11
    STRUCTURED_SNIPPET = 12
    SITELINK = 13
    MOBILE_APP = 14
    HOTEL_CALLOUT = 15
    CALL = 16
    LONG_HEADLINE = 17
    BUSINESS_NAME = 18
    SQUARE_MARKETING_IMAGE = 19
    PORTRAIT_MARKETING_IMAGE = 20
    LOGO = 21
    LANDSCAPE_LOGO = 22
    VIDEO = 23
    PRICE = 24
    BUSINESS_MESSAGE = 31


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


class AdGroupStatusEnum(enum.Enum):
    UNSPECIFIED = 0
    ENABLED = 2
    PAUSED = 3
    REMOVED = 4


class AdGroupTypeEnum(enum.Enum):
    UNSPECIFIED = 0
    SEARCH_STANDARD = 2
    DISPLAY_STANDARD = 3
    SHOPPING_PRODUCT_ADS = 4
    VIDEO_BUMPER = 8
    VIDEO_TRUE_VIEW_IN_STREAM = 9
    VIDEO_TRUE_VIEW_IN_DISPLAY = 10
    VIDEO_NON_SKIPPABLE_IN_STREAM = 11
    SEARCH_DYNAMIC_ADS = 13
    VIDEO_RESPONSIVE = 16


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
    MULTI_CHANNEL = 7
    PERFORMANCE_MAX = 13
    DEMAND_GEN = 14


class AdvertisingChannelSubTypeEnum(enum.Enum):
    UNSPECIFIED = 0
    APP_CAMPAIGN = 12
    APP_CAMPAIGN_FOR_ENGAGEMENT = 13


class EuPoliticalAdvertisingStatusEnum(enum.Enum):
    UNSPECIFIED = 0
    CONTAINS_EU_POLITICAL_ADVERTISING = 2
    DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING = 3


class AssetTypeEnum(enum.Enum):
    UNSPECIFIED = 0
    IMAGE = 2


class BusinessMessageProviderEnum(enum.Enum):
    UNSPECIFIED = 0
    WHATSAPP = 2


class BusinessMessageCallToActionTypeEnum(enum.Enum):
    UNSPECIFIED = 0
    CONTACT_US = 4


class CallConversionReportingStateEnum(enum.Enum):
    UNSPECIFIED = 0
    DISABLED = 2
    USE_ACCOUNT_LEVEL_CALL_CONVERSION_ACTION = 3


class ListingGroupFilterTypeEnum(enum.Enum):
    UNSPECIFIED = 0
    SUBDIVISION = 2
    UNIT_INCLUDED = 3
    UNIT_EXCLUDED = 4


class ListingGroupFilterListingSourceEnum(enum.Enum):
    UNSPECIFIED = 0
    SHOPPING = 2


class ListingGroupFilterProductConditionEnum(enum.Enum):
    UNSPECIFIED = 0
    NEW = 2
    USED = 3
    REFURBISHED = 4


class ListingGroupFilterProductTypeLevelEnum(enum.Enum):
    UNSPECIFIED = 0
    LEVEL1 = 2


class UserListMembershipStatusEnum(enum.Enum):
    UNSPECIFIED = 0
    OPEN = 2
    CLOSED = 3


class UserListPrepopulationStatusEnum(enum.Enum):
    UNSPECIFIED = 0
    REQUESTED = 2
    FINISHED = 3
    FAILED = 4


class UserListStringRuleItemOperatorEnum(enum.Enum):
    UNSPECIFIED = 0
    CONTAINS = 2
    EQUALS = 3


class UserListFlexibleRuleOperatorEnum(enum.Enum):
    UNSPECIFIED = 0
    AND = 2
    OR = 3


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


class KeywordPlanNetworkEnum(enum.Enum):
    UNSPECIFIED = 0
    GOOGLE_SEARCH = 2
    GOOGLE_SEARCH_AND_PARTNERS = 3


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
    UNKNOWN = 1
    ZERO = 2
    FIFTEEN = 3
    THIRTY = 4
    FORTY_FIVE = 5


class DeviceEnum(enum.Enum):
    UNSPECIFIED = 0
    MOBILE = 2
    TABLET = 3
    DESKTOP = 4


class ExperimentTypeEnum(enum.Enum):
    UNSPECIFIED = 0
    SEARCH_CUSTOM = 2


class ExperimentStatusEnum(enum.Enum):
    UNSPECIFIED = 0
    SETUP = 2
    INITIALIZING = 3
    ENABLED = 4
    GRADUATED = 5
    REMOVED = 6
    PROMOTED = 7
    ENDED = 8


class ConsentStatusEnum(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    GRANTED = 2
    DENIED = 3


class AppCampaignAppStoreEnum(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    APPLE_APP_STORE = 2
    GOOGLE_APP_STORE = 3


class AppCampaignBiddingStrategyGoalTypeEnum(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    OPTIMIZE_INSTALLS_TARGET_INSTALL_COST = 2
    OPTIMIZE_IN_APP_CONVERSIONS_TARGET_INSTALL_COST = 3
    OPTIMIZE_IN_APP_CONVERSIONS_TARGET_CONVERSION_COST = 4
    OPTIMIZE_RETURN_ON_ADVERTISING_SPEND = 5
    OPTIMIZE_PRE_REGISTRATION_CONVERSION_VOLUME = 6
    OPTIMIZE_INSTALLS_WITHOUT_TARGET_INSTALL_COST = 7
    OPTIMIZE_IN_APP_CONVERSIONS_WITHOUT_TARGET_CPA = 8
    OPTIMIZE_TOTAL_VALUE_WITHOUT_TARGET_ROAS = 9


class WebpageConditionOperandEnum(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    URL = 2
    CATEGORY = 3
    PAGE_TITLE = 4
    PAGE_CONTENT = 5
    CUSTOM_LABEL = 6


class WebpageConditionOperatorEnum(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    EQUALS = 2
    CONTAINS = 3


class ListingGroupTypeEnum(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    SUBDIVISION = 2
    UNIT = 3


class ProductCategoryLevelEnum(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    LEVEL1 = 2
    LEVEL2 = 3
    LEVEL3 = 4
    LEVEL4 = 5
    LEVEL5 = 6


class ProductConditionEnum(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    NEW = 3
    REFURBISHED = 4
    USED = 5


class ProductChannelEnum(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    ONLINE = 2
    LOCAL = 3


class ProductChannelExclusivityEnum(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    SINGLE_CHANNEL = 2
    MULTI_CHANNEL = 3


class LeadFormCallToActionTypeEnum(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    LEARN_MORE = 2
    GET_QUOTE = 3
    APPLY_NOW = 4
    SIGN_UP = 5
    CONTACT_US = 6
    SUBSCRIBE = 7
    DOWNLOAD = 8
    BOOK_NOW = 9
    GET_OFFER = 10
    REGISTER = 11
    GET_INFO = 12
    REQUEST_DEMO = 13
    JOIN_NOW = 14
    GET_STARTED = 15


class LeadFormDesiredIntentEnum(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    LOW_INTENT = 2
    HIGH_INTENT = 3


class LeadFormFieldUserInputTypeEnum(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    FULL_NAME = 2
    EMAIL = 3
    PHONE_NUMBER = 4
    POSTAL_CODE = 5
    FIRST_NAME = 23
    LAST_NAME = 24
    PRODUCT = 1016


class LeadFormPostSubmitCallToActionTypeEnum(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    VISIT_SITE = 2
    DOWNLOAD = 3
    LEARN_MORE = 4
    SHOP_NOW = 5


class PriceExtensionTypeEnum(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    BRANDS = 2
    EVENTS = 3
    LOCATIONS = 4
    NEIGHBORHOODS = 5
    PRODUCT_CATEGORIES = 6
    PRODUCT_TIERS = 7
    SERVICES = 8
    SERVICE_CATEGORIES = 9
    SERVICE_TIERS = 10


class PriceExtensionPriceQualifierEnum(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    FROM = 2
    UP_TO = 3
    AVERAGE = 4


class PriceExtensionPriceUnitEnum(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    PER_HOUR = 2
    PER_DAY = 3
    PER_WEEK = 4
    PER_MONTH = 5
    PER_YEAR = 6
    PER_NIGHT = 7


class FrequencyCapLevelEnum(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    AD_GROUP_AD = 2
    AD_GROUP = 3
    CAMPAIGN = 4


class FrequencyCapEventTypeEnum(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    IMPRESSION = 2
    VIDEO_VIEW = 3


class FrequencyCapTimeUnitEnum(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    DAY = 2
    WEEK = 3
    MONTH = 4


class UserIdentifierSourceEnum(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    FIRST_PARTY = 2
    THIRD_PARTY = 3


class AdServingOptimizationStatusEnum(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    OPTIMIZE = 2
    CONVERSION_OPTIMIZE = 3
    ROTATE = 4
    ROTATE_INDEFINITELY = 5
    UNAVAILABLE = 6


class FakeEnums:
    AssetFieldTypeEnum = AssetFieldTypeEnum
    ConversionActionStatusEnum = ConversionActionStatusEnum
    AdGroupCriterionStatusEnum = AdGroupCriterionStatusEnum
    AdGroupStatusEnum = AdGroupStatusEnum
    AdGroupTypeEnum = AdGroupTypeEnum
    AdGroupAdStatusEnum = AdGroupAdStatusEnum
    CampaignStatusEnum = CampaignStatusEnum
    AssetGroupStatusEnum = AssetGroupStatusEnum
    AdvertisingChannelTypeEnum = AdvertisingChannelTypeEnum
    AdvertisingChannelSubTypeEnum = AdvertisingChannelSubTypeEnum
    EuPoliticalAdvertisingStatusEnum = EuPoliticalAdvertisingStatusEnum
    AssetTypeEnum = AssetTypeEnum
    BusinessMessageProviderEnum = BusinessMessageProviderEnum
    BusinessMessageCallToActionTypeEnum = BusinessMessageCallToActionTypeEnum
    CallConversionReportingStateEnum = CallConversionReportingStateEnum
    ListingGroupFilterTypeEnum = ListingGroupFilterTypeEnum
    ListingGroupFilterListingSourceEnum = ListingGroupFilterListingSourceEnum
    ListingGroupFilterProductConditionEnum = ListingGroupFilterProductConditionEnum
    ListingGroupFilterProductTypeLevelEnum = ListingGroupFilterProductTypeLevelEnum
    UserListMembershipStatusEnum = UserListMembershipStatusEnum
    UserListPrepopulationStatusEnum = UserListPrepopulationStatusEnum
    UserListStringRuleItemOperatorEnum = UserListStringRuleItemOperatorEnum
    UserListFlexibleRuleOperatorEnum = UserListFlexibleRuleOperatorEnum
    DayOfWeekEnum = DayOfWeekEnum
    MinuteOfHourEnum = MinuteOfHourEnum
    DeviceEnum = DeviceEnum
    CustomerMatchUploadKeyTypeEnum = CustomerMatchUploadKeyTypeEnum
    OfflineUserDataJobTypeEnum = OfflineUserDataJobTypeEnum
    KeywordMatchTypeEnum = KeywordMatchTypeEnum
    KeywordPlanNetworkEnum = KeywordPlanNetworkEnum
    ExperimentTypeEnum = ExperimentTypeEnum
    ExperimentStatusEnum = ExperimentStatusEnum
    ConsentStatusEnum = ConsentStatusEnum
    AppCampaignAppStoreEnum = AppCampaignAppStoreEnum
    AppCampaignBiddingStrategyGoalTypeEnum = AppCampaignBiddingStrategyGoalTypeEnum
    WebpageConditionOperandEnum = WebpageConditionOperandEnum
    WebpageConditionOperatorEnum = WebpageConditionOperatorEnum
    ListingGroupTypeEnum = ListingGroupTypeEnum
    ProductCategoryLevelEnum = ProductCategoryLevelEnum
    ProductConditionEnum = ProductConditionEnum
    ProductChannelEnum = ProductChannelEnum
    ProductChannelExclusivityEnum = ProductChannelExclusivityEnum
    AdServingOptimizationStatusEnum = AdServingOptimizationStatusEnum
    UserIdentifierSourceEnum = UserIdentifierSourceEnum
    LeadFormCallToActionTypeEnum = LeadFormCallToActionTypeEnum
    LeadFormDesiredIntentEnum = LeadFormDesiredIntentEnum
    LeadFormFieldUserInputTypeEnum = LeadFormFieldUserInputTypeEnum
    LeadFormPostSubmitCallToActionTypeEnum = LeadFormPostSubmitCallToActionTypeEnum
    PriceExtensionTypeEnum = PriceExtensionTypeEnum
    PriceExtensionPriceQualifierEnum = PriceExtensionPriceQualifierEnum
    PriceExtensionPriceUnitEnum = PriceExtensionPriceUnitEnum
    FrequencyCapLevelEnum = FrequencyCapLevelEnum
    FrequencyCapEventTypeEnum = FrequencyCapEventTypeEnum
    FrequencyCapTimeUnitEnum = FrequencyCapTimeUnitEnum


class AutoVivify:
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
        def _path(*args):
            return (
                f"customers/{args[0]}/{self._name}Path/"
                f"{'/'.join(str(a) for a in args[1:])}"
            )

        return _path


class FakeRawClient:
    enums = FakeEnums

    def __init__(self, extra_services: dict | None = None):
        self._extra_services = extra_services or {}

    def get_type(self, name):
        return AutoVivify()

    def get_service(self, name):
        if name in self._extra_services:
            return self._extra_services[name]
        return FakePathService(name)

    def copy_from(self, target, source):
        return None


def _normalize_customer_id(customer_id: str) -> str:
    value = str(customer_id).replace("-", "").strip()
    if not value.isdigit():
        raise ValueError("customer_id must be numeric with optional dashes")
    return value


def _assert_resource_name_customer(
    customer_id: str,
    resource_name: str,
    *,
    field_name: str = "resource_name",
) -> str:
    customer = _normalize_customer_id(customer_id)
    value = str(resource_name).strip()
    root = f"customers/{customer}"
    if value != root and not value.startswith(root + "/"):
        raise ValueError(f"{field_name} belongs to another customer")
    return value


def build_ctx(
    mutate_side_effect,
    extra_services: dict | None = None,
    search_side_effect=None,
):
    """Build a test context whose normal/atomic mutates are observable."""
    raw = FakeRawClient(extra_services=extra_services)

    def mutate_atomic(customer_id, operations, **kwargs):
        return mutate_side_effect(
            "GoogleAdsService",
            customer_id,
            operations,
            **kwargs,
        )

    def fake_search(customer_id, query):
        if search_side_effect is not None:
            return search_side_effect(customer_id, query)
        return [{"campaign": {"advertising_channel_type": "SEARCH"}}]

    fake_client = SimpleNamespace(
        raw=raw,
        mutate=mutate_side_effect,
        mutate_atomic=mutate_atomic,
        search=fake_search,
        assert_customer_allowed=_normalize_customer_id,
        assert_resource_name_customer=_assert_resource_name_customer,
    )
    safety = SafetyLayer(auto_approve=True, ttl_minutes=30, audit_log=FakeAuditLog())
    return AppContext(
        settings=None,
        client=fake_client,
        safety=safety,
        audit=FakeAuditLog(),
    )


def register_module(module, ctx):
    mcp = FakeMcp()
    module.register(mcp, ctx)
    return mcp.registered
