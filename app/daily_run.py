from pathlib import Path
from app.discovery.job_recency import get_recent_jobs
from app.discovery.search_executor import SearchExecutor
from app.discovery.deterministic_job_scorer import score_job
from app.discovery.deduplicator import (
    SourceDeduplicator,
    RAW_JOBS_PATH,
    DEDUPLICATED_JOBS_PATH,
    DEDUPLICATION_REPORT_PATH,
)
from app.discovery.normalizer import (
    load_jobs,
    normalize_jobs,
    save_jobs,
    OUTPUT_FILE,
)
from app.storage.job_store import JobStore


def main():
    print("=" * 60)
    print("JOBPILOT DAILY RUN")
    print("=" * 60)

    # --------------------------------------------------
    # 1. Live job discovery
    # --------------------------------------------------

    print("\n[1/4] Discovering jobs...")

    executor = SearchExecutor()

    jobs = executor.run(
        limit=None,
        priority=None,
    )

    print(f"Jobs discovered: {len(jobs)}")

    # --------------------------------------------------
    # 2. Source-level deduplication
    # --------------------------------------------------

    print("\n[2/4] Deduplicating jobs...")

    deduplicator = SourceDeduplicator()

    raw_jobs = load_jobs(RAW_JOBS_PATH)

    deduplicated_jobs, report = (
        deduplicator.deduplicate(raw_jobs)
    )

    deduplicator.save_jobs(
        DEDUPLICATED_JOBS_PATH,
        deduplicated_jobs,
        report.get("deduplicated_at") or "",
    )

    deduplicator.save_report(
        DEDUPLICATION_REPORT_PATH,
        report,
    )

    print(
        f"Jobs after deduplication: "
        f"{len(deduplicated_jobs)}"
    )

    print(
        f"Duplicates removed: "
        f"{report['duplicates_removed']}"
    )

    # --------------------------------------------------
    # 3. Normalize
    # --------------------------------------------------

    print("\n[3/4] Normalizing jobs...")

    normalized_jobs = normalize_jobs(
        deduplicated_jobs
    )

    save_jobs(
        normalized_jobs,
        OUTPUT_FILE,
    )

    print(
        f"Jobs normalized: "
        f"{len(normalized_jobs)}"
    )

    # --------------------------------------------------
    # 4. Ingest into SQLite
    # --------------------------------------------------

    print("\n[4/4] Updating SQLite...")

    job_store = JobStore()

    counts = job_store.ingest()
    # --------------------------------------------------
    # 5. Seven-day recency filter
    # --------------------------------------------------

    print("\n[5/5] Filtering jobs posted within 7 days...")

    recent_jobs = get_recent_jobs(
        days=7
    )
    print(
        f"Jobs posted within 7 days: "
        f"{len(recent_jobs)}"
    )

    # --------------------------------------------------
    # 6. Deterministic relevance scoring
    # --------------------------------------------------

    print("\n[6/6] Scoring recent jobs...")

    scored_count = 0

    for job in recent_jobs:

        score_result = score_job(
            job
        )

        job_store.update_job_score(
            source=job["source"],
            source_job_id=job["source_job_id"],
            score_result=score_result,
        )

        scored_count += 1

    job_store.database.connection.commit()

    print(
        f"Jobs scored: {scored_count}"
    )

    print("\nDaily run completed.")