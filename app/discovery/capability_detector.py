from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

from pydantic import BaseModel, Field

from app.models.source import (
    JobSource,
    SourceRegistry,
)


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

VALIDATED_REGISTRY_PATH = (
    PROJECT_ROOT
    / "data"
    / "sources"
    / "validated_source_registry.json"
)

CAPABILITY_REGISTRY_PATH = (
    PROJECT_ROOT
    / "data"
    / "sources"
    / "source_capability_registry.json"
)


class SourceCapability(BaseModel):
    """
    Describes how JobPilot may be able to interact
    with a discovered job source.
    """

    source_name: str
    domain: str

    source_category: str

    direct_http_access: bool
    search_url_available: bool
    variable_domain: bool

    search_engine_discovery: bool
    browser_strategy_possible: bool

    capability_confidence: float

    recommended_strategy: str

    evidence: list[str] = Field(
        default_factory=list
    )


class SourceCapabilityRegistry(BaseModel):
    """
    Registry containing capability assessments
    for all discovered sources.
    """

    generated_at: str

    capabilities: list[SourceCapability] = Field(
        default_factory=list
    )


class CapabilityDetector:

    def __init__(self):

        self.registry = self.load_registry()

    # ------------------------------------------------------------------
    # Load validated source registry
    # ------------------------------------------------------------------

    def load_registry(self) -> SourceRegistry:

        if not VALIDATED_REGISTRY_PATH.exists():

            raise FileNotFoundError(
                f"Validated source registry not found: "
                f"{VALIDATED_REGISTRY_PATH}"
            )

        with open(
            VALIDATED_REGISTRY_PATH,
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

        return SourceRegistry.model_validate(data)

    # ------------------------------------------------------------------
    # Detect source category
    # ------------------------------------------------------------------

    def detect_category(
        self,
        source: JobSource,
    ) -> str:

        source_type = (
            source.source_type or ""
        ).lower()

        name = (
            source.name or ""
        ).lower()

        combined = (
            source_type
            + " "
            + name
        )

        # --------------------------------------------------------------
        # Discovery / search layer
        # --------------------------------------------------------------

        if (
            "discovery layer" in source_type
            or "search engine" in source_type
        ):
            return "DISCOVERY_LAYER"

        # --------------------------------------------------------------
        # ATS / employer career platforms
        # --------------------------------------------------------------

        if (
            "applicant tracking system" in source_type
            or "ats" in source_type
            or "employer career platform" in source_type
        ):
            return "ATS_PLATFORM"

        # --------------------------------------------------------------
        # Public employment systems
        # --------------------------------------------------------------

        if (
            "public employment" in source_type
            or "public-sector employment" in source_type
            or "national public employment" in source_type
            or "regional public employment" in source_type
        ):
            return "PUBLIC_EMPLOYMENT"

        # --------------------------------------------------------------
        # Job aggregators
        # --------------------------------------------------------------

        if "aggregator" in source_type:

            return "JOB_AGGREGATOR"

        # --------------------------------------------------------------
        # Professional employment / job networks
        # --------------------------------------------------------------

        if (
            "professional job network" in source_type
            or "professional employment" in source_type
            or "employment network" in source_type
        ):
            return "JOB_NETWORK"

        # --------------------------------------------------------------
        # Job boards
        # --------------------------------------------------------------

        if (
            "job board" in source_type
            or "regional job board" in source_type
            or "specialist job board" in source_type
        ):
            return "JOB_BOARD"

        # --------------------------------------------------------------
        # Employer-owned career sites
        # --------------------------------------------------------------

        if (
            "employer-owned career" in combined
            or "employer-owned" in combined
        ):
            return "EMPLOYER_CAREERS"

        # --------------------------------------------------------------
        # Industry-specific portals
        # --------------------------------------------------------------

        if (
            "industry employment portal" in source_type
            or "insurance industry" in combined
            or "industry portal" in source_type
        ):
            return "INDUSTRY_PORTAL"

        # --------------------------------------------------------------
        # Known category-source names
        # --------------------------------------------------------------

        if (
            "consulting-firm career sites" in name
            or "consulting firm career sites" in name
        ):
            return "EMPLOYER_CAREERS"

        if (
            "insurance-company career sites" in name
            or "insurance company career sites" in name
        ):
            return "EMPLOYER_CAREERS"

        if (
            "erp, crm and software-vendor career sites" in name
            or "erp, crm and software vendor career sites" in name
        ):
            return "EMPLOYER_CAREERS"

        return "OTHER"

    # ------------------------------------------------------------------
    # Detect variable / dynamic domain
    # ------------------------------------------------------------------

    def detect_variable_domain(
        self,
        source: JobSource,
    ) -> bool:

        domain = (
            source.domain or ""
        ).lower()

        name = (
            source.name or ""
        ).lower()

        source_type = (
            source.source_type or ""
        ).lower()

        combined = (
            domain
            + " "
            + name
            + " "
            + source_type
        )

        # --------------------------------------------------------------
        # Explicit variable-domain indicators
        # --------------------------------------------------------------

        if (
            domain.startswith("varies")
            or "varies by" in domain
            or "various employer domains" in combined
            or "various insurer domains" in combined
            or "various software-vendor domains" in combined
        ):
            return True

        # --------------------------------------------------------------
        # Generic employer/source categories
        # --------------------------------------------------------------

        category_names = {
            "multinational consulting-firm career sites",
            "multinational consulting firm career sites",
            "insurance-company career sites",
            "insurance company career sites",
            "erp, crm and software-vendor career sites",
            "erp, crm and software vendor career sites",
        }

        if name in category_names:

            return True

        return False

    # ------------------------------------------------------------------
    # Detect actual direct HTTP capability
    # ------------------------------------------------------------------

    def detect_direct_http_access(
        self,
        source: JobSource,
    ) -> bool:

        # IMPORTANT:
        #
        # reachable=True does not necessarily mean direct HTTP
        # access is usable.
        #
        # 403 / 405 means the source responded but restricted
        # automated access.
        #
        # Therefore direct HTTP is only considered available when
        # validation succeeded without a restriction.

        if source.http_status in {403, 405}:

            return False

        if source.reachable is not True:

            return False

        return True

    # ------------------------------------------------------------------
    # Detect concrete search URL
    # ------------------------------------------------------------------

    def detect_search_url(
        self,
        source: JobSource,
    ) -> bool:

        return bool(
            source.search_url
        )

    # ------------------------------------------------------------------
    # Detect search-engine discovery
    # ------------------------------------------------------------------

    def detect_search_engine_discovery(
        self,
        source: JobSource,
    ) -> bool:

        if source.web_search_available is True:

            return True

        category = self.detect_category(
            source
        )

        return category in {
            "JOB_NETWORK",
            "JOB_AGGREGATOR",
            "JOB_BOARD",
            "ATS_PLATFORM",
            "EMPLOYER_CAREERS",
            "PUBLIC_EMPLOYMENT",
            "INDUSTRY_PORTAL",
            "DISCOVERY_LAYER",
        }

    # ------------------------------------------------------------------
    # Detect browser strategy
    # ------------------------------------------------------------------

    def detect_browser_strategy(
        self,
        source: JobSource,
    ) -> bool:

        category = self.detect_category(
            source
        )

        return category in {
            "JOB_NETWORK",
            "JOB_AGGREGATOR",
            "JOB_BOARD",
            "ATS_PLATFORM",
            "EMPLOYER_CAREERS",
            "PUBLIC_EMPLOYMENT",
            "INDUSTRY_PORTAL",
        }

    # ------------------------------------------------------------------
    # Determine recommended strategy
    # ------------------------------------------------------------------

    def determine_strategy(
        self,
        source: JobSource,
        direct_http: bool,
        search_url: bool,
        variable_domain: bool,
        search_engine: bool,
        browser_strategy: bool,
    ) -> str:

        # Generic employer-domain categories need to discover
        # actual employer domains first.
        if variable_domain:

            return "DYNAMIC_DOMAIN_DISCOVERY"

        # Direct HTTP + concrete search URL.
        if direct_http and search_url:

            return "DIRECT_SEARCH"

        # Direct HTTP without a concrete search URL.
        if direct_http:

            return "DIRECT_SOURCE_DISCOVERY"

        # Search-engine discovery is the preferred fallback
        # when direct HTTP is unavailable/restricted.
        if search_engine:

            return "SEARCH_ENGINE_DISCOVERY"

        # Browser search is a final fallback.
        if browser_strategy:

            return "BROWSER_SEARCH"

        return "UNSUPPORTED"

    # ------------------------------------------------------------------
    # Calculate confidence
    # ------------------------------------------------------------------

    def calculate_confidence(
        self,
        source: JobSource,
        direct_http: bool,
        search_url: bool,
        search_engine: bool,
        browser_strategy: bool,
        variable_domain: bool,
    ) -> float:

        score = 0.0

        # --------------------------------------------------------------
        # Direct HTTP
        # --------------------------------------------------------------

        if direct_http:

            score += 0.35

        # --------------------------------------------------------------
        # Search URL
        # --------------------------------------------------------------

        if search_url:

            score += 0.20

        # --------------------------------------------------------------
        # Search-engine discovery
        # --------------------------------------------------------------

        if search_engine:

            score += 0.20

        # --------------------------------------------------------------
        # Browser strategy
        # --------------------------------------------------------------

        if browser_strategy:

            score += 0.10

        # --------------------------------------------------------------
        # Dynamic domain discovery
        # --------------------------------------------------------------

        if variable_domain:

            # Dynamic domains are legitimate but inherently
            # less deterministic than a fixed source.
            score += 0.05

        # --------------------------------------------------------------
        # Source Discovery confidence
        # --------------------------------------------------------------

        if source.confidence:

            score += (
                min(
                    source.confidence,
                    1.0,
                )
                * 0.10
            )

        return round(
            min(score, 1.0),
            2,
        )

    # ------------------------------------------------------------------
    # Build evidence
    # ------------------------------------------------------------------

    def build_evidence(
        self,
        source: JobSource,
        direct_http: bool,
        search_url: bool,
        variable_domain: bool,
        search_engine: bool,
        browser_strategy: bool,
    ) -> list[str]:

        evidence: list[str] = []

        # --------------------------------------------------------------
        # HTTP evidence
        # --------------------------------------------------------------

        if direct_http:

            evidence.append(
                "Source responded successfully "
                "to HTTP validation and direct HTTP "
                "access is available."
            )

        elif source.http_status in {403, 405}:

            evidence.append(
                f"Source responded with HTTP "
                f"{source.http_status}; direct automated "
                f"HTTP access is restricted."
            )

        elif source.reachable is True:

            evidence.append(
                "Source is reachable, but direct HTTP "
                "access is not considered available "
                "because the validation result is restricted."
            )

        elif source.validation_error:

            evidence.append(
                "Direct HTTP validation was "
                "uncertain or unavailable."
            )

        # --------------------------------------------------------------
        # Search URL
        # --------------------------------------------------------------

        if search_url:

            evidence.append(
                "A concrete search URL is available."
            )

        # --------------------------------------------------------------
        # Variable domain
        # --------------------------------------------------------------

        if variable_domain:

            evidence.append(
                "Source represents multiple employer "
                "or vendor domains rather than one "
                "fixed job-search domain."
            )

        # --------------------------------------------------------------
        # Search-engine discovery
        # --------------------------------------------------------------

        if search_engine:

            evidence.append(
                "Search-engine discovery is available "
                "or appropriate for this source."
            )

        # --------------------------------------------------------------
        # Browser
        # --------------------------------------------------------------

        if browser_strategy:

            evidence.append(
                "Browser-based interaction may be "
                "possible for this source."
            )

        # --------------------------------------------------------------
        # Validation
        # --------------------------------------------------------------

        if source.verified:

            evidence.append(
                "Source passed validation or has a "
                "supported alternative discovery method."
            )

        return evidence

    # ------------------------------------------------------------------
    # Detect capability for one source
    # ------------------------------------------------------------------

    def detect_source(
        self,
        source: JobSource,
    ) -> SourceCapability:

        category = self.detect_category(
            source
        )

        variable_domain = (
            self.detect_variable_domain(
                source
            )
        )

        direct_http = (
            self.detect_direct_http_access(
                source
            )
        )

        search_url = (
            self.detect_search_url(
                source
            )
        )

        search_engine = (
            self.detect_search_engine_discovery(
                source
            )
        )

        browser_strategy = (
            self.detect_browser_strategy(
                source
            )
        )

        strategy = self.determine_strategy(
            source=source,
            direct_http=direct_http,
            search_url=search_url,
            variable_domain=variable_domain,
            search_engine=search_engine,
            browser_strategy=browser_strategy,
        )

        confidence = self.calculate_confidence(
            source=source,
            direct_http=direct_http,
            search_url=search_url,
            search_engine=search_engine,
            browser_strategy=browser_strategy,
            variable_domain=variable_domain,
        )

        evidence = self.build_evidence(
            source=source,
            direct_http=direct_http,
            search_url=search_url,
            variable_domain=variable_domain,
            search_engine=search_engine,
            browser_strategy=browser_strategy,
        )

        return SourceCapability(
            source_name=source.name,
            domain=source.domain,
            source_category=category,
            direct_http_access=direct_http,
            search_url_available=search_url,
            variable_domain=variable_domain,
            search_engine_discovery=search_engine,
            browser_strategy_possible=browser_strategy,
            capability_confidence=confidence,
            recommended_strategy=strategy,
            evidence=evidence,
        )

    # ------------------------------------------------------------------
    # Detect all sources
    # ------------------------------------------------------------------

    def detect_all(
        self,
    ) -> SourceCapabilityRegistry:

        capabilities: list[SourceCapability] = []

        for source in self.registry.sources:

            capability = self.detect_source(
                source
            )

            capabilities.append(
                capability
            )

        return SourceCapabilityRegistry(
            generated_at=datetime.now(
                timezone.utc
            ).isoformat(),
            capabilities=capabilities,
        )

    # ------------------------------------------------------------------
    # Save capability registry
    # ------------------------------------------------------------------

    def save_registry(
        self,
        registry: SourceCapabilityRegistry,
    ) -> None:

        CAPABILITY_REGISTRY_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with open(
            CAPABILITY_REGISTRY_PATH,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                registry.model_dump(),
                file,
                indent=2,
                ensure_ascii=False,
            )

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(
        self,
    ) -> SourceCapabilityRegistry:

        capability_registry = self.detect_all()

        self.save_registry(
            capability_registry
        )

        return capability_registry


if __name__ == "__main__":

    detector = CapabilityDetector()

    registry = detector.run()

    total = len(
        registry.capabilities
    )

    direct = sum(
        1
        for capability in registry.capabilities
        if capability.direct_http_access
    )

    search_url = sum(
        1
        for capability in registry.capabilities
        if capability.search_url_available
    )

    search_engine = sum(
        1
        for capability in registry.capabilities
        if capability.search_engine_discovery
    )

    browser = sum(
        1
        for capability in registry.capabilities
        if capability.browser_strategy_possible
    )

    dynamic = sum(
        1
        for capability in registry.capabilities
        if capability.recommended_strategy
        == "DYNAMIC_DOMAIN_DISCOVERY"
    )

    direct_search = sum(
        1
        for capability in registry.capabilities
        if capability.recommended_strategy
        == "DIRECT_SEARCH"
    )

    search_engine_strategy = sum(
        1
        for capability in registry.capabilities
        if capability.recommended_strategy
        == "SEARCH_ENGINE_DISCOVERY"
    )

    browser_strategy = sum(
        1
        for capability in registry.capabilities
        if capability.recommended_strategy
        == "BROWSER_SEARCH"
    )

    unsupported = sum(
        1
        for capability in registry.capabilities
        if capability.recommended_strategy
        == "UNSUPPORTED"
    )

    print("Capability Detection Complete")
    print("------------------------------")
    print(f"Total sources:           {total}")
    print(f"Direct HTTP:             {direct}")
    print(f"Search URL available:    {search_url}")
    print(f"Search-engine discovery: {search_engine}")
    print(f"Browser strategy:        {browser}")
    print(f"Dynamic domain:          {dynamic}")
    print(f"DIRECT_SEARCH:           {direct_search}")
    print(
        f"SEARCH_ENGINE_DISCOVERY: "
        f"{search_engine_strategy}"
    )
    print(f"BROWSER_SEARCH:          {browser_strategy}")
    print(f"UNSUPPORTED:             {unsupported}")
    print(
        f"Output:                  "
        f"{CAPABILITY_REGISTRY_PATH}"
    )