from __future__ import annotations

from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.parse import (
    parse_qs,
    quote_plus,
    unquote,
    urljoin,
    urlparse,
)
import argparse
import hashlib
import html
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests
from pydantic import BaseModel, Field
from app.discovery.linkedin_search import LinkedInSearch
from app.discovery.indeed_search import IndeedSearch
from app.discovery.browser_job_page import BrowserJobPageExtractor
from bs4 import BeautifulSoup
# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = (
    Path(__file__).resolve().parents[2]
)

SEARCH_PLAN_PATH = (
    PROJECT_ROOT
    / "data"
    / "jobs"
    / "search_plan.json"
)

RAW_JOBS_PATH = (
    PROJECT_ROOT
    / "data"
    / "jobs"
    / "raw_jobs.json"
)

EXECUTION_REPORT_PATH = (
    PROJECT_ROOT
    / "data"
    / "jobs"
    / "search_execution_report.json"
)

CACHE_PATH = (
    PROJECT_ROOT
    / "data"
    / "jobs"
    / "search_cache.json"
)

CAPABILITY_REGISTRY_PATH = (
    PROJECT_ROOT
    / "data"
    / "sources"
    / "source_capability_registry.json"
)


# ============================================================
# EXECUTION SETTINGS
# ============================================================

REQUEST_TIMEOUT = 20

MAX_RESULTS_PER_TASK = 10

REQUEST_DELAY_SECONDS = 1.0

MAX_CONCURRENT_TASKS = 5

USER_AGENT = (
    "JobPilot/1.0 "
    "(job discovery; respectful automated retrieval)"
)

SEARCH_ENGINE_URL = (
    "https://www.google.com/search?q={query}"
)

SEARCH_ENGINE_FALLBACK_URL = (
    "https://html.duckduckgo.com/html/?q={query}"
)


# ============================================================
# MODELS
# ============================================================

class RawJob(BaseModel):
    """
    A job discovered by the Python search executor.

    Provider-specific information is preserved inside raw_data.
    """

    raw_job_id: str

    title: str
    company: str

    location: str | None = None
    country: str | None = None
    remote_type: str | None = None

    source: str
    source_domain: str | None = None

    source_url: str | None = None
    apply_url: str | None = None

    description: str | None = None
    posted_date: str | None = None

    search_task_id: str

    discovered_at: str = Field(
        default_factory=lambda:
        datetime.now(timezone.utc).isoformat()
    )

    raw_data: dict[str, Any] = Field(
        default_factory=dict
    )


class SearchResult(BaseModel):
    jobs: list[RawJob] = Field(
        default_factory=list
    )


# ============================================================
# EXECUTOR
# ============================================================

