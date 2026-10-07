from mkt_measurement_ops.astro import build_astro_measurement_plan, datalayer_helper_source, gtm_component_source


def test_astro_plan_uses_environment_gtm_id() -> None:
    plan = build_astro_measurement_plan()
    assert plan["environment"]["PUBLIC_GTM_ID"] == "GTM-XXXXXXX"
    assert "PUBLIC_GTM_ID" in gtm_component_source()
    assert "window.dataLayer" in datalayer_helper_source()


def test_astro_plan_requires_single_global_install() -> None:
    plan = build_astro_measurement_plan(layout_path="src/layouts/Base.astro")
    assert plan["layout_path"] == "src/layouts/Base.astro"
    assert "Do not add a second GTM bootstrap" in plan["layout_instruction"]
