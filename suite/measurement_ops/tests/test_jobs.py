from mkt_measurement_ops.jobs import JobStore
from mkt_measurement_ops.workflow import JobState


def test_job_store_survives_reopen(tmp_path) -> None:
    path = tmp_path / "jobs.db"
    first = JobStore(path)
    job = first.create("cambridge")
    first.transition(job.id, JobState.AUDITED, evidence={"kind": "audit", "pages": 4})

    second = JobStore(path)
    restored = second.get(job.id)

    assert restored.site_key == "cambridge"
    assert restored.state == JobState.AUDITED
    assert restored.evidence == [{"kind": "audit", "pages": 4}]


def test_job_store_preserves_preview_verification_gate(tmp_path) -> None:
    store = JobStore(tmp_path / "jobs.db")
    job = store.create("cambridge")
    store.transition(job.id, JobState.AUDITED)
    store.transition(job.id, JobState.PLANNED)
    store.transition(job.id, JobState.PREPARED)
    store.transition(
        job.id,
        JobState.PREVIEW_VERIFIED,
        evidence={"kind": "preview_verification", "passed": True, "checks": ["gtm_preview"]},
    )
    approved = store.transition(job.id, JobState.APPROVED)

    assert approved.state == JobState.APPROVED


def test_atomic_publish_claim_can_only_be_taken_once(tmp_path) -> None:
    store = JobStore(tmp_path / "jobs.db")
    job = store.create("cambridge")
    store.transition(job.id, JobState.AUDITED)
    store.transition(job.id, JobState.PLANNED)
    store.transition(job.id, JobState.PREPARED)
    store.transition(
        job.id,
        JobState.PREVIEW_VERIFIED,
        evidence={"kind": "preview_verification", "passed": True},
    )
    store.transition(job.id, JobState.APPROVED)

    claimed = store.claim(
        job.id,
        expected=JobState.APPROVED,
        target=JobState.PUBLISHING,
    )
    assert claimed.state == JobState.PUBLISHING

    try:
        store.claim(
            job.id,
            expected=JobState.APPROVED,
            target=JobState.PUBLISHING,
        )
    except ValueError as exc:
        assert "expected approved, found publishing" in str(exc)
    else:
        raise AssertionError("second publish claim unexpectedly succeeded")
