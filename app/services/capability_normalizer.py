from __future__ import annotations

from typing import Any


class CapabilityNormalizer:
    """
    Normalizes candidate capabilities into consistent canonical names.

    The normalizer does not discover new capabilities.
    It only standardizes aliases/variants produced by the CV analyzer.
    """

    ALIASES = {
        # AI / GenAI
        "GPT APIS": "GPT APIs",
        "GPT API": "GPT APIs",
        "GPT APIs": "GPT APIs",
        "GENERATIVE AI": "GenAI",
        "GENERATIVEAI": "GenAI",
        "GEN AI": "GenAI",

        # Business analysis
        "BRD/FRD": "BRD/FRD",
        "BRD / FRD": "BRD/FRD",
        "BUSINESS REQUIREMENTS DOCUMENT": "BRD",
        "FUNCTIONAL REQUIREMENTS DOCUMENT": "FRD",

        # Testing
        "USER ACCEPTANCE TESTING": "UAT",
        "USER ACCEPTANCE TEST": "UAT",

        # Process modelling
        "PROCESS MODELING": "Process Modelling",
        "BUSINESS PROCESS MODELING": "Process Modelling",
        "BUSINESS PROCESS MODELLING": "Process Modelling",

        # Requirements
        "REQUIREMENT GATHERING": "Requirements Gathering",
        "REQUIREMENTS GATHERING": "Requirements Gathering",
        "REQUIREMENT ELICITATION": "Requirements Elicitation",
        "REQUIREMENTS ELICITATION": "Requirements Elicitation",

        # Tools
        "JIRA": "Jira",
        "GITHUB": "GitHub",
        "GIT LAB": "GitLab",
        "GITLAB": "GitLab",
        "HIVE SQL": "Hive",
    }

    CAPABILITY_FIELDS = [
        "skills",
        "tools",
        "technologies",
        "methodologies",
        "domains",
        "functional_areas",
        "role_signals",
    ]

    @classmethod
    def normalize_name(cls, value: str) -> str:
        """
        Convert one capability name to its canonical representation.
        """

        if not isinstance(value, str):
            return value

        value = value.strip()

        if not value:
            return value

        # First check the exact value.
        if value in cls.ALIASES:
            return cls.ALIASES[value]

        # Then check case-insensitively.
        value_upper = value.upper()

        for alias, canonical in cls.ALIASES.items():
            if alias.upper() == value_upper:
                return canonical

        return value

    @classmethod
    def normalize_list(cls, values: list[str]) -> list[str]:
        """
        Normalize a list of capabilities and remove duplicates
        while preserving order.
        """

        normalized = []
        seen = set()

        for value in values or []:
            canonical = cls.normalize_name(value)

            if not canonical:
                continue

            # Case-insensitive duplicate detection.
            key = canonical.casefold()

            if key in seen:
                continue

            seen.add(key)
            normalized.append(canonical)

        return normalized

    @classmethod
    def normalize_profile(cls, profile: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize all capability fields in a candidate profile.

        Returns a new profile dictionary and does not mutate the
        original profile.
        """

        normalized_profile = dict(profile)

        capabilities = dict(
            profile.get("capabilities", {})
        )

        for field in cls.CAPABILITY_FIELDS:
            capabilities[field] = cls.normalize_list(
                capabilities.get(field, [])
            )

        normalized_profile["capabilities"] = capabilities

        return normalized_profile