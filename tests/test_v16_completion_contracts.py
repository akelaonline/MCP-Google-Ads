from __future__ import annotations

from types import SimpleNamespace

import pytest
from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

from google_ads_mcp.tools import asset_generation_optional, experiment_arm_batch


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


class _CapturingSafety:
    def __init__(self):
        self.last = None

    def propose(self, **kwargs):
        self.last = kwargs
        return {
            "status": "pending_confirmation",
            "pending_action_id": "test-action",
            "risk_alias": kwargs["tool_name"],
        }


def _raw_client() -> GoogleAdsClient:
    return GoogleAdsClient(
        credentials=Credentials(token="contract-token"),
        developer_token="contract-developer-token",
        version="v25",
        use_proto_plus=True,
    )


class _ExperimentClient:
    def __init__(self):
        self.raw = _raw_client()
        self.last_mutate = None

    def assert_customer_allowed(self, customer_id: str) -> str:
        value = str(customer_id).replace("-", "").strip()
        if value != "1111111111":
            raise AssertionError(f"unexpected customer {value}")
        return value

    def assert_resource_name_customer(
        self, customer_id: str, resource_name: str, *, field_name: str = "resource_name"
    ) -> str:
        customer = self.assert_customer_allowed(customer_id)
        value = str(resource_name).strip()
        if not value.startswith(f"customers/{customer}/"):
            raise ValueError(f"{field_name} belongs to another customer")
        return value

    def mutate(
        self,
        service_name: str,
        customer_id: str,
        operations,
        *,
        partial_failure: bool = False,
        validate_only: bool = False,
        **kwargs,
    ):
        self.last_mutate = {
            "service_name": service_name,
            "customer_id": customer_id,
            "operations": list(operations),
            "partial_failure": partial_failure,
            "validate_only": validate_only,
        }
        return SimpleNamespace(results=[])


def test_atomic_experiment_split_tool_is_registered_and_builds_one_two_arm_rpc():
    client = _ExperimentClient()
    safety = _CapturingSafety()
    mcp = _FakeMcp()
    experiment_arm_batch.register(mcp, SimpleNamespace(client=client, safety=safety))

    assert "update_experiment_arm_traffic_splits" in mcp.tools
    response = mcp.tools["update_experiment_arm_traffic_splits"](
        customer_id="111-111-1111",
        arms=[
            {
                "experiment_arm_resource_name": (
                    "customers/1111111111/experimentArms/900~1"
                ),
                "traffic_split": 70,
            },
            {
                "experiment_arm_resource_name": (
                    "customers/1111111111/experimentArms/900~2"
                ),
                "traffic_split": 30,
            },
        ],
    )

    assert response["status"] == "pending_confirmation"
    assert safety.last["tool_name"] == "update_experiment_arm"
    assert [item["traffic_split"] for item in safety.last["payload"]["arms"]] == [70, 30]

    safety.last["execute"]()
    call = client.last_mutate
    assert call["service_name"] == "ExperimentArmService"
    assert call["customer_id"] == "1111111111"
    assert call["partial_failure"] is False
    assert len(call["operations"]) == 2
    assert [op.update.traffic_split for op in call["operations"]] == [70, 30]
    assert all(list(op.update_mask.paths) == ["traffic_split"] for op in call["operations"])


def test_atomic_experiment_split_rejects_invalid_total_and_mixed_experiments():
    client = _ExperimentClient()
    safety = _CapturingSafety()
    mcp = _FakeMcp()
    experiment_arm_batch.register(mcp, SimpleNamespace(client=client, safety=safety))
    tool = mcp.tools["update_experiment_arm_traffic_splits"]

    with pytest.raises(ValueError, match="total exactly 100"):
        tool(
            "1111111111",
            [
                {
                    "experiment_arm_resource_name": "customers/1111111111/experimentArms/900~1",
                    "traffic_split": 60,
                },
                {
                    "experiment_arm_resource_name": "customers/1111111111/experimentArms/900~2",
                    "traffic_split": 30,
                },
            ],
        )

    with pytest.raises(ValueError, match="same experiment"):
        tool(
            "1111111111",
            [
                {
                    "experiment_arm_resource_name": "customers/1111111111/experimentArms/900~1",
                    "traffic_split": 50,
                },
                {
                    "experiment_arm_resource_name": "customers/1111111111/experimentArms/901~2",
                    "traffic_split": 50,
                },
            ],
        )


class _AssetGenerationService:
    def __init__(self, raw):
        self.raw = raw
        self.calls = []

    def generate_text(self, request):
        assert request.customer_id == "1111111111"
        self.calls.append(("text", request))
        return self.raw.get_type("GenerateTextResponse")

    def generate_images(self, request):
        assert request.customer_id == "1111111111"
        self.calls.append(("images", request))
        return self.raw.get_type("GenerateImagesResponse")


class _AssetGenerationClient:
    def __init__(self):
        self.raw = _raw_client()
        self.asset_generation_service = _AssetGenerationService(self.raw)

    def assert_customer_allowed(self, customer_id: str) -> str:
        value = str(customer_id).replace("-", "").strip()
        if value != "1111111111":
            raise AssertionError(f"unexpected customer {value}")
        return value

    def service(self, name: str):
        assert name == "AssetGenerationService"
        return self.asset_generation_service


def test_asset_generation_v25_contracts_are_registered_and_customer_scoped():
    client = _AssetGenerationClient()
    mcp = _FakeMcp()
    asset_generation_optional.register(mcp, SimpleNamespace(client=client))

    assert "generate_google_ads_text_assets" in mcp.tools
    assert "generate_google_ads_image_assets" in mcp.tools

    assert mcp.tools["generate_google_ads_text_assets"]("1111111111", {}) == {}
    assert mcp.tools["generate_google_ads_image_assets"]("1111111111", {}) == {}
    assert [kind for kind, _ in client.asset_generation_service.calls] == ["text", "images"]


def test_asset_generation_rejects_customer_id_inside_protobuf_payload():
    client = _AssetGenerationClient()
    mcp = _FakeMcp()
    asset_generation_optional.register(mcp, SimpleNamespace(client=client))

    with pytest.raises(ValueError, match="Do not put customer_id"):
        mcp.tools["generate_google_ads_text_assets"](
            "1111111111", {"customer_id": "2222222222"}
        )
