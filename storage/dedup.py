"""Persistent URL-based deduplication store across weekly runs.

Stores seen job URLs in data/seen_jobs.json committed to the repo,
so GitHub Actions can filter already-seen jobs on each weekly run.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

_DEFAULT_PATH = "data/seen_jobs.json"


def load_seen(store_path: str = _DEFAULT_PATH) -> dict:
    """Load seen job URL store. Returns empty dict if file missing or corrupt."""
    path = Path(store_path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_seen(seen: dict, store_path: str = _DEFAULT_PATH) -> None:
    """Write seen store back to disk."""
    path = Path(store_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(seen, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def filter_new(jobs: list, seen: dict) -> tuple[list, int]:
    """Return only jobs whose URL hasn't been seen before.

    Returns (new_jobs, skipped_count).
    """
    new_jobs = []
    skipped = 0
    for job in jobs:
        if job.url and job.url in seen:
            skipped += 1
        else:
            new_jobs.append(job)
    return new_jobs, skipped


def mark_seen(jobs: list, seen: dict) -> dict:
    """Add new jobs to the seen store. Returns updated dict."""
    today = date.today().isoformat()
    for job in jobs:
        if job.url and job.url not in seen:
            seen[job.url] = {
                "title": job.title,
                "company": job.company,
                "source": job.source,
                "first_seen": today,
            }
    return seen
