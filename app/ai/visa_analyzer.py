"""
AI Visa / Sponsorship Analyzer.

Purpose:
    Analyze available job-posting evidence for sponsorship and
    work-authorization requirements.

This module does NOT:
    - evaluate job relevance
    - change the relevance score
    - infer sponsorship from country
    - infer sponsorship from company size or reputation
    - infer immigration eligibility
    - determine whether a candidate will receive a visa
    - exclude jobs automatically

Visa status is intentionally separate from job relevance.

Allowed visa statuses:

    SPONSORSHIP_CONFIRMED
    SPONSORSHIP_POSSIBLE
    NOT_SPECIFIED
    NO_SPONSORSHIP
    WORK_AUTHORIZATION_REQUIRED
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


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BASE_DIR / ".env")

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "jobs"
    / "matched_jobs.json"
)

OUTPUT_FILE = (
    BASE_DIR
    / "data"
    / "jobs"
    / "visa_analyzed_jobs.json"
)

DEFAULT_MODEL = "gpt-5.6-luna"


# ============================================================
# VISA STATUS ENUMERATION
# ============================================================

VALID_VISA_STATUSES = {
    "SPONSORSHIP_CONFIRMED",
    "SPONSORSHIP_POSSIBLE",
    "NOT_SPECIFIED",
    "NO_SPONSORSHIP",
    "WORK_AUTHORIZATION_REQUIRED",
}


# ============================================================
# AI STRUCTURED OUTPUT
# ============================================================

class VisaAnalysisResult(BaseModel):
    """
    Structured AI assessment of sponsorship/work authorization
    evidence found in the job posting.
    """

    visa_status: str = Field(
        description=(
            "One of: SPONSORSHIP_CONFIRMED, "
            "SPONSORSHIP_POSSIBLE, NOT_SPECIFIED, "
            "NO_SPONSORSHIP, WORK_AUTHORIZATION_REQUIRED."
        )
    )

    visa_evidence: Optional[str] = Field(
        default=None,
        description=(
            "Exact or closely paraphrased evidence from the "
            "provided job information supporting the classification. "
            "If no evidence exists, return null."
        )
    )

    work_authorization_requirement: Optional[str] = Field(
        default=None,
        description=(
            "Description of any explicit work authorization "
            "requirement. If none is stated, return null."
        )
    )

    confidence: float = Field(
        ge=0,
        le=1,
        description=(
            "Confidence that the classification accurately "
            "reflects the provided job evidence."
        )
    )

    reasoning: str = Field(
        description=(
            "Brief explanation of why the evidence supports "
            "the selected classification."
        )
    )


# ============================================================
# FILE HELPERS
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


def load_matched_jobs(
    path: Path,
) -> list[dict[str, Any]]:
    """Load matched jobs."""

    data = load_json(path)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        jobs = data.get("jobs")

        if isinstance(jobs, list):
            return jobs

    raise ValueError(
        "matched_jobs.json must contain either a list "
        "or an object containing a 'jobs' list."
    )


# ============================================================
# VISA ANALYZER
# ============================================================

class VisaAnalyzer:
    """AI-powered visa/sponsorship evidence analyzer."""

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

    def analyze_job(
        self,
        job: dict[str, Any],
    ) -> VisaAnalysisResult:
        """
        Analyze sponsorship and work authorization evidence
        for one job.
        """

        system_prompt = """
You are the JobPilot Visa and Work Authorization Analyzer.

Your task is to classify the visa sponsorship and work
authorization information contained in a job posting.

You MUST base your conclusion ONLY on the job information
provided to you.

Do NOT use:
- general knowledge about the company
- assumptions about the country
- assumptions about the employer
- assumptions about immigration law
- assumptions about industry
- assumptions based on the job title
- assumptions based on company size
- assumptions based on previous jobs
- assumptions about what employers usually do

Do NOT determine whether the candidate is personally eligible
for a visa.

Do NOT determine whether the candidate should apply.

Do NOT modify or consider the job relevance score.

============================================================
ALLOWED CLASSIFICATIONS
============================================================

1. SPONSORSHIP_CONFIRMED

Use when the job posting explicitly indicates that the employer
provides visa sponsorship or will sponsor the successful candidate.

Examples of evidence:
- "visa sponsorship available"
- "we sponsor work visas"
- "sponsorship is available"
- "employer sponsorship provided"

2. SPONSORSHIP_POSSIBLE

Use when the posting provides evidence suggesting sponsorship
may be available but does not explicitly guarantee it.

Examples:
- "sponsorship may be available"
- "visa sponsorship considered"
- "we may sponsor qualified candidates"

Do NOT use this category simply because sponsorship is not
mentioned.

3. NOT_SPECIFIED

Use when the job posting provides no meaningful information
about visa sponsorship or work authorization.

This is the default when there is no evidence either way.

Do NOT infer NO_SPONSORSHIP from silence.

4. NO_SPONSORSHIP

Use when the job explicitly states that sponsorship is not
available.

Examples:
- "no visa sponsorship"
- "we do not sponsor"
- "sponsorship is not available"
- "not eligible for visa sponsorship"

