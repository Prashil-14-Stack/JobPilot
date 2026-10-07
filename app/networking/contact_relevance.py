from dataclasses import dataclass


@dataclass
class ContactRelevance:
    score: int
    level: str
    reasons: list[str]


class ContactRelevanceAnalyzer:
    """
    Deterministic, job-aware contact relevance scoring for JobPilot.

    Relevance is calculated using:
        1. Contact's job title
        2. Canonical job role
        3. Matched job skills
    """

    VERY_HIGH_TITLE_KEYWORDS = [
        "head of business analysis",
        "architecture",
        "architect",
        "enterprise architecture",
        "solution architecture",
        "technology strategy",
        "head of business analyst",
        "business analysis director",
        "business analysis manager",
        "director of business analysis",
        "director business analysis",
        "business transformation",
        "digital transformation",
        "transformation director",
        "transformation manager",
    ]

    HIGH_TITLE_KEYWORDS = [
        "talent acquisition",
        "talent partner",
        "talent manager",
        "recruiter",
        "recruitment",
        "recruiting",
        "technical recruiter",
        "senior recruiter",
        "hr business partner",
        "product manager",
        "product director",
        "head of product",
        "technology director",
        "technology manager",
        "technology lead",
        "engineering manager",
        "engineering director",
        "it director",
        "head of technology",
        "head of digital",
        "digital director",
        "digital manager",
    ]

    SENIORITY_KEYWORDS = [
        "vice president",
        "vp ",
        "director",
        "head of",
        "managing director",
        "senior manager",
        "general manager",
        "chief technology officer",
        "cto",
        "chief digital officer",
        "cdo",
    ]

    LOW_RELEVANCE_KEYWORDS = [
        "finance",
        "financial",
        "accounting",
        "legal",
        "lawyer",
        "counsel",
        "communications",
        "marketing",
        "sales",
        "procurement",
        "payroll",
    ]

    ROLE_KEYWORDS = {
        "business analyst": [
            "business analysis",
            "business analyst",
            "requirements",
            "transformation",
            "process",
            "product",
            "technology",
            "digital",
        ],
        "data analyst": [
            "data",
            "analytics",
            "business intelligence",
            "insights",
            "reporting",
        ],
        "product manager": [
            "product",
            "product management",
            "digital product",
            "technology",
        ],
        "project manager": [
            "project",
            "program",
            "delivery",
            "transformation",
        ],
        "digital transformation consultant": [
            "digital transformation",
            "transformation",
            "digital",
            "technology",
            "innovation",
        ],
        "ai transformation consultant": [
            "artificial intelligence",
            "ai",
            "automation",
            "digital transformation",
            "transformation",
            "innovation",
            "technology",
        ],
    }

    def analyze(
        self,
        position: str | None,
        canonical_role: str | None = None,
        matched_skills: list[str] | None = None,
    ) -> ContactRelevance:
        """
        Calculate job-aware contact relevance.

        Args:
            position:
                Contact's professional title.

            canonical_role:
                JobPilot canonical role associated with the job.

            matched_skills:
                Skills matched against the candidate profile/job.

        Returns:
            ContactRelevance containing score, level and reasons.
        """

        title = (position or "").strip().lower()
        role = (canonical_role or "").strip().lower()

        skills = [
            str(skill).strip().lower()
            for skill in (matched_skills or [])
            if str(skill).strip()
        ]

        if not title:
            return ContactRelevance(
                score=0,
                level="UNKNOWN",
                reasons=["Contact has no job title"],
            )

        score = 30
        reasons: list[str] = []

        # --------------------------------------------------
        # 1. Very-high title relevance
        # --------------------------------------------------

        very_high_matches = [
            keyword
            for keyword in self.VERY_HIGH_TITLE_KEYWORDS
            if keyword in title
        ]

        if very_high_matches:
            score += 40

            reasons.extend(
                [
                    f"Strong leadership/function match: {keyword}"
                    for keyword in very_high_matches
                ]
            )

        # --------------------------------------------------
        # 2. High title relevance
        # --------------------------------------------------

        high_matches = [
            keyword
            for keyword in self.HIGH_TITLE_KEYWORDS
            if keyword in title
        ]

        if high_matches:
            score += 25

            reasons.extend(
                [
                    f"Relevant hiring/product/technology title: {keyword}"
                    for keyword in high_matches
                ]
            )

        # --------------------------------------------------
        # 3. Seniority
        # --------------------------------------------------

        seniority_matches = [
            keyword
            for keyword in self.SENIORITY_KEYWORDS
            if keyword in title
        ]

        if seniority_matches:
            score += 10

            reasons.append(
                f"Senior leadership signal: {seniority_matches[0]}"
            )

        # --------------------------------------------------
        # 4. Explicitly unrelated functions
        # --------------------------------------------------

        low_matches = [
            keyword
            for keyword in self.LOW_RELEVANCE_KEYWORDS
            if keyword in title
        ]

        if low_matches:
            score -= 25

            reasons.extend(
                [
                    f"Potentially unrelated function: {keyword}"
                    for keyword in low_matches
                ]
            )

        # --------------------------------------------------
        # 5. Job-aware role matching
        # --------------------------------------------------

        role_keywords = self._get_role_keywords(role)

        role_matches = [
            keyword
            for keyword in role_keywords
            if keyword in title
        ]

        if role_matches:
            score += min(25, len(role_matches) * 10)

            reasons.extend(
                [
                    f"Contact title aligns with target role: {keyword}"
                    for keyword in role_matches
                ]
            )

        # --------------------------------------------------
        # 6. Job skill alignment
        # --------------------------------------------------

        skill_matches = [
            skill
            for skill in skills
            if skill and skill in title
        ]

        if skill_matches:
            score += min(15, len(skill_matches) * 5)

            reasons.extend(
                [
                    f"Contact title aligns with job skill: {skill}"
                    for skill in skill_matches
                ]
            )

        # --------------------------------------------------
        # 7. Normalize score
        # --------------------------------------------------

        score = max(0, min(100, score))

        level = self._get_level(score)

        if not reasons:
            reasons.append(
                "No strong relevance signal detected"
            )

        return ContactRelevance(
            score=score,
            level=level,
            reasons=reasons,
        )

    # --------------------------------------------------
    # Role keyword mapping
    # --------------------------------------------------

    def _get_role_keywords(
        self,
        canonical_role: str,
    ) -> list[str]:

        if not canonical_role:
            return []

        for role_name, keywords in self.ROLE_KEYWORDS.items():
            if role_name in canonical_role:
                return keywords

        return []

    # --------------------------------------------------
    # Score → level
    # --------------------------------------------------

    @staticmethod
    def _get_level(score: int) -> str:

        if score >= 80:
            return "VERY_HIGH"

        if score >= 65:
            return "HIGH"

        if score >= 45:
            return "MEDIUM"

        if score >= 25:
            return "LOW"

        return "VERY_LOW"


if __name__ == "__main__":

    analyzer = ContactRelevanceAnalyzer()

    tests = [
        {
            "position": "Director of Business Analysis",
            "canonical_role": "Business Analyst",
            "matched_skills": ["SQL", "Power BI"],
        },
        {
            "position": "Vice President of Architecture",
            "canonical_role": "Business Analyst",
            "matched_skills": ["SQL", "Power BI"],
        },
        {
            "position": "Digital Transformation Director",
            "canonical_role": "AI Transformation Consultant",
            "matched_skills": ["AI", "Automation"],
        },
        {
            "position": "Communications Director",
            "canonical_role": "Business Analyst",
            "matched_skills": ["SQL"],
        },
        {
            "position": "Finance Director",
            "canonical_role": "Business Analyst",
            "matched_skills": ["SQL"],
        },
    ]

    for test in tests:

        result = analyzer.analyze(
            position=test["position"],
            canonical_role=test["canonical_role"],
            matched_skills=test["matched_skills"],
        )

        print(
            f"{test['position']} | "
            f"{test['canonical_role']} | "
            f"{result.score} | "
            f"{result.level}"
        )

        for reason in result.reasons:
            print(f"  - {reason}")