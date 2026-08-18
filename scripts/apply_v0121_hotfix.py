from pathlib import Path


ads_path = Path("src/google_ads_mcp/tools/ads.py")
text = ads_path.read_text()
start = "    @mcp.tool()\n    def create_video_ad("
end = "    @mcp.tool()\n    def update_responsive_search_ad("
i = text.index(start)
j = text.index(end, i)
replacement = '''    @mcp.tool()
    def create_video_ad(
        customer_id: str,
        ad_group_id: str,
        youtube_video_id: str,
        headline: str,
        final_urls: list[str],
        description1: str | None = None,
        description2: str | None = None,
        companion_banner_asset_resource_name: str | None = None,
    ) -> dict:
        """Compatibility endpoint for legacy Video campaigns; never mutates."""
        return {
            "status": "unsupported",
            "reason": (
                "Google Ads API v25 supports legacy VIDEO campaigns for fetching and "
                "reporting only; it does not support creating or updating Video campaigns "
                "or their ads. No Google Ads mutation was attempted."
            ),
            "replacement_tool": "create_demand_gen_video_ad",
            "migration": (
                "Use a DEMAND_GEN campaign/ad group and create_demand_gen_video_ad for "
                "programmatic video delivery across YouTube and other Demand Gen inventory."
            ),
            "customer_id": customer_id,
            "ad_group_id": ad_group_id,
            "youtube_video_id": youtube_video_id,
        }

    @mcp.tool()
    def create_demand_gen_video_ad(
        customer_id: str,
        ad_group_id: str,
        youtube_video_ids: list[str],
        headlines: list[str],
        long_headlines: list[str],
        descriptions: list[str],
        business_name: str,
        final_urls: list[str],
        logo_image_urls: list[str],
    ) -> dict:
        """Create a PAUSED Demand Gen video responsive ad atomically."""
        if not (1 <= len(youtube_video_ids) <= 5):
            raise ValueError("Provide between 1 and 5 YouTube video IDs.")
        if any(len(video_id) != 11 for video_id in youtube_video_ids):
            raise ValueError("Each youtube_video_id must be the 11-character YouTube ID.")
        if not (1 <= len(headlines) <= 5):
            raise ValueError("Provide between 1 and 5 Demand Gen video headlines.")
        if any(len(value) > 40 for value in headlines):
            raise ValueError("Each Demand Gen video headline must be 40 characters or fewer.")
        if not (1 <= len(long_headlines) <= 5):
            raise ValueError("Provide between 1 and 5 Demand Gen video long headlines.")
        if any(len(value) > 90 for value in long_headlines):
            raise ValueError("Each Demand Gen video long headline must be 90 characters or fewer.")
        if not (1 <= len(descriptions) <= 5):
            raise ValueError("Provide between 1 and 5 Demand Gen video descriptions.")
        if any(len(value) > 90 for value in descriptions):
            raise ValueError("Each Demand Gen video description must be 90 characters or fewer.")
        if not business_name or len(business_name) > 25:
            raise ValueError("business_name is required and must be 25 characters or fewer.")
        if not final_urls:
            raise ValueError("Provide at least one final URL.")
        if not (1 <= len(logo_image_urls) <= 5):
            raise ValueError("Provide between 1 and 5 square logo image URLs.")

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        ad_group_resource_name = client.get_service("AdGroupService").ad_group_path(
            customer_id_clean, ad_group_id
        )
        description_text = (
            f"Create Demand Gen video responsive ad in ad group {ad_group_id} "
            f"({len(youtube_video_ids)} video(s), {len(headlines)} headline(s)), "
            "created PAUSED; atomic mutation"
        )

        def execute():
            operations = []
            video_refs: list[str] = []
            next_temp_id = -1

            for youtube_video_id in youtube_video_ids:
                resource_name = client.get_service("AssetService").asset_path(
                    customer_id_clean, next_temp_id
                )
                next_temp_id -= 1
                asset_operation = client.get_type("AssetOperation")
                asset_operation.create.resource_name = resource_name
                asset_operation.create.youtube_video_asset.youtube_video_id = youtube_video_id
                operations.append(_wrap_mutate(client, "asset_operation", asset_operation))
                video_refs.append(resource_name)

            logo_refs, logo_ops, next_temp_id = _build_image_asset_operations(
                client,
                customer_id_clean,
                logo_image_urls,
                next_temp_id,
                max_bytes=_DEMAND_GEN_LOGO_MAX_BYTES,
            )
            operations.extend(logo_ops)

            ad_operation = client.get_type("AdGroupAdOperation")
            ad_group_ad = ad_operation.create
            ad_group_ad.ad_group = ad_group_resource_name
            ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED
            ad = ad_group_ad.ad
            ad.final_urls.extend(final_urls)
            demand_gen_video = ad.demand_gen_video_responsive_ad
            demand_gen_video.business_name.text = business_name

            for resource_name in video_refs:
                video_link = client.get_type("AdVideoAsset")
                video_link.asset = resource_name
                demand_gen_video.videos.append(video_link)
            for resource_name in logo_refs:
                demand_gen_video.logo_images.append(_image_ref(client, resource_name))
            for value in headlines:
                demand_gen_video.headlines.append(_text_asset(client, value))
            for value in long_headlines:
                demand_gen_video.long_headlines.append(_text_asset(client, value))
            for value in descriptions:
                demand_gen_video.descriptions.append(_text_asset(client, value))

            operations.append(_wrap_mutate(client, "ad_group_ad_operation", ad_operation))
            return ctx.client.mutate_atomic(customer_id, operations)

        return ctx.safety.propose(
            tool_name="create_demand_gen_video_ad",
            customer_id=customer_id,
            description=description_text,
            payload={
                "ad_group_id": ad_group_id,
                "youtube_video_ids": youtube_video_ids,
                "headlines": headlines,
                "long_headlines": long_headlines,
                "descriptions": descriptions,
                "business_name": business_name,
                "final_urls": final_urls,
                "logo_image_urls": logo_image_urls,
            },
            execute=execute,
        )

'''
text = text[:i] + replacement + text[j:]
text = text.replace(
    "_IMAGE_MAX_BYTES = 5_120_000\n",
    "_IMAGE_MAX_BYTES = 5_120_000\n_DEMAND_GEN_LOGO_MAX_BYTES = 150_000\n",
    1,
)
text = text.replace(
    "    next_temp_id: int,\n):\n    resource_names: list[str] = []",
    "    next_temp_id: int,\n    *,\n    max_bytes: int = _IMAGE_MAX_BYTES,\n):\n    resource_names: list[str] = []",
    1,
)
text = text.replace(
    "image_bytes = fetch_public_https_image(url, max_bytes=_IMAGE_MAX_BYTES)",
    "image_bytes = fetch_public_https_image(url, max_bytes=max_bytes)",
)
ads_path.write_text(text)

