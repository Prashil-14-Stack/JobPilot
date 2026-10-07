"""
AI Job Matching Engine.

Purpose:
    Evaluate how well each normalized job matches the candidate profile.

This module:
    - Uses the candidate profile as the source of truth for candidate fit.
    - Uses the normalized job as the source of truth for job requirements.
    - Produces a structured relevance assessment.
    - Preserves the original normalized job data.

This module does NOT:
    - Deduplicate jobs.
    - Determine visa sponsorship.
    - Exclude jobs based on visa status.
    - Rewrite the candidate CV.
    - Apply to jobs.
"""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BASE_DIR / ".env")

CANDIDATE_PROFILE_FILE = BASE_DIR / "candidate_profile.json"

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "jobs"
    / "normalized_jobs.json"
)

OUTPUT_FILE = (
    BASE_DIR
    / "data"
    / "jobs"
    / "matched_jobs.json"
)

DEFAULT_MODEL = "gpt-5.6-luna"


# ============================================================
# STRUCTURED AI OUTPUT
# ============================================================

class JobMatchResult(BaseModel):
    """
    AI assessment of a job against the candidate profile.
    """

    relevance_score: float = Field(
        ge=0,
        le=100,
        description=(
            "Overall job relevance score from 0 to 100. "
            "This measures candidate-job fit, not visa eligibility."
        ),
    )

    relevance_level: str = Field(
        description=(
            "HIGH, MEDIUM, or LOW based on the overall relevance."
        ),
    )

    match_reasons: list[str] = Field(
        default_factory=list,
        description=(
            "Specific reasons why the candidate matches the job."
        ),
    )

    missing_requirements: list[str] = Field(
        default_factory=list,
        description=(
            "Important job requirements that are missing or "
            "not evidenced in the candidate profile."
        ),
    )

    matched_skills: list[str] = Field(
        default_factory=list,
        description=(
            "Skills, tools, technologies, methodologies, or "
            "domain capabilities that match."
        ),
    )

    matched_experience: list[str] = Field(
        default_factory=list,
        description=(
            "Candidate experience that directly aligns with "
            "the job."
        ),
    )

    domain_match: Optional[str] = Field(
        default=None,
        description=(
            "Describe the domain alignment, such as insurance, "
            "digital transformation, data migration, CRM, etc."
        ),
    )

    seniority_match: Optional[str] = Field(
        default=None,
        description=(
            "Describe whether the job seniority appears aligned "
            "with the candidate's experience."
        ),
    )


class MatchedJob(BaseModel):
    """
    Normalized job plus its AI relevance assessment.
    """

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
    highlights: list[str] = Field(default_factory=list)

    posted_date: Optional[str] = None

    canonical_role: Optional[str] = None
    matched_search_variant: Optional[str] = None

    visa_status: Optional[str] = None
    visa_evidence: Optional[str] = None
    work_authorization_requirement: Optional[str] = None

    search_task_id: Optional[str] = None

    relevance_score: Optional[float] = None
    relevance_level: Optional[str] = None

    match_reasons: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    matched_experience: list[str] = Field(default_factory=list)

    domain_match: Optional[str] = None
    seniority_match: Optional[str] = None

    normalized_at: Optional[str] = None

    raw_data: dict[str, Any] = Field(
        default_factory=dict
    )


# ============================================================
# FILE HANDLING
# ============================================================

def load_json(path: Path) -> Any:
    """Load JSON from disk."""

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def load_candidate_profile(path: Path) -> dict[str, Any]:
    """Load candidate profile."""

    data = load_json(path)

    if not isinstance(data, dict):
        raise ValueError(
            "candidate_profile.json must contain a JSON object."
        )

    return data


def load_normalized_jobs(
    path: Path,
) -> list[dict[str, Any]]:
    """Load normalized jobs."""

    data = load_json(path)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        jobs = data.get("jobs")

        if isinstance(jobs, list):
            return jobs

    raise ValueError(
        "normalized_jobs.json must contain either a list "
        "or an object containing a 'jobs' list."
    )


# ============================================================
# AI MATCHER
# ============================================================

class JobMatcher:
    """AI-powered candidate/job relevance matcher."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
    ):
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY is not set. "
                "Check your .env file."
            )

        self.client = OpenAI(
            api_key=api_key
        )

        self.model = model

    def match_job(
        self,
        candidate_profile: dict[str, Any],
        job: dict[str, Any],
    ) -> JobMatchResult:
        """
        Evaluate one job against the candidate profile.
        """

        system_prompt = """
You are the JobPilot job relevance engine.

Your task is to evaluate whether a job is relevant to a candidate
based ONLY on the candidate profile and the job information supplied.

You are NOT evaluating:
- visa sponsorship
- immigration eligibility
- salary attractiveness
- company attractiveness
- whether the candidate should apply
- probability of getting an interview

You are evaluating candidate-job fit.

Use the following principles:

1. Match actual experience against job requirements.
2. Consider role/title alignment.
3. Consider business analysis experience.
4. Consider technical skills.
5. Consider domain experience.
6. Consider transformation, automation, data migration,
   CRM, insurance, AI and related experience where relevant.
7. Consider seniority alignment.
8. Do not invent experience that is not present in the candidate profile.
9. Do not assume that a missing skill is absent unless the profile
   provides enough information to establish that.
10. Distinguish between:
      - clearly demonstrated experience
      - partially aligned experience
      - missing or unsupported requirements
11. A job does not need to match every requirement to receive a
    meaningful relevance score.
12. Score from 0 to 100.

13. Do NOT use location, country, remote status, visa status,
    sponsorship, immigration status, or work authorization as
    factors in the relevance score.

