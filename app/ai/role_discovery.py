from pathlib import Path
from datetime import datetime, timezone
from typing import Literal
import json
import os

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROFILE_PATH = (
    PROJECT_ROOT
    / "data"
    / "candidate"
    / "current_profile.json"
)
OUTPUT_PATH = PROJECT_ROOT / "data" / "role_universe.json"


# ---------------------------------------------------------
# Load environment variables
# ---------------------------------------------------------

load_dotenv(PROJECT_ROOT / ".env")


# ---------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------

class Role(BaseModel):
    canonical_title: str = Field(
        description="The canonical job title representing the role."
    )

    role_family: str = Field(
        description="The broader family or functional area of the role."
    )

    relevance: Literal["HIGH", "MEDIUM", "LOW"] = Field(
        description="How strongly the role aligns with the candidate profile."
    )

    search_variants: list[str] = Field(
        description="Alternative job titles companies may use for the same role."
    )

    related_keywords: list[str] = Field(
        description="Keywords useful for discovering jobs belonging to this role."
    )

    matching_experience: list[str] = Field(
        description="Specific candidate experience, skills or domains supporting the role."
    )

    rationale: str = Field(
        description="Concise explanation of why this role is supported by the candidate profile."
    )


class RoleUniverse(BaseModel):
    candidate_profile_version: str = Field(
        description="Version of the candidate profile used for generation."
    )

    generated_at: str = Field(
        description="UTC timestamp when the role universe was generated."
    )

    roles: list[Role] = Field(
        description="AI-generated canonical role universe."
    )


# ---------------------------------------------------------
# Role Discovery Engine
# ---------------------------------------------------------

