from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROFILE_PATH = (
    PROJECT_ROOT
    / "data"
    / "candidate"
    / "current_profile.json"
)


# ---------------------------------------------------------------------
# Weighted capability groups
# ---------------------------------------------------------------------

CAPABILITY_GROUPS = {
    "business_analysis": {
        "weight": 20,
        "keywords": [
            "business analyst",
            "business analysis",
            "business requirements",
            "requirements gathering",
            "requirements elicitation",
            "requirements analysis",
            "requirements management",
            "functional requirements",
            "business requirements document",
            "brd",
            "frd",
            "functional specification",
            "functional specifications",
            "user stories",
            "acceptance criteria",
            "stakeholder management",
            "stakeholder engagement",
        ],
    },

    "process_transformation": {
        "weight": 15,
        "keywords": [
            "process modelling",
            "process modeling",
            "process mapping",
            "business process",
            "process improvement",
            "process transformation",
            "digital transformation",
            "business transformation",
            "bpr",
            "business process reengineering",
            "gap analysis",
            "bpmn",
        ],
    },

    "data": {
        "weight": 15,
        "keywords": [
            "data migration",
            "data mapping",
            "data transformation",
            "data analysis",
            "data analytics",
            "data management",
            "sql",
            "hive",
            "hql",
            "dashboard",
            "dashboards",
            "reporting",
            "large datasets",
        ],
    },

    "insurance": {
        "weight": 15,
        "keywords": [
            "insurance",
            "life insurance",
            "p&c insurance",
            "property and casualty",
            "claims",
            "policy",
            "policies",
            "underwriting",
            "policy administration",
            "policy servicing",
        ],
    },

    "testing_delivery": {
        "weight": 10,
        "keywords": [
            "uat",
            "user acceptance testing",
            "functional testing",
            "test scenarios",
            "test cases",
            "defect management",
            "defect resolution",
            "production defects",
            "release",
            "implementation",
        ],
    },

    "technology_transformation": {
        "weight": 10,
        "keywords": [
            "crm",
            "microsoft dynamics",
            "dynamics 365",
            "automation",
            "rpa",
            "robotic process automation",
            "ai",
            "artificial intelligence",
            "genai",
            "generative ai",
            "llm",
            "python",
            "digital",
        ],
    },

    "seniority": {
        "weight": 10,
        "keywords": [
            "senior business analyst",
            "lead business analyst",
            "principal business analyst",
            "business consultant",
            "business transformation",
            "consultant",
            "lead",
        ],
    },

    "project_delivery": {
        "weight": 5,
        "keywords": [
            "project",
            "programme",
            "program",
            "delivery",
            "implementation",
            "cross-functional",
            "cross functional",
            "workshops",
            "jad",
        ],
    },
}


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).lower()

    text = re.sub(
        r"[^a-z0-9+#&.\- ]+",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def profile_to_text(value: Any) -> str:
    """
    Recursively convert the candidate profile into searchable text.
    This allows the scorer to work with the existing profile structure
    without depending on a single hard-coded JSON field.
    """

    if isinstance(value, dict):
        return " ".join(
            profile_to_text(v)
            for v in value.values()
        )

    if isinstance(value, list):
        return " ".join(
            profile_to_text(v)
            for v in value
        )

    return str(value)


def keyword_present(
    keyword: str,
    text: str,
) -> bool:
    """
    Match a keyword as a phrase rather than as an arbitrary substring.
    """

    keyword = normalize_text(keyword)

    if not keyword:
        return False

    pattern = (
        r"(?<![a-z0-9])"
        + re.escape(keyword)
        + r"(?![a-z0-9])"
    )

    return re.search(
        pattern,
        text,
        re.IGNORECASE,
    ) is not None


# ---------------------------------------------------------------------
# Profile loading
# ---------------------------------------------------------------------

def load_candidate_profile() -> dict[str, Any]:
    with PROFILE_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


# ---------------------------------------------------------------------
# Job scoring
# ---------------------------------------------------------------------

def score_job(
    job: dict[str, Any],
    candidate_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Deterministically score one job against the candidate profile.

    Score components:
        Role alignment              35
        Core BA requirements        25
        Data / analytics            15
        Transformation / process    10
        Domain                       5
        Testing / UAT                5
        Seniority                    5

    Total: 100

    Match confidence reflects the amount of job-description evidence
    available and is independent of relevance score.

    Location, country, visa and sponsorship are deliberately excluded.
    """

    if candidate_profile is None:
        candidate_profile = load_candidate_profile()

    title = normalize_text(
        job.get("title", "")
    )

    description = normalize_text(
        job.get("description", "")
    )

    job_text = f"{title} {description}".strip()

    profile_text = normalize_text(
        profile_to_text(candidate_profile)
    )

    # -------------------------------------------------------------
    # 1. Role alignment — 35 points
    # -------------------------------------------------------------

    role_score = 0

    if keyword_present(
        "senior business analyst",
        title,
    ):
        role_score = 35

    elif keyword_present(
        "business analyst",
        title,
    ):
        role_score = 35

    elif keyword_present(
        "business consultant",
        title,
    ):
        role_score = 32

    elif keyword_present(
        "business analysis",
        title,
    ):
        role_score = 28

    elif keyword_present(
        "business",
        title,
    ):
        role_score = 15

    # -------------------------------------------------------------
    # 2. Core BA requirements — 25 points
    # -------------------------------------------------------------

    ba_keywords = [
        "business requirements",
        "requirements gathering",
        "requirements elicitation",
        "requirements analysis",
        "requirements management",
        "functional requirements",
        "business requirements document",
        "brd",
        "frd",
        "functional specification",
        "user stories",
        "acceptance criteria",
        "stakeholder management",
        "stakeholder engagement",
    ]

    ba_matches = [
        keyword
        for keyword in ba_keywords
        if keyword_present(
            keyword,
            job_text,
        )
        and keyword_present(
            keyword,
            profile_text,
        )
    ]

    if ba_matches:
        ba_score = min(
            25,
            12 + (
                (len(set(ba_matches)) - 1) * 3
            ),
        )
    else:
        ba_score = 0

    # -------------------------------------------------------------
    # 3. Data / analytics — 15 points
    # -------------------------------------------------------------

    data_keywords = [
        "data migration",
        "data mapping",
        "data transformation",
        "data analysis",
        "data analytics",
        "data management",
        "sql",
        "hive",
        "hql",
        "dashboard",
        "dashboards",
        "reporting",
        "large datasets",
    ]

    data_matches = [
        keyword
        for keyword in data_keywords
        if keyword_present(
            keyword,
            job_text,
        )
        and keyword_present(
            keyword,
            profile_text,
        )
    ]

    if data_matches:
        data_score = min(
            10,
            6 + (
                (len(set(data_matches)) - 1) * 2
            ),
        )
    else:
        data_score = 0

    # -------------------------------------------------------------
    # 4. Transformation / process / automation — 10 points
    # -------------------------------------------------------------

    transformation_keywords = [
        "process modelling",
        "process modeling",
        "process mapping",
        "business process",
        "process improvement",
        "process transformation",
        "digital transformation",
        "business transformation",
        "bpr",
        "business process reengineering",
        "gap analysis",
        "bpmn",
        "automation",
        "rpa",
        "robotic process automation",
        "digital",
    ]

    transformation_matches = [
        keyword
        for keyword in transformation_keywords
        if keyword_present(
            keyword,
            job_text,
        )
        and keyword_present(
            keyword,
            profile_text,
        )
    ]

    if transformation_matches:
        transformation_score = min(
            15,
            8 + (
                (len(set(transformation_matches)) - 1) * 2
            ),
        )
    else:
        transformation_score = 0

    # -------------------------------------------------------------
    # 5. Domain — 5 points
    # -------------------------------------------------------------

    insurance_keywords = [
        "insurance",
        "life insurance",
        "p&c insurance",
        "property and casualty",
        "claims",
        "policy",
        "policies",
        "underwriting",
        "policy administration",
        "policy servicing",
    ]

    insurance_matches = [
        keyword
        for keyword in insurance_keywords
        if keyword_present(
            keyword,
            job_text,
        )
        and keyword_present(
            keyword,
            profile_text,
        )
    ]

    if insurance_matches:
        insurance_score = 5
    else:
        insurance_score = 0

    # -------------------------------------------------------------
    # 6. Testing / UAT — 5 points
    # -------------------------------------------------------------

    testing_keywords = [
        "uat",
        "user acceptance testing",
        "functional testing",
        "test scenarios",
        "test cases",
        "defect management",
        "defect resolution",
        "production defects",
        "release",
        "implementation",
    ]

    testing_matches = [
        keyword
        for keyword in testing_keywords
        if keyword_present(
            keyword,
            job_text,
        )
        and keyword_present(
            keyword,
            profile_text,
        )
    ]

    if testing_matches:
        testing_score = 5
    else:
        testing_score = 0

    # -------------------------------------------------------------
    # 7. Seniority — 5 points
    # -------------------------------------------------------------

    seniority_keywords = [
        "senior business analyst",
        "lead business analyst",
        "principal business analyst",
        "business consultant",
        "lead",
        "senior",
        "consultant",
    ]

    seniority_matches = [
        keyword
        for keyword in seniority_keywords
        if keyword_present(
            keyword,
            job_text,
        )
        and keyword_present(
            keyword,
            profile_text,
        )
    ]

    if seniority_matches:
        seniority_score = 5
    else:
        seniority_score = 0

    # -------------------------------------------------------------
    # Final score
    # -------------------------------------------------------------

    score = min(
        100,
        role_score
        + ba_score
        + data_score
        + transformation_score
        + insurance_score
        + testing_score
        + seniority_score,
    )

    # -------------------------------------------------------------
    # Match confidence
    #
    # The score tells us HOW WELL the job appears to fit.
    # Confidence tells us HOW MUCH evidence we had to make that
    # assessment.
    # -------------------------------------------------------------

    description_length = len(
        description
    )

    if description_length >= 1000:
        match_confidence = "HIGH"

    elif description_length >= 500:
        match_confidence = "MEDIUM"

    elif description_length >= 200:
        match_confidence = "LOW"

    elif description_length > 0:
        match_confidence = "VERY_LOW"

    else:
        match_confidence = "NONE"

    # -------------------------------------------------------------
    # Relevance level
    # -------------------------------------------------------------

    if score >= 80:
        relevance_level = "VERY_HIGH"

    elif score >= 65:
        relevance_level = "HIGH"

    elif score >= 50:
        relevance_level = "MEDIUM"

    elif score >= 35:
        relevance_level = "LOW"

    else:
        relevance_level = "VERY_LOW"

    # -------------------------------------------------------------
    # Matched capabilities
    # -------------------------------------------------------------

    matched_capabilities = []

    if role_score:
        matched_capabilities.append(
            "role_alignment"
        )

    if ba_score:
        matched_capabilities.append(
            "business_analysis"
        )

    if data_score:
        matched_capabilities.append(
            "data"
        )

    if transformation_score:
        matched_capabilities.append(
            "process_transformation"
        )

    if insurance_score:
        matched_capabilities.append(
            "insurance"
        )

    if testing_score:
        matched_capabilities.append(
            "testing_delivery"
        )

    if seniority_score:
        matched_capabilities.append(
            "seniority"
        )

    matched_keywords = sorted(
        set(
            ba_matches
            + data_matches
            + transformation_matches
            + insurance_matches
            + testing_matches
            + seniority_matches
        )
    )

    return {
        "relevance_score": score,
        "relevance_level": relevance_level,
        "match_confidence": match_confidence,
        "description_length": description_length,
        "matched_capabilities": matched_capabilities,
        "matched_keywords": matched_keywords,
        "missing_capabilities": [],
    }