from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.discovery.search_executor import SearchExecutor
from app.discovery.deduplicator import (
    SourceDeduplicator,
)
from app.discovery.normalizer import (
    load_jobs,
    normalize_jobs,
    save_jobs,
    OUTPUT_FILE,
)
from app.storage.job_store import JobStore
from app.storage.database import JobDatabase
from app.discovery.job_recency import get_recent_jobs
from app.discovery.deterministic_job_scorer import score_job

from app.networking.company_domain_resolver import CompanyDomainResolver
from app.networking.hunter_client import HunterClient
from app.networking.contact_relevance import ContactRelevanceAnalyzer
from app.networking.contact_discovery import ContactDiscovery
from app.storage.contact_store import ContactStore
from app.networking.outreach_generator import OutreachGenerator
from app.networking.outreach_tracker import OutreachTracker


BASE_DIR = Path(__file__).resolve().parent.parent

PROFILE_PATH = (
    BASE_DIR / "data" / "candidate" / "current_profile.json"
)

RAW_JOBS_PATH = (
    BASE_DIR / "data" / "jobs" / "raw_jobs.json"
)

DEDUPLICATED_JOBS_PATH = (
    BASE_DIR / "data" / "jobs" / "source_deduplicated_jobs.json"
)

DEDUPLICATION_REPORT_PATH = (
    BASE_DIR / "data" / "jobs" / "deduplication_report.json"
)

RECENCY_DAYS = 7

# A Business Analyst title is a hard inclusion for outreach.
BA_TITLE_SIGNALS = (
    "business analyst",
    "senior business analyst",
    "lead business analyst",
    "principal business analyst",
)


def load_profile() -> dict[str, Any]:
    with PROFILE_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def is_ba_title(title: str | None) -> bool:
    value = (title or "").strip().lower()

    return any(
        signal in value
        for signal in BA_TITLE_SIGNALS
    )


def build_contact_discovery(
    database: JobDatabase,
) -> ContactDiscovery:

    hunter = HunterClient()
    contact_store = ContactStore(database)
    relevance = ContactRelevanceAnalyzer()

    return ContactDiscovery(
        hunter_client=hunter,
        contact_store=contact_store,
        relevance_analyzer=relevance,
    )