class SearchExecutor:

    def __init__(self):

        self.session = requests.Session()

        self.linkedin_search = LinkedInSearch()
        self.indeed_search = IndeedSearch()

        self.browser_job_page_extractor = (
            BrowserJobPageExtractor()
        )

        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": (
                    "text/html,application/xhtml+xml,"
                    "application/xml;q=0.9,*/*;q=0.8"
                ),
                "Accept-Language": (
                    "en-US,en;q=0.9"
                ),
            }
        )

        self.capability_registry = (
            self.load_capability_registry()
        )

        self.cache = self.load_cache()

    # ========================================================
    # FILE LOADING
    # ========================================================

    @staticmethod
    def load_json(path: Path):

        if not path.exists():
            return {}

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    def load_capability_registry(self) -> dict:

        return self.load_json(
            CAPABILITY_REGISTRY_PATH
        )

    def load_cache(self) -> dict:

        cache = self.load_json(
            CACHE_PATH
        )

        if not isinstance(cache, dict):
            return {}

        return cache

    def save_cache(self):

        CACHE_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with open(
            CACHE_PATH,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                self.cache,
                file,
                indent=2,
                ensure_ascii=False,
            )

    # ========================================================
    # SEARCH PLAN
    # ========================================================

    def load_search_plan(self) -> dict:

        return self.load_json(
            SEARCH_PLAN_PATH
        )

    # ========================================================
    # CAPABILITY LOOKUP
    # ========================================================

    def get_capability(
        self,
        source_name: str,
    ) -> dict:

        capabilities = (
            self.capability_registry.get(
                "capabilities",
                []
            )
        )

        for capability in capabilities:

            if (
                capability.get("source_name")
                == source_name
            ):
                return capability

        return {}
    # ========================================================
    # BROWSER JOB PAGE ADAPTER
    # ========================================================

    def browser_page_to_raw_job(
        self,
        html_content: str,
        source_url: str,
        search_task_id: str,
        task: dict[str, Any] | None = None,
    ) -> RawJob:

        browser_job = (
            self.browser_job_page_extractor.extract(
                html=html_content,
                source_url=source_url,
            )
        )

        raw_data = dict(
            browser_job.raw_data
        )

        if task:
            raw_data.update(
                {
                    "query": task.get("query"),
                    "search_variant": task.get(
                        "search_variant"
                    ),
                    "canonical_role": task.get(
                        "canonical_role"
                    ),
                    "strategy": task.get(
                        "strategy"
                    ),
                    "source_category": task.get(
                        "source_category"
                    ),
                    "location_scope": task.get(
                        "location_scope"
                    ),
                }
            )

        return RawJob(
            raw_job_id=(
                f"{browser_job.source.lower()}"
                f"-{browser_job.source_job_id}"
            ),
            title=browser_job.title,
            company=browser_job.company,
            location=browser_job.location,
            country=browser_job.country,
            remote_type=browser_job.remote_type,
            source=browser_job.source,
            source_domain=browser_job.source_domain,
            source_url=browser_job.source_url,
            apply_url=(
                browser_job.apply_url
                or browser_job.source_url
            ),
            description=browser_job.description,
            posted_date=browser_job.posted_date,
            search_task_id=search_task_id,
            raw_data=raw_data,
        )
    # ========================================================
    # REQUEST HELPERS
    # ========================================================

    def fetch(
        self,
        url: str,
    ) -> requests.Response | None:

        try:

            response = self.session.get(
                url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )

            return response

        except requests.RequestException:

            return None

    # ========================================================
    # DOMAIN HELPERS
    # ========================================================

    @staticmethod
    def normalise_domain(
        domain: str | None,
    ) -> str | None:

        if not domain:
            return None

        value = str(domain).strip().lower()

        value = re.sub(
            r"^https?://",
            "",
            value,
        )

        value = value.split("/")[0]

        return value or None

    @staticmethod
    def url_matches_domain(
        url: str,
        domain: str | None,
    ) -> bool:

        if not domain:
            return True

        try:

            hostname = (
                urlparse(url)
                .hostname
                or ""
            ).lower()

        except Exception:

            return False

        domain = domain.lower().strip()

        return (
            hostname == domain
            or hostname.endswith(
                "." + domain
            )
        )

    # ========================================================
    # QUERY HELPERS
    # ========================================================

    @staticmethod
    def clean_query(
        query: str,
    ) -> str:

        query = str(
            query or ""
        ).strip()

        query = re.sub(
            r"\s+",
            " ",
            query,
        )

        return query

    @staticmethod
    def add_site_filter(
        query: str,
        domain: str | None,
    ) -> str:

        if not domain:
            return query

        if domain.startswith(
            "varies"
        ):
            return query

        if "site:" in query.lower():
            return query

        return (
            f"{query} site:{domain}"
        )

    # ========================================================
    # SOURCE URL FILTERING
    # ========================================================

    @staticmethod
    def is_job_like_url(
        url: str,
    ) -> bool:

        value = url.lower()

        job_terms = [
            "/jobs/",
            "/job/",
            "/jobs?",
            "/job?",
            "/vacancy/",
            "/vacancies/",
            "/position/",
            "/positions/",
            "/careers/",
            "/career/",
            "/apply/",
            "/view/",
            "jobid=",
            "job_id=",
            "job-id=",
        ]

        return any(
            term in value
            for term in job_terms
        )

    @staticmethod
    def looks_like_generic_page(
        url: str,
    ) -> bool:

        value = url.lower()

        blocked_terms = [
            "/about",
            "/contact",
            "/privacy",
            "/terms",
            "/login",
            "/signin",
            "/signup",
            "/register",
            "/blog",
            "/news",
        ]

        return any(
            term in value
            for term in blocked_terms
        )

    # ========================================================
    # GOOGLE RESULT EXTRACTION
    # ========================================================

    @staticmethod
    def extract_google_links(
        page: str,
    ) -> list[dict]:

        results = []
        seen_urls = set()

        soup = BeautifulSoup(
            page,
            "html.parser",
        )

        # Current Google result pages commonly expose
        # the result title inside an <h3> whose parent
        # <a> contains the actual destination URL.
        for heading in soup.find_all("h3"):

            title = heading.get_text(
                " ",
                strip=True,
            )

            if not title:
                continue

            anchor = heading.find_parent(
                "a",
                href=True,
            )

            if anchor is None:
                continue

            href = anchor.get(
                "href",
                "",
            ).strip()

            if not href:
                continue

            target = href

            parsed = urlparse(
                href
            )

            # Handle Google's redirect-style URLs.
            if parsed.path == "/url":

                params = parse_qs(
                    parsed.query
                )

                target_values = (
                    params.get("q")
                    or params.get("url")
                )

                if target_values:
                    target = unquote(
                        target_values[0]
                    )

            # Ignore relative Google links.
            if not target.startswith(
                "http://"
            ) and not target.startswith(
                "https://"
            ):
                continue

            # Ignore Google-owned URLs.
            hostname = (
                urlparse(target).hostname
                or ""
            ).lower()

            if (
                hostname == "google.com"
                or hostname.endswith(
                    ".google.com"
                )
            ):
                continue

            if target in seen_urls:
                continue

            seen_urls.add(target)

            results.append(
                {
                    "title": title,
                    "url": target,
                }
            )

            if len(results) >= MAX_RESULTS_PER_TASK:
                break

        return results
    # ========================================================
    # DUCKDUCKGO RESULT EXTRACTION
    # ========================================================

    @staticmethod
    def extract_duckduckgo_links(
        page: str,
    ) -> list[dict]:

        results = []
        seen_urls = set()

        soup = BeautifulSoup(
            page,
            "html.parser",
        )

        # DuckDuckGo HTML results commonly use
        # the result__a class for result links.
        anchors = soup.select(
            "a.result__a"
        )

        for anchor in anchors:

            href = anchor.get(
                "href",
                "",
            ).strip()

            title = anchor.get_text(
                " ",
                strip=True,
            )

            if not href or not title:
                continue

            target = html.unescape(
                href
            )

            if not target.startswith(
                "http://"
            ) and not target.startswith(
                "https://"
            ):
                continue

            if target in seen_urls:
                continue

            seen_urls.add(target)

            results.append(
                {
                    "title": title,
                    "url": target,
                }
            )

            if len(results) >= MAX_RESULTS_PER_TASK:
                break

        return results
    # ========================================================
    # SEARCH ENGINE DISCOVERY
    # ========================================================

    def search_engine(
        self,
        query: str,
        domain: str | None = None,
    ) -> list[dict]:

        query = self.clean_query(
            query
        )

        query = self.add_site_filter(
            query,
            domain,
        )

        google_url = (
            SEARCH_ENGINE_URL.format(
                query=quote_plus(query)
            )
        )

        response = self.fetch(
            google_url
        )

        if (
            response is not None
            and response.status_code == 200
        ):

            results = (
                self.extract_google_links(
                    response.text
                )
            )

            if results:
                return results

        # Fallback search engine.
        duck_url = (
            SEARCH_ENGINE_FALLBACK_URL.format(
                query=quote_plus(query)
            )
        )

        response = self.fetch(
            duck_url
        )

        if (
            response is not None
            and response.status_code == 200
        ):

            return (
                self.extract_duckduckgo_links(
                    response.text
                )
            )

        return []

    # ========================================================
    # JOB TITLE / COMPANY EXTRACTION
    # ========================================================

    @staticmethod
    def clean_result_title(
        title: str,
    ) -> str:

        title = html.unescape(
            title or ""
        )

        title = re.sub(
            r"\s+",
            " ",
            title,
        ).strip()

        # Remove common search-engine suffixes.
        title = re.sub(
            r"\s*[-|]\s*(LinkedIn|Indeed|Dice|"
            r"Glassdoor|Naukri|Bayt|GulfTalent|"
            r"eFinancialCareers|SEEK).*$",
            "",
            title,
            flags=re.IGNORECASE,
        )

        return title.strip()

    @staticmethod
    def extract_company_from_title(
        title: str,
    ) -> str:

        separators = [
            " - ",
            " | ",
            " – ",
            " — ",
        ]

        for separator in separators:

            if separator in title:

                parts = [
                    part.strip()
                    for part in title.split(
                        separator
                    )
                    if part.strip()
                ]

                if len(parts) >= 2:

                    return parts[-1]

        return "Unknown"

    @staticmethod
    def looks_like_job_title(
        title: str,
    ) -> bool:

        value = title.lower()

        job_terms = [
            "analyst",
            "consultant",
            "manager",
            "specialist",
            "engineer",
            "developer",
            "architect",
            "lead",
            "director",
            "administrator",
            "coordinator",
            "associate",
            "product owner",
            "scrum master",
        ]

        return any(
            term in value
            for term in job_terms
        )

    # ========================================================
    # RESULT TO RAW JOB
    # ========================================================

    def build_raw_job(
        self,
        result: dict,
        task: dict,
    ) -> RawJob | None:

        url = result.get(
            "url"
        )

        title = self.clean_result_title(
            result.get(
                "title",
                ""
            )
        )

        if not url or not title:
            return None

        source_domain = (
            task.get(
                "source_domain"
            )
        )

        if source_domain:

            source_domain = (
                self.normalise_domain(
                    source_domain
                )
            )

            if not self.url_matches_domain(
                url,
                source_domain,
            ):

                return None

        if self.looks_like_generic_page(
            url
        ):

            return None

        if not self.is_job_like_url(
            url
        ):

            # Search-engine results can sometimes
            # point directly to a job page without
            # an obvious /job/ path. Keep them only
            # when the title looks job-related.
            if not self.looks_like_job_title(
                title
            ):
                return None

        company = (
            self.extract_company_from_title(
                title
            )
        )

        raw_job_id = (
            self.generate_raw_job_id(
                url,
                task,
            )
        )

        return RawJob(
            raw_job_id=raw_job_id,

            title=title,

            company=company,

            location=None,

            country=None,

            remote_type=None,

            source=task.get(
                "source_name",
                "",
            ),

            source_domain=source_domain,

            source_url=url,

            apply_url=url,

            description=None,

            posted_date=None,

            search_task_id=task.get(
                "task_id",
                "",
            ),

            raw_data={
                "search_result_title": (
                    result.get(
                        "title"
                    )
                ),
                "search_result_url": url,
                "query": task.get(
                    "query"
                ),
                "strategy": task.get(
                    "strategy"
                ),
                "source_category": task.get(
                    "source_category"
                ),
            },
        )

    # ========================================================
    # ID GENERATION
    # ========================================================

    @staticmethod
    def generate_raw_job_id(
        url: str,
        task: dict,
    ) -> str:

        value = (
            f"{task.get('source_name', '')}|"
            f"{url}"
        )

        digest = hashlib.sha256(
            value.encode(
                "utf-8"
            )
        ).hexdigest()[:16]

        return (
            f"raw-{digest}"
        )

    # ========================================================
    # RESULT DEDUPLICATION
    # ========================================================

    @staticmethod
    def deduplicate_jobs(
        jobs: list[RawJob],
    ) -> list[RawJob]:

        unique = []

        seen = set()

        for job in jobs:

            key = (
                job.source.lower().strip(),
                (
                    job.source_url
                    or job.apply_url
                    or job.raw_job_id
                ).lower().strip(),
            )

            if key in seen:
                continue

            seen.add(
                key
            )

            unique.append(
                job
            )

        return unique

    # ========================================================
    # TASK CACHE KEY
    # ========================================================

    @staticmethod
    def task_cache_key(
        task: dict,
    ) -> str:

        relevant = {
            "task_id": task.get(
                "task_id"
            ),
            "source": task.get(
                "source_name"
            ),
            "query": task.get(
                "query"
            ),
            "strategy": task.get(
                "strategy"
            ),
            "location": task.get(
                "location_scope"
            ),
        }

        serialized = json.dumps(
            relevant,
            sort_keys=True,
        )

        return hashlib.sha256(
            serialized.encode(
                "utf-8"
            )
        ).hexdigest()

    # ========================================================
    # CACHE LOOKUP
    # ========================================================

    def get_cached_result(
        self,
        task: dict,
    ) -> SearchResult | None:

        key = self.task_cache_key(
            task
        )

        cached = self.cache.get(
            key
        )

        if not cached:
            return None

        try:

            cached_at = datetime.fromisoformat(
                cached["cached_at"]
            )

            if (
                datetime.now(timezone.utc)
                - cached_at
                > timedelta(hours=CACHE_TTL_HOURS)
            ):
                return None

            return SearchResult.model_validate(
                cached["result"]
            )

        except Exception:

            return None
    def cache_result(
        self,
        task: dict,
        result: SearchResult,
    ):

        key = self.task_cache_key(
            task
        )

        self.cache[key] = {
            "cached_at": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
            "task": {
                "task_id": task.get(
                    "task_id"
                ),
                "source_name": task.get(
                    "source_name"
                ),
                "query": task.get(
                    "query"
                ),
                "strategy": task.get(
                    "strategy"
                ),
            },
            "result": result.model_dump(),
        }

    # ========================================================
    # DIRECT SEARCH
    # ========================================================


    def execute_direct_search(
        self,
        task: dict,
    ) -> SearchResult:
        
        if (
            task.get("source_name")
            == "LinkedIn Jobs"
        ):
            return self.execute_linkedin_search(
                task
            )
        
        if (
            task.get("source_name")
            == "Indeed"
        ):
            return self.execute_indeed_search(
                task
            )
        query = self.clean_query(
            task.get(
                "query",
                ""
            )
        )

        domain = self.normalise_domain(
            task.get(
                "source_domain"
            )
        )

        # Direct-capable sources are still searched
        # through the public search interface rather
        # than through an assumed private API.
        results = self.search_engine(
            query=query,
            domain=domain,
        )

        jobs = []

        for result in results:

            if len(jobs) >= MAX_RESULTS_PER_TASK:
                break

            job = self.build_raw_job(
                result,
                task,
            )

            if job:
                jobs.append(
                    job
                )

        return SearchResult(
            jobs=self.deduplicate_jobs(
                jobs
            )
        )

    # ========================================================
    # LINKEDIN DIRECT SEARCH
    # ========================================================

    def execute_linkedin_search(
        self,
        task: dict,
    ) -> SearchResult:

        query = self.clean_query(
            task.get(
                "query",
                "",
            )
        )

        linkedin_jobs = (
            self.linkedin_search.search(
                query=query,
                max_results=MAX_RESULTS_PER_TASK,
            )
        )

        jobs = []

        for linkedin_job in linkedin_jobs:

            raw_job = RawJob(
                raw_job_id=(
                    f"linkedin-"
                    f"{linkedin_job.source_job_id}"
                ),

                title=linkedin_job.title,

                company=linkedin_job.company,

                location=linkedin_job.location,

                country=None,

                remote_type=None,

                source="LinkedIn Jobs",

                source_domain="linkedin.com",

                source_url=linkedin_job.source_url,

                apply_url=linkedin_job.source_url,

                description=None,

                posted_date=linkedin_job.posted_date,

                search_task_id=task.get(
                    "task_id",
                    "",
                ),

                raw_data={
                    "source_job_id": (
                        linkedin_job.source_job_id
                    ),
                    "query": task.get(
                        "query"
                    ),
                    "search_variant": task.get(
                        "search_variant"
                    ),
                    "canonical_role": task.get(
                        "canonical_role"
                    ),
                    "strategy": task.get(
                        "strategy"
                    ),
                    "source_category": task.get(
                        "source_category"
                    ),
                    "location_scope": task.get(
                        "location_scope"
                    ),
                },
            )

            jobs.append(
                raw_job
            )

        return SearchResult(
            jobs=self.deduplicate_jobs(
                jobs
            )
        )
    def execute_indeed_search(
        self,
        task: dict[str, Any],
    ) -> list[RawJob]:

        query = (
            task.get("search_variant")
            or task.get("query")
            or task.get("canonical_role")
            or ""
        ).strip()

        if not query:
            return []

        country_domain = (
            task.get("country_domain")
            or "au.indeed.com"
        )

        max_results = int(
            task.get(
                "max_results",
                10,
            )
        )

        indeed_jobs = self.indeed_search.search(
            query=query,
            country_domain=country_domain,
            max_results=max_results,
        )

        raw_jobs: list[RawJob] = []

        for indeed_job in indeed_jobs:

            raw_jobs.append(
                RawJob(
                    raw_job_id=(
                        f"indeed-"
                        f"{indeed_job.source_job_id}"
                    ),
                    title=indeed_job.title,
                    company=indeed_job.company,
                    location=indeed_job.location,
                    country=None,
                    remote_type=None,
                    source="Indeed",
                    source_domain="indeed.com",
                    source_url=indeed_job.source_url,
                    apply_url=indeed_job.source_url,
                    description=None,
                    posted_date=indeed_job.posted_date,
                    search_task_id=(
                        task.get("task_id")
                        or ""
                    ),
                    raw_data={
                        "source_job_id": (
                            indeed_job.source_job_id
                        ),
                        "query": task.get("query"),
                        "search_variant": (
                            task.get("search_variant")
                        ),
                        "canonical_role": (
                            task.get("canonical_role")
                        ),
                        "strategy": task.get(
                            "strategy"
                        ),
                        "source_category": task.get(
                            "source_category"
                        ),
                        "location_scope": task.get(
                            "location_scope"
                        ),
                    },
                )
            )

        return raw_jobs

    # ========================================================
    # SEARCH ENGINE DISCOVERY
    # ========================================================

    def execute_search_engine_discovery(
        self,
        task: dict,
    ) -> SearchResult:
        if (
            task.get("source_name")
            == "Indeed"
        ):
            return SearchResult(
                jobs=self.execute_indeed_search(
                    task
                )
            )
        query = self.clean_query(
            task.get(
                "query",
                ""
            )
        )

        domain = self.normalise_domain(
            task.get(
                "source_domain"
            )
        )

        results = self.search_engine(
            query=query,
            domain=domain,
        )

        jobs = []

        for result in results:

            if len(jobs) >= MAX_RESULTS_PER_TASK:
                break

            job = self.build_raw_job(
                result,
                task,
            )

            if job:
                jobs.append(
                    job
                )

        return SearchResult(
            jobs=self.deduplicate_jobs(
                jobs
            )
        )

    # ========================================================
    # DYNAMIC DOMAIN DISCOVERY
    # ========================================================

    def execute_dynamic_domain_discovery(
        self,
        task: dict,
    ) -> SearchResult:

        query = self.clean_query(
            task.get(
                "query",
                ""
            )
        )

        # Dynamic employer sources intentionally
        # have no fixed domain.
        results = self.search_engine(
            query=query,
            domain=None,
        )

        jobs = []

        for result in results:

            if len(jobs) >= MAX_RESULTS_PER_TASK:
                break

            job = self.build_raw_job(
                result,
                task,
            )

            if job:
                jobs.append(
                    job
                )

        return SearchResult(
            jobs=self.deduplicate_jobs(
                jobs
            )
        )

    # ========================================================
    # TASK EXECUTION
    # ========================================================

    def execute_task(
        self,
        task: dict,
    ) -> SearchResult:

        cached = self.get_cached_result(
            task
        )

        if cached is not None:

            return cached

        strategy = task.get(
            "strategy"
        )

        if strategy == "DIRECT_SEARCH":

            result = (
                self.execute_direct_search(
                    task
                )
            )

        elif strategy == "SEARCH_ENGINE_DISCOVERY":

            result = (
                self.execute_search_engine_discovery(
                    task
                )
            )

        elif strategy == "DIRECT_SOURCE_DISCOVERY":

            result = (
                self.execute_direct_search(
                    task
                )
            )

        elif strategy == "DYNAMIC_DOMAIN_DISCOVERY":

            result = (
                self.execute_dynamic_domain_discovery(
                    task
                )
            )

        else:

            raise ValueError(
                f"Unsupported search strategy: "
                f"{strategy}"
            )

        self.cache_result(
            task,
            result,
        )

        return result

    # ========================================================
    # EXECUTE PLAN
    # ========================================================

    def execute_plan(
        self,
        limit: int | None = None,
        priority: str | None = None,
    ) -> tuple[list[RawJob], dict]:

        plan = self.load_search_plan()

        tasks = plan.get(
            "tasks",
            []
        )

        if priority:

            priority = priority.upper()

            tasks = [
                task
                for task in tasks
                if str(
                    task.get(
                        "priority",
                        ""
                    )
                ).upper()
                == priority
            ]

        if limit is not None:

            tasks = tasks[:limit]

        print()
        print("=" * 60)
        print(
            "PYTHON SEARCH EXECUTOR"
        )
        print("=" * 60)

        print(
            f"Tasks selected: "
            f"{len(tasks)}"
        )

        print(
            f"Concurrent workers: "
            f"{MAX_CONCURRENT_TASKS}"
        )

        jobs = []

        execution_started = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        successful_tasks = 0
        failed_tasks = 0
        cached_tasks = 0

        task_results = []

        def run_task(
            task: dict[str, Any],
        ) -> dict[str, Any]:

            task_id = task.get(
                "task_id",
                "UNKNOWN",
            )

            try:

                cache_before = (
                    self.get_cached_result(
                        task
                    )
                    is not None
                )

                result = self.execute_task(
                    task
                )

                return {
                    "task": task,
                    "task_id": task_id,
                    "result": result,
                    "cache_before": cache_before,
                    "error": None,
                }

            except Exception as exc:

                return {
                    "task": task,
                    "task_id": task_id,
                    "result": None,
                    "cache_before": False,
                    "error": str(exc),
                }

        with ThreadPoolExecutor(
            max_workers=MAX_CONCURRENT_TASKS
        ) as executor:

            future_to_index = {
                executor.submit(
                    run_task,
                    task,
                ): index
                for index, task in enumerate(
                    tasks,
                    start=1,
                )
            }

            for future in as_completed(
                future_to_index
            ):

                index = future_to_index[
                    future
                ]

                outcome = future.result()

                task = outcome["task"]
                task_id = outcome["task_id"]
                result = outcome["result"]
                cache_before = outcome[
                    "cache_before"
                ]
                error = outcome["error"]

                print(
                    f"[{index}/{len(tasks)}] "
                    f"{task_id} | "
                    f"{task.get('search_variant')} | "
                    f"{task.get('source_name')} | "
                    f"{task.get('strategy')}"
                )

                if error is not None:

                    failed_tasks += 1

                    task_results.append(
                        {
                            "task_id": task_id,
                            "status": "FAILED",
                            "jobs_found": 0,
                            "error": error,
                        }
                    )

                    print(
                        f"    ERROR: {error}"
                    )

                    continue

                if cache_before:

                    cached_tasks += 1

                jobs.extend(
                    result.jobs
                )

                successful_tasks += 1

                task_results.append(
                    {
                        "task_id": task_id,
                        "status": (
                            "CACHED"
                            if cache_before
                            else "SUCCESS"
                        ),
                        "jobs_found": len(
                            result.jobs
                        ),
                    }
                )

                print(
                    f"    Jobs found: "
                    f"{len(result.jobs)}"
                )

                if cache_before:

                    print(
                        "    Source: cache"
                    )

                else:

                    print(
                        "    Source: web"
                    )

        jobs = self.deduplicate_jobs(
            jobs
        )

        self.save_cache()

        execution_finished = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        report = {

            "executed_at":
                execution_finished,

            "started_at":
                execution_started,

            "finished_at":
                execution_finished,

            "executor":
                "python",

            "search_plan_path":
                str(
                    SEARCH_PLAN_PATH
                ),

            "tasks_available":
                len(
                    plan.get(
                        "tasks",
                        []
                    )
                ),

            "tasks_selected":
                len(
                    tasks
                ),

            "successful_tasks":
                successful_tasks,

            "failed_tasks":
                failed_tasks,

            "cached_tasks":
                cached_tasks,

            "raw_jobs_found":
                len(
                    jobs
                ),

            "task_results":
                task_results,
        }

        return jobs, report
    # ========================================================
    # SAVE RAW JOBS
    # ========================================================

    @staticmethod
    def save_jobs(
        jobs: list[RawJob],
    ):

        RAW_JOBS_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = {

            "generated_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "executor":
                "python",

            "total_jobs":
                len(
                    jobs
                ),

            "jobs": [
                job.model_dump()
                for job in jobs
            ],
        }

        with open(
            RAW_JOBS_PATH,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                payload,
                file,
                indent=2,
                ensure_ascii=False,
            )

        print()
        print(
            "Raw jobs saved to:"
        )

        print(
            RAW_JOBS_PATH
        )

    # ========================================================
    # SAVE REPORT
    # ========================================================

    @staticmethod
    def save_report(
        report: dict,
    ):

        EXECUTION_REPORT_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with open(
            EXECUTION_REPORT_PATH,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                report,
                file,
                indent=2,
                ensure_ascii=False,
            )

        print()
        print(
            "Execution report saved to:"
        )

        print(
            EXECUTION_REPORT_PATH
        )

    # ========================================================
    # RUN
    # ========================================================

    def run(
        self,
        limit: int | None = 5,
        priority: str | None = None,
    ):

        jobs, report = (
            self.execute_plan(
                limit=limit,
                priority=priority,
            )
        )

        self.save_jobs(
            jobs
        )

        self.save_report(
            report
        )

        print()
        print("=" * 60)
        print(
            "SEARCH EXECUTION COMPLETE"
        )
        print("=" * 60)

        print(
            f"Executor: Python"
        )

        print(
            f"Tasks executed: "
            f"{report['tasks_selected']}"
        )

        print(
            f"Successful tasks: "
            f"{report['successful_tasks']}"
        )

        print(
            f"Failed tasks: "
            f"{report['failed_tasks']}"
        )

        print(
            f"Cached tasks: "
            f"{report['cached_tasks']}"
        )

        print(
            f"Raw jobs found: "
            f"{report['raw_jobs_found']}"
        )

        return jobs


# ============================================================
# CLI
# ============================================================

def parse_args():

    parser = argparse.ArgumentParser(
        description=(
            "Execute JobPilot search tasks "
            "using Python HTTP/search-engine discovery."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help=(
            "Maximum number of search tasks "
            "to execute. Default: 5."
        ),
    )

    parser.add_argument(
        "--priority",
        choices=[
            "HIGH",
            "MEDIUM",
            "LOW",
        ],
        default=None,
        help=(
            "Execute only tasks of the "
            "specified priority."
        ),
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help=(
            "Execute all tasks in the "
            "search plan."
        ),
    )

    return parser.parse_args()


def main():

    args = parse_args()

    limit = (
        None
        if args.all
        else args.limit
    )

    executor = SearchExecutor()

    executor.run(
        limit=limit,
        priority=args.priority,
    )


if __name__ == "__main__":

    main()