from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup


LINKEDIN_SEARCH_URL = (
    "https://www.linkedin.com/jobs/search/"
    "?keywords={query}&location=Worldwide"
)

REQUEST_TIMEOUT = 20

USER_AGENT = (
    "JobPilot/1.0 "
    "(job discovery; respectful automated retrieval)"
)


@dataclass
class LinkedInJob:
    source_job_id: str
    title: str
    company: str
    location: str | None
    posted_date: str | None
    source_url: str
    source: str = "LinkedIn Jobs"

    def to_dict(self) -> dict:
        return asdict(self)


class LinkedInSearch:

    def __init__(self):
        self.session = requests.Session()

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

    # ========================================================
    # SEARCH
    # ========================================================

    def search(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[LinkedInJob]:

        query = str(
            query or ""
        ).strip()

        if not query:
            return []

        url = LINKEDIN_SEARCH_URL.format(
            query=quote_plus(query)
        )

        response = self.session.get(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        response.raise_for_status()

        return self.parse_results(
            response.text,
            max_results=max_results,
        )

    # ========================================================
    # PARSER
    # ========================================================

    @staticmethod
    def parse_results(
        page: str,
        max_results: int = 10,
    ) -> list[LinkedInJob]:

        soup = BeautifulSoup(
            page,
            "html.parser",
        )

        cards = soup.select(
            "div.base-search-card"
        )

        results = []
        seen_ids = set()

        for card in cards:

            # ------------------------------------------------
            # Job ID
            # ------------------------------------------------

            urn = card.get(
                "data-entity-urn",
                "",
            )

            match = re.search(
                r"jobPosting:(\d+)",
                urn,
            )

            source_job_id = (
                match.group(1)
                if match
                else ""
            )

            # ------------------------------------------------
            # Job URL
            # ------------------------------------------------

            link = card.select_one(
                "a.base-card__full-link"
            )

            if link is None:
                continue

            source_url = (
                link.get("href", "")
                .strip()
            )

            # Remove LinkedIn search-session/tracking parameters.
            parsed_url = urlparse(source_url)

            source_url = (
                f"{parsed_url.scheme}://"
                f"{parsed_url.netloc}"
                f"{parsed_url.path}"
            )

            if not source_url:
                continue

            # If LinkedIn ever fails to expose
            # the entity URN, derive the ID from
            # the job URL as a fallback.
            if not source_job_id:

                url_match = re.search(
                    r"/jobs/view/[^/]*-(\d+)",
                    source_url,
                )

                if url_match:
                    source_job_id = (
                        url_match.group(1)
                    )

            if not source_job_id:
                continue

            if source_job_id in seen_ids:
                continue

            # ------------------------------------------------
            # Title
            # ------------------------------------------------

            title_element = card.select_one(
                ".base-search-card__title"
            )

            title = (
                title_element.get_text(
                    " ",
                    strip=True,
                )
                if title_element
                else ""
            )

            if not title:
                continue

            # ------------------------------------------------
            # Company
            # ------------------------------------------------

            company_element = card.select_one(
                ".base-search-card__subtitle"
            )

            company = (
                company_element.get_text(
                    " ",
                    strip=True,
                )
                if company_element
                else "Unknown"
            )

            # ------------------------------------------------
            # Location
            # ------------------------------------------------

            location_element = card.select_one(
                ".job-search-card__location"
            )

            location = (
                location_element.get_text(
                    " ",
                    strip=True,
                )
                if location_element
                else None
            )

            # ------------------------------------------------
            # Posted date
            # ------------------------------------------------

            date_element = card.select_one(
                ".job-search-card__listdate"
            )

            posted_date = None

            if date_element:

                posted_date = (
                    date_element.get(
                        "datetime"
                    )
                    or date_element.get_text(
                        " ",
                        strip=True,
                    )
                )

            # ------------------------------------------------
            # Store
            # ------------------------------------------------

            results.append(
                LinkedInJob(
                    source_job_id=source_job_id,
                    title=title,
                    company=company,
                    location=location,
                    posted_date=posted_date,
                    source_url=source_url,
                )
            )

            seen_ids.add(
                source_job_id
            )

            if len(results) >= max_results:
                break

        return results


# ============================================================
# CLI TEST
# ============================================================

def main():

    print("=" * 60)
    print("LINKEDIN SEARCH TEST")
    print("=" * 60)

    query = "Business Analyst"

    print(
        f"Query: {query}"
    )

    searcher = LinkedInSearch()

    jobs = searcher.search(
        query=query,
        max_results=10,
    )

    print(
        f"Jobs found: {len(jobs)}"
    )

    print()

    for index, job in enumerate(
        jobs,
        start=1,
    ):

        print(
            f"[{index}] {job.title}"
        )

        print(
            f"    Company:  {job.company}"
        )

        print(
            f"    Location: {job.location}"
        )

        print(
            f"    Posted:   {job.posted_date}"
        )

        print(
            f"    Job ID:   {job.source_job_id}"
        )

        print(
            f"    URL:      {job.source_url}"
        )

        print()


if __name__ == "__main__":
    main()