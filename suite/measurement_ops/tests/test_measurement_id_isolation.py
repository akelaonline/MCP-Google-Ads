from types import SimpleNamespace

import pytest

from mkt_measurement_ops import server


def _wire_job(monkeypatch, *, property_id: str | None = "123") -> None:
    monkeypatch.setattr(
        server,
        "_require_planned_job",
        lambda job_id: SimpleNamespace(site_key="cambridge"),
    )
    monkeypatch.setattr(
        server,
        "registry",
        SimpleNamespace(
            get=lambda site_key: SimpleNamespace(
                key=site_key,
                domain="cambridge.com.ar",
                google=SimpleNamespace(ga4_property_id=property_id),
            )
        ),
    )

    def resolve(prop: str, domain: str) -> dict:
        assert prop == "123"
        assert domain == "cambridge.com.ar"
        return {"measurement_id": "G-CAMBRIDGE1"}

    monkeypatch.setattr(
        server,
        "_ga4_admin",
        lambda: SimpleNamespace(resolve_web_stream=resolve),
    )


def test_job_uses_only_its_registered_ga4_web_stream(monkeypatch) -> None:
    _wire_job(monkeypatch)
    assert server._measurement_id_for_job("job-a") == "G-CAMBRIDGE1"
    assert server._measurement_id_for_job("job-a", "g-cambridge1") == "G-CAMBRIDGE1"


def test_cross_customer_measurement_id_override_is_rejected(monkeypatch) -> None:
    _wire_job(monkeypatch)
    with pytest.raises(ValueError, match="does not match"):
        server._measurement_id_for_job("job-a", "G-OTHERCLIENT")


def test_missing_registered_property_cannot_be_bypassed_with_override(monkeypatch) -> None:
    _wire_job(monkeypatch, property_id=None)
    with pytest.raises(ValueError, match="no GA4 property registered"):
        server._measurement_id_for_job("job-a", "G-OTHERCLIENT")


def test_empty_override_is_not_a_way_to_bypass_site_identity(monkeypatch) -> None:
    _wire_job(monkeypatch)
    with pytest.raises(ValueError, match="does not match"):
        server._measurement_id_for_job("job-a", "")
