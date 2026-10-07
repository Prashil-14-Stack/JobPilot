from dataclasses import dataclass
from urllib.parse import quote_plus, urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


@dataclass
class DomainCandidate:
    domain: str
    url: str
    title: str | None = None
    source: str = "SEARCH_ENGINE"


class DomainSearch:
    """
    Searches the web for a company's official website.

    Responsibility:
        Company name
            ↓
        Search engine
            ↓
        Candidate URLs/domains

    This class does NOT validate whether a domain is the
    official company domain. Validation belongs to
    CompanyDomainResolver.
    """

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 30000,
    ) -> None:
        self.headless = headless
        self.timeout = timeout

    def search(
        self,
        company: str,
        max_results: int = 10,
    ) -> list[DomainCandidate]:
        """
        Search for candidate company domains.

        Returns:
            List of unique DomainCandidate objects.
        """

        if not company or not company.strip():
            return []

        query = f'"{company.strip()}" official website'
        search_url = (
            "https://www.bing.com/search"
            f"?q={quote_plus(query)}"
        )

        candidates: list[DomainCandidate] = []

        with sync_playwright() as playwright:

            browser = playwright.chromium.launch(
                headless=self.headless,
            )

            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 "
                    "(Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/144.0 Safari/537.36"
                ),
            )

            try:
                page.goto(
                    search_url,
                    wait_until="domcontentloaded",
                    timeout=self.timeout,
                )

                page.wait_for_timeout(1000)

                links = page.locator("a").all()

                seen_domains: set[str] = set()

                for link in links:

                    if len(candidates) >= max_results:
                        break

                    try:
                        href = link.get_attribute("href")

                        if not href:
                            continue

                        # Bing search results expose the destination URL
                        # inside a <cite> element.
                        cite = link.locator("cite").first

                        if not cite.count():
                            continue

                        cited_url = cite.inner_text().strip()

                        if not cited_url.startswith(("http://", "https://")):
                            continue

                        parsed = urlparse(cited_url)

                        if not parsed.netloc:
                            continue

                        if "›" in cited_url:
                            continue

                        parsed = urlparse(cited_url)

                        if not parsed.netloc:
                            continue

                        parsed = urlparse(cited_url)

                        domain = parsed.netloc.lower()

                        if domain.startswith("www."):
                            domain = domain[4:]

                        if not domain:
                            continue

                        if domain in seen_domains:
                            continue

                        if self._is_blocked_domain(domain):
                            continue

                        title = None

                        try:
                            title = link.inner_text(
                                timeout=1000
                            ).strip() or None
                        except Exception:
                            pass

                        candidates.append(
                            DomainCandidate(
                                domain=domain,
                                url=cited_url,
                                title=title,
                            )
                        )

                        seen_domains.add(domain)

                    except Exception:
                        continue

                        if not domain:
                            continue

                        if domain in seen_domains:
                            continue

                        if self._is_blocked_domain(domain):
                            continue

                        title = None

                        try:
                            title = link.inner_text(
                                timeout=1000
                            ).strip() or None
                        except Exception:
                            pass

                        candidates.append(
                            DomainCandidate(
                                domain=domain,
                                url=href,
                                title=title,
                            )
                        )

                        seen_domains.add(domain)

                    except Exception:
                        continue
            except PlaywrightTimeoutError:
                return []

            finally:
                browser.close()

        return candidates

    @staticmethod
    def _is_blocked_domain(
        domain: str,
    ) -> bool:
        """
        Domains that are search engines, job boards,
        social networks or aggregators rather than
        employer domains.
        """

        blocked_domains = {
            "google.com",
            "google.co.uk",
            "google.com.au",
            "bing.com",
            "yahoo.com",

            "linkedin.com",
            "indeed.com",
            "glassdoor.com",
            "ziprecruiter.com",
            "monster.com",
            "talent.com",
            "adzuna.com",
            "jooble.org",
            "jobgether.com",

            "facebook.com",
            "instagram.com",
            "x.com",
            "twitter.com",
            "youtube.com",
        }

        return domain in blocked_domains


if __name__ == "__main__":

    searcher = DomainSearch()

    company = "Virgin Australia"

    candidates = searcher.search(
        company=company,
        max_results=10,
    )

    print("=" * 60)
    print("DOMAIN SEARCH")
    print("=" * 60)

    print(f"Company: {company}")
    print(f"Candidates: {len(candidates)}")
    print()

    for index, candidate in enumerate(
        candidates,
        start=1,
    ):
        print(
            f"{index}. "
            f"{candidate.domain} | "
            f"{candidate.url} | "
            f"{candidate.title}"
        )