14. Do NOT mention visa, sponsorship, immigration, or work
    authorization in match_reasons, missing_requirements,
    matched_skills, matched_experience, domain_match, or
    seniority_match.

15. Geographic suitability and work authorization will be
    evaluated by a separate downstream module.

Scoring guidance:

90-100:
Very strong alignment across role, experience, skills and domain.

75-89:
Strong alignment with some gaps or secondary requirements.

60-74:
Meaningful alignment but several gaps exist.

40-59:
Partial alignment; significant requirements are missing.

0-39:
Weak alignment with the candidate profile.

Return only the structured result.
"""

        user_prompt = f"""
CANDIDATE PROFILE
=================
{json.dumps(
    candidate_profile,
    indent=2,
    ensure_ascii=False,
)}

JOB
===
{json.dumps(
    job,
    indent=2,
    ensure_ascii=False,
)}

Evaluate this job against the candidate profile.
"""

        response = self.client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            text_format=JobMatchResult,
        )

        result = response.output_parsed

        if result is None:
            raise ValueError(
                "OpenAI returned no structured match result."
            )

        return result


# ============================================================
# JOB MERGING
# ============================================================

def merge_match_result(
    job: dict[str, Any],
    match: JobMatchResult,
) -> MatchedJob:
    """
    Combine normalized job data with AI matching results.
    """

    return MatchedJob(
        job_id=str(
            job.get("job_id")
            or ""
        ),

        title=job.get("title"),
        company=job.get("company"),

        location=job.get("location"),
        country=job.get("country"),
        remote_type=job.get("remote_type"),

        source=job.get("source"),
        source_job_id=job.get("source_job_id"),

        source_url=job.get("source_url"),
        apply_url=job.get("apply_url"),

        description=job.get("description"),
        highlights=job.get(
            "highlights",
            [],
        ),

        posted_date=job.get("posted_date"),

        canonical_role=job.get(
            "canonical_role"
        ),

        matched_search_variant=job.get(
            "matched_search_variant"
        ),

        visa_status=job.get(
            "visa_status"
        ),

        visa_evidence=job.get(
            "visa_evidence"
        ),

        work_authorization_requirement=job.get(
            "work_authorization_requirement"
        ),

        search_task_id=job.get(
            "search_task_id"
        ),

        relevance_score=match.relevance_score,
        relevance_level=match.relevance_level,

        match_reasons=match.match_reasons,
        missing_requirements=match.missing_requirements,

        matched_skills=match.matched_skills,
        matched_experience=match.matched_experience,

        domain_match=match.domain_match,
        seniority_match=match.seniority_match,

        normalized_at=job.get(
            "normalized_at"
        ),

        raw_data=job.get(
            "raw_data",
            {},
        ),
    )


# ============================================================
# OUTPUT
# ============================================================

def save_results(
    jobs: list[MatchedJob],
    path: Path,
) -> None:
    """Save matched jobs."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "matched_at": datetime.now(
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


# ============================================================
# MAIN PIPELINE
# ============================================================

def run_matching(
    candidate_profile_path: Path,
    input_path: Path,
    output_path: Path,
    limit: Optional[int] = None,
    model: str = DEFAULT_MODEL,
) -> None:

    print("=" * 60)
    print("AI JOB MATCHER")
    print("=" * 60)

    print(
        f"Candidate profile: {candidate_profile_path}"
    )

    print(
        f"Input:  {input_path}"
    )

    print(
        f"Output: {output_path}"
    )

    print(
        f"Model:  {model}"
    )

    print()

    candidate_profile = load_candidate_profile(
        candidate_profile_path
    )

    jobs = load_normalized_jobs(
        input_path
    )

    if limit is not None:
        jobs = jobs[:limit]

    print(
        f"Jobs selected: {len(jobs)}"
    )

    print()

    matcher = JobMatcher(
        model=model
    )

    matched_jobs: list[MatchedJob] = []

    successful = 0
    failed = 0

    for index, job in enumerate(
        jobs,
        start=1,
    ):

        title = (
            job.get("title")
            or "Unknown title"
        )

        company = (
            job.get("company")
            or "Unknown company"
        )

        print(
            f"[{index}/{len(jobs)}] "
            f"{title} | {company}"
        )

        if job.get("content_mode") == "METADATA_ONLY":
            print(
                "    SKIPPED: metadata-only job"
            )
            continue

        try:
            match = matcher.match_job(
                candidate_profile,
                job,
            )

            matched_job = merge_match_result(
                job,
                match,
            )

            matched_jobs.append(
                matched_job
            )

            successful += 1

            print(
                f"    Relevance: "
                f"{match.relevance_score:.1f} "
                f"({match.relevance_level})"
            )

        except Exception as exc:
            failed += 1

            print(
                f"    ERROR: {exc}"
            )

    save_results(
        matched_jobs,
        output_path,
    )

    print()
    print("=" * 60)
    print("MATCHING COMPLETE")
    print("=" * 60)

    print(
        f"Tasks processed: {len(jobs)}"
    )

    print(
        f"Successful:      {successful}"
    )

    print(
        f"Failed:          {failed}"
    )

    print(
        f"Results saved:   {output_path}"
    )


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Evaluate normalized jobs against "
            "the candidate profile using AI."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Process only the first N jobs. "
            "Useful for testing."
        ),
    )

    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=(
            f"OpenAI model to use. "
            f"Default: {DEFAULT_MODEL}"
        ),
    )

    parser.add_argument(
        "--candidate-profile",
        type=Path,
        default=CANDIDATE_PROFILE_FILE,
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

    run_matching(
        candidate_profile_path=args.candidate_profile,
        input_path=args.input,
        output_path=args.output,
        limit=args.limit,
        model=args.model,
    )


if __name__ == "__main__":
    main()