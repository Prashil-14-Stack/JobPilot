from pathlib import Path

import pytest

from app.networking.outreach_generator import OutreachGenerator


@pytest.fixture
def profile_directory(monkeypatch, tmp_path):
    directories = {}

    def get_directory(user_id):
        directory = tmp_path / user_id.replace("@", "_at_")
        directory.mkdir(parents=True, exist_ok=True)
        directories[user_id.strip().lower()] = directory
        return directory

    monkeypatch.setattr(
        "app.networking.outreach_generator.get_user_profile_directory",
        get_directory,
    )
    return directories, get_directory


def test_business_analyst_signature_and_cv_are_user_specific(
    profile_directory,
):
    directories, get_directory = profile_directory
    user_id = "prashil@example.com"
    directory = get_directory(user_id)
    cv = directory / "current_cv.pdf"
    cv.write_bytes(b"test cv")

    profile = {
        "candidate_name": "Prashil Wanjari",
        "professional_summary": (
            "Business analyst experienced in insurance data migration "
            "and stakeholder management."
        ),
        "experience": [
            {
                "text": (
                    "Led migration of 6.5M+ insurance policies from "
                    "OPUS to McCamish NGIN."
                )
            }
        ],
        "capabilities": {
            "skills": ["Business Analysis", "Data Migration"],
            "domains": ["Insurance"],
        },
    }

    generator = OutreachGenerator(profile, user_id=user_id)
    message = generator.generate(
        job={
            "id": "job-1",
            "company": "Example Insurance",
            "title": "Business Analyst",
            "description": (
                "Seeking business analysis, data migration, "
                "and stakeholder management experience."
            ),
        },
        contact={
            "contact_id": "contact-1",
            "full_name": "Alex Recruiter",
            "email": "alex@example.com",
            "position": "Talent Acquisition",
        },
    )

    assert "Prashil Wanjari" in message.body
    assert "Priyanka Maske" not in message.body
    assert "OPUS" in message.body or "Business analyst" in message.body
    assert Path(message.cv_path) == cv
    assert Path(message.cv_path).parent == directories[user_id]


def test_sam_signature_and_evidence_use_wife_profile(profile_directory):
    directories, get_directory = profile_directory
    user_id = "priyanka@example.com"
    directory = get_directory(user_id)
    cv = directory / "current_cv.pdf"
    cv.write_bytes(b"test cv")

    profile = {
        "candidate_name": "Priyanka Maske",
        "professional_summary": (
            "Software Asset Management professional with experience in "
            "software licensing, renewals, IT compliance, vendor governance, "
            "ServiceNow SAM Pro, and FlexeraOne."
        ),
        "experience": [],
        "capabilities": {
            "skills": [
                "Software Asset Management",
                "Software Licensing",
                "IT Compliance",
                "Vendor Governance",
            ],
            "tools": ["ServiceNow SAM Pro", "FlexeraOne"],
        },
    }

    generator = OutreachGenerator(profile, user_id=user_id)
    message = generator.generate(
        job={
            "id": "job-2",
            "company": "Example Technology",
            "title": "Software Asset Management Consultant",
            "description": (
                "Seeking software asset management, software licensing, "
                "IT compliance, renewals, and vendor governance experience."
            ),
        },
        contact={
            "contact_id": "contact-2",
            "full_name": "Taylor Recruiter",
            "email": "taylor@example.com",
            "position": "Talent Acquisition",
        },
    )

    assert "Priyanka Maske" in message.body
    assert "Prashil Wanjari" not in message.body
    assert (
        "Software Asset Management" in message.body
        or "software licensing" in message.body.lower()
    )
    assert "OPUS" not in message.body
    assert "McCamish" not in message.body
    assert Path(message.cv_path) == cv
    assert Path(message.cv_path).parent == directories[user_id]


def test_missing_cv_does_not_fall_back_to_another_users_cv(
    profile_directory,
):
    _, get_directory = profile_directory
    user_id = "priyanka@example.com"
    directory = get_directory(user_id)

    # Another user's CV must not be used as a fallback.
    other_directory = get_directory("prashil@example.com")
    (other_directory / "current_cv.pdf").write_bytes(b"other user's cv")

    generator = OutreachGenerator(
        {"candidate_name": "Priyanka Maske"},
        user_id=user_id,
    )

    message = generator.generate(
        job={
            "id": "job-3",
            "company": "Example Technology",
            "title": "SAM Consultant",
            "description": "Software licensing and compliance.",
        },
        contact={
            "contact_id": "contact-3",
            "full_name": "Jordan Recruiter",
            "email": "jordan@example.com",
            "position": "Recruiter",
        },
    )

    assert message.cv_path == ""
    assert "Priyanka Maske" in message.body
    assert Path(message.cv_path).parent != other_directory


def test_generator_rejects_missing_authenticated_identity():
    with pytest.raises(ValueError, match="authenticated user_id"):
        OutreachGenerator({"candidate_name": "Test Candidate"})