pyproject = Path("pyproject.toml")
pyproject.write_text(pyproject.read_text().replace('version = "0.12.0"', 'version = "0.12.1"', 1))

init_path = Path("src/google_ads_mcp/__init__.py")
init_path.write_text(init_path.read_text().replace('__version__ = "0.12.0"', '__version__ = "0.12.1"', 1))

readme = Path("README.md")
r = readme.read_text().replace("version-0.12.0", "version-0.12.1")
r = r.replace(
    "| **Ads** | Responsive Search, Responsive Display, Video and Demand Gen creatives; RSA edits; legacy Call Ad compatibility via RSA + Call Asset |",
    "| **Ads** | Responsive Search, Responsive Display, Demand Gen image/video creatives; RSA edits; legacy Call Ad compatibility via RSA + Call Asset; legacy VIDEO writes blocked safely |",
)
if "## v0.12.1 video hotfix" not in r:
    note = '''## v0.12.1 video hotfix

Google Ads API v25 exposes legacy `VIDEO` campaigns for fetching/reporting only. `create_video_ad` is retained as a compatibility endpoint but now returns `status=unsupported` and performs **no mutation**. Use `create_demand_gen_video_ad` for supported programmatic video creation. The Demand Gen video flow creates YouTube video assets, logo assets and the PAUSED `DemandGenVideoResponsiveAd` atomically.

'''
    r = r.replace("## v0.12 compatibility & hardening\n", note + "## v0.12 compatibility & hardening\n", 1)
