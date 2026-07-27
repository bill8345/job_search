"""Persistent dashboard job pool.

Accumulates scored jobs across runs so the dashboard shows a rolling
worklist instead of only the current run's new jobs. Jobs stay until they
age out (POOL_TTL_DAYS). "Applied" state is tracked client-side in the
dashboard (localStorage), so applied jobs are hidden there rather than
removed here — the server never learns which jobs were applied to.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from scrapers.base import Job

_DEFAULT_PATH = "data/dashboard_pool.json"
POOL_TTL_DAYS = 45

# Job attributes persisted per entry — enough to render the dashboard.
_FIELDS = (
    "title", "company", "location", "salary", "url",
    "source", "posted_date", "score", "score_reason",
)


def load_pool(pool_path: str = _DEFAULT_PATH) -> dict:
    """Load the pool, dropping entries older than POOL_TTL_DAYS."""
    path = Path(pool_path)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    cutoff = (date.today() - timedelta(days=POOL_TTL_DAYS)).isoformat()
    return {u: v for u, v in raw.items() if v.get("first_seen", "") >= cutoff}


def save_pool(pool: dict, pool_path: str = _DEFAULT_PATH) -> None:
    path = Path(pool_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def update_pool(new_jobs: list, pool_path: str = _DEFAULT_PATH) -> list:
    """Merge new scored jobs into the pool and return the whole pool as a
    list of Job objects sorted by score (descending)."""
    pool = load_pool(pool_path)
    today = date.today().isoformat()
    for job in new_jobs:
        if not job.url:
            continue
        if job.url in pool:
            # Refresh the score; keep the original first_seen.
            pool[job.url]["score"] = job.score
            pool[job.url]["score_reason"] = job.score_reason
        else:
            record = {f: getattr(job, f) for f in _FIELDS}
            record["first_seen"] = today
            pool[job.url] = record
    save_pool(pool, pool_path)

    jobs = [_to_job(v) for v in pool.values()]
    jobs.sort(key=lambda j: j.score, reverse=True)
    return jobs


def _to_job(record: dict) -> Job:
    return Job(
        title=record.get("title", ""),
        company=record.get("company", ""),
        location=record.get("location", ""),
        salary=record.get("salary", ""),
        description="",
        requirements="",
        url=record.get("url", ""),
        source=record.get("source", ""),
        posted_date=record.get("posted_date", ""),
        score=record.get("score", 0.0),
        score_reason=record.get("score_reason", ""),
    )
