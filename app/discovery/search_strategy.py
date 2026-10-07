from pathlib import Path
from datetime import datetime, timezone
import json

from pydantic import BaseModel, Field


PROJECT_ROOT = (
    Path(__file__).resolve().parents[2]
)

ROLE_UNIVERSE_PATH = (
    PROJECT_ROOT
    / "data"
    / "role_universe.json"
)

CAPABILITY_REGISTRY_PATH = (
    PROJECT_ROOT
    / "data"
    / "sources"
    / "source_capability_registry.json"
)

# Current versioned candidate profile.
CANDIDATE_PROFILE_PATH = (
    PROJECT_ROOT
    / "data"
    / "candidate"
    / "current_profile.json"
)

SEARCH_PLAN_PATH = (
    PROJECT_ROOT
    / "data"
    / "jobs"
    / "search_plan.json"
)


class SearchTask(BaseModel):
    """
    A single planned job-discovery operation.
    """

    task_id: str

    canonical_role: str
    search_variant: str

    role_relevance: str

    source_name: str
    source_category: str
    strategy: str

    location_scope: str

    query: str

    priority: str

    rationale: str

    source_domain: str | None = None


class SearchPlan(BaseModel):
    """
    Complete set of search tasks generated for the
    current role universe and available sources.
    """

    generated_at: str

    candidate_profile_version: str | None = None

    total_roles: int
    total_sources: int
    total_tasks: int

    tasks: list[SearchTask] = Field(
        default_factory=list
    )