5. WORK_AUTHORIZATION_REQUIRED

Use when the job explicitly requires the candidate to already
have authorization to work in the relevant country.

Examples:
- "must be authorized to work in the United States"
- "must have existing work authorization"
- "no visa transfer"
- "candidates must have unrestricted work authorization"

If the posting both explicitly requires existing authorization
AND explicitly says sponsorship is available, carefully describe
both pieces of evidence in the reasoning. The primary
classification should reflect the explicit sponsorship situation,
while the work authorization requirement should be captured
separately.

============================================================
IMPORTANT RULES
============================================================

1. Silence means NOT_SPECIFIED.

2. Country does not imply sponsorship.

3. Location does not imply sponsorship.

4. Company does not imply sponsorship.

5. A multinational company does not imply sponsorship.

6. "Remote" does not imply sponsorship.

7. "International" does not imply sponsorship.

8. Do not invent immigration information.

9. Preserve uncertainty.

10. Evidence must come from the supplied job data.

11. If evidence is insufficient, use NOT_SPECIFIED.

12. Keep visa analysis completely separate from job relevance.

Return only the structured result.
"""

        user_prompt = f"""
Analyze the following job posting for visa sponsorship and
work authorization information.

JOB DATA
========

{json.dumps(
    job,
    indent=2,
    ensure_ascii=False,
)}

Classify the visa/work-authorization situation using ONLY
evidence contained in this job data.
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
            text_format=VisaAnalysisResult,
        )

        result = response.output_parsed

        if result is None:
            raise ValueError(
                "OpenAI returned no structured visa analysis."
            )

        if result.visa_status not in VALID_VISA_STATUSES:
            raise ValueError(
                "Invalid visa status returned by model: "
                f"{result.visa_status}"
            )

        return result


# ============================================================
# RESULT MERGING
# ============================================================

def merge_analysis(
    job: dict[str, Any],
    analysis: VisaAnalysisResult,
) -> dict[str, Any]:
    """
    Add visa analysis to the existing matched job.

    Existing relevance information is preserved unchanged.
    """

    result = dict(job)

    result["visa_status"] = analysis.visa_status
    result["visa_evidence"] = analysis.visa_evidence
    result["work_authorization_requirement"] = (
        analysis.work_authorization_requirement
    )

    result["visa_analysis_confidence"] = (
        analysis.confidence
    )

    result["visa_analysis_reasoning"] = (
        analysis.reasoning
    )

    return result


# ============================================================
# OUTPUT
# ============================================================

def save_results(
    jobs: list[dict[str, Any]],
    path: Path,
) -> None:
    """Save visa-analyzed jobs."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "visa_analyzed_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "input_jobs": len(jobs),
        "output_jobs": len(jobs),

        "visa_statuses": {
            status: sum(
                1
                for job in jobs
                if job.get("visa_status") == status
            )
            for status in sorted(
                VALID_VISA_STATUSES
            )
        },

        "jobs": jobs,
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
# PIPELINE
# ============================================================

def run_analysis(
    input_path: Path,
    output_path: Path,
    limit: Optional[int] = None,
    model: str = DEFAULT_MODEL,
) -> None:

    print("=" * 60)
    print("AI VISA / SPONSORSHIP ANALYZER")
    print("=" * 60)

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

    jobs = load_matched_jobs(
        input_path
    )

    if limit is not None:
        jobs = jobs[:limit]

    print(
        f"Jobs selected: {len(jobs)}"
    )

    print()

    analyzer = VisaAnalyzer(
        model=model
    )

    analyzed_jobs: list[dict[str, Any]] = []

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

        try:
            analysis = analyzer.analyze_job(
                job
            )

            result = merge_analysis(
                job,
                analysis,
            )

            analyzed_jobs.append(
                result
            )

            successful += 1

            print(
                f"    Visa status: "
                f"{analysis.visa_status}"
            )

            print(
                f"    Confidence: "
                f"{analysis.confidence:.0%}"
            )

        except Exception as exc:
            failed += 1

            print(
                f"    ERROR: {exc}"
            )

    save_results(
        analyzed_jobs,
        output_path,
    )

    print()
    print("=" * 60)
    print("VISA ANALYSIS COMPLETE")
    print("=" * 60)

    print(
        f"Jobs processed: {len(jobs)}"
    )

    print(
        f"Successful:     {successful}"
    )

    print(
        f"Failed:         {failed}"
    )

    print(
        f"Results saved:  {output_path}"
    )

    print()
    print("VISA STATUS SUMMARY")
    print("-" * 60)

    for status in sorted(
        VALID_VISA_STATUSES
    ):
        count = sum(
            1
            for job in analyzed_jobs
            if job.get("visa_status") == status
        )

        print(
            f"{status:<30} {count}"
        )


# ============================================================
# CLI
# ============================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Analyze job postings for visa sponsorship "
            "and work authorization evidence."
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

    run_analysis(
        input_path=args.input,
        output_path=args.output,
        limit=args.limit,
        model=args.model,
    )


if __name__ == "__main__":
    main()