
from __future__ import annotations

import secrets
from collections.abc import Mapping
from typing import Any

import streamlit as st
from google_auth_oauthlib.flow import Flow

from app.services.user_context import get_user_profile_directory

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
STATE_KEY = "jobpilot_gmail_oauth_state"
USER_KEY = "jobpilot_gmail_oauth_user"


def _oauth_config() -> dict[str, str]:
    try:
        config = st.secrets["gmail_oauth"]
        client_id = str(config["client_id"]).strip()
        client_secret = str(config["client_secret"]).strip()
        redirect_uri = str(config["redirect_uri"]).strip()
    except (KeyError, TypeError):
        raise RuntimeError(
            "Gmail OAuth is not configured. Check the gmail_oauth "
            "section in Streamlit Cloud Secrets."
        ) from None

    if not all((client_id, client_secret, redirect_uri)):
        raise RuntimeError(
            "Gmail OAuth requires client_id, client_secret, and redirect_uri."
        )

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }


def _new_flow(state: str | None = None) -> Flow:
    config = _oauth_config()
    client_config: dict[str, Any] = {
        "web": {
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [config["redirect_uri"]],
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        state=state,
    )
    flow.redirect_uri = config["redirect_uri"]
    return flow


def gmail_token_path(user_id: str):
    return get_user_profile_directory(user_id) / "gmail_token.json"



def begin_gmail_authorization(user_id: str) -> str:
    normalized_user = user_id.strip().lower()

    # Reuse the pending authorization URL for this user across reruns.
    existing_user = st.session_state.get(USER_KEY)
    existing_state = st.session_state.get(STATE_KEY)
    existing_url = st.session_state.get("jobpilot_gmail_oauth_url")

    if (
        existing_user == normalized_user
        and existing_state
        and existing_url
    ):
        return existing_url

    state = secrets.token_urlsafe(32)
    st.session_state[STATE_KEY] = state
    st.session_state[USER_KEY] = normalized_user

    flow = _new_flow(state=state)
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    st.session_state["jobpilot_gmail_oauth_url"] = authorization_url
    return authorization_url


def finish_gmail_authorization(
    user_id: str,
    query_params: Mapping[str, Any],
) -> None:
    current_user = user_id.strip().lower()
    expected_user = st.session_state.get(USER_KEY)
    expected_state = st.session_state.get(STATE_KEY)

    if not expected_user or expected_user != current_user:
        raise PermissionError(
            "Gmail authorization session does not match the signed-in user. "
            "Start Connect Gmail again."
        )

    returned_state = query_params.get("state")
    if isinstance(returned_state, list):
        returned_state = returned_state[0] if returned_state else None

    if not expected_state or not secrets.compare_digest(
        str(returned_state or ""),
        str(expected_state),
    ):
        raise PermissionError(
            "Gmail authorization state validation failed. "
            "Start Connect Gmail again."
        )

    error = query_params.get("error")
    if error:
        raise RuntimeError(
            "Google Gmail authorization was cancelled or denied."
        )

    code = query_params.get("code")
    if isinstance(code, list):
        code = code[0] if code else None
    if not code:
        raise RuntimeError("Google did not return an authorization code.")

    flow = _new_flow(state=expected_state)
    flow.fetch_token(code=str(code))
    credentials = flow.credentials

    if not credentials.refresh_token:
        raise RuntimeError(
            "Google did not return a refresh token. Revoke JobPilot's Gmail "
            "access in your Google Account and connect Gmail again."
        )

    token_path = gmail_token_path(current_user)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")

    st.session_state.pop(STATE_KEY, None)
    st.session_state.pop(USER_KEY, None)
    st.session_state.pop("jobpilot_gmail_oauth_url", None)
