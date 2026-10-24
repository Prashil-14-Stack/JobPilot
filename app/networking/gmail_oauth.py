
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlencode

import streamlit as st
from google_auth_oauthlib.flow import Flow

from app.services.user_context import get_user_profile_directory

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
STATE_KEY = "jobpilot_gmail_oauth_state"
USER_KEY = "jobpilot_gmail_oauth_user"
URL_KEY = "jobpilot_gmail_oauth_url"
STATE_TTL_SECONDS = 600


def _oauth_config() -> dict[str, str]:
    try:
        config = st.secrets["gmail_oauth"]
        client_id = str(config["client_id"]).strip()
        client_secret = str(config["client_secret"]).strip()
        redirect_uri = str(config["redirect_uri"]).strip()
        state_secret = str(st.secrets["GMAIL_OAUTH_STATE_SECRET"]).strip()
    except (KeyError, TypeError):
        raise RuntimeError(
            "Gmail OAuth is not configured. Check the gmail_oauth section "
            "and GMAIL_OAUTH_STATE_SECRET in Streamlit Cloud Secrets."
        ) from None

    if not all((client_id, client_secret, redirect_uri, state_secret)):
        raise RuntimeError(
            "Gmail OAuth configuration contains an empty required value."
        )

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "state_secret": state_secret,
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


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _create_signed_state(user_id: str, now: int | None = None) -> str:
    config = _oauth_config()
    normalized_user = user_id.strip().lower()

    if not normalized_user or "@" not in normalized_user:
        raise ValueError("A valid authenticated user identity is required.")

    payload = {
        "sub": normalized_user,
        "nonce": secrets.token_urlsafe(24),
        "iat": int(time.time() if now is None else now),
    }
    encoded_payload = _b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    )
    signature = hmac.new(
        config["state_secret"].encode(),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()

    return f"{encoded_payload}.{_b64encode(signature)}"


def _verify_signed_state(
    state: str,
    user_id: str,
    now: int | None = None,
) -> dict[str, Any]:
    config = _oauth_config()
    try:
        encoded_payload, encoded_signature = state.split(".", 1)
        supplied_signature = _b64decode(encoded_signature)
        expected_signature = hmac.new(
            config["state_secret"].encode(),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()

        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ValueError

        payload = json.loads(_b64decode(encoded_payload))
        current_time = int(time.time() if now is None else now)
        issued_at = int(payload["iat"])
        subject = str(payload["sub"]).strip().lower()
        nonce = str(payload["nonce"])

        if current_time < issued_at:
            raise ValueError
        if current_time - issued_at > STATE_TTL_SECONDS:
            raise ValueError
        if subject != user_id.strip().lower():
            raise ValueError
        if not nonce:
            raise ValueError

        return payload
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise PermissionError(
            "Gmail authorization state is invalid, expired, or belongs to "
            "a different signed-in user. Start Connect Gmail again."
        ) from exc


def begin_gmail_authorization(user_id: str) -> str:
    normalized_user = user_id.strip().lower()

    existing_user = st.session_state.get(USER_KEY)
    existing_state = st.session_state.get(STATE_KEY)
    existing_url = st.session_state.get(URL_KEY)

    if (
        existing_user == normalized_user
        and existing_state
        and existing_url
    ):
        return existing_url

    state = _create_signed_state(normalized_user)
    flow = _new_flow(state=state)
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    st.session_state[STATE_KEY] = state
    st.session_state[USER_KEY] = normalized_user
    st.session_state[URL_KEY] = authorization_url
    return authorization_url


def finish_gmail_authorization(
    user_id: str,
    query_params: Mapping[str, Any],
) -> None:
    returned_state = query_params.get("state")
    if isinstance(returned_state, list):
        returned_state = returned_state[0] if returned_state else None
    if not returned_state:
        raise PermissionError("Google did not return OAuth state.")

    state = str(returned_state)
    _verify_signed_state(state, user_id)

    error = query_params.get("error")
    if isinstance(error, list):
        error = error[0] if error else None
    if error:
        raise RuntimeError(
            "Google Gmail authorization was cancelled or denied."
        )

    code = query_params.get("code")
    if isinstance(code, list):
        code = code[0] if code else None
    if not code:
        raise RuntimeError("Google did not return an authorization code.")

    flow = _new_flow(state=state)
    flow.fetch_token(code=str(code))
    credentials = flow.credentials

    if not credentials.refresh_token:
        raise RuntimeError(
            "Google did not return a refresh token. Revoke JobPilot's Gmail "
            "access in your Google Account and connect Gmail again."
        )

    current_user = user_id.strip().lower()
    token_path = gmail_token_path(current_user)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")

    # Clear pending state in this session if it exists.
    st.session_state.pop(STATE_KEY, None)
    st.session_state.pop(USER_KEY, None)
    st.session_state.pop(URL_KEY, None)
