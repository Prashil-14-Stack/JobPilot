"""Validate public ATS APIs or careers URLs using the Python standard library."""
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json, re

class SourceValidator:
    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout

    def validate(self, source: dict[str, Any]) -> dict[str, Any]:
        platform = (source.get("ats_platform") or "unknown").lower()
        token = (source.get("board_token") or "").strip()
        url = (source.get("canonical_board_url") or source.get("careers_url") or "").strip()
        if platform == "greenhouse":
            token = token or self._token(url, r"(?:boards|job-boards)\.greenhouse\.io/([^/?#]+)")
            if not token:
                return self._result(False, None, "Greenhouse board token missing", "greenhouse_api")
            return self._json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true", "greenhouse_public_jobs_api", ("jobs",))
        if platform == "lever":
            token = token or self._token(url, r"jobs(?:\.eu)?\.lever\.co/([^/?#]+)")
            if not token:
                return self._result(False, None, "Lever site identifier missing", "lever_api")
            return self._json(f"https://api.lever.co/v0/postings/{token}?mode=json", "lever_postings_api", expected_type=list)
        if platform == "ashby":
            token = token or self._token(url, r"jobs\.ashbyhq\.com/([^/?#]+)")
            if not token:
                return self._result(False, None, "Ashby board identifier missing", "ashby_api")
            return self._json(f"https://api.ashbyhq.com/posting-api/job-board/{token}", "ashby_public_job_board", ("jobs",))
        if platform == "smartrecruiters":
            token = token or self._token(url, r"smartrecruiters\.com/([^/?#]+)")
            if not token:
                return self._result(False, None, "SmartRecruiters company identifier missing", "smartrecruiters_api")
            return self._json(f"https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=1", "smartrecruiters_api", ("content",))
        # Workday tenant URLs differ, so validate reachability only; no job-fetch adapter is implied.
        return self._page(url, "careers_page_http")

    def _get(self, url: str) -> tuple[int, str, str]:
        req = Request(url, headers={"User-Agent": "JobPilotSourceValidator/1.0", "Accept": "application/json,text/html,*/*"})
        with urlopen(req, timeout=self.timeout) as response:
            return response.status, response.read(2_000_000).decode("utf-8", "replace"), response.headers.get("Content-Type", "")

    def _json(self, url: str, method: str, keys: tuple[str, ...] = (), expected_type: type | None = None) -> dict[str, Any]:
        try:
            status, body, content_type = self._get(url)
            data = json.loads(body)
            ok = isinstance(data, expected_type) if expected_type else isinstance(data, dict) and any(k in data for k in keys)
            if not ok:
                return self._result(False, status, "HTTP succeeded but response schema did not match", method)
            count = len(data) if isinstance(data, list) else next((len(data[k]) for k in keys if isinstance(data.get(k), list)), None)
            return {"verified": True, "reachable": True, "http_status": status, "validation_error": "", "validation_method": method, "validation_status": "verified", "capabilities": ["public_api", "fetch_jobs"], "reported_job_count": count, "content_type": content_type}
        except HTTPError as e:
            return self._result(False, e.code, f"HTTP {e.code}", method)
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
            return self._result(False, None, str(e)[:300], method)
        except Exception as e:
            return self._result(False, None, f"{type(e).__name__}: {e}"[:300], method)

    def _page(self, url: str, method: str) -> dict[str, Any]:
        if not url.startswith(("https://", "http://")):
            return self._result(False, None, "Missing or invalid HTTP(S) URL", method)
        try:
            status, body, content_type = self._get(url)
            ok = 200 <= status < 400 and bool(body.strip())
            return {"verified": ok, "reachable": ok, "http_status": status, "validation_error": "" if ok else "Empty or unexpected response", "validation_method": method, "validation_status": "verified" if ok else "failed", "capabilities": ["careers_page"] if ok else [], "content_type": content_type}
        except HTTPError as e:
            return self._result(False, e.code, f"HTTP {e.code}", method)
        except (URLError, TimeoutError, OSError) as e:
            return self._result(False, None, str(e)[:300], method)

    @staticmethod
    def _token(url: str, pattern: str) -> str:
        m = re.search(pattern, url or "", re.I)
        return m.group(1).strip() if m else ""

    @staticmethod
    def _result(verified: bool, status: int | None, error: str, method: str) -> dict[str, Any]:
        return {"verified": verified, "reachable": bool(verified and status and 200 <= status < 400), "http_status": status, "validation_error": error, "validation_method": method, "validation_status": "verified" if verified else "failed", "capabilities": []}
