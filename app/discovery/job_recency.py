
from __future__ import annotations

import re
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "jobs" / "jobpilot.db"

RECENCY_PATTERN = re.compile(
    r"^\s*(\d+)\s+(minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years)\s+ago\s*$",
    re.IGNORECASE,
)


def parse_posted_date(
    posted_date: str | None,
    now: datetime | None = None,
) -> datetime | None:
    """Parse relative dates, ISO timestamps, and YYYY-MM-DD dates."""
    if not posted_date:
        return None

    value = str(posted_date).strip()
    now = now or datetime.now().astimezone()

    match = RECENCY_PATTERN.match(value)
    if match:
        amount = int(match.group(1))
        unit = match.group(2).lower()

        if unit.startswith("minute"):
            delta = timedelta(minutes=amount)
        elif unit.startswith("hour"):
            delta = timedelta(hours=amount)
        elif unit.startswith("day"):
            delta = timedelta(days=amount)
        elif unit.startswith("week"):
            delta = timedelta(weeks=amount)
        elif unit.startswith("month"):
            delta = timedelta(days=amount * 30)
        elif unit.startswith("year"):
            delta = timedelta(days=amount * 365)
        else:
            return None

        return now - delta

    # Support ISO 8601 timestamps, including UTC offsets and Z suffixes.
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=now.tzinfo)
        return parsed.astimezone(now.tzinfo)
    except ValueError:
        pass

    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
        return parsed.replace(tzinfo=now.tzinfo)
    except ValueError:
        return None


def is_posted_within_days(
    posted_date: str | None,
    days: int = 7,
    now: datetime | None = None,
) -> bool:
    """Return True if a parsed date falls within the requested window."""
    if days < 0:
        raise ValueError("days must be >= 0")

    now = now or datetime.now().astimezone()
    parsed_date = parse_posted_date(posted_date, now=now)

    if parsed_date is None:
        return False

    cutoff = now - timedelta(days=days)
    return cutoff <= parsed_date <= now


def get_recent_jobs(
    days: int = 7,
    limit: int | None = None,
) -> list[dict]:
    """Return recently posted or newly discovered jobs."""
    if days < 0:
        raise ValueError("days must be >= 0")

    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        query = "SELECT * FROM jobs"
        if limit is not None:
            query += " LIMIT ?"
            rows = db.execute(query, (max(0, int(limit)),)).fetchall()
        else:
            rows = db.execute(query).fetchall()

    recent_jobs = []

    for row in rows:
        job = dict(row)
        posted_date = job.get("posted_date")

        # Prefer the actual posting date when it can be parsed.
        if parse_posted_date(posted_date) is not None:
            if is_posted_within_days(posted_date, days=days):
                recent_jobs.append(job)
            continue

        # Otherwise use the earliest available discovery timestamp.
        fallback_date = (
            job.get("first_seen_at")
            or job.get("discovered_at")
        )

        if is_posted_within_days(fallback_date, days=days):
            recent_jobs.append(job)

    return recent_jobs
