from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from typing import Any
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup


@dataclass
class BrowserJobPage:
    source_job_id: str
    title: str
    company: str
    location: str | None
    country: str | None
    remote_type: str | None
    source: str
    source_domain: str
    source_url: str
    apply_url: str | None
    description: str | None
    posted_date: str | None
    raw_data: dict[str, Any]


class BrowserJobPageExtractor:
    """Extract a normalized job record from browser HTML."""

    def extract(
        self,
        html: str,
        source_url: str,
    ) -> BrowserJobPage:

        if not html or not html.strip():
            raise ValueError(
                "HTML content is empty."
            )

        source_domain = (
            urlparse(source_url)
            .netloc
            .lower()
        )

        source = self._source_name(
            source_domain
        )

        source_job_id = (
            self._job_id_from_url(
                source_url
            )
        )

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        json_ld = (
            self._extract_jobposting_json_ld(
                soup,
                html,
            )
        )

        title = self._clean_text(
            json_ld.get("title")
        )

        company = self._clean_text(
            self._nested_value(
                json_ld,
                "hiringOrganization",
                "name",
            )
        )

        location = (
            self._extract_location(
                json_ld
            )
        )

        country = (
            self._extract_country(
                json_ld
            )
        )

        description = (
            self._html_to_text(
                json_ld.get("description")
            )
        )

        posted_date = self._clean_text(
            json_ld.get("datePosted")
        )

        embedded = (
            self._extract_indeed_embedded_fields(
                html
            )
        )

        source_job_id = (
            source_job_id
            or embedded.get("jobKey")
        )

        title = (
            title
            or self._clean_text(
                embedded.get("jobTitle")
            )
        )

        company = (
            company
            or self._clean_text(
                embedded.get("companyName")
            )
        )

        location = (
            location
            or self._clean_text(
                embedded.get("jobLocation")
            )
        )

        posted_date = (
            posted_date
            or embedded.get("datePosted")
        )

        if not source_job_id:
            raise ValueError(
                "Could not determine a stable "
                "source job ID."
            )

        if not title:
            raise ValueError(
                "Could not determine job title."
            )

        if not company:
            raise ValueError(
                "Could not determine company."
            )

        remote_type = (
            self._infer_remote_type(
                location,
                description,
            )
        )

        return BrowserJobPage(
            source_job_id=str(
                source_job_id
            ),
            title=title,
            company=company,
            location=location,
            country=country,
            remote_type=remote_type,
            source=source,
            source_domain=source_domain,
            source_url=source_url,
            apply_url=None,
            description=description,
            posted_date=posted_date,
            raw_data={
                "extraction_method":
                    "browser_html",
                "json_ld_found":
                    bool(json_ld),
                "embedded_fields_found":
                    bool(embedded),
                "source_job_id":
                    str(source_job_id),
            },
        )

    @staticmethod
    def _source_name(
        source_domain: str,
    ) -> str:

        if "indeed." in source_domain:
            return "Indeed"

        return source_domain

    @staticmethod
    def _job_id_from_url(
        source_url: str,
    ) -> str | None:

        query = parse_qs(
            urlparse(source_url).query
        )

        for key in (
            "jk",
            "job_id",
            "jobId",
        ):

            value = query.get(key)

            if value and value[0]:
                return value[0]

        return None

    @staticmethod
    def _nested_value(
        data: dict[str, Any],
        *keys: str,
    ) -> Any:

        current: Any = data

        for key in keys:

            if not isinstance(
                current,
                dict,
            ):
                return None

            current = current.get(key)

        return current

    @classmethod
    def _extract_jobposting_json_ld(
        cls,
        soup: BeautifulSoup,
        html: str,
    ) -> dict[str, Any]:

        for script in soup.find_all(
            "script",
            attrs={
                "type":
                    "application/ld+json"
            },
        ):

            raw = (
                script.string
                or script.get_text()
            )

            if not raw:
                continue

            raw = raw.strip()

            try:
                payload = json.loads(raw)

            except json.JSONDecodeError:

                repaired = (
                    raw.replace(
                        "\\:",
                        ":",
                    )
                )

                try:
                    payload = json.loads(
                        repaired
                    )

                except json.JSONDecodeError:
                    continue

            candidates = (
                payload
                if isinstance(
                    payload,
                    list,
                )
                else [payload]
            )

            for item in candidates:

                if (
                    isinstance(
                        item,
                        dict,
                    )
                    and item.get("@type")
                    == "JobPosting"
                ):
                    return item

        marker = (
            r'{"@context":"http:\u002F\u002Fschema.org",'
            r'"@type":"JobPosting"'
        )

        start = html.find(marker)

        if start != -1:

            raw = html[start:]

            raw = raw.replace(
                "\\:",
                ":",
            )

            try:

                payload, _ = (
                    json.JSONDecoder()
                    .raw_decode(raw)
                )

                if (
                    isinstance(
                        payload,
                        dict,
                    )
                    and payload.get(
                        "@type"
                    )
                    == "JobPosting"
                ):
                    return payload

            except json.JSONDecodeError:
                pass

        return {}

    @staticmethod
    def _extract_indeed_embedded_fields(
        html: str,
    ) -> dict[str, str]:

        fields: dict[str, str] = {}

        patterns = {
            "jobKey":
                r'"jobKey"\s*:\s*"([^"]+)"',

            "jobTitle":
                r'"jobTitle"\s*:\s*"([^"]+)"',

            "jobLocation":
                r'"jobLocation"\s*:\s*"([^"]+)"',

            "companyName":
                r'"companyName"\s*:\s*"([^"]+)"',

            "datePosted":
                r'"datePosted"\s*:\s*"([^"]+)"',
        }

        for key, pattern in patterns.items():

            match = re.search(
                pattern,
                html,
            )

            if match:

                fields[key] = (
                    unescape(
                        match.group(1)
                    )
                )

        return fields

    @staticmethod
    def _extract_location(
        job_posting: dict[str, Any],
    ) -> str | None:

        location = (
            job_posting.get(
                "jobLocation"
            )
        )

        if not isinstance(
            location,
            dict,
        ):
            return None

        address = location.get(
            "address"
        )

        if not isinstance(
            address,
            dict,
        ):
            return None

        parts = [
            address.get(
                "addressLocality"
            ),
            address.get(
                "addressRegion"
            ),
        ]

        return ", ".join(
            str(part)
            for part in parts
            if part
        )

    @staticmethod
    def _extract_country(
        job_posting: dict[str, Any],
    ) -> str | None:

        location = (
            job_posting.get(
                "jobLocation"
            )
        )

        if not isinstance(
            location,
            dict,
        ):
            return None

        address = location.get(
            "address"
        )

        if not isinstance(
            address,
            dict,
        ):
            return None

        return (
            BrowserJobPageExtractor
            ._clean_text(
                address.get(
                    "addressCountry"
                )
            )
        )

    @staticmethod
    def _html_to_text(
        value: Any,
    ) -> str | None:

        if not value:
            return None

        soup = BeautifulSoup(
            str(value),
            "html.parser",
        )

        text = soup.get_text(
            " ",
            strip=True,
        )

        return text or None

    @staticmethod
    def _clean_text(
        value: Any,
    ) -> str | None:

        if value is None:
            return None

        text = " ".join(
            str(value).split()
        )

        return text or None

    @staticmethod
    @staticmethod
    def _infer_remote_type(
        location: str | None,
        description: str | None,
    ) -> str | None:

        location_text = (
            location or ""
        ).lower()

        description_text = (
            description or ""
        ).lower()

        # Explicit hybrid wording is sufficiently strong.
        if "hybrid" in location_text:
            return "Hybrid"

        # Only classify Remote when the work location itself
        # explicitly indicates remote work.
        remote_location_patterns = [
            "remote",
            "work from home",
            "wfh",
            "anywhere",
        ]

        if any(
            pattern in location_text
            for pattern in remote_location_patterns
        ):
            return "Remote"

        # Description-based detection requires an explicit
        # work-location statement. Do not classify generic
        # phrases such as "remote-first team" as Remote.
        explicit_remote_patterns = [
            "position is fully remote",
            "role is fully remote",
            "this position is remote",
            "this role is remote",
            "work remotely",
            "working remotely",
            "work from home",
            "100% remote",
            "fully remote position",
            "fully remote role",
        ]

        if any(
            pattern in description_text
            for pattern in explicit_remote_patterns
        ):
            return "Remote"

        explicit_hybrid_patterns = [
            "position is hybrid",
            "role is hybrid",
            "this position is hybrid",
            "this role is hybrid",
        ]

        if any(
            pattern in description_text
            for pattern in explicit_hybrid_patterns
        ):
            return "Hybrid"

        return None