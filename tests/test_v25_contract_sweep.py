"""v25 contract sweep: every service and mutate method the codebase touches
must exist on the real v25 stubs.

This is the regression guard for the class of latent bugs where the repo's
pluralizer or service naming drifted from the real Google Ads API v25 surface
(for example `STANDARD_SHOPPING` channel sub-type, `TopicConstantService`,
`mutate_customers` vs the real `mutate_customer`). The offline fakes are more
permissive than v25, so only a sweep against the real stubs can catch these.
"""

from __future__ import annotations

import re
from pathlib import Path

from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

from google_ads_mcp.client import _mutate_method_name

_SRC = Path(__file__).resolve().parents[1] / "src" / "google_ads_mcp"

_SERVICE_CALL = re.compile(
    r'(?:get_service\(|mutate\(|mutate_atomic\()"([A-Za-z0-9]+)"'
)


def _services_used() -> set[str]:
    services: set[str] = set()
    for path in (_SRC / "tools").glob("*.py"):
        services.update(_SERVICE_CALL.findall(path.read_text()))
    services.update(_SERVICE_CALL.findall((_SRC / "client.py").read_text()))
    services.update(_SERVICE_CALL.findall((_SRC / "scoped_client.py").read_text()))
    return services


def _services_mutated() -> set[str]:
    mutated: set[str] = set()
    for path in (_SRC / "tools").glob("*.py"):
        for match in re.finditer(r'ctx\.client\.mutate\("([A-Za-z0-9]+)"', path.read_text()):
            mutated.add(match.group(1))
    return mutated


def _client() -> GoogleAdsClient:
    return GoogleAdsClient(
        credentials=Credentials(token="contract-token"),
        developer_token="contract-developer-token",
        version="v25",
        use_proto_plus=True,
    )


def test_every_used_service_exists_on_real_v25_stubs():
    client = _client()
    missing = []
    for service_name in sorted(_services_used()):
        try:
            client.get_service(service_name)
        except ValueError:
            missing.append(service_name)
    assert missing == [], f"services used but missing from v25: {missing}"


def test_every_mutated_service_has_a_real_mutate_method():
    client = _client()
    broken = []
    for service_name in sorted(_services_mutated()):
        method = _mutate_method_name(service_name)
        service = client.get_service(service_name)
        if not hasattr(service, method):
            broken.append(f"{service_name} -> {method}")
    assert broken == [], (
        "services mutated with methods that do not exist on the real v25 stubs: "
        f"{broken}"
    )


def test_irregular_plural_services_map_to_real_stub_methods():
    assert _mutate_method_name("CustomerService") == "mutate_customer"
    assert _mutate_method_name("BiddingStrategyService") == "mutate_bidding_strategies"


def test_topic_targeting_uses_global_topic_constant_resource_name():
    # Topic constants are global "topicConstants/{id}" resources; v25 has no
    # TopicConstantService stub. The tool must build the name inline.
    source = (_SRC / "tools" / "audiences.py").read_text()
    assert 'get_service("TopicConstantService")' not in source
    assert 'f"topicConstants/{topic_id}"' in source


def test_add_topic_targeting_builds_global_topic_resource_name():
    captured = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        captured.extend(list(operations))
        return []

    from conftest import build_ctx, register_module

    from google_ads_mcp import tools

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.audiences, ctx)
    result = tool_fns["add_topic_targeting"](
        customer_id="123", ad_group_id="456", topic_id="77"
    )
    assert result["status"] == "executed"
    topic = captured[0].create.topic.topic_constant
    assert topic == "topicConstants/77"


def test_new_url_option_tools_use_real_customer_mutate_method():
    # set_account_tracking_url goes through CustomerService, whose v25 stub
    # method is mutate_customer (not mutate_customers) — covered by the sweep,
    # but assert the mapping here so the regression is attributable.
    assert _mutate_method_name("CustomerService") == "mutate_customer"
