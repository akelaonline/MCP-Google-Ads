from mkt_measurement_ops.models import DeploymentMode, GoogleStack, SitePlatform, SiteTarget
from mkt_measurement_ops.registry import SiteRegistry


def test_site_registry_survives_reopen(tmp_path) -> None:
    path = tmp_path / "measurement.db"
    first = SiteRegistry(db_path=path)
    first.add(
        SiteTarget(
            key="cambridge",
            domain="cambridge.com.ar",
            platform=SitePlatform.ASTRO,
            deployment_mode=DeploymentMode.GITHUB,
            repository="akelaonline/cambridge",
            google=GoogleStack(
                gtm_account_id="1",
                gtm_container_id="2",
                ga4_property_id="3",
                google_ads_customer_id="4",
            ),
        )
    )

    second = SiteRegistry(db_path=path)
    site = second.get("cambridge")

    assert site.domain == "cambridge.com.ar"
    assert site.repository == "akelaonline/cambridge"
    assert site.google.ga4_property_id == "3"


def test_persistent_registry_rejects_duplicate_domain_after_reopen(tmp_path) -> None:
    path = tmp_path / "measurement.db"
    first = SiteRegistry(db_path=path)
    first.add(
        SiteTarget(
            key="one",
            domain="example.com",
            platform=SitePlatform.STATIC,
            deployment_mode=DeploymentMode.MANUAL,
        )
    )

    second = SiteRegistry(db_path=path)
    try:
        second.add(
            SiteTarget(
                key="two",
                domain="EXAMPLE.com",
                platform=SitePlatform.STATIC,
                deployment_mode=DeploymentMode.MANUAL,
            )
        )
    except ValueError as exc:
        assert "duplicate site domain" in str(exc)
    else:
        raise AssertionError("duplicate domain was accepted")
