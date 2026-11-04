from mkt_measurement_ops.astro import (
    build_astro_measurement_plan,
    datalayer_helper_source,
    gtm_body_component_source,
    gtm_head_component_source,
)


def test_astro_plan_uses_environment_gtm_id() -> None:
    plan = build_astro_measurement_plan(gtm_public_id="GTM-ABC123")
    assert plan["environment"]["PUBLIC_GTM_ID"] == "GTM-ABC123"
    assert "PUBLIC_GTM_ID" in gtm_head_component_source()
    assert "PUBLIC_GTM_ID" in gtm_body_component_source()
    assert "window.dataLayer" in datalayer_helper_source()


def test_astro_plan_places_gtm_in_head_and_body() -> None:
    plan = build_astro_measurement_plan(gtm_public_id="GTM-ABC123", layout_path="src/layouts/Base.astro")
    assert plan["layout_path"] == "src/layouts/Base.astro"
    assert "inside <head>" in plan["layout_instruction"]
    assert "immediately after <body>" in plan["layout_instruction"]
    assert "Do not install either component" in plan["layout_instruction"]


def test_astro_plan_rejects_invalid_gtm_public_id() -> None:
    import pytest

    with pytest.raises(ValueError, match="gtm_public_id"):
        build_astro_measurement_plan(gtm_public_id="not-a-container")
