from __future__ import annotations

from pathlib import Path

from app.networking.outreach_tracker import OutreachTracker
from app.networking.outreach import OutreachMessage


def create_test_outreach() -> dict:
    tracker = OutreachTracker()

    message = OutreachMessage(
        contact_id="TEST-CONTACT-001",
        contact_name="Test User",
        contact_email="test@example.com",
        company="JobPilot Test",
        role="Business Analyst",
        subject="JobPilot Approval Test",
        body=(
            "This is a JobPilot approval workflow test. "
            "No real recruiter is involved."
        ),
        cv_path=str(
            Path(
                "data/candidate/cv/current_cv.pdf"
            )
        ),
        job_id=None,
        status="DRAFT",
    )

    job = {
        "location": "Test Location",
        "source": "JobPilot Test",
    }

    contact = {
        "position": "Test Contact",
    }

    result = tracker.record(
        message=message,
        job=job,
        contact=contact,
    )

    return result


if __name__ == "__main__":

    result = create_test_outreach()

    print(result)