"""December 2026 Google Ads API changes (confirmed in Google's developer blog).

* 2026-12-04  PMax image extraction (GENERATE_IMAGE_EXTRACTION) defaults to
              OPTED_IN on new campaigns -> proposals must say so, and callers
              can opt out explicitly.
* week of 2026-12-07  multi-party approvals -> "executed" is not "completed":
              a result with a review is pending Google authorization.
* week of 2026-12-01  Demand Gen: network_settings.target_content_network can
              no longer be set to false; this server never sets it.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from test_v25_contracts import _ctx, _register

from google_ads_mcp import safety as safety_module
from google_ads_mcp.tools import performance_max


def _pmax(**kwargs):
    ctx, captured = _ctx()
    tool = _register(performance_max, ctx)["create_performance_max_campaign"]
    result = tool(
        customer_id="1234567890",
        name="PMax",
        campaign_budget_resource_name="customers/1234567890/campaignBudgets/1",
        **kwargs,
    )
    return result, captured[0][2][0].create


def test_pmax_without_explicit_setting_documents_the_google_default():
    result, campaign = _pmax()
    assert len(campaign.asset_automation_settings) == 0
    assert result["status"] == "executed"
    assert "2026-12-04" in str(result)  # proposal states the new default


@pytest.mark.parametrize("value", ["OPTED_OUT", "opted_in"])
def test_pmax_explicit_image_extraction_is_sent(value):
    _, campaign = _pmax(image_extraction=value)
    (setting,) = campaign.asset_automation_settings
    assert setting.asset_automation_type.name == "GENERATE_IMAGE_EXTRACTION"
    assert setting.asset_automation_status.name == value.upper()


def test_pmax_rejects_unknown_image_extraction_value():
    with pytest.raises(ValueError, match="OPTED_IN or OPTED_OUT"):
        _pmax(image_extraction="MAYBE")


class _Result:
    def __init__(self, resource_name="", review=""):
        self.resource_name = resource_name
        self.multi_party_auth_review = review


def test_mpa_pending_result_is_distinguished_from_completed():
    pending = safety_module._safe_result(
        SimpleNamespace(result=_Result(review="customers/1/multiPartyAuthReviews/9"))
    )
    assert pending["approval_state"] == "PENDING_GOOGLE_AUTHORIZATION"
    assert pending["multi_party_auth_review"].endswith("/9")
    assert "resource_name" not in pending  # deferred invitation: nothing exists yet

    done = safety_module._safe_result(
        SimpleNamespace(result=_Result(resource_name="customers/1/customerUserAccessInvitations/2"))
    )
    assert done["approval_state"] == "COMPLETED"
    assert done["resource_name"].endswith("/2")


def test_results_without_mpa_field_have_no_approval_state():
    plain = safety_module._safe_result(
        SimpleNamespace(result=SimpleNamespace(resource_name="customers/1"))
    )
    assert "approval_state" not in plain


def test_server_never_sets_target_content_network():
    root = Path(performance_max.__file__).resolve().parents[1]
    offenders = [
        str(path.relative_to(root))
        for path in root.rglob("*.py")
        if "target_content_network" in path.read_text()
    ]
    assert offenders == []
