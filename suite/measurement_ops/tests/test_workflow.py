import pytest

from mkt_measurement_ops.workflow import JobState, MeasurementJob


def _prepared_job() -> MeasurementJob:
    job = MeasurementJob(site_key="cambridge")
    job.transition(JobState.AUDITED)
    job.transition(JobState.PLANNED)
    job.transition(JobState.PREPARED)
    return job


def test_job_cannot_skip_preview_verification_or_approval() -> None:
    job = _prepared_job()
    with pytest.raises(ValueError, match="invalid transition"):
        job.transition(JobState.PUBLISHED)


def test_approval_requires_positive_preview_evidence() -> None:
    job = _prepared_job()
    job.transition(JobState.PREVIEW_VERIFIED)
    with pytest.raises(ValueError, match="preview-verification"):
        job.transition(JobState.APPROVED)


def test_publish_requires_preview_verification_and_approval() -> None:
    job = _prepared_job()
    job.transition(
        JobState.PREVIEW_VERIFIED,
        evidence={"kind": "preview_verification", "passed": True},
    )
    job.transition(JobState.APPROVED)
    job.transition(JobState.PUBLISHING)
    job.transition(JobState.PUBLISHED)
    assert job.state == JobState.PUBLISHED


def test_job_is_not_complete_until_production_verification() -> None:
    job = _prepared_job()
    job.transition(
        JobState.PREVIEW_VERIFIED,
        evidence={"kind": "preview_verification", "passed": True},
    )
    job.transition(JobState.APPROVED)
    job.transition(JobState.PUBLISHED)
    job.transition(
        JobState.PRODUCTION_VERIFIED,
        evidence={"kind": "production_verification", "passed": True},
    )
    assert job.state == JobState.PRODUCTION_VERIFIED