class SearchStrategy:

    def __init__(self):

        self.role_universe = (
            self.load_json(
                ROLE_UNIVERSE_PATH
            )
        )

        self.capability_registry = (
            self.load_json(
                CAPABILITY_REGISTRY_PATH
            )
        )

        self.candidate_profile = (
            self.load_json(
                CANDIDATE_PROFILE_PATH,
                required=True
            )
        )

    # --------------------------------------------------
    # Generic file loading
    # --------------------------------------------------

    @staticmethod
    def load_json(
        path: Path,
        required: bool = True
    ):

        if not path.exists():

            if required:
                raise FileNotFoundError(
                    f"Required file not found: {path}"
                )

            return {}

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    # --------------------------------------------------
    # Role handling
    # --------------------------------------------------

    def get_roles(self):

        return self.role_universe.get(
            "roles",
            []
        )

    @staticmethod
    def get_role_relevance(role) -> str:

        return str(
            role.get(
                "relevance",
                "MEDIUM"
            )
        ).upper()

    @staticmethod
    def get_search_variants(role) -> list[str]:

        variants = role.get(
            "search_variants",
            []
        )

        canonical_title = role.get(
            "canonical_title"
        )

        if not variants and canonical_title:

            variants = [
                canonical_title
            ]

        return variants

    # --------------------------------------------------
    # Source handling
    # --------------------------------------------------

    def get_sources(self):

        return self.capability_registry.get(
            "capabilities",
            []
        )

    # --------------------------------------------------
    # Candidate profile
    # --------------------------------------------------

    def get_profile_version(self):

        return self.candidate_profile.get(
            "profile_version"
        )

    def get_location_scope(self) -> str:
        """
        Extract a geographic preference from the
        candidate profile without hardcoding countries.

        If the profile does not contain a usable
        location preference, retain international scope.
        """

        profile = self.candidate_profile

        possible_fields = [
            "target_locations",
            "target_countries",
            "preferred_locations",
            "preferred_countries",
            "relocation_targets",
            "location_preferences",
            "job_search_locations",
        ]

        for field in possible_fields:

            value = profile.get(field)

            if value:

                if isinstance(value, list):

                    return ", ".join(
                        str(item)
                        for item in value
                    )

                return str(value)

        return "INTERNATIONAL_OUTSIDE_INDIA"

    # --------------------------------------------------
    # Source suitability
    # --------------------------------------------------

    @staticmethod
    def source_is_searchable(source) -> bool:

        strategy = source.get(
            "recommended_strategy",
            "UNSUPPORTED"
        )

        return strategy != "UNSUPPORTED"

    @staticmethod
    def source_priority(
        source
    ) -> int:
        """
        Generic source priority.

        This is based on source capability,
        not on specific provider names.
        """

        strategy = source.get(
            "recommended_strategy"
        )

        category = source.get(
            "source_category"
        )

        score = 0

        if strategy == "DIRECT_SEARCH":
            score += 40

        elif strategy == "DIRECT_SOURCE_DISCOVERY":
            score += 35

        elif strategy == "SEARCH_ENGINE_DISCOVERY":
            score += 30

        elif strategy == "DYNAMIC_DOMAIN_DISCOVERY":
            score += 25

        if category in {
            "JOB_NETWORK",
            "JOB_AGGREGATOR",
            "JOB_BOARD",
        }:
            score += 10

        elif category == "ATS_PLATFORM":
            score += 15

        elif category == "PUBLIC_EMPLOYMENT":
            score += 10

        elif category == "INDUSTRY_PORTAL":
            score += 10

        return score

    # --------------------------------------------------
    # Query construction
    # --------------------------------------------------

    def build_query(
        self,
        role_variant: str,
        source: dict,
        location_scope: str
    ) -> str:

        strategy = source.get(
            "recommended_strategy"
        )

        domain = source.get(
            "domain"
        )

        base = (
            f'"{role_variant}" jobs'
        )

        if (
            location_scope
            != "INTERNATIONAL_OUTSIDE_INDIA"
        ):

            base = (
                f'{base} '
                f'{location_scope}'
            )

        else:

            base = (
                f'{base} international'
            )

        if strategy == "SEARCH_ENGINE_DISCOVERY":

            if (
                domain
                and not domain.startswith("varies")
            ):

                return (
                    f'{base} '
                    f'site:{domain}'
                )

            return base

        if strategy == "DYNAMIC_DOMAIN_DISCOVERY":

            return (
                f'{base} '
                f'career OR careers'
            )

        if strategy == "DIRECT_SOURCE_DISCOVERY":

            return base

        return base

    # --------------------------------------------------
    # Task rationale
    # --------------------------------------------------

    @staticmethod
    def build_rationale(
        role: dict,
        source: dict
    ) -> str:

        role_title = role.get(
            "canonical_title",
            "Unknown role"
        )

        source_name = source.get(
            "source_name",
            "Unknown source"
        )

        strategy = source.get(
            "recommended_strategy",
            "UNKNOWN"
        )

        return (
            f"Search for the candidate-relevant role "
            f"'{role_title}' using '{source_name}' "
            f"through the {strategy} strategy."
        )

    # --------------------------------------------------
    # Priority
    # --------------------------------------------------

    def calculate_priority(
        self,
        role: dict,
        source: dict
    ) -> str:

        relevance = (
            self.get_role_relevance(role)
        )

        source_score = (
            self.source_priority(source)
        )

        if (
            relevance == "HIGH"
            and source_score >= 40
        ):

            return "HIGH"

        if (
            relevance == "HIGH"
            and source_score >= 30
        ):

            return "HIGH"

        if relevance == "HIGH":

            return "MEDIUM"

        if (
            relevance == "MEDIUM"
            and source_score >= 40
        ):

            return "MEDIUM"

        return "LOW"

    # --------------------------------------------------
    # Search variant selection
    # --------------------------------------------------

    @staticmethod
    def select_variants(
        role
    ) -> list[str]:

        """
        Select canonical title plus up to two
        unique variants.
        """

        canonical = role.get(
            "canonical_title"
        )

        variants = role.get(
            "search_variants",
            []
        )

        if not variants and canonical:

            return [canonical]

        unique_variants = []

        seen = set()

        for variant in variants:

            if not variant:
                continue

            value = str(
                variant
            ).strip()

            normalized = value.lower()

            if (
                normalized
                and normalized not in seen
            ):

                seen.add(normalized)

                unique_variants.append(
                    value
                )

        if canonical:

            canonical_value = str(
                canonical
            ).strip()

            if (
                canonical_value.lower()
                not in seen
            ):

                unique_variants.insert(
                    0,
                    canonical_value
                )

        return unique_variants[:3]

    @staticmethod
    def select_variants_for_source(
        role,
        source
    ) -> list[str]:

        """
        Select search variants based on role intent
        and source category.

        This controls task volume while preserving
        meaningful search coverage.
        """

        canonical = str(
            role.get(
                "canonical_title",
                ""
            )
        ).strip()

        variants = role.get(
            "search_variants",
            []
        )

        source_category = source.get(
            "source_category"
        )

        if not canonical:

            return []

        # --------------------------------------------------
        # Build clean ordered variant list
        # --------------------------------------------------

        all_variants = []

        seen = set()

        for value in (
            [canonical] + variants
        ):

            if not value:
                continue

            value = str(
                value
            ).strip()

            normalized = value.lower()

            if (
                normalized
                and normalized not in seen
            ):

                seen.add(normalized)

                all_variants.append(
                    value
                )

        if not all_variants:

            return []

        # --------------------------------------------------
        # Source-specific search coverage
        # --------------------------------------------------

        if source_category == "JOB_NETWORK":

            return all_variants[:2]

        if source_category == "JOB_AGGREGATOR":

            return all_variants[:2]

        if source_category == "JOB_BOARD":

            return all_variants[:2]

        if source_category == "ATS_PLATFORM":

            return all_variants[:1]

        if source_category == "DISCOVERY_LAYER":

            return all_variants[:1]

        if source_category == "PUBLIC_EMPLOYMENT":

            return all_variants[:1]

        if source_category == "EMPLOYER_CAREERS":

            return all_variants[:1]

        if source_category == "INDUSTRY_PORTAL":

            return all_variants[:2]

        return all_variants[:1]

    # --------------------------------------------------
    # Source suitability
    # --------------------------------------------------

    @staticmethod
    def select_sources_for_role(
        role,
        sources
    ) -> list[dict]:
        """
        Select suitable sources based on role intent and
        deterministic source-coverage limits.

        The goal is to preserve source diversity while
        preventing excessive search-task multiplication.
        """

        title = str(
            role.get(
                "canonical_title",
                ""
            )
        ).lower()

        keywords = role.get(
            "related_keywords",
            []
        )

        role_text = (
            f"{title} "
            f"{' '.join(str(k).lower() for k in keywords)}"
        )

        relevance = SearchStrategy.get_role_relevance(role)

        def has_any(*terms):
            return any(
                term in role_text
                for term in terms
            )

        # --------------------------------------------------
        # Role intent detection
        # --------------------------------------------------

        is_insurance = has_any(
            "insurance",
            "insurer",
            "life insurance",
            "policy",
            "claims",
        )

        is_ai = has_any(
            "ai",
            "artificial intelligence",
            "machine learning",
            "genai",
            "generative ai",
        )

        is_data = has_any(
            "data",
            "analytics",
            "business intelligence",
            "bi",
            "data migration",
            "data quality",
        )

        is_crm = has_any(
            "crm",
            "dynamics",
            "microsoft dynamics",
        )

        is_automation = has_any(
            "automation",
            "rpa",
            "robotic process",
            "process automation",
        )

        is_transformation = has_any(
            "transformation",
            "digital",
            "process improvement",
            "process re-engineering",
            "bpr",
        )

        is_technology = has_any(
            "technical",
            "technology",
            "systems",
            "solution",
            "it",
            "software",
        )

        is_general_ba = any(
            phrase in title
            for phrase in [
                "business analyst",
                "functional analyst",
                "process analyst",
            ]
        )

        # --------------------------------------------------
        # Source categories
        # --------------------------------------------------

        core_categories = {
            "JOB_NETWORK",
            "JOB_AGGREGATOR",
            "JOB_BOARD",
            "ATS_PLATFORM",
        }

        supplementary_categories = {
            "PUBLIC_EMPLOYMENT"
        }

        dynamic_categories = {
            "EMPLOYER_CAREERS"
        }

        # --------------------------------------------------
        # Source limits
        #
        # These limits prevent one role from generating
        # dozens of almost-identical searches.
        # --------------------------------------------------

        if relevance == "HIGH":
            max_job_boards = 4
        elif relevance == "MEDIUM":
            max_job_boards = 3
        else:
            max_job_boards = 2

        source_limits = {
            "JOB_NETWORK": 1,
            "JOB_AGGREGATOR": 1,
            "JOB_BOARD": max_job_boards,
            "ATS_PLATFORM": 2,
            "PUBLIC_EMPLOYMENT": 1,
            "EMPLOYER_CAREERS": 2,
        }

        # --------------------------------------------------
        # Specialist source eligibility
        # --------------------------------------------------

        employer_relevant = (
            is_insurance
            or is_ai
            or is_data
            or is_crm
            or is_automation
            or is_transformation
            or is_technology
        )

        public_employment_relevant = (
            is_general_ba
            or is_insurance
            or is_technology
            or is_data
            or is_transformation
        )

        # --------------------------------------------------
        # Group eligible sources by category
        # --------------------------------------------------

        grouped_sources = {}

        for source in sources:

            category = source.get(
                "source_category"
            )

            strategy = source.get(
                "recommended_strategy"
            )

            if category not in (
                core_categories
                | supplementary_categories
                | dynamic_categories
            ):
                continue

            # Employer career sources are only relevant
            # when the role has a corresponding domain.
            if category == "EMPLOYER_CAREERS":
                if (
                    strategy == "DYNAMIC_DOMAIN_DISCOVERY"
                    and not employer_relevant
                ):
                    continue

            # Public employment is supplementary rather
            # than universal.
            if category == "PUBLIC_EMPLOYMENT":
                if not public_employment_relevant:
                    continue

            grouped_sources.setdefault(
                category,
                []
            ).append(source)

        # --------------------------------------------------
        # Rank sources deterministically
        #
        # Higher capability sources are preferred.
        # Source name is used only as a stable tie-breaker.
        # --------------------------------------------------

        for category in grouped_sources:

            grouped_sources[category].sort(
                key=lambda source: (
                    -SearchStrategy.source_priority(source),
                    -float(
                        source.get(
                            "capability_confidence",
                            0
                        ) or 0
                    ),
                    str(
                        source.get(
                            "source_name",
                            ""
                        )
                    ).lower(),
                )
            )

        # --------------------------------------------------
        # Select capped source set
        # --------------------------------------------------

        selected = []

        for category, limit in source_limits.items():

            category_sources = grouped_sources.get(
                category,
                []
            )

            selected.extend(
                category_sources[:limit]
            )

        return selected
    # --------------------------------------------------
    # Task generation
    # --------------------------------------------------

    def generate_tasks(self):

        roles = self.get_roles()

        sources = [
            source
            for source in self.get_sources()
            if self.source_is_searchable(source)
        ]

        location_scope = (
            self.get_location_scope()
        )

        tasks = []

        task_number = 1

        for role in roles:

            relevance = (
                self.get_role_relevance(
                    role
                )
            )

            suitable_sources = (
                self.select_sources_for_role(
                    role,
                    sources
                )
            )

            for source in suitable_sources:

                variants = (
                    self.select_variants_for_source(
                        role,
                        source
                    )
                )

                for variant in variants:

                    query = self.build_query(
                        variant,
                        source,
                        location_scope
                    )

                    priority = (
                        self.calculate_priority(
                            role,
                            source
                        )
                    )

                    task = SearchTask(

                        task_id=(
                            f"SEARCH-{task_number:05d}"
                        ),

                        canonical_role=(
                            role.get(
                                "canonical_title"
                            )
                        ),

                        search_variant=variant,

                        role_relevance=relevance,

                        source_name=(
                            source.get(
                                "source_name"
                            )
                        ),

                        source_category=(
                            source.get(
                                "source_category"
                            )
                        ),

                        strategy=(
                            source.get(
                                "recommended_strategy"
                            )
                        ),

                        location_scope=(
                            location_scope
                        ),

                        query=query,

                        priority=priority,

                        rationale=(
                            self.build_rationale(
                                role,
                                source
                            )
                        ),

                        source_domain=(
                            source.get(
                                "domain"
                            )
                        ),
                    )

                    tasks.append(
                        task
                    )

                    task_number += 1

        return tasks

    # --------------------------------------------------
    # Deduplicate planned tasks
    # --------------------------------------------------

    @staticmethod
    def deduplicate_tasks(
        tasks: list[SearchTask]
    ) -> list[SearchTask]:

        unique_tasks = []

        seen = set()

        for task in tasks:

            key = (
                task.canonical_role,
                task.search_variant,
                task.source_name,
                task.strategy,
                task.location_scope,
                task.query,
            )

            if key in seen:

                continue

            seen.add(key)

            unique_tasks.append(
                task
            )

        return unique_tasks

    # --------------------------------------------------
    # Search plan diagnostics
    # --------------------------------------------------

    @staticmethod
    def print_diagnostics(
        tasks: list[SearchTask]
    ):

        """
        Print diagnostic information about the
        generated search tasks.

        Does not modify the search plan.
        """

        from collections import Counter

        print()
        print("=" * 60)
        print("SEARCH PLAN DIAGNOSTICS")
        print("=" * 60)

        print()
        print(
            f"Total search tasks: "
            f"{len(tasks)}"
        )

        # --------------------------------------------------
        # Tasks by role
        # --------------------------------------------------

        role_counts = Counter(
            task.canonical_role
            for task in tasks
        )

        print()
        print("TASKS BY ROLE")
        print("-" * 60)

        for role, count in (
            role_counts.most_common()
        ):

            print(
                f"{role:<45} {count:>5}"
            )

        # --------------------------------------------------
        # Tasks by source category
        # --------------------------------------------------

        category_counts = Counter(
            task.source_category
            for task in tasks
        )

        print()
        print("TASKS BY SOURCE CATEGORY")
        print("-" * 60)

        for category, count in (
            category_counts.most_common()
        ):

            print(
                f"{category:<30} {count:>5}"
            )

        # --------------------------------------------------
        # Tasks by source
        # --------------------------------------------------

        source_counts = Counter(
            task.source_name
            for task in tasks
        )

        print()
        print("TASKS BY SOURCE")
        print("-" * 60)

        for source, count in (
            source_counts.most_common()
        ):

            print(
                f"{source:<50} {count:>5}"
            )

        # --------------------------------------------------
        # Tasks by priority
        # --------------------------------------------------

        priority_counts = Counter(
            task.priority
            for task in tasks
        )

        print()
        print("TASKS BY PRIORITY")
        print("-" * 60)

        for priority, count in (
            priority_counts.most_common()
        ):

            print(
                f"{priority:<15} {count:>5}"
            )

        # --------------------------------------------------
        # Tasks by search strategy
        # --------------------------------------------------

        strategy_counts = Counter(
            task.strategy
            for task in tasks
        )

        print()
        print("TASKS BY SEARCH STRATEGY")
        print("-" * 60)

        for strategy, count in (
            strategy_counts.most_common()
        ):

            print(
                f"{strategy:<35} {count:>5}"
            )

        print()
        print("=" * 60)

    # --------------------------------------------------
    # Build search plan
    # --------------------------------------------------

    def build_plan(self):

        tasks = self.generate_tasks()

        tasks = self.deduplicate_tasks(
            tasks
        )

        self.print_diagnostics(
            tasks
        )

        return SearchPlan(

            generated_at=(
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),

            candidate_profile_version=(
                self.get_profile_version()
            ),

            total_roles=len(
                self.get_roles()
            ),

            total_sources=len(
                self.get_sources()
            ),

            total_tasks=len(
                tasks
            ),

            tasks=tasks,
        )

    # --------------------------------------------------
    # Save
    # --------------------------------------------------

    @staticmethod
    def save(
        plan: SearchPlan
    ):

        SEARCH_PLAN_PATH.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(
            SEARCH_PLAN_PATH,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                plan.model_dump(),
                file,
                indent=2,
                ensure_ascii=False
            )

        print()
        print(
            "Search plan saved to:"
        )

        print(
            SEARCH_PLAN_PATH
        )

    # --------------------------------------------------
    # Run
    # --------------------------------------------------

    def run(self):

        print(
            "Loading role universe..."
        )

        print(
            "Loading source capabilities..."
        )

        print(
            "Loading candidate profile..."
        )

        print(
            "Generating search plan..."
        )

        plan = self.build_plan()

        self.save(
            plan
        )

        print()

        print(
            f"Roles: {plan.total_roles}"
        )

        print(
            f"Sources: {plan.total_sources}"
        )

        print(
            f"Search tasks: {plan.total_tasks}"
        )

        print(
            f"Candidate profile: "
            f"{plan.candidate_profile_version}"
        )

        return plan


if __name__ == "__main__":

    strategy = SearchStrategy()

    strategy.run()