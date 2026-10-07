import argparse
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_JOBS_PATH = PROJECT_ROOT / "data" / "jobs" / "raw_jobs.json"
DEDUPLICATED_JOBS_PATH = PROJECT_ROOT / "data" / "jobs" / "source_deduplicated_jobs.json"
DEDUPLICATION_REPORT_PATH = PROJECT_ROOT / "data" / "jobs" / "deduplication_report.json"

FALLBACK_JOB_ID_PATTERN = re.compile(r"^SEARCH-\d+-\d+$", re.IGNORECASE)
TRACKING_PARAMETERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "trk",
    "trkInfo",
}


class SourceDeduplicator:
    """Deduplicate jobs only when the same source exposes a stable job identity."""

    @staticmethod
    def normalize_source(source: str | None) -> str:
        return (source or "").strip().casefold()

    @staticmethod
    def normalize_job_url(url: str | None) -> str | None:
        """Remove common tracking parameters without changing the job identity."""
        if not url:
            return None

        value = str(url).strip()
        if not value.startswith(("http://", "https://")):
            return None

        parts = urlsplit(value)
        query = [
            (key, val)
            for key, val in parse_qsl(parts.query, keep_blank_values=True)
            if key not in TRACKING_PARAMETERS
        ]

        return urlunsplit(
            (
                parts.scheme.lower(),
                parts.netloc.lower(),
                parts.path.rstrip("/"),
                urlencode(query),
                "",
            )
        )

    @classmethod
    def get_stable_job_identity(cls, job: dict) -> str | None:
        """
        Return a stable source-specific job identity.

        Priority:
        1. source + raw_job_id when raw_job_id is a provider job identifier.
        2. source + normalized source_url when raw_job_id itself is a URL.
        3. None when the executor generated a SEARCH-xxxx-xxx fallback ID.

        We deliberately do not use title/company/location/description.
        """
        source = cls.normalize_source(job.get("source"))
        raw_job_id = str(job.get("raw_job_id") or "").strip()

        if not source or not raw_job_id:
            return None

        if FALLBACK_JOB_ID_PATTERN.fullmatch(raw_job_id):
            return None

        # URL-shaped raw IDs are intentionally not used as identities.
        # Some job boards return a search/listing page URL rather than a
        # unique posting URL, so treating it as a job ID can remove real jobs.
        if raw_job_id.startswith(("http://", "https://")):
            return None

        return f"{source}|id|{raw_job_id}"

    def deduplicate(self, jobs: list[dict]) -> tuple[list[dict], dict]:
        seen: dict[str, int] = {}
        unique_jobs: list[dict] = []
        duplicates: list[dict] = []
        no_stable_identity = 0

        for index, job in enumerate(jobs):
            key = self.get_stable_job_identity(job)

            if key is None:
                no_stable_identity += 1
                unique_jobs.append(job)
                continue

            if key in seen:
                original_index = seen[key]
                duplicates.append(
                    {
                        "duplicate_index": index,
                        "original_index": original_index,
                        "source": job.get("source"),
                        "raw_job_id": job.get("raw_job_id"),
                        "source_url": job.get("source_url"),
                        "search_task_id": job.get("search_task_id"),
                        "title": job.get("title"),
                        "company": job.get("company"),
                    }
                )
                continue

            seen[key] = index
            unique_jobs.append(job)

        source_counts_before = Counter(job.get("source") for job in jobs)
        source_counts_after = Counter(job.get("source") for job in unique_jobs)

        report = {
            "deduplicated_at": None,
            "input_jobs": len(jobs),
            "output_jobs": len(unique_jobs),
            "duplicates_removed": len(duplicates),
            "records_without_stable_identity": no_stable_identity,
            "deduplication_rule": "Same source + same stable source job identity only.",
            "fields_not_used_for_deduplication": [
                "title",
                "company",
                "location",
                "country",
                "description",
                "canonical_role",
                "search_variant",
            ],
            "source_counts_before": dict(source_counts_before),
            "source_counts_after": dict(source_counts_after),
            "duplicates": duplicates,
        }

        return unique_jobs, report

    @staticmethod
    def load_jobs(path: Path) -> list[dict]:
        with open(path, "r", encoding="utf-8") as file:
            payload = json.load(file)
        return payload.get("jobs", [])

    @staticmethod
    def save_jobs(path: Path, jobs: list[dict], generated_at: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": generated_at,
            "total_jobs": len(jobs),
            "jobs": jobs,
        }
        with open(path, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, ensure_ascii=False)

    @staticmethod
    def save_report(path: Path, report: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(report, file, indent=2, ensure_ascii=False)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Deduplicate JobPilot raw jobs at source level only."
    )
    parser.add_argument(
        "--input",
        default=str(RAW_JOBS_PATH),
        help="Path to raw_jobs.json",
    )
    parser.add_argument(
        "--output",
        default=str(DEDUPLICATED_JOBS_PATH),
        help="Path for source_deduplicated_jobs.json",
    )
    parser.add_argument(
        "--report",
        default=str(DEDUPLICATION_REPORT_PATH),
        help="Path for deduplication_report.json",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    report_path = Path(args.report)

    print("=" * 60)
    print("SOURCE-LEVEL DEDUPLICATOR")
    print("=" * 60)
    print(f"Input: {input_path}")

    deduplicator = SourceDeduplicator()
    jobs = deduplicator.load_jobs(input_path)
    unique_jobs, report = deduplicator.deduplicate(jobs)

    from datetime import datetime, timezone
    generated_at = datetime.now(timezone.utc).isoformat()
    report["deduplicated_at"] = generated_at

    deduplicator.save_jobs(output_path, unique_jobs, generated_at)
    deduplicator.save_report(report_path, report)

    print()
    print(f"Input jobs:                         {report['input_jobs']}")
    print(f"Unique jobs:                        {report['output_jobs']}")
    print(f"Duplicates removed:                {report['duplicates_removed']}")
    print(f"Without stable identity:            {report['records_without_stable_identity']}")
    print()
    print("DUPLICATES REMOVED")
    print("-" * 60)

    if report["duplicates"]:
        for duplicate in report["duplicates"]:
            print(
                f"{duplicate['source']} | "
                f"{duplicate['raw_job_id']} | "
                f"{duplicate['company']} | "
                f"{duplicate['title']} | "
                f"{duplicate['search_task_id']}"
            )
    else:
        print("None")

    print()
    print(f"Deduplicated jobs saved to: {output_path}")
    print(f"Deduplication report saved to: {report_path}")


if __name__ == "__main__":
    main()
