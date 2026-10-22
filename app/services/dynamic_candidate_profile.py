
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from openai import OpenAI


PROFILE_DIR = Path("data/profiles")
MODEL = os.getenv("OPENAI_PROFILE_MODEL", "gpt-4o-mini")


def _safe_user_id(user_id: str) -> str:
    """Prevent path traversal and require an authenticated identity."""
    value = re.sub(r"[^a-zA-Z0-9_.@-]", "_", user_id).strip("._")
    if not value:
        raise ValueError("A valid authenticated user ID is required.")
    return value


def extract_cv_text(filename: str, content: bytes) -> str:
    """Extract text from PDF, DOCX, or TXT CVs."""
    suffix = Path(filename).suffix.lower()

    if suffix == ".pdf":
        from pypdf import PdfReader
        from io import BytesIO

        reader = PdfReader(BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)

    elif suffix == ".docx":
        from docx import Document
        from io import BytesIO

        document = Document(BytesIO(content))
        paragraphs = [p.text for p in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                paragraphs.append(" | ".join(cell.text for cell in row.cells))
        text = "\n".join(paragraphs)

    elif suffix == ".txt":
        text = content.decode("utf-8", errors="replace")

    else:
        raise ValueError("Upload a PDF, DOCX, or TXT CV.")

    text = text.strip()
    if len(text) < 100:
        raise ValueError(
            "Too little text was extracted. If this is a scanned PDF, "
            "OCR is required before profile analysis."
        )

    return text[:60000]


def analyze_cv(cv_text: str) -> dict[str, Any]:
    """Build a structured profile and role universe from the CV."""
    client = OpenAI()

    response = client.chat.completions.create(
        model=MODEL,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": """
You are a recruitment and career-profile analyst.
Use only evidence in the supplied CV. Do not invent qualifications,
employers, years of experience, certifications, or achievements.

Return one JSON object with these fields:
{
  "headline": "short professional headline",
  "seniority": "evidence-based level",
  "experience_summary": "brief evidence-based summary",
  "skills": ["skill"],
  "industries": ["industry"],
  "job_titles": ["10 to 20 relevant job titles"],
  "search_queries": ["10 to 20 distinct job search queries"],
  "location_preferences": [],
  "certifications": [],
  "strengths": ["evidence-backed strengths"],
  "gaps_or_uncertainties": ["items that need user confirmation"]
}

Job titles must include close matches to the person's demonstrated experience,
adjacent realistic roles, and alternative titles employers may use.
Do not restrict recommendations to a single predefined profession.
Do not infer location or work authorization preferences from nationality.
""",
            },
            {
                "role": "user",
                "content": f"Analyze this CV:\n\n{cv_text}",
            },
        ],
    )

    result = json.loads(response.choices[0].message.content or "{}")

    for key in (
        "skills", "industries", "job_titles", "search_queries",
        "location_preferences", "certifications", "strengths",
        "gaps_or_uncertainties",
    ):
        if not isinstance(result.get(key), list):
            result[key] = []

    if not result["job_titles"]:
        raise ValueError("The CV analysis did not produce suitable job titles.")

    result["job_titles"] = list(dict.fromkeys(
        str(x).strip() for x in result["job_titles"] if str(x).strip()
    ))
    result["search_queries"] = list(dict.fromkeys(
        str(x).strip() for x in result["search_queries"] if str(x).strip()
    ))

    return result


def save_profile(user_id: str, profile: dict[str, Any]) -> Path:
    """Persist a profile in that user's own directory."""
    safe_id = _safe_user_id(user_id)
    directory = PROFILE_DIR / safe_id
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / "profile.json"
    temporary_path = directory / "profile.json.tmp"

    temporary_path.write_text(
        json.dumps(profile, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary_path.replace(path)
    return path


def load_profile(user_id: str) -> dict[str, Any] | None:
    path = PROFILE_DIR / _safe_user_id(user_id) / "profile.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def create_candidate_profile(user_id: str, filename: str, content: bytes):
    text = extract_cv_text(filename, content)
    profile = analyze_cv(text)
    save_profile(user_id, profile)
    return profile
