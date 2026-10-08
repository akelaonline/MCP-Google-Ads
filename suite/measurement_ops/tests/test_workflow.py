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
    job.transition(JobState.PUBLISHING)
    job.transition(JobState.PUBLISHED)
    job.transition(
        JobState.PRODUCTION_VERIFIED,
        evidence={"kind": "production_verification", "passed": True},
    )
    assert job.state == JobState.PRODUCTION_VERIFIED


@pytest.mark.parametrize(
    "bad_evidence",
    [
        None,
        {"kind": "production_verification", "passed": False},
        {"kind": "preview_verification", "passed": True},
        {"kind": "production_verification", "passed": 1},
    ],
)
def test_production_verification_requires_current_passed_evidence(bad_evidence) -> None:
    job = _prepared_job()
    job.transition(
        JobState.PREVIEW_VERIFIED,
        evidence={"kind": "preview_verification", "passed": True},
    )
    job.transition(JobState.APPROVED)
    job.transition(JobState.PUBLISHING)
    job.transition(JobState.PUBLISHED)

    prior = list(job.evidence)
    with pytest.raises(ValueError, match="production-verification evidence"):
        job.transition(JobState.PRODUCTION_VERIFIED, evidence=bad_evidence)
    assert job.state == JobState.PUBLISHED
    assert job.evidence == prior


def test_old_passed_production_evidence_cannot_replace_fresh_result() -> None:
    job = _prepared_job()
    job.transition(
        JobState.PREVIEW_VERIFIED,
        evidence={"kind": "preview_verification", "passed": True},
    )
    job.transition(JobState.APPROVED)
    job.transition(JobState.PUBLISHING)
    job.transition(JobState.PUBLISHED)
    job.evidence.append({"kind": "production_verification", "passed": True})
    with pytest.raises(ValueError, match="production-verification evidence"):
        job.transition(
            JobState.PRODUCTION_VERIFIED,
            evidence={"kind": "production_verification", "passed": False},
        )
    assert job.state == JobState.PUBLISHED