readme.write_text(r)

tools = Path("docs/TOOLS.md")
t = tools.read_text()
old_start = "### `create_video_ad(customer_id, ad_group_id, youtube_video_id, headline, final_urls, description1=None, description2=None, companion_banner_asset_resource_name=None)` `[write]`\n"
old_end = "### `create_call_ad("
a = t.index(old_start)
b = t.index(old_end, a)
video_docs = '''### `create_video_ad(customer_id, ad_group_id, youtube_video_id, headline, final_urls, description1=None, description2=None, companion_banner_asset_resource_name=None)`
**Compatibility endpoint; no write.** Google Ads API v25 only supports fetching/reporting for legacy `VIDEO` campaigns. This tool returns `status=unsupported`, performs no mutation, and points clients to `create_demand_gen_video_ad`.

### `create_demand_gen_video_ad(customer_id, ad_group_id, youtube_video_ids, headlines, long_headlines, descriptions, business_name, final_urls, logo_image_urls)` `[write]`
Creates YouTube video assets, square logo assets and a PAUSED `DemandGenVideoResponsiveAd` in one atomic `GoogleAdsService.Mutate` request. Supports 1-5 videos/headlines/long-headlines/descriptions/logos. Headlines are <=40 chars, long headlines/descriptions <=90, business name <=25.

'''
t = t[:a] + video_docs + t[b:]
tools.write_text(t)

changelog = Path("CHANGELOG.md")
c = changelog.read_text()
if "## 0.12.1 — 2026-08-18" not in c:
    entry = '''# Changelog

## 0.12.1 — 2026-08-18

### Fixed
- **P0 production safety:** `create_video_ad` no longer attempts an unsupported legacy VIDEO mutation. Google Ads API v25 only permits fetching/reporting for legacy VIDEO campaigns; the compatibility endpoint now fails safe with a structured `unsupported` result and zero mutation.
- Added real-v25 contract coverage so a legacy `ad.video_ad` write path cannot silently return.

### Added
- **`create_demand_gen_video_ad`** — supported programmatic video path using `DemandGenVideoResponsiveAd`, existing YouTube video IDs, square logos, text assets and an atomic multi-resource mutation. Created PAUSED.

### Changed
- Version bumped to 0.12.1 and docs now distinguish legacy VIDEO reporting from Demand Gen video creation.

## 0.12.0 — 2026-08-18

### Fixed
- Google Ads API v25 compatibility and hardening across campaigns, ads, assets, PMax, bidding, targeting, audiences, conversions, recommendations, atomic writes, SSRF protections and audit/retry behavior. See `docs/RELEASE_0.12.0.md` for the full release notes.

'''
    c = c.replace("# Changelog\n\n", entry, 1)
changelog.write_text(c)

Path("docs/RELEASE_0.12.1.md").write_text('''# v0.12.1 — Production video hotfix

v0.12.1 closes a production-safety gap discovered after the v0.12 API-contract audit.

## Fixed

- Legacy Google Ads `VIDEO` campaigns are fetch/report-only through Google Ads API v25.
- `create_video_ad` is retained for client compatibility but performs no mutation and returns an explicit migration response.
- Added a source/contract regression guard that fails if the unsupported `ad.video_ad` write path returns.

## Added

- `create_demand_gen_video_ad` creates supported Demand Gen video responsive ads.
- The tool accepts 1-5 existing YouTube video IDs, 1-5 headlines, long headlines, descriptions and square logos.
- YouTube assets, logo assets and the PAUSED ad are created atomically with `GoogleAdsService.Mutate`.

## Operational impact

Existing clients can continue to discover/call `create_video_ad` without causing an unsupported Google Ads write. They receive a structured `unsupported` response and the replacement tool name. New video automation should use Demand Gen.
''')

