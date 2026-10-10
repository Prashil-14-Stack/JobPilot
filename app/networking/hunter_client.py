import os
from typing import Any

import requests
from dotenv import load_dotenv


class HunterClient:
    BASE_URL = "https://api.hunter.io/v2"

    def __init__(self) -> None:
        load_dotenv()

        self.api_key = os.getenv("HUNTER_API_KEY")

        if not self.api_key:
            try:
                import streamlit as st
                self.api_key = st.secrets.get("HUNTER_API_KEY")
            except Exception:
                self.api_key = None

        if not self.api_key:
            raise ValueError(
                "HUNTER_API_KEY is not configured in the environment."
            )

        self.session = requests.Session()

    def get_account(self) -> dict[str, Any]:
        """Return Hunter account information and API usage."""
        response = self.session.get(
            f"{self.BASE_URL}/account",
            params={"api_key": self.api_key},
            timeout=20,
        )

        response.raise_for_status()

        return response.json()

    def domain_search(
        self,
        domain: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Find professional email addresses associated with a domain."""
        response = self.session.get(
            f"{self.BASE_URL}/domain-search",
            params={
                "domain": domain,
                "limit": limit,
                "api_key": self.api_key,
            },
            timeout=20,
        )

        response.raise_for_status()

        return response.json()