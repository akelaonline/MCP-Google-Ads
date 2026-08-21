"""Real Google Ads API v25 contracts for v0.14 agency-management tools."""

from __future__ import annotations

from types import SimpleNamespace

from conftest import FakeAuditLog, FakeMcp, FakeMutateResult
from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

from google_ads_mcp.client import _mutate_method_name
from google_ads_mcp.context import AppContext
from google_ads_mcp.safety import RiskLevel, SafetyLayer, classify_risk
from google_ads_mcp.tools import account_access, billing, labels, shared_sets


class _Raw:
    def __init__(self):
        self.client = GoogleAdsClient(
            credentials=Credentials(token="contract-token"),
            developer_token="contract-developer-token",
            version="v25",
            use_proto_plus=True,
        )
        self.enums = self.client.enums

    def get_type(self, name):
        return self.client.get_type(name)

    def get_service(self, name):
        return self.client.get_service(name)


class _InvoiceService:
    def __init__(self, calls):
        self.calls = calls

    def list_invoices(self, **kwargs):
        self.calls.append(("InvoiceService.list_invoices", kwargs))
        return SimpleNamespace(invoices=[])


class _CaptureClient:
    def __init__(self, search_fn=None):
        self.raw = _Raw()
        self.calls = []
        self.search_fn = search_fn or (lambda customer_id, query: [])

    def search(self, customer_id, query):
        self.calls.append(("search", customer_id, query))
        return self.search_fn(customer_id, query)

    def mutate(self, service_name, customer_id, operations, **kwargs):
        operation_list = list(operations)
        self.calls.append((service_name, customer_id, operation_list, kwargs))
        return FakeMutateResult(f"customers/{customer_id}/{service_name}/1")

    def assert_customer_allowed(self, customer_id):
        value = str(customer_id).replace("-", "").strip()
        if not value.isdigit():
            raise ValueError("customer_id must be numeric")
        return value

    def assert_resource_name_customer(
        self, customer_id, resource_name, *, field_name="resource_name"
    ):
        customer = self.assert_customer_allowed(customer_id)
        value = str(resource_name).strip()
        root = f"customers/{customer}"
        if value != root and not value.startswith(root + "/"):
            raise ValueError(f"{field_name} belongs to another customer")
        return value

    def service(self, name):
        if name == "InvoiceService":
            return _InvoiceService(self.calls)
        return self.raw.get_service(name)


def _ctx(search_fn=None):
    client = _CaptureClient(search_fn=search_fn)
    audit = FakeAuditLog()
    safety = SafetyLayer(auto_approve=True, ttl_minutes=30, audit_log=audit)
    return AppContext(settings=None, client=client, safety=safety, audit=audit), client


def _tools(module, ctx):
    mcp = FakeMcp()
    module.register(mcp, ctx)
    return mcp.registered


def test_create_label_builds_real_v25_label_operation():
    ctx, client = _ctx()
    result = _tools(labels, ctx)["create_label"](
        customer_id="1234567890",
        name="VIP",
        background_color="#112233",
        description="High value accounts",
    )

    assert result["status"] == "executed"
    operation = client.calls[0][2][0]
    assert operation.create.name == "VIP"
    assert operation.create.text_label.background_color == "#112233"
    assert operation.create.text_label.description == "High value accounts"


def test_campaign_label_uses_real_v25_relationship_fields():
    ctx, client = _ctx()
    result = _tools(labels, ctx)["attach_label_to_campaign"](
        customer_id="1234567890",
        campaign_id="111",
        label_id="222",
    )

    assert result["status"] == "executed"
    operation = client.calls[0][2][0]
    assert operation.create.campaign == "customers/1234567890/campaigns/111"
    assert operation.create.label == "customers/1234567890/labels/222"


def test_ad_group_label_uses_real_v25_relationship_fields():
    ctx, client = _ctx()
    result = _tools(labels, ctx)["attach_label_to_ad_group"](
        customer_id="1234567890",
        ad_group_id="333",
        label_id="222",
    )

    assert result["status"] == "executed"
    operation = client.calls[0][2][0]
    assert operation.create.ad_group == "customers/1234567890/adGroups/333"
    assert operation.create.label == "customers/1234567890/labels/222"


