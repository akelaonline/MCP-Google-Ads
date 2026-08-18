"""Additional static guards against known legacy Google Ads API regressions."""

from __future__ import annotations

from pathlib import Path


SRC = Path(__file__).parents[1] / "src" / "google_ads_mcp"
TOOLS = SRC / "tools"


def _hits(root: Path, needle: str) -> list[str]:
    matches = []
    for path in sorted(root.rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if needle in line:
                matches.append(f"{path.relative_to(SRC)}:{lineno}: {line.strip()}")
    return matches


def test_no_legacy_local_campaign_enum_in_tools():
    hits = _hits(TOOLS, "AdvertisingChannelTypeEnum.LOCAL")
    assert not hits, "Legacy Local campaign enum returned:\n" + "\n".join(hits)


def test_no_legacy_smart_shopping_enum_in_tools():
    hits = _hits(TOOLS, "AdvertisingChannelSubTypeEnum.SMART_SHOPPING")
    assert not hits, "Legacy Smart Shopping enum returned:\n" + "\n".join(hits)


def test_no_removed_recommendation_status_field():
    hits = _hits(TOOLS, "recommendation.status")
    assert not hits, "Recommendation.status is not the current API contract:\n" + "\n".join(hits)


def test_no_direct_urllib_fetches_from_tool_modules():
    hits = _hits(TOOLS, "urllib.request")
    assert not hits, (
        "Tool modules must use google_ads_mcp.net.fetch_public_https_image():\n"
        + "\n".join(hits)
    )


def test_no_mutation_of_immutable_include_in_conversions_metric():
    hits = _hits(TOOLS, ".include_in_conversions_metric =")
    assert not hits, (
        "ConversionAction.include_in_conversions_metric is immutable; use primary_for_goal:\n"
        + "\n".join(hits)
    )


def test_no_silent_partial_failure_true_in_normal_mutate_tools():
    hits = _hits(TOOLS, "partial_failure=True")
    assert not hits, (
        "Normal mutate helpers must not silently accept partial failure without parsing it:\n"
        + "\n".join(hits)
    )
