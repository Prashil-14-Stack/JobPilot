from typing import Any

from app.models.contact import Contact
from app.networking.contact_relevance import ContactRelevanceAnalyzer
from app.networking.hunter_client import HunterClient
from app.storage.contact_store import ContactStore
from app.storage.database import JobDatabase


class ContactDiscovery:
    """
    Discovers professional contacts for a JobPilot job.

    Flow:

        Job
         ↓
        Company domain
         ↓
        Hunter Domain Search
         ↓
        Contact model
         ↓
        Job-aware relevance analysis
         ↓
        Relevant contacts stored in SQLite
    """

    def __init__(
        self,
        hunter_client: HunterClient,
        contact_store: ContactStore,
        relevance_analyzer: ContactRelevanceAnalyzer,
    ) -> None:

        self.hunter_client = hunter_client
        self.contact_store = contact_store
        self.relevance_analyzer = relevance_analyzer

    def discover_for_job(
        self,
        company: str,
        company_domain: str,
        canonical_role: str,
        matched_skills: list[str] | None = None,
        limit: int = 10,
        max_contacts: int = 5,
        minimum_score: int = 25,
    ) -> dict[str, Any]:
        """
        Discover, rank and store the best contacts for a job/company.

        Hunter contacts are first scored using the job-aware relevance
        analyzer. Clearly irrelevant contacts are excluded, and the
        highest-ranked remaining contacts are selected.

        Args:
            company:
                Company name associated with the job.

            company_domain:
                Company's verified domain.

            canonical_role:
                JobPilot canonical role.

            matched_skills:
                Skills relevant to the job.

            limit:
                Maximum number of contacts requested from Hunter.

            max_contacts:
                Maximum number of contacts to retain.

            minimum_score:
                Minimum score required for a contact to be considered.

        Returns:
            Discovery summary.
        """

        if not company_domain:
            raise ValueError(
                "company_domain is required for Hunter Domain Search."
            )

        hunter_response = self.hunter_client.domain_search(
            domain=company_domain,
            limit=limit,
        )

        hunter_data = hunter_response.get("data", {})
        hunter_contacts = hunter_data.get("emails", [])

        discovered = 0
        rejected = 0
        stored_new = 0
        stored_updated = 0

        scored_contacts: list[dict[str, Any]] = []

        # --------------------------------------------------
        # Score every Hunter contact
        # --------------------------------------------------

        for hunter_contact in hunter_contacts:

            discovered += 1

            first_name = hunter_contact.get("first_name")
            last_name = hunter_contact.get("last_name")

            full_name = self._build_full_name(
                first_name,
                last_name,
            )

            email = hunter_contact.get("value")
            position = hunter_contact.get("position")
            confidence = hunter_contact.get("confidence")
            linkedin_url = hunter_contact.get("linkedin")

            relevance = self.relevance_analyzer.analyze(
                position=position,
                canonical_role=canonical_role,
                matched_skills=matched_skills,
            )

            contact_result = {
                "first_name": first_name,
                "last_name": last_name,
                "full_name": full_name,
                "email": email,
                "position": position,
                "company": company,
                "company_domain": company_domain,
                "linkedin_url": linkedin_url,
                "email_confidence": confidence,
                "email_verification_status": hunter_contact.get(
                    "verification",
                    {},
                ).get("status"),
                "relevance_score": relevance.score,
                "relevance_level": relevance.level,
                "relevance_reasons": relevance.reasons,
            }

            if not email:
                rejected += 1
                continue

            if relevance.score < minimum_score:
                rejected += 1
                continue

            scored_contacts.append(contact_result)

        # --------------------------------------------------
        # Rank contacts
        # --------------------------------------------------

        scored_contacts.sort(
            key=lambda contact: (
                contact["relevance_score"],
                contact["email_confidence"] or 0,
            ),
            reverse=True,
        )

        # --------------------------------------------------
        # Select top contacts
        # --------------------------------------------------

        selected_contacts = scored_contacts[:max_contacts]

        # Contacts that passed the minimum threshold but were
        # outside the top-N selection are not stored.
        not_selected = (
            len(scored_contacts) - len(selected_contacts)
        )

        rejected += max(0, not_selected)

        # --------------------------------------------------
        # Store selected contacts
        # --------------------------------------------------

        for contact_data in selected_contacts:

            contact_id = self._build_contact_id(
                company_domain=company_domain,
                email=contact_data["email"],
            )

            contact = Contact(
                contact_id=contact_id,
                first_name=contact_data["first_name"],
                last_name=contact_data["last_name"],
                full_name=contact_data["full_name"],
                email=contact_data["email"],
                position=contact_data["position"],
                company=contact_data["company"],
                company_domain=contact_data["company_domain"],
                linkedin_url=contact_data["linkedin_url"],
                email_confidence=contact_data["email_confidence"],
                email_verification_status=(
                    contact_data[
                        "email_verification_status"
                    ]
                ),
                source="Hunter",
            )

            save_result = self.contact_store.save_contact(
                contact
            )

            if save_result == "NEW":
                stored_new += 1

            elif save_result == "UPDATED":
                stored_updated += 1

        return {
            "company": company,
            "company_domain": company_domain,
            "canonical_role": canonical_role,
            "discovered": discovered,
            "eligible": len(scored_contacts),
            "selected": len(selected_contacts),
            "rejected": rejected,
            "stored_new": stored_new,
            "stored_updated": stored_updated,
            "contacts": selected_contacts,
        }
    
    @staticmethod
    def _build_full_name(
        first_name: str | None,
        last_name: str | None,
    ) -> str | None:

        parts = [
            part.strip()
            for part in [first_name, last_name]
            if part and part.strip()
        ]

        if not parts:
            return None

        return " ".join(parts)

    @staticmethod
    def _build_contact_id(
        company_domain: str,
        email: str,
    ) -> str:

        normalized_domain = company_domain.strip().lower()
        normalized_email = email.strip().lower()

        return (
            f"hunter-{normalized_domain}-{normalized_email}"
        )


if __name__ == "__main__":

    database = JobDatabase()

    hunter_client = HunterClient()

    contact_store = ContactStore(
        database=database
    )

    relevance_analyzer = ContactRelevanceAnalyzer()

    discovery = ContactDiscovery(
        hunter_client=hunter_client,
        contact_store=contact_store,
        relevance_analyzer=relevance_analyzer,
    )

    result = discovery.discover_for_job(
        company="Fidelity Investments",
        company_domain="fidelity.com",
        canonical_role="Business Analyst",
        matched_skills=[
            "SQL",
            "Power BI",
            "Digital Transformation",
        ],
        limit=5,
        max_contacts=5,
        minimum_score=25,
    )
    print("=" * 60)
    print("CONTACT DISCOVERY")
    print("=" * 60)

    print(f"Company: {result['company']}")
    print(f"Domain: {result['company_domain']}")
    print(f"Role: {result['canonical_role']}")
    print(f"Discovered: {result['discovered']}")
    print(f"Relevant: {result['relevant']}")
    print(f"Rejected: {result['rejected']}")
    print(f"New contacts: {result['stored_new']}")
    print(f"Updated contacts: {result['stored_updated']}")

    print()
    print("CONTACT RESULTS")
    print("-" * 60)

    for contact in result["contacts"]:
        print(
            contact["full_name"],
            "|",
            contact["position"],
            "|",
            contact["email"],
            "| Score:",
            contact["relevance_score"],
            "|",
            contact["relevance_level"],
        )

    database.close()