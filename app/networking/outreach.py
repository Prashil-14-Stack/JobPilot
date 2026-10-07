from dataclasses import dataclass
from typing import Optional


@dataclass
class OutreachMessage:
    """
    Represents a personalised job outreach message.
    """

    contact_id: str
    contact_name: str
    contact_email: str

    company: str
    role: str

    subject: str
    body: str

    cv_path: str

    job_id: Optional[int] = None
    status: str = "DRAFT"