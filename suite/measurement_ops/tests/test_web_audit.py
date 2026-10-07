import pytest

from mkt_measurement_ops.web_audit import UnsafeUrlError, _providers, assert_public_http_url, classify_form


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


def test_classifies_contact_form_as_lead() -> None:
    form = {
        "id": "contact",
        "text": "Pedí presupuesto - Enviar consulta",
        "fields": [
            {"type": "email", "name": "email"},
            {"type": "textarea", "name": "mensaje"},
        ],
        "buttons": ["Enviar"],
    }
    assert classify_form(form) == "lead"


def test_classifies_newsletter_separately_from_lead() -> None:
    form = {
        "text": "Suscribite al newsletter",
        "fields": [{"type": "email", "name": "email"}],
        "buttons": ["Suscribirme"],
    }
    assert classify_form(form) == "newsletter"


def test_login_and_search_are_never_leads() -> None:
    login = {
        "text": "Iniciar sesión",
        "fields": [
            {"type": "email", "name": "email"},
            {"type": "password", "name": "password"},
        ],
    }
    search = {
        "text": "Buscar",
        "fields": [{"type": "search", "name": "q"}],
    }
    assert classify_form(login) == "login"
    assert classify_form(search) == "search"


def test_ambiguous_email_only_form_stays_other() -> None:
    form = {"fields": [{"type": "email", "name": "email"}]}
    assert classify_form(form) == "other"
