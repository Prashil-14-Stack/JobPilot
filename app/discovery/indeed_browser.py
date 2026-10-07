from __future__ import annotations

from playwright.sync_api import (
    Browser,
    Page,
    sync_playwright,
)


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/144.0.0.0 Safari/537.36"
)


class IndeedBrowser:

    def __init__(
        self,
        headless: bool = True,
    ):
        self.headless = headless
        self.playwright = None
        self.browser: Browser | None = None
        self.page: Page | None = None

    def start(self) -> None:

        self.playwright = (
            sync_playwright().start()
        )

        self.browser = (
            self.playwright.chromium.launch(
                headless=self.headless,
            )
        )

        self.page = (
            self.browser.new_page(
                user_agent=USER_AGENT,
            )
        )

    def fetch_html(
        self,
        url: str,
        wait_until: str = "domcontentloaded",
        timeout: int = 30000,
    ) -> str:

        if self.page is None:
            raise RuntimeError(
                "IndeedBrowser has not been started."
            )

        self.page.goto(
            url,
            wait_until=wait_until,
            timeout=timeout,
        )

        return self.page.content()

    def close(self) -> None:

        if self.browser is not None:
            self.browser.close()

        if self.playwright is not None:
            self.playwright.stop()

        self.browser = None
        self.page = None
        self.playwright = None