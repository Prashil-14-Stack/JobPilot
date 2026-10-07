from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from app.discovery.indeed_browser import IndeedBrowser


@dataclass
class IndeedSearchResult:
    source_job_id: str
    title: str
    company: str
    location: str | None
    posted_date: str | None
    source_url: str
    source: str = "Indeed"


class IndeedSearch:
    def __init__(
        self,
        browser: IndeedBrowser | None = None,
    ):
        self.browser = browser

    @staticmethod
    def build_search_url(
        query: str,
        country_domain: str = "au.indeed.com",
    ) -> str:

        encoded_query = quote_plus(query)

        return (
            f"https://{country_domain}/jobs"
            f"?q={encoded_query}"
        )

    @staticmethod
    def parse_results(
        page: str,
        base_url: str,
        max_results: int = 10,
    ) -> list[IndeedSearchResult]:

        soup = BeautifulSoup(
            page,
            "html.parser",
        )

        results = []
        seen_ids: set[str] = set()

        job_links = soup.select(
            "a.jcs-JobTitle[data-jk]"
        )

        for job_link in job_links:

            source_job_id = (
                job_link.get(
                    "data-jk",
                    "",
                )
                .strip()
            )

            if not source_job_id:
                continue

            if source_job_id in seen_ids:
                continue

            card = job_link.find_parent(
                "td",
                class_="resultContent",
            )

            if card is None:
                continue

            href = (
                job_link.get(
                    "href",
                    "",
                )
                .strip()
            )

            if not href:
                continue

            source_url = urljoin(
                base_url,
                href,
            )

            title = job_link.get_text(
                " ",
                strip=True,
            )

            if not title:
                title_element = (
                    job_link.select_one(
                        "span[title]"
                    )
                )

                title = (
                    title_element.get(
                        "title",
                        "",
                    ).strip()
                    if title_element
                    else ""
                )

            if not title:
                continue

            company_element = (
                card.select_one(
                    '[data-testid="company-name"]'
                )
            )

            company = (
                company_element.get_text(
                    " ",
                    strip=True,
                )
                if company_element
                else "Unknown"
            )

            location_element = (
                card.select_one(
                    '[data-testid="text-location"]'
                )
            )

            location = (
                location_element.get_text(
                    " ",
                    strip=True,
                )
                if location_element
                else None
            )

            date_element = (
                card.select_one(
                    "time"
                )
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

            results.append(
                IndeedSearchResult(
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

    def search(
        self,
        query: str,
        country_domain: str = "au.indeed.com",
        max_results: int = 10,
    ) -> list[IndeedSearchResult]:

        search_url = self.build_search_url(
            query=query,
            country_domain=country_domain,
        )

        browser = self.browser
        owns_browser = False

        if browser is None:
            browser = IndeedBrowser(
                headless=True
            )
            owns_browser = True

        try:
            if owns_browser:
                browser.start()

            html = browser.fetch_html(
                search_url
            )

            return self.parse_results(
                page=html,
                base_url=(
                    f"https://{country_domain}"
                ),
                max_results=max_results,
            )

        finally:
            if owns_browser:
                browser.close()