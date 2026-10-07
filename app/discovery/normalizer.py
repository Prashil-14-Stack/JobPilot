"""
Job normalization layer.

Converts source-deduplicated jobs into a consistent internal
representation while preserving source evidence.

This module does NOT:
- perform AI relevance matching
- perform AI visa analysis
- deduplicate jobs
- discard jobs
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "jobs"
    / "source_deduplicated_jobs.json"
)

OUTPUT_FILE = (
    BASE_DIR
    / "data"
    / "jobs"
    / "normalized_jobs.json"
)


class NormalizedJob(BaseModel):
    """Standard internal representation of a job."""

    job_id: str

    title: Optional[str] = None
    company: Optional[str] = None

    location: Optional[str] = None
    country: Optional[str] = None
    remote_type: Optional[str] = None

    source: Optional[str] = None
    source_job_id: Optional[str] = None

    source_url: Optional[str] = None
    apply_url: Optional[str] = None

    description: Optional[str] = None
    content_mode: str = "FULL_CONTENT"
    highlights: list[str] = Field(default_factory=list)

    posted_date: Optional[str] = None

    canonical_role: Optional[str] = None
    matched_search_variant: Optional[str] = None

    visa_status: Optional[str] = None
    visa_evidence: Optional[str] = None
    work_authorization_requirement: Optional[str] = None

    search_task_id: Optional[str] = None

    normalized_at: str = Field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )

    raw_data: dict[str, Any] = Field(
        default_factory=dict
    )


def load_jobs(
    path: Path,
) -> list[dict[str, Any]]:
    """Load source-deduplicated jobs."""

    if not path.exists():
        raise FileNotFoundError(
            f"Input file not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        jobs = data.get("jobs")

        if isinstance(jobs, list):
            return jobs

    raise ValueError(
        "Expected a JSON list or an object containing "
        "a 'jobs' list."
    )


def first_value(
    record: dict[str, Any],
    *keys: str,
) -> Optional[Any]:
    """
    Return the first non-empty value from the supplied keys.
    """

    for key in keys:

        value = record.get(key)

        if value is None:
            continue

        if isinstance(value, str):

            if not value.strip():
                continue

        return value

    return None

def get_raw_data(
    record: dict[str, Any],
) -> dict[str, Any]:
    """Return the immediate raw_data dictionary when available."""

    raw_data = record.get(
        "raw_data",
        {},
    )

    if isinstance(raw_data, dict):
        return raw_data

    return {}

def normalize_text(
    value: Any,
) -> Optional[str]:
    """Normalize whitespace without changing meaning."""

    if value is None:
        return None

    if not isinstance(value, str):
        value = str(value)

    value = " ".join(
        value.split()
    )

    if not value:
        return None

    return value


def normalize_list(
    value: Any,
) -> list[str]:
    """Convert a value into a clean string list."""

    if value is None:
        return []

    if isinstance(value, list):

        result = []

        for item in value:

            if item is None:
                continue

            text = normalize_text(item)

            if text:
                result.append(text)

        return result

    text = normalize_text(value)

    if text:
        return [text]

    return []


def build_job_id(
    record: dict[str, Any],
    index: int,
) -> str:
    """
    Preserve an existing job ID.

    If none exists, create an internal normalization ID.

    This generated ID is NOT a source identity and must not
    be used for source-level deduplication.
    """

    existing_id = first_value(
        record,
        "job_id",
        "id",
    )

    if existing_id is not None:
        return str(existing_id)

    source = normalize_text(
        first_value(
            record,
            "source",
        )
    )

    if not source:
        source = "unknown"

    safe_source = (
        source
        .lower()
        .replace(" ", "-")
    )

    return (
        f"normalized-{index:06d}-{safe_source}"
    )
def find_nested_value(
    record: Any,
    key: str,
) -> Optional[Any]:
    """
    Recursively search nested dictionaries/lists for a key.

    Used to recover source-specific evidence that may be nested
    at different depths inside raw_data.

    This function does not infer or transform the value.
    It only retrieves an existing source field.
    """

    if isinstance(record, dict):

        if key in record:
            value = record[key]

            if value is not None:
                return value

        for value in record.values():

            result = find_nested_value(
                value,
                key,
            )

            if result is not None:
                return result

    elif isinstance(record, list):

        for item in record:

            result = find_nested_value(
                item,
                key,
            )

            if result is not None:
                return result

    return None

def extract_visa_information(
    record: dict[str, Any],
) -> tuple[
    Optional[str],
    Optional[str],
    Optional[str],
]:
    """
    Extract explicit visa/work-authorization information
    already captured by the source.

    This is deterministic preservation of source evidence.
    It is NOT AI inference.
    """

    visa_status = first_value(
        record,
        "visa_status",
    )

    visa_evidence = first_value(
        record,
        "visa_evidence",
    )

    work_authorization = first_value(
        record,
        "work_authorization_requirement",
        "work_authorization",
    )

    nested_raw_data = record.get(
        "raw_data",
        {},
    )

    if not isinstance(
        nested_raw_data,
        dict,
    ):
        nested_raw_data = {}

    source_visa_sponsorship = first_value(
        nested_raw_data,
        "visa_sponsorship",
    )

    source_eligibility = first_value(
        nested_raw_data,
        "eligibility",
    )

    if (
        visa_evidence is None
        and source_visa_sponsorship is not None
    ):
        visa_evidence = (
            source_visa_sponsorship
        )

    if (
        work_authorization is None
        and source_eligibility is not None
    ):
        work_authorization = (
            source_eligibility
        )

    # Only classify explicit source language here.
    # More nuanced analysis belongs to visa_analyzer.py.

    if (
        visa_status is None
        and source_visa_sponsorship is not None
    ):

        sponsorship_text = (
            str(source_visa_sponsorship)
            .strip()
            .lower()
        )

        explicit_no_sponsorship = (
            "not available" in sponsorship_text
            or "no sponsorship" in sponsorship_text
            or "does not sponsor" in sponsorship_text
            or "do not sponsor" in sponsorship_text
            or "sponsorship unavailable"
            in sponsorship_text
        )

        if explicit_no_sponsorship:
            visa_status = (
                "NO_SPONSORSHIP"
            )

    return (
        normalize_text(visa_status),
        normalize_text(visa_evidence),
        normalize_text(work_authorization),
    )


def normalize_job(
    record: dict[str, Any],
    index: int,
) -> NormalizedJob:
    """Normalize one job record."""

    source = normalize_text(
        first_value(
            record,
            "source",
        )
    )

    source_job_id = first_value(
        record,
        "source_job_id",
    )

    if source_job_id is None:
        raw_data = record.get(
            "raw_data",
            {},
        )

        if isinstance(raw_data, dict):
            source_job_id = first_value(
                raw_data,
                "source_job_id",
            )

    if source_job_id is None:
        source_job_id = first_value(
            record,
            "raw_job_id",
        )

    if source_job_id is not None:
        source_job_id = str(
            source_job_id
        )

    raw_data = get_raw_data(record)

    (
        visa_status,
        visa_evidence,
        work_authorization,
    ) = extract_visa_information(
        record
    )

    return NormalizedJob(
        job_id=build_job_id(
            record,
            index,
        ),

        title=normalize_text(
            first_value(
                record,
                "title",
            )
        ),

        company=normalize_text(
            first_value(
                record,
                "company",
            )
        ),

        location=normalize_text(
            first_value(
                record,
                "location",
            )
        ),

        country=normalize_text(
            first_value(
                record,
                "country",
            )
        ),

        remote_type=normalize_text(
            first_value(
                record,
                "remote_type",
                "workplace_type",
            )
        ),

        source=source,

        source_job_id=source_job_id,

        source_url=normalize_text(
            first_value(
                record,
                "source_url",
                "url",
                "job_url",
            )
        ),

        apply_url=normalize_text(
            first_value(
                record,
                "apply_url",
                "application_url",
            )
        ),

        description=normalize_text(
            first_value(
                record,
                "description",
            )
        ),

        content_mode=(
            "METADATA_ONLY"
            if source == "Indeed"
            else "FULL_CONTENT"
        ),

        highlights=normalize_list(
            first_value(
                record,
                "highlights",
                "summary",
            )
        ),

        posted_date=normalize_text(
            first_value(
                record,
                "posted_date",
                "date_posted",
            )
        ),

        canonical_role=normalize_text(
            first_value(
                record,
                "canonical_role",
            )
            or first_value(
                raw_data,
                "canonical_role",
            )
        ),

        matched_search_variant=normalize_text(
            first_value(
                record,
                "matched_search_variant",
                "search_variant",
            )
            or first_value(
                raw_data,
                "matched_search_variant",
                "search_variant",
            )
        ),

        visa_status=visa_status,

        visa_evidence=visa_evidence,

        work_authorization_requirement=(
            work_authorization
        ),

        search_task_id=normalize_text(
            first_value(
                record,
                "search_task_id",
                "task_id",
            )
        ),

        raw_data=record,
    )


def normalize_jobs(
    records: list[dict[str, Any]],
) -> list[NormalizedJob]:
    """Normalize all jobs."""

    normalized = []

    for index, record in enumerate(
        records,
        start=1,
    ):

        try:

            job = normalize_job(
                record,
                index,
            )

            normalized.append(job)

        except Exception as exc:

            print(
                f"Warning: failed to normalize "
                f"record {index}: {exc}"
            )

    return normalized


def save_jobs(
    jobs: list[NormalizedJob],
    path: Path,
) -> None:
    """Save normalized jobs."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "normalized_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "input_jobs": len(jobs),

        "output_jobs": len(jobs),

        "jobs": [
            job.model_dump()
            for job in jobs
        ],
    }

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            payload,
            file,
            indent=2,
            ensure_ascii=False,
        )


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Normalize source-deduplicated jobs."
        )
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=INPUT_FILE,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_FILE,
    )

    args = parser.parse_args()

    print("=" * 60)
    print("JOB NORMALIZER")
    print("=" * 60)

    print(
        f"Input:  {args.input}"
    )

    print(
        f"Output: {args.output}"
    )

    print()

    records = load_jobs(
        args.input
    )

    print(
        f"Input jobs: {len(records)}"
    )

    jobs = normalize_jobs(
        records
    )

    save_jobs(
        jobs,
        args.output
    )

    print(
        f"Normalized jobs: {len(jobs)}"
    )

    print()

    print(
        f"Normalized jobs saved to: "
        f"{args.output}"
    )


if __name__ == "__main__":
    main()