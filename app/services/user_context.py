
from __future__ import annotations

import hashlib
import os
import re

import streamlit as st


def get_authenticated_user_id() -> str:
    """
    Return the authenticated Streamlit OIDC identity.
    Never accept a user ID from a text input or URL parameter.
    """
    if os.getenv("JOBPILOT_REQUIRE_AUTH", "true").lower() != "true":
        raise RuntimeError(
            "Multi-user mode requires authentication."
        )

    try:
        user = st.user
        if not user.is_logged_in:
            st.login()
            st.stop()

        email = str(user.email).strip().lower()
    except AttributeError as exc:
        raise RuntimeError(
            "Configure Streamlit OIDC authentication before "
            "enabling multi-user JobPilot."
        ) from exc

    if not email or "@" not in email:
        raise RuntimeError(
            "No verified user email is available. "
            "Check the OIDC provider configuration."
        )

    return email


def get_user_storage_key(user_id: str) -> str:
    """Create a stable, filesystem-safe pseudonymous identifier."""
    normalized = user_id.strip().lower()

    if not normalized or "@" not in normalized:
        raise ValueError("Invalid authenticated user identity.")

    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_user_profile_directory(user_id: str):
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    directory = (
        project_root
        / "data"
        / "candidate"
        / "profiles_by_user"
        / get_user_storage_key(user_id)
    )
    directory.mkdir(parents=True, exist_ok=True)
    return directory
