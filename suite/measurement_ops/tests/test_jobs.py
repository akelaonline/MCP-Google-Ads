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
