"""
Persistent, thread-safe job store for compliance review tasks.
"""

import json
import os
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


class JobStore:
    """In-memory job store with JSON persistence."""

    def __init__(self, storage_path: str = "data/jobs_state.json"):
        self.storage_path = storage_path
        self._lock = threading.Lock()
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Load jobs from disk if present."""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._jobs = data
        except Exception:
            # Corrupt or unreadable store; start fresh
            self._jobs = {}

    def _persist(self) -> None:
        """Persist current job state to disk atomically."""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        tmp_path = f"{self.storage_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self._jobs, f, indent=2)
        os.replace(tmp_path, self.storage_path)

    def create_job(self, job_id: str, job_info: Dict[str, Any]) -> None:
        with self._lock:
            self._jobs[job_id] = job_info
            self._persist()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def list_jobs(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(info, job_id=job_id) for job_id, info in self._jobs.items()]

    def update_job(self, job_id: str, updates: Dict[str, Any]) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(updates)
                self._persist()

    def delete_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.pop(job_id, None)
            if job is not None:
                self._persist()
                return job
            return None

    def cleanup_old_jobs(
        self,
        max_age_seconds: int,
        completed_or_failed_age_seconds: int = 3600
    ) -> List[str]:
        """Remove old jobs and return list of removed job IDs."""
        removed = []
        now = datetime.now()
        with self._lock:
            for job_id, info in list(self._jobs.items()):
                start_time_str = info.get("start_time")
                try:
                    start_time = datetime.fromisoformat(start_time_str)
                except Exception:
                    start_time = now

                age_seconds = (now - start_time).total_seconds()
                status = info.get("status")
                if age_seconds > max_age_seconds or (
                    status in {"failed", "completed"} and age_seconds > completed_or_failed_age_seconds
                ):
                    removed.append(job_id)
                    self._jobs.pop(job_id, None)

            if removed:
                self._persist()

        return removed