def test_shared_negative_keyword_list_builds_real_v25_shared_set():
    ctx, client = _ctx()
    result = _tools(shared_sets, ctx)["create_shared_negative_keyword_list"](
        customer_id="1234567890",
        name="Global junk",
    )

    assert result["status"] == "executed"
    operation = client.calls[0][2][0]
    assert operation.create.name == "Global junk"
    assert operation.create.type_.name == "NEGATIVE_KEYWORDS"


def test_shared_negative_keywords_build_real_v25_criteria():
    ctx, client = _ctx()
    result = _tools(shared_sets, ctx)["add_shared_negative_keywords"](
        customer_id="1234567890",
        shared_set_id="77",
        keywords=[
            {"text": "free", "match_type": "BROAD"},
            {"text": "jobs", "match_type": "PHRASE"},
        ],
    )

    assert result["status"] == "executed"
    operations = client.calls[0][2]
    assert len(operations) == 2
    assert operations[0].create.shared_set == "customers/1234567890/sharedSets/77"
    assert operations[0].create.negative is True
    assert operations[0].create.keyword.text == "free"
    assert operations[0].create.keyword.match_type.name == "BROAD"
    assert operations[1].create.keyword.match_type.name == "PHRASE"


def test_campaign_shared_set_builds_real_v25_relation():
    ctx, client = _ctx()
    result = _tools(shared_sets, ctx)[
        "attach_shared_negative_keyword_list_to_campaign"
    ](
        customer_id="1234567890",
        campaign_id="111",
        shared_set_id="77",
    )

    assert result["status"] == "executed"
    operation = client.calls[0][2][0]
    assert operation.create.campaign == "customers/1234567890/campaigns/111"
    assert operation.create.shared_set == "customers/1234567890/sharedSets/77"


def test_invite_account_user_builds_real_v25_invitation_operation():
    ctx, client = _ctx()
    result = _tools(account_access, ctx)["invite_account_user"](
        customer_id="1234567890",
        email_address="user@example.com",
        access_role="READ_ONLY",
    )

    assert result["status"] == "executed"
    operation = client.calls[0][2][0]
    assert operation.create.email_address == "user@example.com"
    assert operation.create.access_role.name == "READ_ONLY"
    assert client.calls[0][3]["operations_field"] == "operation"


def test_update_user_access_builds_real_v25_update_mask():
    ctx, client = _ctx()
    result = _tools(account_access, ctx)["update_user_access_role"](
        customer_id="1234567890",
        user_id="44",
        access_role="STANDARD",
    )

    assert result["status"] == "executed"
    operation = client.calls[0][2][0]
    assert operation.update.resource_name == (
        "customers/1234567890/customerUserAccesses/44"
    )
    assert operation.update.access_role.name == "STANDARD"
    assert list(operation.update_mask.paths) == ["access_role"]


def test_account_access_mutate_rpc_names_are_singular_in_v25():
    assert _mutate_method_name("CustomerUserAccessService") == "mutate_customer_user_access"
    assert _mutate_method_name("CustomerUserAccessInvitationService") == (
        "mutate_customer_user_access_invitation"
    )
    assert _mutate_method_name("SharedCriterionService") == "mutate_shared_criteria"


def test_account_access_actions_get_high_risk_classification():
    assert classify_risk("invite_account_user", {}) is RiskLevel.SENSITIVE
    assert classify_risk("update_user_access_role", {}) is RiskLevel.SENSITIVE
    assert classify_risk("remove_account_user", {}) is RiskLevel.DESTRUCTIVE
    assert classify_risk("revoke_user_access_invitation", {}) is RiskLevel.DESTRUCTIVE


def test_invoice_tool_calls_v25_list_invoices_with_scoped_resource_name():
    ctx, client = _ctx()
    result = _tools(billing, ctx)["list_invoices"](
        customer_id="123-456-7890",
        billing_setup_id="999",
        issue_year=2026,
        issue_month="july",
        include_granular_details=True,
    )

    assert result["count"] == 0
    name, kwargs = client.calls[0]
    assert name == "InvoiceService.list_invoices"
    assert kwargs["customer_id"] == "1234567890"
    assert kwargs["billing_setup"] == "customers/1234567890/billingSetups/999"
    assert kwargs["issue_year"] == "2026"
    assert kwargs["issue_month"] == client.raw.enums.MonthOfYearEnum.JULY.value
    assert kwargs["include_granular_level_invoice_details"] is True
