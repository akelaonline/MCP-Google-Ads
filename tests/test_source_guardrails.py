"""Static regression guards for bugs that were previously hidden by test fakes."""

from __future__ import annotations

from pathlib import Path


SRC = Path(__file__).parents[1] / "src" / "google_ads_mcp"


def _matches(needle: str) -> list[str]:
    hits = []
    for path in sorted(SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if needle in line:
                hits.append(f"{path.relative_to(SRC)}:{lineno}: {line.strip()}")
    return hits


def test_no_native_protobuf_set_in_parent_calls():
    hits = _matches(".SetInParent(")
    assert not hits, "Proto-plus does not expose SetInParent():\n" + "\n".join(hits)


def test_removed_call_ad_proto_does_not_return():
    hits = _matches(".call_ad")
    assert not hits, "CallAd was removed from current Google Ads API:\n" + "\n".join(hits)


def test_removed_message_asset_proto_does_not_return():
    hits = _matches(".message_asset")
    assert not hits, "MessageAsset was replaced by BusinessMessageAsset:\n" + "\n".join(hits)


def test_removed_campaign_date_fields_do_not_return():
    hits = _matches("campaign.start_date =") + _matches("campaign.end_date =")
    assert not hits, "Use v25 campaign start_date_time/end_date_time:\n" + "\n".join(hits)
