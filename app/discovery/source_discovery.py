from pathlib import Path
from datetime import datetime, timezone
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from app.models.source import SourceRegistry


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

PROJECT_ROOT = (
    Path(__file__).resolve().parents[2]
)

ROLE_UNIVERSE_PATH = (
    PROJECT_ROOT
    / "data"
    / "role_universe.json"
)

SOURCE_REGISTRY_PATH = (
    PROJECT_ROOT
    / "data"
    / "sources"
    / "source_registry.json"
)


# ---------------------------------------------------------
# Environment
# ---------------------------------------------------------

load_dotenv(
    PROJECT_ROOT / ".env"
)


# ---------------------------------------------------------
# Source Discovery
# ---------------------------------------------------------

class SourceDiscovery:

    def __init__(self):

        api_key = os.getenv(
            "OPENAI_API_KEY"
        )

        if not api_key:

            raise ValueError(
                "OPENAI_API_KEY was not found "
                "in the .env file."
            )

        self.client = OpenAI(
            api_key=api_key
        )

        self.role_universe = (
            self.load_role_universe()
        )

    # -----------------------------------------------------
    # Load role universe
    # -----------------------------------------------------

    def load_role_universe(self):

        if not ROLE_UNIVERSE_PATH.exists():

            raise FileNotFoundError(
                f"Role universe not found: "
                f"{ROLE_UNIVERSE_PATH}"
            )

        with open(
            ROLE_UNIVERSE_PATH,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    # -----------------------------------------------------
    # Load existing source registry
    # -----------------------------------------------------

    def load_existing_registry(self):

        if not SOURCE_REGISTRY_PATH.exists():

            return None

        with open(
            SOURCE_REGISTRY_PATH,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    # -----------------------------------------------------
    # Check whether source registry is current
    # -----------------------------------------------------

    def source_registry_is_current(self):

        existing = (
            self.load_existing_registry()
        )

        if existing is None:

            return False

        current_role_version = (
            self.role_universe.get(
                "candidate_profile_version"
            )
        )

        existing_role_version = (
            existing.get(
                "role_universe_version"
            )
        )

        return (
            current_role_version
            == existing_role_version
        )

    # -----------------------------------------------------
    # Build discovery prompt
    # -----------------------------------------------------

    def build_prompt(self):

        roles = [
            role["canonical_title"]
            for role in self.role_universe["roles"]
        ]

        prompt = f"""
You are the Source Discovery Engine for JobPilot.

JobPilot is an international job discovery system.

The system has already generated the following candidate role
universe:

{json.dumps(roles, indent=2)}

Your task is NOT to find individual jobs.

Your task is to identify categories and types of online sources
that can be used to discover vacancies matching these roles.

Consider sources such as:

- job aggregators
- professional job networks
- regional job boards
- specialist job boards
- employer career sites
- applicant tracking systems
- recruitment platforms
- government or public employment portals
- industry-specific employment portals
- international employment portals

IMPORTANT:

Do not assume that the list of sources is fixed.

The architecture must remain extensible.

Do not restrict the result to commonly known platforms.

Identify source categories that could provide relevant international
vacancies for this candidate.

For each source provide:

- name
- source_type
- domain
- search_url if known
- whether an API may exist
- whether web search can discover jobs
- whether structured job data may be available
- likely access method
- why the source could be relevant

Do NOT generate individual job vacancies.

Do NOT generate fake URLs.

Do NOT invent API availability.

If something is uncertain, represent it as uncertain.

The output should describe potential job sources, not guarantee that
JobPilot can programmatically access them.
"""

        return prompt

    # -----------------------------------------------------
    # Discover sources
    # -----------------------------------------------------

    def discover(self):

        prompt = self.build_prompt()

        response = self.client.responses.parse(
            model="gpt-5.6-luna",

            input=[
                {
                    "role": "system",
                    "content": (
                        "You are a job-source discovery "
                        "engine. Follow the supplied "
                        "structured schema exactly."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            text_format=SourceRegistry
        )

        registry = response.output_parsed

        if registry is None:

            raise ValueError(
                "The model did not return "
                "a structured source registry."
            )

        registry.generated_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        registry.role_universe_version = (
            self.role_universe.get(
                "candidate_profile_version"
            )
        )

        return registry

    # -----------------------------------------------------
    # Save registry
    # -----------------------------------------------------

    def save_registry(
        self,
        registry
    ):

        SOURCE_REGISTRY_PATH.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(
            SOURCE_REGISTRY_PATH,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                registry.model_dump(),
                file,
                indent=2,
                ensure_ascii=False
            )

        print()
        print(
            "Source registry saved to:"
        )

        print(
            SOURCE_REGISTRY_PATH
        )

    # -----------------------------------------------------
    # Run
    # -----------------------------------------------------

    def run(self):

        print(
            "Loading role universe..."
        )

        print(
            f"Role universe version: "
            f"{self.role_universe.get('candidate_profile_version')}"
        )

        # -------------------------------------------------
        # Check existing registry
        # -------------------------------------------------

        if self.source_registry_is_current():

            existing = (
                self.load_existing_registry()
            )

            print()
            print(
                "Source registry is already current."
            )

            print(
                f"Existing sources: "
                f"{len(existing.get('sources', []))}"
            )

            return SourceRegistry.model_validate(
                existing
            )

        # -------------------------------------------------
        # Generate source registry
        # -------------------------------------------------

        print()
        print(
            "Source registry is outdated or missing."
        )

        print(
            "Discovering job sources..."
        )

        registry = self.discover()

        self.save_registry(
            registry
        )

        print()

        print(
            f"Discovered "
            f"{len(registry.sources)} "
            f"potential job sources."
        )

        print()

        print(
            "Source discovery completed successfully."
        )

        return registry


# ---------------------------------------------------------
# Entry point
# ---------------------------------------------------------

if __name__ == "__main__":

    discovery = SourceDiscovery()

    result = discovery.run()

    print()

    for index, source in enumerate(
        result.sources,
        start=1
    ):

        print(
            f"{index}. "
            f"{source.name}"
        )