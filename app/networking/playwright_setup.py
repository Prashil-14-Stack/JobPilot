
import subprocess
import sys

from playwright.sync_api import sync_playwright


def ensure_chromium_installed() -> None:
    """Ensure the matching headless Chromium browser is installed."""

    def can_launch_chromium() -> bool:
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                browser.close()
            return True
        except Exception as exc:
            if "Executable doesn't exist" in str(exc):
                return False
            raise

    if can_launch_chromium():
        return

    subprocess.run(
        [
            sys.executable,
            "-m",
            "playwright",
            "install",
            "chromium",
        ],
        check=True,
        timeout=300,
    )

    if not can_launch_chromium():
        raise RuntimeError(
            "Chromium installation completed, but the browser still cannot launch."
        )
