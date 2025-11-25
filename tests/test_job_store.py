"""Tests for persistent job store."""

import json
from pathlib import Path

from src.utils.job_store import JobStore


def test_job_store_crud(tmp_path):
    store_path = tmp_path / "jobs.json"
    store = JobStore(storage_path=str(store_path))

    job_id = "job_1"
    info = {"status": "processing", "progress": 0, "start_time": "2024-01-01T00:00:00", "file": "a.txt"}
    store.create_job(job_id, info)

    loaded = store.get_job(job_id)
    assert loaded["status"] == "processing"

    store.update_job(job_id, {"progress": 50})
    assert store.get_job(job_id)["progress"] == 50

    listed = store.list_jobs()
    assert len(listed) == 1
    assert listed[0]["job_id"] == job_id

    removed = store.delete_job(job_id)
    assert removed["status"] == "processing"
    assert store.get_job(job_id) is None


def test_job_store_persistence(tmp_path):
    store_path = tmp_path / "jobs.json"
    store = JobStore(storage_path=str(store_path))
    job_id = "job_2"
    info = {"status": "completed", "progress": 100, "start_time": "2024-01-01T00:00:00", "file": "b.txt"}
    store.create_job(job_id, info)

    # Rehydrate new instance to ensure persistence works
    store2 = JobStore(storage_path=str(store_path))
    loaded = store2.get_job(job_id)
    assert loaded["status"] == "completed"
    assert loaded["progress"] == 100


def test_job_store_cleanup(tmp_path):
    store_path = tmp_path / "jobs.json"
    store = JobStore(storage_path=str(store_path))

    store.create_job("old", {"status": "processing", "start_time": "2020-01-01T00:00:00", "progress": 0, "file": "x"})
    store.create_job("recent", {"status": "processing", "start_time": "2099-01-01T00:00:00", "progress": 0, "file": "y"})
    removed = store.cleanup_old_jobs(max_age_seconds=1, completed_or_failed_age_seconds=1)
    assert "old" in removed
    assert store.get_job("old") is None
    assert store.get_job("recent") is not None