Path("tests/test_video_v25_hotfix.py").write_text(r'''"""Production guardrails for Google Ads v25 video behavior."""

from __future__ import annotations

import inspect
from types import SimpleNamespace

from conftest import FakeAuditLog, FakeMcp
from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

from google_ads_mcp.context import AppContext
from google_ads_mcp.safety import SafetyLayer
from google_ads_mcp.tools import ads


def _ctx():
    captured = []
    raw = GoogleAdsClient(
        credentials=Credentials(token="contract-test-token"),
        developer_token="contract-test-developer-token",
        version="v25",
        use_proto_plus=True,
    )

    def mutate(service_name, customer_id, operations, **kwargs):
        captured.append((service_name, customer_id, list(operations), kwargs))
        return {"service": service_name}

    def mutate_atomic(customer_id, operations, **kwargs):
        operation_list = list(operations)
        captured.append(("GoogleAdsService", customer_id, operation_list, kwargs))
        return {"service": "GoogleAdsService", "operation_count": len(operation_list)}

    client = SimpleNamespace(raw=raw, mutate=mutate, mutate_atomic=mutate_atomic)
    audit = FakeAuditLog()
    safety = SafetyLayer(auto_approve=True, ttl_minutes=30, audit_log=audit)
    return AppContext(settings=None, client=client, safety=safety, audit=audit), captured


def _tools(ctx):
    mcp = FakeMcp()
    ads.register(mcp, ctx)
    return mcp.registered


def test_legacy_video_create_is_fail_safe_and_never_mutates():
    ctx, captured = _ctx()
    result = _tools(ctx)["create_video_ad"](
        customer_id="1234567890",
        ad_group_id="222",
        youtube_video_id="abcdefghijk",
        headline="Learn more",
        final_urls=["https://example.com"],
    )

    assert result["status"] == "unsupported"
    assert result["replacement_tool"] == "create_demand_gen_video_ad"
    assert captured == []


def test_demand_gen_video_builds_real_v25_atomic_operations(monkeypatch):
    ctx, captured = _ctx()
    monkeypatch.setattr(
        ads,
        "fetch_public_https_image",
        lambda *args, **kwargs: b"contract-logo",
    )
    result = _tools(ctx)["create_demand_gen_video_ad"](
        customer_id="1234567890",
        ad_group_id="222",
        youtube_video_ids=["abcdefghijk"],
        headlines=["A short headline", "Another headline"],
        long_headlines=["A longer Demand Gen video headline"],
        descriptions=["A Demand Gen video description"],
        business_name="Akela",
        final_urls=["https://example.com"],
        logo_image_urls=["https://example.com/logo.png"],
    )

    assert result["status"] == "executed"
    service, customer_id, operations, _ = captured[0]
    assert service == "GoogleAdsService"
    assert customer_id == "1234567890"
    assert len(operations) == 3
    assert operations[0].asset_operation.create.youtube_video_asset.youtube_video_id == "abcdefghijk"
    ad_group_ad = operations[-1].ad_group_ad_operation.create
    assert ad_group_ad.status.name == "PAUSED"
    assert list(ad_group_ad.ad.final_urls) == ["https://example.com"]
    video = ad_group_ad.ad.demand_gen_video_responsive_ad
    assert video.business_name.text == "Akela"
    assert len(video.videos) == 1
    assert len(video.logo_images) == 1
    assert len(video.headlines) == 2
    assert len(video.long_headlines) == 1
    assert len(video.descriptions) == 1


def test_source_has_no_legacy_video_ad_write_path():
    source = inspect.getsource(ads)
    assert ".ad.video_ad" not in source
    assert "demand_gen_video_responsive_ad" in source
''')
