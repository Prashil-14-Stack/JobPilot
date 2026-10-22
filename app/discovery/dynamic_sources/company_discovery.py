"""Extract company and supported ATS URLs from existing JobPilot search/job results."""
from dataclasses import dataclass, asdict
from typing import Any, Iterable
from urllib.parse import urlparse, urlunparse
import re

@dataclass
class DiscoveredCompany:
    company_name: str
    careers_url: str
    discovered_from_url: str = ""
    job_url: str = ""
    discovery_method: str = "job_result"
    ats_platform: str = "unknown"
    board_token: str = ""
    validation_status: str = "pending"

def clean_url(value: str) -> str:
    value = (value or "").strip()
    if not value.startswith(("https://", "http://")):
        return ""
    p = urlparse(value)
    if not p.netloc:
        return ""
    return urlunparse((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), "", "", ""))

def first_value(item: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""

class CompanyDiscovery:
    COMPANY_KEYS = ("company_name", "company", "employer", "organization", "hiring_company")
    JOB_URL_KEYS = ("apply_url", "job_url", "source_url", "url", "absolute_url")
    CAREERS_KEYS = ("careers_url", "company_careers_url", "company_url", "employer_url")

    def discover_from_jobs(self, jobs: Iterable[dict[str, Any]]) -> list[DiscoveredCompany]:
        found: dict[tuple[str, str], DiscoveredCompany] = {}
        for job in jobs:
            if not isinstance(job, dict):
                continue
            company = first_value(job, self.COMPANY_KEYS)
            job_url = clean_url(first_value(job, self.JOB_URL_KEYS))
            careers_url = clean_url(first_value(job, self.CAREERS_KEYS))
            if not company and job_url:
                host = urlparse(job_url).hostname or ""
                company = host.removeprefix("www.").split(".")[0].replace("-", " ").title()
            if not company:
                continue
            if not careers_url:
                careers_url = self._infer_careers_url(job_url)
            # Do not register a company-name-only record: it must have a URL.
            if not careers_url:
                continue
            name = re.sub(r"\s+", " ", company).strip()
            key = (name.casefold(), careers_url.casefold())
            found.setdefault(key, DiscoveredCompany(
                company_name=name, careers_url=careers_url,
                discovered_from_url=job_url, job_url=job_url
            ))
        return list(found.values())

    @staticmethod
    def _infer_careers_url(job_url: str) -> str:
        if not job_url:
            return ""
        p = urlparse(job_url)
        host = (p.hostname or "").lower()
        parts = [x for x in p.path.strip("/").split("/") if x]
        if host in {"boards.greenhouse.io", "job-boards.greenhouse.io"} and parts:
            return f"https://boards.greenhouse.io/{parts[0]}" if parts[0] != "embed" else ""
        if host in {"jobs.lever.co", "jobs.eu.lever.co"} and parts:
            return f"https://{host}/{parts[0]}"
        if host == "jobs.ashbyhq.com" and parts:
            return f"https://jobs.ashbyhq.com/{parts[0]}"
        return ""

def to_dict(company: DiscoveredCompany) -> dict[str, Any]:
    return asdict(company)
