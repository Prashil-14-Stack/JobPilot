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
    """
    Convert a JobPilot posted_date value into
    an absolute datetime.

    Supported examples:

        17 minutes ago
        5 hours ago
        3 days ago
        1 week ago
        2026-10-02

    Returns None when the value cannot be interpreted.
    """

    if not posted_date:
        return None

    value = str(posted_date).strip()

    now = now or datetime.now().astimezone()

    match = RECENCY_PATTERN.match(value)

    if match:

        amount = int(
            match.group(1)
        )

        unit = (
            match.group(2)
            .lower()
        )

        if unit.startswith("minute"):
            delta = timedelta(
                minutes=amount
            )

        elif unit.startswith("hour"):
            delta = timedelta(
                hours=amount
            )

        elif unit.startswith("day"):
            delta = timedelta(
                days=amount
            )

        elif unit.startswith("week"):
            delta = timedelta(
                weeks=amount
            )

        elif unit.startswith("month"):
            delta = timedelta(
                days=amount * 30
            )

        elif unit.startswith("year"):
            delta = timedelta(
                days=amount * 365
            )

        else:
            return None

        return now - delta

    try:

        parsed_date = datetime.strptime(
            value,
            "%Y-%m-%d",
        )

        return parsed_date.replace(
            tzinfo=now.tzinfo
        )

    except ValueError:

        return None


def is_posted_within_days(
    posted_date: str | None,
    days: int = 7,
    now: datetime | None = None,
) -> bool:
    """
    Return True when the job was posted within
    the specified number of days.

    Unparseable dates return False.
    """

    if days < 0:
        raise ValueError(
            "days must be >= 0"
        )

    now = now or datetime.now().astimezone()

    parsed_date = parse_posted_date(
        posted_date,
        now=now,
    )

    if parsed_date is None:
        return False

    cutoff = (
        now - timedelta(days=days)
    )

    return parsed_date >= cutoff

def get_recent_jobs(
    days: int = 7,
    limit: int | None = None,
) -> list[dict]:
    """
    Return jobs posted within the specified number of days.

    Jobs with missing or unparseable posted dates are excluded.
    """

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    query = """
        SELECT *
        FROM jobs
        WHERE posted_date IS NOT NULL
    """

    if limit is not None:
        query += f" LIMIT {int(limit)}"

    rows = db.execute(query).fetchall()
    db.close()

    recent_jobs = []

    for row in rows:

        if not is_posted_within_days(
            row["posted_date"],
            days=days,
        ):
            continue

        recent_jobs.append(
            dict(row)
        )

    return recent_jobs