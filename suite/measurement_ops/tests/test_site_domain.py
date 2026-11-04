import pytest

from mkt_measurement_ops.models import DeploymentMode, SitePlatform, SiteTarget


def make_site(domain: str) -> SiteTarget:
    return SiteTarget(
        key="test-site",
        domain=domain,
        platform=SitePlatform.STATIC,
        deployment_mode=DeploymentMode.MANUAL,
    )


@pytest.mark.parametrize("domain", ["example.com", "www.example.com", "cambridge.com.ar", "foo-bar.example.org"])
def test_normal_public_hostname_allowed(domain: str) -> None:
    make_site(domain).validate()


@pytest.mark.parametrize(
    "domain",
    [
        "https://example.com",
        "example.com:8080",
        "example.com/admin",
        "user@example.com",
        "127.0.0.1",
        "169.254.169.254",
        "myhost.local",
        "internal.internal",
        "localhost",
        "-bad.example.com",
    ],
)
def test_invalid_site_destination_rejected(domain: str) -> None:
    with pytest.raises(ValueError, match="domain|DNS|IP"):
        make_site(domain).validate()