class RoleDiscovery:

    def __init__(self):
        self.profile = self.load_profile()

        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY was not found. "
                "Add it to the .env file in the project root."
            )

        self.client = OpenAI(api_key=api_key)

    # -----------------------------------------------------
    # Load candidate profile
    # -----------------------------------------------------

    def load_profile(self) -> dict:

        if not PROFILE_PATH.exists():
            raise FileNotFoundError(
                f"Candidate profile not found: {PROFILE_PATH}"
            )

        with open(PROFILE_PATH, "r", encoding="utf-8") as file:
            return json.load(file)


    # -----------------------------------------------------
    # Check whether role universe is current
    # -----------------------------------------------------

    def role_universe_is_current(
        self,
    ) -> bool:

        existing = self.load_existing_role_universe()

        if existing is None:
            return False

        current_profile_version = (
            self.profile.get(
                "profile_version"
            )
        )

        existing_profile_version = (
            existing.get(
                "candidate_profile_version"
            )
        )

        return (
            current_profile_version
            == existing_profile_version
        )


    # -----------------------------------------------------
    # Load existing role universe
    # -----------------------------------------------------

    def load_existing_role_universe(
        self,
    ) -> dict | None:

        if not OUTPUT_PATH.exists():
            return None

        with open(
            OUTPUT_PATH,
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    # -----------------------------------------------------
    # Build AI instructions
    # -----------------------------------------------------

    def build_prompt(self) -> str:

        profile_json = json.dumps(
            self.profile,
            indent=2,
            ensure_ascii=False
        )

        return f"""
You are the Role Discovery Engine for JobPilot.

Your task is to analyze the candidate profile below and generate a
comprehensive but realistic job-role universe.

This is NOT job search yet.

Do NOT search for companies.
Do NOT generate individual job vacancies.
Do NOT generate URLs.
Do NOT evaluate visa sponsorship.

Your task is only to determine which professional roles should be
searched for later.

============================================================
CANDIDATE PROFILE
============================================================

{profile_json}

============================================================
ROLE DISCOVERY RULES
============================================================

1. Derive roles from the candidate's actual documented experience,
   skills, responsibilities, domains and projects.

2. Do not invent experience that is not supported by the profile.

3. The candidate is primarily positioned around:
   - Business Analysis
   - Business Systems / Functional Analysis
   - Digital Transformation
   - Process Transformation
   - Insurance / BFSI
   - Data and Analytics
   - Data Migration
   - CRM
   - RPA / Automation
   - AI transformation and AI-enabled business analysis

   These are themes to evaluate, NOT a predefined role list.
   You must determine the actual roles from the candidate profile.

4. Discover role titles that companies may realistically use even if
   those exact titles are not present in the candidate's CV.

5. Separate:
   - canonical roles
   - search variants

Example:

Canonical role:
Senior Business Analyst

Search variants:
- Senior Business Analyst
- Senior BA

These variants represent the same underlying role and should not
be treated as separate canonical roles.

6. Search variants should represent realistic terminology used by
   employers internationally.

7. Avoid duplicate or near-duplicate canonical roles.

8. Do not create overly broad roles simply because the candidate has
   some exposure to a technology.

For example, exposure to AWS does not automatically justify:
- Cloud Engineer
- AWS Solutions Architect

9. Distinguish business-facing roles from engineering roles.

The candidate should not be classified as an engineer merely because
the profile contains technical tools.

10. AI-related roles are allowed where the candidate's documented
   experience supports business-facing AI, automation, transformation,
   use-case discovery, process analysis or AI adoption.

Do NOT infer that the candidate is:
- Machine Learning Engineer
- Data Scientist
- AI Researcher

unless the profile explicitly supports those roles.

11. Insurance roles should reflect the candidate's documented
    insurance/BFSI experience.

12. Data roles should focus on business-facing analytics, requirements,
    migration and transformation rather than advanced data engineering
    unless explicitly supported.

13. Product roles should remain business-analysis/product-delivery
    oriented unless the candidate has documented product ownership.

14. Functional consulting roles are appropriate where the candidate's
    experience supports requirements, configuration support,
    implementation, UAT, migration or business-user coordination.

15. Generate approximately 15-30 canonical roles.

16. Use these relevance levels:

HIGH:
Strongly supported by multiple aspects of the candidate profile.

MEDIUM:
Reasonably supported but with some limitations or narrower applicability.

LOW:
Potentially relevant but requires significant additional evidence.

17. For every role provide:
- canonical_title
- role_family
- relevance
- search_variants
- related_keywords
- matching_experience
- rationale

18. Do not rank roles by "best" or "worst".

19. Do not use visa eligibility or sponsorship availability when
    determining professional relevance.

20. The output must represent a reusable role taxonomy that JobPilot
    can later feed into its job-search engine.

Return ONLY the structured RoleUniverse object.
"""


    # -----------------------------------------------------
    # Generate role universe
    # -----------------------------------------------------

    def generate_roles(self) -> RoleUniverse:

        print("Analyzing candidate profile...")
        print("Generating role universe...")

        prompt = self.build_prompt()

        response = self.client.responses.parse(
            model="gpt-5.6-luna",
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional job-role taxonomy "
                        "engine. Follow the supplied schema exactly."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            text_format=RoleUniverse
        )

        role_universe = response.output_parsed

        if role_universe is None:
            raise ValueError(
                "The model did not return a structured RoleUniverse."
            )

        return role_universe

    # -----------------------------------------------------
    # Save role universe
    # -----------------------------------------------------

    def save_role_universe(self, role_universe: RoleUniverse):

        OUTPUT_PATH.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(
            OUTPUT_PATH,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                role_universe.model_dump(),
                file,
                indent=2,
                ensure_ascii=False
            )

        print()
        print(f"Role universe saved to:")
        print(OUTPUT_PATH)

    # -----------------------------------------------------
    # Main workflow
    # -----------------------------------------------------

    def run(self):

        current_profile_version = (
            self.profile.get(
                "profile_version"
            )
        )

        print(
            f"Candidate profile version: "
            f"{current_profile_version}"
        )

        # -------------------------------------------------
        # Check whether existing role universe is current
        # -------------------------------------------------

        if self.role_universe_is_current():

            existing = (
                self.load_existing_role_universe()
            )

            print()
            print(
                "Role universe is already current."
            )

            print(
                f"Existing roles: "
                f"{len(existing.get('roles', []))}"
            )

            return RoleUniverse.model_validate(
                existing
            )

        # -------------------------------------------------
        # Generate new role universe
        # -------------------------------------------------

        print()
        print(
            "Role universe is outdated or missing."
        )

        print(
            "Generating a new role universe..."
        )

        role_universe = self.generate_roles()

        # -------------------------------------------------
        # Tie role universe to candidate profile version
        # -------------------------------------------------

        role_universe.candidate_profile_version = (
            current_profile_version
        )

        self.save_role_universe(
            role_universe
        )

        print()
        print(
            f"Generated "
            f"{len(role_universe.roles)} "
            f"canonical roles."
        )

        print()
        print(
            "Role universe generation "
            "completed successfully."
        )

        return role_universe


# ---------------------------------------------------------
# Entry point
# ---------------------------------------------------------

if __name__ == "__main__":

    discovery = RoleDiscovery()

    result = discovery.run()

    print()

    for index, role in enumerate(result.roles, start=1):

        print(
            f"{index}. "
            f"{role.canonical_title} "
            f"[{role.relevance}]"
        )