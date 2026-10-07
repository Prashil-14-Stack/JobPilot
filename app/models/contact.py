from dataclasses import dataclass
from typing import Optional


@dataclass
class Contact:
    contact_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    position: Optional[str] = None
    company: Optional[str] = None
    company_domain: Optional[str] = None
    linkedin_url: Optional[str] = None
    email_confidence: Optional[int] = None
    email_verification_status: Optional[str] = None
    source: str = "Hunter"