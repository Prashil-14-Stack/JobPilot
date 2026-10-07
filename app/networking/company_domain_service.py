from app.networking.company_domain_resolver import (
    CompanyDomainResolver,
)
from app.storage.company_domain_store import CompanyDomainStore
from app.storage.database import JobDatabase


class CompanyDomainService:
    """
    Resolves company domains for companies discovered
    through JobPilot jobs.

    Uses SQLite as the cache so web discovery is only
    performed when a company has no stored resolution.
    """

    def __init__(
        self,
        database: JobDatabase | None = None,
        resolver: CompanyDomainResolver | None = None,
        domain_store: CompanyDomainStore | None = None,
    ) -> None:

        self.database = database or JobDatabase()
        self.resolver = (
            resolver
            or CompanyDomainResolver()
        )
        self.domain_store = (
            domain_store
            or CompanyDomainStore(self.database)
        )

    def resolve_company(
        self,
        company: str,
    ):
        """
        Resolve one company to a verified domain.

        First checks the SQLite cache.
        If no cached resolution exists, performs
        domain discovery and stores the result.
        """

        cached = self.domain_store.get(company)

        if cached is not None:
            return cached

        result = self.resolver.resolve(company)

        self.domain_store.save(
            company=result.company,
            domain=result.domain,
            status=result.status,
            confidence=result.confidence,
            source=result.source,
            reason=result.reason,
        )

        return result

    def discover_company(
        self,
        company: str,
    ):
        """
        Discover and validate a domain for one company.

        First checks the SQLite cache.
        If no cached resolution exists, performs
        web discovery and stores the result.
        """

        cached = self.domain_store.get(company)

        if cached is not None:
            return cached

        result = self.resolver.discover_domain(
            company
        )

        self.domain_store.save(
            company=result.company,
            domain=result.domain,
            status=result.status,
            confidence=result.confidence,
            source=result.source,
            reason=result.reason,
        )

        return result
    def resolve_domain(
        self,
        company: str,
    ):
        """
        Resolve a company's domain using the cached result
        when available, otherwise discover and persist it.
        """

        cached = self.domain_store.get(company)

        if cached is not None:
            return cached

        result = self.resolver.discover_domain(
            company
        )

        self.domain_store.save(
            company=result.company,
            domain=result.domain,
            status=result.status,
            confidence=result.confidence,
            source=result.source,
            reason=result.reason,
        )

        return result
    def get_companies(self) -> list[str]:
        """
        Return unique companies currently present
        in the JobPilot job database.
        """

        return self.database.get_unique_companies()