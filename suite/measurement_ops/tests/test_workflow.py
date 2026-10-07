import pytest

from mkt_measurement_ops.workflow import JobState, MeasurementJob


def test_job_cannot_skip_verification_or_approval() -> None:
    job = MeasurementJob(site_key="cambridge")
    with pytest.raises(ValueError, match="invalid transition"):
        job.transition(JobState.PUBLISHED)


def test_approval_requires_positive_verification_evidence() -> None:
    job = MeasurementJob(site_key="cambridge")
    job.transition(JobState.AUDITED)
    job.transition(JobState.PLANNED)
    job.transition(JobState.PREPARED)
    job.transition(JobState.VERIFIED)
    with pytest.raises(ValueError, match="verification evidence"):
        job.transition(JobState.APPROVED)


def test_verified_job_can_publish_only_after_approval() -> None:
    job = MeasurementJob(site_key="cambridge")
    job.transition(JobState.AUDITED)
    job.transition(JobState.PLANNED)
    job.transition(JobState.PREPARED)
    job.transition(JobState.VERIFIED, evidence={"kind": "verification", "passed": True})
    job.transition(JobState.APPROVED)
    job.transition(JobState.PUBLISHED)
    assert job.state == JobState.PUBLISHED
