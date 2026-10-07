from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from app.networking.domain_search import DomainSearch

@dataclass
class DomainResolution:
    """
    Result of resolving a company name to a domain.
    """

    company: str
    domain: Optional[str]
    status: str
    confidence: int
    source: str
    reason: str


class CompanyDomainResolver:
    """
    Resolves a company name to a verified company domain.

    Current implementation:
        - Uses a controlled registry.
        - Returns structured resolution information.
        - Does not guess unknown domains.

    Future implementation:
        - Web-based domain discovery.
        - Domain validation.
        - Cached resolutions.
        - Ambiguity handling.
    """

    COMPANY_DOMAINS = {
        "fidelity investments": "fidelity.com",
        "capgemini": "capgemini.com",
        "ibm": "ibm.com",
        "oracle": "oracle.com",
        "wipro": "wipro.com",
        "cgi": "cgi.com",
        "bairesdev": "bairesdev.com",
        "hatch": "hatch.com",
    }

    # Domains that must never be treated as employer domains.
    BLOCKED_DOMAINS = {
        "linkedin.com",
        "indeed.com",
        "glassdoor.com",
        "ziprecruiter.com",
        "monster.com",
        "talent.com",
        "adzuna.com",
        "jooble.org",
        "jobgether.com",
    }
    BLOCKED_SUBDOMAIN_PREFIXES = [
        "jobs.",
        "careers.",
        "career.",
        "talent.",
        "recruiting.",
        "recruitment.",
        "work.",
        "workwithus.",
        "join.",
    ]
    def resolve(
        self,
        company: str,
    ) -> DomainResolution:
        """
        Resolve a company name.

        Returns a structured DomainResolution rather than
        returning a domain string directly.
        """

        if not company or not company.strip():
            return DomainResolution(
                company=company or "",
                domain=None,
                status="INVALID",
                confidence=0,
                source="NONE",
                reason="Company name is empty.",
            )

        normalized_company = self._normalize_company_name(
            company
        )

        domain = self.COMPANY_DOMAINS.get(
            normalized_company
        )

        if not domain:
            return DomainResolution(
                company=company,
                domain=None,
                status="UNRESOLVED",
                confidence=0,
                source="NONE",
                reason=(
                    "Company is not present in the verified "
                    "domain registry."
                ),
            )

        if not self._is_allowed_domain(domain):
            return DomainResolution(
                company=company,
                domain=domain,
                status="INVALID",
                confidence=0,
                source="REGISTRY",
                reason=(
                    "Resolved domain is a blocked job-board "
                    "or aggregator domain."
                ),
            )

        return DomainResolution(
            company=company,
            domain=domain,
            status="VERIFIED",
            confidence=100,
            source="REGISTRY",
            reason="Exact match found in verified company domain registry.",
        )

    # --------------------------------------------------
    # Company normalization
    # --------------------------------------------------
    def discover_domain(
        self,
        company: str,
    ) -> DomainResolution:
        """
        Discover a company's official domain using DomainSearch.

        DomainSearch finds candidate domains.
        This resolver validates those candidates.
        """

        if not company or not company.strip():
            return DomainResolution(
                company=company or "",
                domain=None,
                status="INVALID",
                confidence=0,
                source="NONE",
                reason="Company name is empty.",
            )

        searcher = DomainSearch()

        candidates = searcher.search(
            company=company,
            max_results=10,
        )

        if not candidates:
            return DomainResolution(
                company=company,
                domain=None,
                status="UNRESOLVED",
                confidence=0,
                source="WEB_DISCOVERY",
                reason=(
                    "No candidate domains were returned "
                    "by the domain search."
                ),
            )

        ranked_candidates = sorted(
            candidates,
            key=lambda candidate: self._domain_company_match_score(
                candidate.domain,
                company,
            ),
            reverse=True,
        )

        for candidate in ranked_candidates:

            domain = candidate.domain

            if self._is_functional_subdomain(domain):
                continue

            if not self._is_allowed_domain(domain):
                continue

            validation = self._validate_domain(
                domain=domain,
                company=company,
            )

            if validation:
                return DomainResolution(
                company=company,
                domain=domain,
                status="VERIFIED",
                confidence=90,
                source="WEB_DISCOVERY",
                reason=(
                    "Candidate domain was discovered through "
                    "web search and successfully validated."
                ),
            )

        return DomainResolution(
            company=company,
            domain=None,
            status="UNRESOLVED",
            confidence=0,
            source="WEB_DISCOVERY",
            reason=(
                "Candidate domains were found, but none could "
                "be confidently validated as the company's "
                "official website."
            ),
        )
    def _domain_company_match_score(    
        self,
        domain: str,
        company: str,
    ) -> int:
        """
        Score how closely a domain name matches the company name.

        Higher scores indicate stronger evidence that the
        domain belongs to the requested company.
        """

        domain_name = domain.lower().split(".")[0]

        company_words = [
            word.lower()
            for word in company.split()
            if len(word) >= 3
        ]

        if not company_words:
            return 0

        matched_words = sum(
            1
            for word in company_words
            if word in domain.lower()
        )

        if matched_words == len(company_words):
            return 100

        if matched_words > 0:
            return 50

        return 0
    def _is_functional_subdomain(
        self,
        domain: str,
    ) -> bool:
        """
        Return True when a domain is an operational subdomain
        such as careers, jobs, talent, or applicant portals.
        """

        domain_lower = domain.lower()

        return any(
            domain_lower.startswith(prefix)
            for prefix in self.BLOCKED_SUBDOMAIN_PREFIXES
        )


    def _validate_domain(
        self,
        domain: str,
        company: str,
    ) -> bool:
        """
        Validate that a candidate domain is reachable and
        contains evidence that it represents the requested company.
        """
        domain_lower = domain.lower()

        if any(
            domain_lower.startswith(prefix)
            for prefix in self.BLOCKED_SUBDOMAIN_PREFIXES
        ):
            return False
        try:
            response = requests.get(
                f"https://{domain}",
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 "
                        "(Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 "
                        "(KHTML, like Gecko) "
                        "Chrome/144.0 Safari/537.36"
                    )
                },
                timeout=10,
                allow_redirects=True,
            )

            if response.status_code >= 400:
                return False

        except requests.RequestException:
            return False

        final_domain = urlparse(
            response.url
        ).netloc.lower()

        if final_domain.startswith("www."):
            final_domain = final_domain[4:]

        if not self._is_allowed_domain(final_domain):
            return False

        page_text = BeautifulSoup(
            response.text,
            "html.parser",
        ).get_text(
            " ",
            strip=True,
        ).lower()

        company_words = [
            word.lower()
            for word in company.split()
            if len(word) >= 3
        ]

        if not company_words:
            return False

        matches = sum(
            1
            for word in company_words
            if word in page_text
        )

        return matches >= 1

    
    @staticmethod
    def _normalize_company_name(
        company: str,
    ) -> str:

        normalized = company.strip().lower()

        # Remove common legal suffixes.
        suffixes = [
            ", inc.",
            " inc.",
            " inc",
            ", ltd.",
            " ltd.",
            " ltd",
            ", limited",
            " limited",
            ", llc",
            " llc",
            ", plc",
            " plc",
        ]

        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[
                    : -len(suffix)
                ].strip()
                break

        return normalized

    # --------------------------------------------------
    # Domain validation
    # --------------------------------------------------

    def _is_allowed_domain(
        self,
        domain: str,
    ) -> bool:

        normalized_domain = (
            domain.strip()
            .lower()
            .replace("https://", "")
            .replace("http://", "")
            .rstrip("/")
        )

        if not normalized_domain:
            return False

        if normalized_domain in self.BLOCKED_DOMAINS:
            return False

        return True


if __name__ == "__main__":

    resolver = CompanyDomainResolver()

    test_companies = [
        "Fidelity Investments",
        "IBM",
        "Capgemini",
        "IBM Inc.",
        "Unknown Company",
        "",
    ]

    print("=" * 60)
    print("COMPANY DOMAIN RESOLVER")
    print("=" * 60)

    for company in test_companies:

        result = resolver.resolve(company)

        print()
        print(f"Company:    {result.company}")
        print(f"Domain:     {result.domain}")
        print(f"Status:     {result.status}")
        print(f"Confidence: {result.confidence}")
        print(f"Source:     {result.source}")
        print(f"Reason:     {result.reason}")