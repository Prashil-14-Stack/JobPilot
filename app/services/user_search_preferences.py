from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.user_context import get_user_profile_directory


BA_ONLY = "BA_ONLY"
PROFILE_MATCHED = "PROFILE_MATCHED"
VALID_SEARCH_MODES = {BA_ONLY, PROFILE_MATCHED}


def get_search_preferences_path(user_id: str) -> Path:
    """Return the preferences path for one authenticated user."""
    return get_user_profile_directory(user_id) / "search_preferences.json"


def load_search_preferences(user_id: str) -> dict[str, Any]:
    """Load one user's preferences; default safely to BA-only."""
    path = get_search_preferences_path(user_id)

    if not path.exists():
        return {"search_mode": BA_ONLY}

    try:
        with path.open("r", encoding="utf-8") as file:
            preferences = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {"search_mode": BA_ONLY}

    if not isinstance(preferences, dict):
        return {"search_mode": BA_ONLY}

    mode = str(preferences.get("search_mode", BA_ONLY)).upper()
    if mode not in VALID_SEARCH_MODES:
        mode = BA_ONLY

    return {**preferences, "search_mode": mode}


def save_search_mode(user_id: str, search_mode: str) -> dict[str, Any]:
    """Save a validated search mode for one authenticated user."""
    mode = str(search_mode).strip().upper()

    if mode not in VALID_SEARCH_MODES:
        raise ValueError(f"Unsupported search mode: {search_mode}")

    path = get_search_preferences_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    preferences = load_search_preferences(user_id)
    preferences["search_mode"] = mode

    with path.open("w", encoding="utf-8") as file:
        json.dump(preferences, file, indent=2, ensure_ascii=False)

    return preferences
