import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.candidate_profile import CandidateProfile
from app.services.capability_normalizer import CapabilityNormalizer


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CANDIDATE_DIR = PROJECT_ROOT / "data" / "candidate"

PROFILES_DIR = CANDIDATE_DIR / "profiles"

CURRENT_PROFILE_PATH = (
    CANDIDATE_DIR / "current_profile.json"
)

PROFILE_DELTA_PATH = (
    CANDIDATE_DIR / "profile_delta.json"
)


class CandidateProfileService:
    """
    Manages versioned candidate profiles.

    Responsibilities:
    - Save profile versions
    - Load the current profile
    - Determine the next profile version
    - Maintain cumulative capabilities
    - Normalize capability names
    - Calculate capability delta
    """

    CAPABILITY_FIELDS = [
        "skills",
        "tools",
        "technologies",
        "methodologies",
        "domains",
        "functional_areas",
        "role_signals",
    ]

    def __init__(self):
        CANDIDATE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        PROFILES_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

    @staticmethod
    def utc_now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()

    def get_current_profile(
        self,
    ) -> dict[str, Any] | None:

        if not CURRENT_PROFILE_PATH.exists():
            return None

        with CURRENT_PROFILE_PATH.open(
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    def get_next_version(self) -> str:

        current = self.get_current_profile()

        if current is None:
            return "v1"

        current_version = current.get(
            "profile_version",
            "v0",
        )

        number = int(
            current_version.replace("v", "")
        )

        return f"v{number + 1}"

    @classmethod
    def normalize_profile(
        cls,
        profile: dict[str, Any],
    ) -> dict[str, Any]:

        return CapabilityNormalizer.normalize_profile(
            profile
        )

    @classmethod
    def merge_capabilities(
        cls,
        previous: dict[str, Any] | None,
        current: dict[str, Any],
    ) -> dict[str, list[str]]:

        previous_capabilities = {}

        if previous:
            previous_capabilities = (
                previous.get(
                    "capabilities",
                    {}
                )
            )

        current_capabilities = (
            current.get(
                "capabilities",
                {}
            )
        )

        merged = {}

        for field in cls.CAPABILITY_FIELDS:

            previous_values = set(
                CapabilityNormalizer.normalize_list(
                    previous_capabilities.get(
                        field,
                        []
                    )
                )
            )

            current_values = set(
                CapabilityNormalizer.normalize_list(
                    current_capabilities.get(
                        field,
                        []
                    )
                )
            )

            merged[field] = sorted(
                previous_values | current_values
            )

        return merged

    @classmethod
    def calculate_delta(
        cls,
        previous: dict[str, Any] | None,
        merged_capabilities: dict[str, list[str]],
    ) -> dict[str, Any]:

        previous_capabilities = {}

        if previous:
            previous_capabilities = (
                previous.get(
                    "capabilities",
                    {}
                )
            )

        delta = {
            "previous_version": (
                previous.get(
                    "profile_version"
                )
                if previous
                else None
            ),
            "added_skills": [],
            "added_tools": [],
            "added_technologies": [],
            "added_methodologies": [],
            "added_domains": [],
            "added_functional_areas": [],
            "added_role_signals": [],
        }

        mapping = {
            "skills": "added_skills",
            "tools": "added_tools",
            "technologies": "added_technologies",
            "methodologies": "added_methodologies",
            "domains": "added_domains",
            "functional_areas": "added_functional_areas",
            "role_signals": "added_role_signals",
        }

        for field, delta_field in mapping.items():

            previous_values = set(
                CapabilityNormalizer.normalize_list(
                    previous_capabilities.get(
                        field,
                        []
                    )
                )
            )

            merged_values = set(
                CapabilityNormalizer.normalize_list(
                    merged_capabilities.get(
                        field,
                        []
                    )
                )
            )

            delta[delta_field] = sorted(
                merged_values - previous_values
            )

        return delta

    def save_profile(
        self,
        profile: dict[str, Any],
    ) -> dict[str, Any]:

        # ---------------------------------------------------------
        # 1. Normalize the newly analyzed profile
        # ---------------------------------------------------------

        profile = self.normalize_profile(
            profile
        )

        # ---------------------------------------------------------
        # 2. Load previous profile
        # ---------------------------------------------------------

        previous = self.get_current_profile()

        # ---------------------------------------------------------
        # 3. Normalize previous profile for comparison
        # ---------------------------------------------------------

        normalized_previous = None

        if previous is not None:
            normalized_previous = dict(
                previous
            )

            normalized_previous = (
                self.normalize_profile(
                    normalized_previous
                )
            )

        # ---------------------------------------------------------
        # 4. Merge cumulative capabilities
        # ---------------------------------------------------------

        merged_capabilities = (
            self.merge_capabilities(
                normalized_previous,
                profile,
            )
        )

        # ---------------------------------------------------------
        # 5. Calculate capability delta
        # ---------------------------------------------------------

        delta = self.calculate_delta(
            normalized_previous,
            merged_capabilities,
        )

        # ---------------------------------------------------------
        # 6. Determine whether anything actually changed
        # ---------------------------------------------------------

        has_changes = any(
            delta[field]
            for field in [
                "added_skills",
                "added_tools",
                "added_technologies",
                "added_methodologies",
                "added_domains",
                "added_functional_areas",
                "added_role_signals",
            ]
        )

        # ---------------------------------------------------------
        # 7. Existing profile is unchanged
        # ---------------------------------------------------------

        if (
            normalized_previous is not None
            and not has_changes
        ):

            # Keep the existing version
            profile["profile_version"] = (
                normalized_previous.get(
                    "profile_version"
                )
            )

            # Keep the original generation timestamp
            profile["generated_at"] = (
                normalized_previous.get(
                    "generated_at"
                )
            )

            # Store the normalized cumulative capabilities
            profile["capabilities"] = (
                merged_capabilities
            )

            # Keep previous delta version reference
            delta["current_version"] = (
                normalized_previous.get(
                    "profile_version"
                )
            )

            # Save normalized current profile
            with CURRENT_PROFILE_PATH.open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    profile,
                    file,
                    indent=2,
                    ensure_ascii=False,
                )

            # Save delta
            with PROFILE_DELTA_PATH.open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    delta,
                    file,
                    indent=2,
                    ensure_ascii=False,
                )

            return profile

        # ---------------------------------------------------------
        # 8. Create a new profile version
        # ---------------------------------------------------------

        new_version = self.get_next_version()

        profile["profile_version"] = (
            new_version
        )

        profile["generated_at"] = (
            self.utc_now()
        )

        profile["capabilities"] = (
            merged_capabilities
        )

        delta["current_version"] = (
            new_version
        )

        # ---------------------------------------------------------
        # 9. Save versioned profile
        # ---------------------------------------------------------

        versioned_profile_path = (
            PROFILES_DIR
            / f"profile_{new_version}.json"
        )

        with versioned_profile_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                profile,
                file,
                indent=2,
                ensure_ascii=False,
            )

        # ---------------------------------------------------------
        # 10. Save current profile
        # ---------------------------------------------------------

        with CURRENT_PROFILE_PATH.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                profile,
                file,
                indent=2,
                ensure_ascii=False,
            )

        # ---------------------------------------------------------
        # 11. Save capability delta
        # ---------------------------------------------------------

        with PROFILE_DELTA_PATH.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                delta,
                file,
                indent=2,
                ensure_ascii=False,
            )

        return profile


if __name__ == "__main__":

    print("=" * 60)
    print("JOBPILOT CANDIDATE PROFILE SERVICE")
    print("=" * 60)

    service = CandidateProfileService()

    profile = service.get_current_profile()

    if profile is None:
        print("No current candidate profile found.")
    else:
        print(
            f"Current profile: "
            f"{profile.get('profile_version')}"
        )