def main() -> None:

    print()
    print("=" * 70)
    print("JOBPILOT LIVE RUN")
    print("=" * 70)

    # ---------------------------------------------------------
    # 1. LIVE JOB DISCOVERY
    # ---------------------------------------------------------

    print("\n[1/8] Live job discovery...")

    executor = SearchExecutor()

    execution_report = executor.run()

    print(
        f"  Tasks executed: "
        f"{execution_report.get('tasks_executed', 0)}"
    )

    print(
        f"  Jobs discovered: "
        f"{execution_report.get('jobs_discovered', 0)}"
    )

    # ---------------------------------------------------------
    # 2. SOURCE DEDUPLICATION
    # ---------------------------------------------------------

    print("\n[2/8] Source deduplication...")

    with RAW_JOBS_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:

        raw_payload = json.load(file)

    raw_jobs = raw_payload.get(
        "jobs",
        raw_payload if isinstance(raw_payload, list) else [],
    )

    deduplicator = SourceDeduplicator()

    unique_jobs, dedup_report = (
        deduplicator.deduplicate(raw_jobs)
    )

    with DEDUPLICATED_JOBS_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            {
                "generated_at": dedup_report.get(
                    "generated_at"
                ),
                "total_jobs": len(unique_jobs),
                "jobs": unique_jobs,
            },
            file,
            indent=2,
            default=str,
        )

    with DEDUPLICATION_REPORT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            dedup_report,
            file,
            indent=2,
            default=str,
        )

    print(
        f"  Unique jobs: {len(unique_jobs)}"
    )

    print(
        f"  Duplicates removed: "
        f"{len(raw_jobs) - len(unique_jobs)}"
    )

    # ---------------------------------------------------------
    # 3. NORMALIZATION
    # ---------------------------------------------------------

    print("\n[3/8] Normalizing jobs...")

    normalized_jobs = normalize_jobs(
        unique_jobs
    )

    save_jobs(
        normalized_jobs,
        OUTPUT_FILE,
    )

    print(
        f"  Normalized jobs: "
        f"{len(normalized_jobs)}"
    )

    # ---------------------------------------------------------
    # 4. SQLITE INGESTION
    # ---------------------------------------------------------

    print("\n[4/8] Updating SQLite...")

    job_store = JobStore()

    ingest_result = job_store.ingest()

    print(
        f"  NEW: {ingest_result.get('NEW', 0)}"
    )

    print(
        f"  EXISTING: "
        f"{ingest_result.get('EXISTING', 0)}"
    )

    print(
        f"  UPDATED: "
        f"{ingest_result.get('UPDATED', 0)}"
    )

    # ---------------------------------------------------------
    # 5. RECENCY + DETERMINISTIC SCORING
    # ---------------------------------------------------------

    print(
        "\n[5/8] Filtering recent jobs and scoring..."
    )

    recent_jobs = get_recent_jobs(
        days=RECENCY_DAYS
    )

    scored_jobs = []

    for job in recent_jobs:

        result = score_job(job)

        job_store.update_job_score(
            source=job["source"],
            source_job_id=job["source_job_id"],
            score_result=result,
        )

        enriched = dict(job)
        enriched.update(result)

        scored_jobs.append(enriched)

    job_store.database.connection.commit()

    ba_jobs = [
        job
        for job in scored_jobs
        if is_ba_title(
            job.get("title")
        )
    ]

    print(
        f"  Recent jobs: {len(recent_jobs)}"
    )

    print(
        f"  Business Analyst-title jobs: "
        f"{len(ba_jobs)}"
    )

    # ---------------------------------------------------------
    # 6. CONTACT DISCOVERY
    # ---------------------------------------------------------

    print(
        "\n[6/8] Finding outreach contacts..."
    )

    profile = load_profile()

    database = JobDatabase()

    domain_resolver = CompanyDomainResolver(
        database=database
    )

    contact_discovery = build_contact_discovery(
        database
    )

    outreach_generator = OutreachGenerator(
        candidate_profile=profile
    )

    outreach_tracker = OutreachTracker()

    created_drafts = []

    # Highest-value opportunities first.
    ba_jobs.sort(
        key=lambda job: (
            job.get("relevance_score") or 0
        ),
        reverse=True,
    )

    for job in ba_jobs:

        company = (
            job.get("company")
            or ""
        ).strip()

        if not company:
            continue

        title = (
            job.get("title")
            or ""
        ).strip()

        print(
            f"\n  → {company} | {title}"
        )

        # -----------------------------------------------------
        # DOMAIN
        # -----------------------------------------------------

        resolution = (
            domain_resolver.resolve(company)
        )

        if resolution.status != "VERIFIED":

            print(
                "    Domain: unresolved"
            )

            continue

        domain = resolution.domain

        print(
            f"    Domain: {domain}"
        )

        # -----------------------------------------------------
        # CONTACTS
        # -----------------------------------------------------

        matched_skills = []

        raw_matched_skills = (
            job.get("matched_skills")
            or []
        )

        if isinstance(
            raw_matched_skills,
            str,
        ):
            try:
                matched_skills = json.loads(
                    raw_matched_skills
                )
            except json.JSONDecodeError:
                matched_skills = [
                    raw_matched_skills
                ]

        try:

            contact_result = (
                contact_discovery.discover_for_job(
                    company=company,
                    company_domain=domain,
                    canonical_role=(
                        job.get("canonical_role")
                        or "Business Analyst"
                    ),
                    matched_skills=matched_skills,
                    limit=10,
                    max_contacts=1,
                    minimum_score=25,
                )
            )

        except Exception as exc:

            print(
                f"    Contact discovery failed: "
                f"{exc}"
            )

            continue

        contacts = contact_result.get(
            "contacts",
            [],
        )

        if not contacts:

            print(
                "    No suitable contact found"
            )

            continue

        contact = contacts[0]

        contact_name = (
            contact.get("full_name")
            or contact.get("first_name")
            or "Unknown"
        )

        print(
            f"    Contact: {contact_name}"
        )

        # -----------------------------------------------------
        # OUTREACH DRAFT
        # -----------------------------------------------------

        draft = outreach_generator.generate(
            job=job,
            contact=contact,
        )

        record_result = outreach_tracker.record(
            message=draft,
            job=job,
            contact=contact,
        )

        run_id = record_result["run_id"]

        created_drafts.append(
            {
                "run_id": run_id,
                "job_id": job.get("id"),
                "company": company,
                "role": title,
                "contact": contact.get(
                    "full_name"
                )
                or contact.get(
                    "first_name"
                ),
                "email": contact.get(
                    "email"
                ),
                "subject": draft.subject,
                "status": "DRAFT",
            }
        )

        print(
            f"    Draft created: {run_id}"
        )

    # ---------------------------------------------------------
    # 7. SUMMARY
    # ---------------------------------------------------------

    print()
    print("=" * 70)
    print("JOBPILOT RUN COMPLETE")
    print("=" * 70)

    print(
        f"Recent jobs:              "
        f"{len(recent_jobs)}"
    )

    print(
        f"BA-title opportunities:   "
        f"{len(ba_jobs)}"
    )

    print(
        f"Outreach drafts created:  "
        f"{len(created_drafts)}"
    )

    print(
        "Emails sent:              0"
    )

    print(
        "Status:                   "
        "AWAITING APPROVAL"
    )

    print("=" * 70)

    if created_drafts:

        print("\nDRAFTS:")

        for draft in created_drafts:

            print(
                f"\n{draft['run_id']} | "
                f"{draft['company']} | "
                f"{draft['role']}"
            )

            print(
                f"  Contact: "
                f"{draft['contact']}"
            )

            print(
                f"  Email: "
                f"{draft['email']}"
            )

            print(
                f"  Subject: "
                f"{draft['subject']}"
            )

    print()


if __name__ == "__main__":
    main()