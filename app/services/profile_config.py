from __future__ import annotations

import os

from app.services.user_context import get_user_storage_key


# Profile identifiers
BA_PROFILE = "business_analyst"
WIFE_PROFILE = "wife"

# Configure these environment variables locally or in your deployment
# secrets. Store account emails there rather than hardcoding them in source.
BUSINESS_ANALYST_USER = os.getenv("JOBPILOT_BA_USER", "").strip().lower()
WIFE_USER = os.getenv("JOBPILOT_WIFE_USER", "").strip().lower()


def get_profile_key(user_id: str) -> str:
    """Resolve an authenticated account to its predefined JobPilot profile."""
    normalized_user = user_id.strip().lower()

    if not normalized_user or "@" not in normalized_user:
        raise ValueError("A valid authenticated user identity is required.")

    if BUSINESS_ANALYST_USER and normalized_user == BUSINESS_ANALYST_USER:
        return BA_PROFILE

    if WIFE_USER and normalized_user == WIFE_USER:
        return WIFE_PROFILE

    raise ValueError(
        "No JobPilot profile is configured for this authenticated account."
    )


def get_profile_storage_key(user_id: str) -> str:
    """Return the existing pseudonymous storage key for an authenticated user."""
    return get_user_storage_key(user_id)
