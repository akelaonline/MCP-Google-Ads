import pytest

from mkt_measurement_ops.web_audit import UnsafeUrlError, _providers, assert_public_http_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://10.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "ftp://example.com/file",
        "https://user:pass@example.com/",
    ],
)
def test_url_guard_blocks_dangerous_targets(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        assert_public_http_url(url)


def test_provider_detection_covers_common_wordpress_forms() -> None:
    html = '<div class="wpcf7"><form></form></div><div class="wpforms-container"></div>'
    assert _providers(html) == ("contactform7", "wpforms")
