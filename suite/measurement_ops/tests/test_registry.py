import pytest

from mkt_measurement_ops.models import DeploymentMode, SitePlatform, SiteTarget
from mkt_measurement_ops.registry import SiteRegistry


def test_astro_github_requires_repo() -> None:
    site = SiteTarget(
        key="cambridge",
        domain="cambridge.com.ar",
        platform=SitePlatform.ASTRO,
        deployment_mode=DeploymentMode.GITHUB,
    )
    with pytest.raises(ValueError, match="repository"):
        site.validate()


def test_registry_rejects_duplicate_domains() -> None:
    first = SiteTarget(
        key="a",
        domain="example.com",
        platform=SitePlatform.STATIC,
        deployment_mode=DeploymentMode.MANUAL,
    )
    second = SiteTarget(
        key="b",
        domain="EXAMPLE.com",
        platform=SitePlatform.STATIC,
        deployment_mode=DeploymentMode.MANUAL,
    )
    registry = SiteRegistry([first])
    with pytest.raises(ValueError, match="duplicate site domain"):
        registry.add(second)
