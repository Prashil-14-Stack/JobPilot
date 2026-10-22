"""Conservative ATS detection from careers/job URLs and optional page text."""
from dataclasses import dataclass
from urllib.parse import urlparse
import re

@dataclass
class DetectedATS:
    platform: str
    board_token: str = ""
    canonical_board_url: str = ""
    detection_method: str = "url"
    confidence: float = 0.0

class ATSDetector:
    def detect(self, url: str, page_text: str = "") -> DetectedATS:
        raw = (url or "").strip()
        p = urlparse(raw)
        host = (p.hostname or "").lower()
        parts = [x for x in p.path.strip("/").split("/") if x]
        if host in {"boards.greenhouse.io", "job-boards.greenhouse.io"} and parts and parts[0] != "embed":
            token = parts[0]
            return DetectedATS("greenhouse", token, f"https://boards.greenhouse.io/{token}", "url", .99)
        if host in {"jobs.lever.co", "jobs.eu.lever.co"} and parts:
            token = parts[0]
            return DetectedATS("lever", token, f"https://{host}/{token}", "url", .99)
        if host == "jobs.ashbyhq.com" and parts:
            token = parts[0]
            return DetectedATS("ashby", token, f"https://jobs.ashbyhq.com/{token}", "url", .99)
        if "myworkdayjobs.com" in host or "workday" in host:
            return DetectedATS("workday", "", raw, "url", .9)
        if "smartrecruiters.com" in host:
            token = parts[0] if parts else ""
            return DetectedATS("smartrecruiters", token, raw, "url", .9)
        text = (page_text or "").lower()
        patterns = [
            ("greenhouse", r"(?:boards|job-boards)\.greenhouse\.io/([a-z0-9_-]+)"),
            ("lever", r"jobs(?:\.eu)?\.lever\.co/([a-z0-9_-]+)"),
            ("ashby", r"jobs\.ashbyhq\.com/([a-z0-9_-]+)"),
            ("workday", r"[a-z0-9.-]+\.myworkdayjobs\.com"),
            ("smartrecruiters", r"careers\.smartrecruiters\.com"),
        ]
        for platform, pattern in patterns:
            m = re.search(pattern, text)
            if not m:
                continue
            token = m.group(1) if m.lastindex else ""
            if platform == "greenhouse":
                board = f"https://boards.greenhouse.io/{token}"
            elif platform == "lever":
                board = f"https://jobs.lever.co/{token}"
            elif platform == "ashby":
                board = f"https://jobs.ashbyhq.com/{token}"
            else:
                board = raw
            return DetectedATS(platform, token, board, "page_text", .8)
        return DetectedATS("unknown", "", raw, "unrecognized", 0.0)
