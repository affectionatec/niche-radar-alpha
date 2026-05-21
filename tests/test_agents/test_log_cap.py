"""Verify JobManager.append_log truncates FIFO once it exceeds the cap."""

from niche_radar.api.jobs import JobManager


def test_log_cap_truncates_oldest_lines():
    mgr = JobManager()
    job = mgr.create("analyze")
    cap = JobManager._MAX_LOG_LINES_PER_JOB

    # Push 2x the cap; only the most recent `cap` lines should remain.
    for i in range(cap * 2):
        mgr.append_log(job.id, f"line {i}")

    retrieved = mgr.get(job.id)
    assert retrieved is not None
    assert len(retrieved.logs) == cap
    # The first kept line is the (cap)th one we wrote (0-indexed: line `cap`).
    assert retrieved.logs[0] == f"line {cap}"
    assert retrieved.logs[-1] == f"line {2 * cap - 1}"


def test_log_cap_no_truncation_below_limit():
    mgr = JobManager()
    job = mgr.create("analyze")
    for i in range(10):
        mgr.append_log(job.id, f"line {i}")
    retrieved = mgr.get(job.id)
    assert len(retrieved.logs) == 10
