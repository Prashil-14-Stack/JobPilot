from pathlib import Path
from typing import Any

from app.networking.outreach import OutreachMessage


class OutreachGenerator:
    """
    Generates personalised cold outreach messages using:

        Job
        Contact
        Candidate Profile

    The generator only uses experience and capabilities
    supported by the candidate profile.
    """

    MASTER_CV_PATH = Path(
        "data/candidate/cv/current_cv.pdf"
    )

    def __init__(
        self,
        candidate_profile: dict[str, Any],
    ) -> None:
        self.candidate_profile = candidate_profile

    def generate(
        self,
        job: dict[str, Any],
        contact: dict[str, Any],
    ) -> OutreachMessage:

        contact_name = self._get_contact_name(contact)
        contact_email = contact.get("email", "")

        company = (
            job.get("company")
            or contact.get("company")
            or ""
        )

        role = (
            job.get("title")
            or job.get("canonical_role")
            or ""
        )

        contact_function = self._get_contact_function(
            contact
        )

        requirement = self._select_relevant_requirement(
            job
        )

        evidence = self._select_relevant_evidence(
            requirement
        )

        subject = self._build_subject(
            company=company,
            role=role,
        )

        body = self._build_body(
            contact_name=contact_name,
            company=company,
            role=role,
            requirement=requirement,
            evidence=evidence,
            contact_function=contact_function,
        )

        return OutreachMessage(
            contact_id=str(
                contact.get("contact_id", "")
            ),
            contact_name=contact_name,
            contact_email=contact_email,
            company=company,
            role=role,
            subject=subject,
            body=body,
            cv_path=str(
                self.MASTER_CV_PATH
            ),
            job_id=job.get("id"),
            status="DRAFT",
        )

    # --------------------------------------------------
    # Contact
    # --------------------------------------------------

    def _get_contact_name(
        self,
        contact: dict[str, Any],
    ) -> str:

        name = (
            contact.get("full_name")
            or ""
        ).strip()

        if name:
            return name

        first_name = (
            contact.get("first_name")
            or ""
        ).strip()

        if first_name:
            return first_name

        return "there"

    def _get_contact_function(
        self,
        contact: dict[str, Any],
    ) -> str:

        position = (
            contact.get("position")
            or ""
        ).strip()

        if not position:
            return "your team"

        position_lower = position.lower()

        mappings = [
            (
                [
                    "talent acquisition",
                    "recruiter",
                    "recruiting",
                    "recruitment",
                    "talent partner",
                    "talent manager",
                    "hr business partner",
                ],
                "Talent Acquisition",
            ),
            (
                [
                    "business analysis",
                    "business analyst",
                ],
                "Business Analysis",
            ),
            (
                [
                    "business transformation",
                    "digital transformation",
                    "transformation",
                ],
                "Business Transformation",
            ),
            (
                [
                    "product manager",
                    "product director",
                    "head of product",
                ],
                "Product",
            ),
            (
                [
                    "technology",
                    "engineering",
                    "architecture",
                ],
                "Technology",
            ),
            (
                [
                    "digital",
                ],
                "Digital Transformation",
            ),
        ]

        for keywords, function in mappings:
            if any(
                keyword in position_lower
                for keyword in keywords
            ):
                return function

        return position

    # --------------------------------------------------
    # Job requirement
    # --------------------------------------------------

    def _select_relevant_requirement(
        self,
        job: dict[str, Any],
    ) -> str:

        description = (
            job.get("description")
            or ""
        ).strip()

        if not description:
            return "the requirements outlined for the role"

        description_lower = description.lower()

        priority_signals = [
            "data migration",
            "requirements gathering",
            "stakeholder management",
            "uat",
            "business analysis",
            "process modelling",
            "data mapping",
            "functional requirements",
            "user stories",
        ]

        matched = [
            signal
            for signal in priority_signals
            if signal in description_lower
        ]

        if len(matched) >= 2:
            return (
                "the focus on "
                + " and ".join(matched[:2])
            )

        if matched:
            return (
                "the focus on "
                + matched[0]
            )

        return "the requirements outlined for the role"

    # --------------------------------------------------
    # Candidate evidence
    # --------------------------------------------------

    def _select_relevant_evidence(
        self,
        requirement: str,
    ) -> str:

        requirement_lower = requirement.lower()

        experience_items = (
            self.candidate_profile
            .get("experience", [])
        )

        # Reconstruct the experience text because the
        # profile stores experience as text fragments.
        experience_text = " ".join(
            item.get("text", "")
            for item in experience_items
            if isinstance(item, dict)
        )

        experience_lower = experience_text.lower()

        # Strongest evidence for data migration /
        # requirements gathering roles.
        if (
            "data migration" in requirement_lower
            and "6.5m+" in experience_lower
            and "opUS".lower() in experience_lower
            and "mccamish ngin" in experience_lower
        ):
            return (
                "My background combines Business Analysis, "
                "data transformation and insurance, including "
                "leading the migration of 6.5M+ insurance policies "
                "from OPUS to McCamish NGIN and working across "
                "business and technology teams."
            )

        return (
            "My background combines Business Analysis, "
            "data transformation and insurance, with experience "
            "working across business and technology teams."
        )
    # --------------------------------------------------
    # Subject
    # --------------------------------------------------

    @staticmethod
    def _build_subject(
        company: str,
        role: str,
    ) -> str:

        if role and company:
            return f"{role} | {company}"

        if role:
            return role

        return "Business Analyst Opportunity"

    # --------------------------------------------------
    # Email body
    # --------------------------------------------------

    @staticmethod
    def _build_body(
        contact_name: str,
        company: str,
        role: str,
        requirement: str,
        evidence: str,
        contact_function: str,
    ) -> str:

        greeting_name = (
            contact_name
            if contact_name != "there"
            else "there"
        )

        return f"""Hi {greeting_name},

I came across {company}'s opening for {role} and was particularly interested in {requirement}.

{evidence}

Given your role in {contact_function}, I thought it would be worth reaching out directly. I've attached my CV for context and would be grateful if you could keep my profile in mind for this role or similar opportunities within your team.

Best regards,
Prashil Wanjari"""