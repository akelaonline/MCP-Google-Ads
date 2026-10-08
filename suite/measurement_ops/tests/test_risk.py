from mkt_measurement_ops.risk import RiskLevel, classify_action, requires_confirmation


def test_publish_requires_confirmation() -> None:
    assert classify_action("publish_gtm_version") == RiskLevel.SENSITIVE
    assert requires_confirmation("publish_gtm_version") is True


def test_deploy_requires_confirmation() -> None:
    assert classify_action("deploy_site") == RiskLevel.SENSITIVE
    assert requires_confirmation("deploy_site") is True


def test_audit_is_read_only() -> None:
    assert classify_action("audit_site") == RiskLevel.READ
    assert requires_confirmation("audit_site") is False
