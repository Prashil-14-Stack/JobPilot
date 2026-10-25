from pathlib import Path
from typing import Any

from app.networking.outreach import OutreachMessage
from app.services.user_context import get_user_profile_directory

class OutreachGenerator:
    """
    Generates personalised cold outreach messages using:

        Job
        Contact
        Candidate Profile

    The generator only uses experience and capabilities
    supported by the candidate profile.
    """
    def __init__(
        self,
        candidate_profile: dict[str, Any],
        user_id: str | None = None,
    ) -> None:
        if not user_id or "@" not in user_id.strip():
            raise ValueError(
                "A verified authenticated user_id is required "
                "for personalized outreach."
            )

        self.candidate_profile = candidate_profile
        self.user_id = user_id.strip().lower()

        profile_dir = get_user_profile_directory(self.user_id)
        cv_files = sorted(
            profile_dir.glob("current_cv.*"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        self.cv_path = cv_files[0] if cv_files else None

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
            candidate_name=(
                str(self.candidate_profile.get("candidate_name") or "Candidate").strip()
            ),
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
            cv_path=str(self.cv_path) if self.cv_path else "",
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
        """Select job requirements relevant to the active candidate's profile."""
        description = str(job.get("description") or "").strip()

        if not description:
            return "the requirements outlined for the role"

        description_lower = description.lower()
        profile = self.candidate_profile

        # Build candidate-specific signals from the active profile.
        signals: list[str] = []

        capabilities = profile.get("capabilities", {})
        if isinstance(capabilities, dict):
            for key in (
                "skills",
                "tools",
                "technologies",
                "domains",
                "functional_areas",
            ):
                values = capabilities.get(key, [])
                if isinstance(values, list):
                    signals.extend(
                        str(value).strip().lower()
                        for value in values
                        if str(value).strip()
                    )

        summary = str(profile.get("professional_summary") or "").strip()
        if summary:
            # Add useful phrases from the candidate's summary.
            summary_parts = (
                summary.replace(".", ",")
                .replace(";", ",")
                .split(",")
            )
            signals.extend(
                part.strip().lower()
                for part in summary_parts
                if len(part.strip()) >= 4
            )

        # Preserve useful role-specific phrases from the job description
        # when they overlap with the candidate's profile.
        matched = []
        for signal in dict.fromkeys(signals):
            if signal in description_lower and signal not in matched:
                matched.append(signal)

        if matched:
            return "the focus on " + " and ".join(matched[:2])

        return "the requirements outlined for the role"

    # --------------------------------------------------
    # Candidate evidence
    # --------------------------------------------------

    def _select_relevant_evidence(
        self,
        requirement: str,
    ) -> str:
        """Select evidence only from the active candidate's profile."""
        profile = self.candidate_profile
        requirement_lower = requirement.lower()

        experience_items = profile.get("experience", [])
        experience_parts = [
            item.get("text", "").strip()
            for item in experience_items
            if isinstance(item, dict) and item.get("text")
        ]

        summary = str(
            profile.get("professional_summary") or ""
        ).strip()

        capabilities = profile.get("capabilities", {})
        capability_parts = []

        if isinstance(capabilities, dict):
            for key in (
                "skills",
                "tools",
                "technologies",
                "domains",
                "functional_areas",
            ):
                values = capabilities.get(key, [])
                if isinstance(values, list):
                    capability_parts.extend(
                        str(value).strip()
                        for value in values
                        if str(value).strip()
                    )

        evidence_pool = experience_parts + ([summary] if summary else [])
        if not evidence_pool:
            evidence_pool = capability_parts

        if not evidence_pool:
            return (
                "My experience and skills are outlined in my "
                "attached CV and can be discussed in more detail."
            )

        # Prefer evidence related to the role's stated requirements.
        signals = [
            signal.strip().lower()
            for signal in requirement_lower.replace("the focus on ", "").split(" and ")
            if signal.strip()
        ]

        scored = []
        for index, item in enumerate(evidence_pool):
            item_lower = item.lower()
            score = sum(1 for signal in signals if signal in item_lower)

            # A summary is useful context, but prefer specific experience
            # when it is relevant to the opportunity.
            scored.append((score, -index, item))

        best_score = max(item[0] for item in scored)
        if best_score > 0:
            selected = [
                item for score, _, item in scored
                if score == best_score
            ][:2]
        else:
            selected = evidence_pool[:2]

        # Keep the draft readable and avoid repeating an entire CV section.
        selected = [
            " ".join(item.split())[:550]
            for item in selected
            if item.strip()
        ]

        if not selected:
            return (
                "My experience and skills are outlined in my "
                "attached CV and can be discussed in more detail."
            )

        return "Relevant experience from my background includes: " + " ".join(selected)
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
        candidate_name: str = "Candidate",
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
{candidate_name}"""