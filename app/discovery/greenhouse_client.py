"""
Greenhouse public Job Board API client for JobPilot.

This module only retrieves and shapes published job-board listings. It does not
write to SQLite, modify JobPilot's search plan, or run AI relevance analysis.

Example:
    from app.discovery.greenhouse_client import GreenhouseClient

    client = GreenhouseClient()
    jobs = client.fetch_board_jobs("stripe", company_name="Stripe")
    print(f"Retrieved {len(jobs)} published listings")

    # Configure additional board tokens explicitly:
    boards = {
        "stripe": "Stripe",
        "example-company": "Example Company",
    }
    results = client.fetch_boards(boards)

The board token is the identifier used in a public Greenhouse board URL/API.
Only configure tokens you have verified.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
import re
import time
from typing import Any, Mapping
from urllib.parse import urlparse

import requests


API_BASE_URL = "https://boards-api.greenhouse.io/v1/boards"
DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_MAX_RETRIES = 2
USER_AGENT = "JobPilot/1.0 (public job-board retrieval)"


class GreenhouseAPIError(RuntimeError):
    """Raised when Greenhouse cannot return a usable job-board response."""


class _HTMLTextExtractor(HTMLParser):
    """Convert HTML descriptions to readable text without extra dependencies."""

    BLOCK_TAGS = {
        "address", "article", "br", "div", "h1", "h2", "h3", "h4",
        "li", "ol", "p", "section", "tr", "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip_depth += 1
        elif self._skip_depth == 0 and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1
        elif self._skip_depth == 0 and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return re.sub(r"\n[ \t]*\n+", "\n\n", "\n".join(self.parts)).strip()


def _html_to_text(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parser = _HTMLTextExtractor()
    try:
        parser.feed(value)
        text = parser.text()
    except Exception:
        # Preserve the retrieval path if an unusual HTML fragment is malformed.
        text = re.sub(r"<[^>]+>", " ", value)
        text = " ".join(text.split())
    return text or None



def classify_role_title(title: str) -> str:
    """
    Lightweight title-only grouping for evaluation, not a relevance verdict.

    Returns: core, adjacent, or irrelevant.
    Review descriptions and requirements before treating a job as relevant.
    """
    normalized = " ".join((title or "").lower().split())

    core_terms = (
        "business analyst",
        "business systems analyst",
        "technical business analyst",
        "functional analyst",
        "process analyst",
        "product analyst",
        "requirements analyst",
        "business process analyst",
        "data migration analyst",
        "business intelligence analyst",
        "bi analyst",
        "transformation analyst",
        "insurance analyst",
        "policy administration analyst",
        "ai business analyst",
        "automation analyst",
    )

    adjacent_terms = (
        "operations analyst",
        "strategy analyst",
        "risk analyst",
        "data analyst",
        "analytics analyst",
        "finance analyst",
        "implementation consultant",
        "implementation specialist",
        "business transformation",
        "transformation",
        "business operations",
        "process improvement",
        "product owner",
        "business consultant",
        "management consultant",
        "business intelligence",
        "reporting analyst",
        "fraud operations",
        "credit risk operations",
    )

    # Avoid classifying sales positions as analyst or consultant roles.
    sales_indicators = (
        "account executive",
        "sales representative",
        "sales development",
        "product sales",
        "sales strategy",
    )
    if any(term in normalized for term in sales_indicators):
        return "irrelevant"

    if any(term in normalized for term in core_terms):
        return "core"

    if any(term in normalized for term in adjacent_terms):
        return "adjacent"

    return "irrelevant"


@dataclass
class BoardFetchResult:
    """Result and diagnostics for one employer board."""

    board_token: str
    company_name: str
    jobs: list[dict[str, Any]] = field(default_factory=list)
    status: str = "NOT_RUN"
    http_status: int | None = None
    error: str | None = None
    api_total: int | None = None


class GreenhouseClient:
    """
    Retrieve published jobs from Greenhouse public Job Board API endpoints.

    This client intentionally does not persist records. Callers can inspect the
    shaped jobs, run deduplication/dry-run checks, and then pass approved records
    into JobPilot's existing normalization and JobStore ingestion flow.
    """

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        session: requests.Session | None = None,
        request_delay_seconds: float = 0.0,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if request_delay_seconds < 0:
            raise ValueError("request_delay_seconds cannot be negative")

        self.timeout = timeout
        self.max_retries = max_retries
        self.request_delay_seconds = request_delay_seconds
        self.session = session or requests.Session()
        self._owns_session = session is None
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            }
        )

    @staticmethod
    def validate_board_token(board_token: str) -> str:
        """Validate and normalize a Greenhouse board token."""
        token = str(board_token or "").strip().strip("/")
        # Tokens are board identifiers, not arbitrary URLs.
        if not token or not re.fullmatch(r"[A-Za-z0-9_-]+", token):
            raise ValueError(
                "board_token must be a valid Greenhouse board identifier, "
                "not a URL. Example: 'stripe'."
            )
        return token

    @staticmethod
    def _company_name(board_token: str, company_name: str | None) -> str:
        if company_name and company_name.strip():
            return company_name.strip()
        # Keep a predictable fallback; board token may not equal the legal name.
        return board_token.replace("-", " ").replace("_", " ").title()

    def _get_json(self, url: str, params: Mapping[str, Any]) -> tuple[dict, int]:
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.get(
                    url,
                    params=dict(params),
                    timeout=self.timeout,
                )
                if response.status_code in (429, 500, 502, 503, 504):
                    response.raise_for_status()

                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise GreenhouseAPIError(
                        "Greenhouse returned JSON with an unexpected structure."
                    )
                return payload, response.status_code

            except (requests.RequestException, ValueError, GreenhouseAPIError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                # Respect Retry-After when provided, otherwise use short backoff.
                retry_after = None
                response_obj = getattr(exc, "response", None)
                if response_obj is not None:
                    retry_after = response_obj.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else min(2**attempt, 4)
                except (TypeError, ValueError):
                    delay = min(2**attempt, 4)
                time.sleep(max(0.0, min(delay, 10.0)))

        raise GreenhouseAPIError(
            f"Greenhouse request failed after {self.max_retries + 1} attempt(s): "
            f"{type(last_error).__name__}: {last_error}"
        ) from last_error

    @staticmethod
    def _shape_job(
        job: Mapping[str, Any],
        *,
        board_token: str,
        company_name: str,
    ) -> dict[str, Any] | None:
        """Map one Greenhouse API job into JobPilot's source-job shape."""
        job_id = job.get("id")
        title = job.get("title")
        if job_id is None or not isinstance(title, str) or not title.strip():
            return None

        raw_location = job.get("location")
        if isinstance(raw_location, dict):
            location = raw_location.get("name")
        elif isinstance(raw_location, str):
            location = raw_location
        else:
            location = None

        apply_url = job.get("absolute_url")
        # The API's absolute_url is the employer's published application page.
        if not isinstance(apply_url, str) or not apply_url.startswith(("https://", "http://")):
            apply_url = None

        departments = job.get("departments")
        offices = job.get("offices")
        content = job.get("content")
        description = _html_to_text(content)

        # Greenhouse's updated_at is not necessarily the original posting date.
        # Keep it in raw_data rather than mislabeling it as posted_date.
        return {
            "raw_job_id": f"greenhouse:{board_token}:{job_id}",
            "job_id": f"greenhouse:{board_token}:{job_id}",
            "source": "Greenhouse",
            "source_job_id": f"{board_token}:{job_id}",
            "source_domain": "greenhouse.io",
            "title": title.strip(),
            "company": company_name,
            "location": location.strip() if isinstance(location, str) and location.strip() else None,
            "country": None,
            "remote_type": None,
            "source_url": apply_url,
            "apply_url": apply_url,
            "description": description,
            "posted_date": None,
            "search_task_id": f"GREENHOUSE:{board_token}",
            "content_mode": "FULL_CONTENT" if description else "TITLE_ONLY",
            "highlights": [],
            "raw_data": {
                "provider": "Greenhouse Job Board API",
                "board_token": board_token,
                "greenhouse_job_id": str(job_id),
                "updated_at": job.get("updated_at"),
                "first_published": job.get("first_published"),
                "departments": departments if isinstance(departments, list) else [],
                "offices": offices if isinstance(offices, list) else [],
                "metadata": job.get("metadata") if isinstance(job.get("metadata"), list) else [],
                "language": job.get("language"),
                "absolute_url": apply_url,
            },
        }

    def fetch_board(
        self,
        board_token: str,
        *,
        company_name: str | None = None,
        include_content: bool = True,
    ) -> BoardFetchResult:
        """Fetch all jobs returned by one public Greenhouse board endpoint."""
        token = self.validate_board_token(board_token)
        company = self._company_name(token, company_name)
        url = f"{API_BASE_URL}/{token}/jobs"
        params = {"content": "true" if include_content else "false"}

        result = BoardFetchResult(
            board_token=token,
            company_name=company,
        )

        try:
            payload, status = self._get_json(url, params)
            result.http_status = status

            records = payload.get("jobs", [])
            if not isinstance(records, list):
                raise GreenhouseAPIError(
                    f"Greenhouse board '{token}' response has no valid jobs list."
                )

            result.api_total = payload.get("meta", {}).get("total") if isinstance(
                payload.get("meta"), dict
            ) else len(records)

            for record in records:
                if not isinstance(record, dict):
                    continue
                shaped = self._shape_job(
                    record,
                    board_token=token,
                    company_name=company,
                )
                if shaped is not None:
                    result.jobs.append(shaped)

            result.status = "SUCCESS"
        except (GreenhouseAPIError, ValueError) as exc:
            result.status = "FAILED"
            result.error = str(exc)

        if self.request_delay_seconds:
            time.sleep(self.request_delay_seconds)

        return result

    def fetch_board_jobs(
        self,
        board_token: str,
        *,
        company_name: str | None = None,
        include_content: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Convenience method returning jobs or raising GreenhouseAPIError.

        Use fetch_board() instead when per-board diagnostics are needed.
        """
        result = self.fetch_board(
            board_token,
            company_name=company_name,
            include_content=include_content,
        )
        if result.status != "SUCCESS":
            raise GreenhouseAPIError(
                result.error or f"Failed to fetch Greenhouse board '{board_token}'."
            )
        return result.jobs

    def fetch_boards(
        self,
        boards: Mapping[str, str] | list[str] | tuple[str, ...],
        *,
        include_content: bool = True,
    ) -> list[BoardFetchResult]:
        """
        Fetch several boards sequentially.

        Mapping format: {board_token: company_display_name}.
        A list/tuple uses each token as its fallback company name.
        """
        if isinstance(boards, Mapping):
            items = list(boards.items())
        else:
            items = [(token, None) for token in boards]

        results: list[BoardFetchResult] = []
        for token, company_name in items:
            try:
                result = self.fetch_board(
                    token,
                    company_name=company_name,
                    include_content=include_content,
                )
            except ValueError as exc:
                result = BoardFetchResult(
                    board_token=str(token),
                    company_name=str(company_name or token),
                    status="FAILED",
                    error=str(exc),
                )
            results.append(result)
        return results

    def close(self) -> None:
        """Close the HTTP session if this client created it."""
        if self._owns_session:
            self.session.close()

    def __enter__(self) -> "GreenhouseClient":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


def summarize_results(results: list[BoardFetchResult]) -> dict[str, Any]:
    """Create a compact diagnostic report without persisting any jobs."""
    all_jobs = [job for result in results for job in result.jobs]
    seen: set[tuple[str, str]] = set()
    unique_jobs: list[dict[str, Any]] = []
    duplicates = 0

    for job in all_jobs:
        identity = (str(job.get("source") or ""), str(job.get("source_job_id") or ""))
        if not all(identity) or identity in seen:
            duplicates += 1
            continue
        seen.add(identity)
        unique_jobs.append(job)

    classifications = {"core": 0, "adjacent": 0, "irrelevant": 0}
    for job in unique_jobs:
        group = classify_role_title(str(job.get("title") or ""))
        classifications[group] += 1

    return {
        "boards_attempted": len(results),
        "boards_succeeded": sum(r.status == "SUCCESS" for r in results),
        "boards_failed": sum(r.status != "SUCCESS" for r in results),
        "api_reported_total": sum(r.api_total or 0 for r in results),
        "retrieved_jobs": len(all_jobs),
        "unique_jobs_by_source_identity": len(unique_jobs),
        "duplicate_records": duplicates,
        "title_classification": classifications,
        "board_results": [
            {
                "board_token": r.board_token,
                "company_name": r.company_name,
                "status": r.status,
                "http_status": r.http_status,
                "api_total": r.api_total,
                "shaped_jobs": len(r.jobs),
                "error": r.error,
            }
            for r in results
        ],
    }
