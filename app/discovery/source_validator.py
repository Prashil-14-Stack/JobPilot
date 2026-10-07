from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.models.source import JobSource, SourceRegistry


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SOURCE_REGISTRY_PATH = (
    PROJECT_ROOT
    / "data"
    / "sources"
    / "source_registry.json"
)

VALIDATED_SOURCE_REGISTRY_PATH = (
    PROJECT_ROOT
    / "data"
    / "sources"
    / "validated_source_registry.json"
)


class SourceValidator:
    """
    Validates discovered job sources.

    Validation is deterministic and does not use AI.

    Important:
    HTTP failure does not automatically mean that a source is invalid.

    A source can be:
    - directly reachable
    - reachable but restricted
    - temporarily unavailable
    - unreachable
    - a generic source category
    - valid through search-engine discovery even without direct access
    """

    CATEGORY_SOURCE_TYPES = {
        "consulting-firm career sites",
        "insurance-company career sites",
        "erp, crm and software-vendor career sites",
    }

    def __init__(
        self,
        source_registry_path: Path = SOURCE_REGISTRY_PATH,
        validated_registry_path: Path = VALIDATED_SOURCE_REGISTRY_PATH,
    ):
        self.source_registry_path = source_registry_path
        self.validated_registry_path = validated_registry_path

    # ------------------------------------------------------------------
    # Registry loading
    # ------------------------------------------------------------------

    def load_source_registry(self) -> SourceRegistry:
        if not self.source_registry_path.exists():
            raise FileNotFoundError(
                f"Source registry not found: {self.source_registry_path}"
            )

        with open(
            self.source_registry_path,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        return SourceRegistry.model_validate(data)

    # ------------------------------------------------------------------
    # URL validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate_url(
        url: str | None,
    ) -> tuple[bool, str | None]:
        """
        Validate URL syntax only.

        Returns:
            (is_valid, error_message)
        """

        if not url:
            return False, "No URL provided"

        try:
            parsed = urlparse(url)

            if parsed.scheme not in {"http", "https"}:
                return False, "URL must use HTTP or HTTPS"

            if not parsed.netloc:
                return False, "URL has no valid domain"

            return True, None

        except Exception as exc:
            return False, f"URL parsing failed: {exc}"

    # ------------------------------------------------------------------
    # HTTP validation
    # ------------------------------------------------------------------

    @staticmethod
    def check_reachability(
        url: str,
        timeout: int = 10,
    ) -> tuple[str, int | None, str | None]:
        """
        Check whether a URL can be reached.

        Returns:

            status:
                REACHABLE
                RESTRICTED
                NOT_REACHABLE
                UNCERTAIN

            http_status:
                HTTP status code when available

            error:
                Diagnostic information
        """

        headers = {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/144.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
        }

        # --------------------------------------------------------------
        # First attempt: HEAD
        # --------------------------------------------------------------

        head_request = Request(
            url,
            method="HEAD",
            headers=headers,
        )

        try:
            with urlopen(
                head_request,
                timeout=timeout,
            ) as response:

                return (
                    "REACHABLE",
                    response.status,
                    None,
                )

        except HTTPError as exc:

            # ----------------------------------------------------------
            # 403 / 405 does NOT mean the site is invalid.
            # It usually means automated HEAD requests are restricted.
            # ----------------------------------------------------------

            if exc.code in {403, 405}:
                return (
                    "RESTRICTED",
                    exc.code,
                    f"HTTP {exc.code} - HEAD request restricted",
                )

            # ----------------------------------------------------------
            # Other HTTP errors mean the domain responded.
            # ----------------------------------------------------------

            if 400 <= exc.code < 600:
                return (
                    "UNCERTAIN",
                    exc.code,
                    f"HTTP {exc.code}",
                )

        except TimeoutError:
            return (
                "UNCERTAIN",
                None,
                "Request timed out",
            )

        except URLError as exc:

            reason = str(exc.reason)

            # DNS / hostname failure
            if "nodename nor servname" in reason.lower():
                return (
                    "NOT_REACHABLE",
                    None,
                    reason,
                )

            if "name or service not known" in reason.lower():
                return (
                    "NOT_REACHABLE",
                    None,
                    reason,
                )

            # Other network failures are uncertain rather than invalid.
            return (
                "UNCERTAIN",
                None,
                reason,
            )

        except Exception as exc:
            return (
                "UNCERTAIN",
                None,
                str(exc),
            )

        # ------------------------------------------------------------------
        # HEAD didn't provide a definitive result.
        # Try GET before declaring the source unreachable.
        # ------------------------------------------------------------------

        get_request = Request(
            url,
            method="GET",
            headers=headers,
        )

        try:
            with urlopen(
                get_request,
                timeout=timeout,
            ) as response:

                return (
                    "REACHABLE",
                    response.status,
                    None,
                )

        except HTTPError as exc:

            if exc.code in {403, 405}:
                return (
                    "RESTRICTED",
                    exc.code,
                    f"HTTP {exc.code} - access restricted",
                )

            return (
                "UNCERTAIN",
                exc.code,
                f"HTTP {exc.code}",
            )

        except TimeoutError:
            return (
                "UNCERTAIN",
                None,
                "GET request timed out",
            )

        except URLError as exc:

            reason = str(exc.reason)

            if "nodename nor servname" in reason.lower():
                return (
                    "NOT_REACHABLE",
                    None,
                    reason,
                )

            if "name or service not known" in reason.lower():
                return (
                    "NOT_REACHABLE",
                    None,
                    reason,
                )

            return (
                "UNCERTAIN",
                None,
                reason,
            )

        except Exception as exc:
            return (
                "UNCERTAIN",
                None,
                str(exc),
            )

    # ------------------------------------------------------------------
    # Source classification
    # ------------------------------------------------------------------

    @classmethod
    def is_category_source(
        cls,
        source: JobSource,
    ) -> bool:
        """
        Detect sources that represent a category of websites
        rather than one concrete website.
        """

        source_name = (
            source.name.strip().lower()
            if source.name
            else ""
        )

        return source_name in cls.CATEGORY_SOURCE_TYPES

    # ------------------------------------------------------------------
    # Validation method
    # ------------------------------------------------------------------

    @staticmethod
    def determine_validation_method(
        source: JobSource,
    ) -> str:

        if source.search_url:
            return "search_url"

        if source.web_search_available:
            return "search_engine"

        return "domain"

    # ------------------------------------------------------------------
    # Single source validation
    # ------------------------------------------------------------------

    def validate_source(
        self,
        source: JobSource,
    ) -> JobSource:

        # Reset validation fields.
        source.validation_error = None
        source.http_status = None
        source.validation_method = (
            self.determine_validation_method(source)
        )

        # ==============================================================
        # 1. Generic/category source
        # ==============================================================

        if self.is_category_source(source):

            source.verified = True
            source.reachable = None
            source.validation_error = (
                "Generic source category; "
                "requires search-engine or employer-domain discovery"
            )
            source.validation_method = "category_discovery"

            return source

        # ==============================================================
        # 2. Determine URL
        # ==============================================================

        validation_url = source.search_url

        # ==============================================================
        # 3. No URL
        # ==============================================================

        if not validation_url:

            # A source can still be useful through search engines.
            if source.web_search_available:

                source.verified = True
                source.reachable = None
                source.validation_method = "search_engine"
                source.validation_error = (
                    "No direct URL; source can be discovered "
                    "through search engine"
                )

                return source

            source.verified = False
            source.reachable = False
            source.validation_error = (
                "No URL or search mechanism available"
            )

            return source

        # ==============================================================
        # 4. Validate URL syntax
        # ==============================================================

        valid_url, error = self.validate_url(
            validation_url
        )

        if not valid_url:

            # If search-engine discovery exists, don't discard it.
            if source.web_search_available:

                source.verified = True
                source.reachable = None
                source.validation_method = "search_engine"
                source.validation_error = (
                    f"Direct URL invalid: {error}; "
                    "search-engine discovery remains available"
                )

                return source

            source.verified = False
            source.reachable = False
            source.validation_error = error

            return source

        # ==============================================================
        # 5. HTTP validation
        # ==============================================================

        status, http_status, error = (
            self.check_reachability(
                validation_url
            )
        )

        source.http_status = http_status

        # ==============================================================
        # 6. Reachable
        # ==============================================================

        if status == "REACHABLE":

            source.verified = True
            source.reachable = True
            source.validation_error = None

            return source

        # ==============================================================
        # 7. Restricted
        # ==============================================================

        if status == "RESTRICTED":

            # The source responded, therefore the domain exists.
            # Direct HTTP access is restricted, but other strategies
            # may still work.
            source.verified = True
            source.reachable = True
            source.validation_error = error

            return source

        # ==============================================================
        # 8. Uncertain
        # ==============================================================

        if status == "UNCERTAIN":

            if source.web_search_available:

                source.verified = True
                source.reachable = None
                source.validation_error = (
                    f"Direct validation uncertain: {error}; "
                    "search-engine discovery remains available"
                )

            else:

                source.verified = False
                source.reachable = None
                source.validation_error = error

            return source

        # ==============================================================
        # 9. Not reachable
        # ==============================================================

        if status == "NOT_REACHABLE":

            if source.web_search_available:

                source.verified = True
                source.reachable = False
                source.validation_error = (
                    f"Direct source unreachable: {error}; "
                    "search-engine discovery remains available"
                )

            else:

                source.verified = False
                source.reachable = False
                source.validation_error = error

            return source

        # ==============================================================
        # Safety fallback
        # ==============================================================

        source.verified = False
        source.reachable = False
        source.validation_error = (
            "Unknown validation result"
        )

        return source

    # ------------------------------------------------------------------
    # Validate all sources
    # ------------------------------------------------------------------

    def validate_all(self) -> SourceRegistry:

        registry = self.load_source_registry()

        validated_sources: list[JobSource] = []

        for source in registry.sources:

            validated_source = self.validate_source(
                source
            )

            validated_sources.append(
                validated_source
            )

        validated_registry = SourceRegistry(
            generated_at=datetime.now(
                timezone.utc
            ).isoformat(),
            role_universe_version=(
                registry.role_universe_version
            ),
            sources=validated_sources,
        )

        return validated_registry

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save_validated_registry(
        self,
        registry: SourceRegistry,
    ) -> None:

        self.validated_registry_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with open(
            self.validated_registry_path,
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
    # Main execution
    # ------------------------------------------------------------------

    def run(self) -> SourceRegistry:

        validated_registry = self.validate_all()

        self.save_validated_registry(
            validated_registry
        )

        return validated_registry


if __name__ == "__main__":

    validator = SourceValidator()

    registry = validator.run()

    total = len(registry.sources)

    verified = sum(
        1
        for source in registry.sources
        if source.verified
    )

    reachable = sum(
        1
        for source in registry.sources
        if source.reachable is True
    )

    restricted = sum(
        1
        for source in registry.sources
        if (
            source.http_status in {403, 405}
        )
    )

    uncertain = sum(
        1
        for source in registry.sources
        if (
            source.reachable is None
            and source.verified
        )
    )

    category_sources = sum(
        1
        for source in registry.sources
        if (
            source.validation_method
            == "category_discovery"
        )
    )

    print("Source Validation Complete")
    print("--------------------------")
    print(f"Total sources:       {total}")
    print(f"Verified:            {verified}")
    print(f"Directly reachable:  {reachable}")
    print(f"Restricted:          {restricted}")
    print(f"Uncertain:           {uncertain}")
    print(f"Category sources:    {category_sources}")
    print(
        f"Output:              "
        f"{VALIDATED_SOURCE_REGISTRY_PATH}"
    )