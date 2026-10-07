import re
from typing import Any


class CVProfileAnalyzer:
    """
    Deterministic first-stage CV profile analyzer.

    Extracts:
    - Professional summary
    - Skills
    - Tools
    - Technologies
    - Methodologies
    - Domains
    - Functional areas
    - Role signals
    - Experience
    - Projects
    - Certifications
    - Education

    The analyzer uses evidence explicitly present in the CV.
    Semantic AI enrichment can be added later.
    """

    SECTION_ALIASES = {
        "summary": [
            "summary",
            "professional summary",
            "profile",
            "professional profile",
            "objective",
        ],
        "skills": [
            "skills",
            "technical skills",
            "core skills",
            "key skills",
            "competencies",
        ],
        "experience": [
            "experience",
            "professional experience",
            "work experience",
            "employment history",
        ],
        "projects": [
            "projects",
            "key projects",
            "professional projects",
        ],
        "education": [
            "education",
            "academic background",
            "academic qualifications",
        ],
        "certifications": [
            "certifications",
            "certificates",
        ],
        "awards": [
            "awards",
            "awards and honors",
            "awards honors",
            "honors",
        ],
    }

    TOOL_TERMS = {
        "Jira",
        "GitHub",
        "Excel",
        "Confluence",
        "Tableau",
        "Power BI",
        "FineBI",
        "ClickHouse",
        "Hive",
        "Automation Anywhere",
        "GitLab",
        "Jenkins",
        "Docker",
        "Terraform",
        "Ansible",
    }

    TECHNOLOGY_TERMS = {
        "Python",
        "SQL",
        "GPT APIs",
        "IDP",
        "GenAI",
        "Generative AI",
        "LLM",
        "RPA",
        "DevOps",
        "AWS",
        "Azure",
        "Microsoft Dynamics 365",
    }

    METHODOLOGY_TERMS = {
        "BPMN",
        "Process Modelling",
        "Gap Analysis",
        "Requirements Gathering",
        "Requirements Elicitation",
        "User Stories",
        "Functional Requirements",
        "UAT",
        "Root Cause Analysis",
    }

    DOMAIN_TERMS = {
        "Life Insurance": [
            "life insurance",
            "life & p&c insurance",
            "life insurance",
        ],
        "P&C Insurance": [
            "p&c insurance",
            "p&c",
            "property and casualty",
            "automotive claims",
        ],
        "Digital Transformation": [
            "digital transformation",
            "digital transformation",
        ],
        "CRM": [
            "crm",
            "customer relationship management",
        ],
        "Data Analytics": [
            "data analytics",
            "business data analyst",
            "data analysis",
            "analytics",
        ],
    }

    FUNCTIONAL_AREA_TERMS = {
        "Requirements Engineering": [
            "requirements gathering",
            "requirements elicitation",
            "business requirements",
            "functional requirements",
            "functional specifications",
        ],
        "Process Modelling": [
            "process modelling",
            "process workflows",
            "current/future-state processes",
            "future-state processes",
        ],
        "Data Migration": [
            "data migration",
            "migration",
            "legacy and target platforms",
            "policy data",
        ],
        "Data Mapping": [
            "data mapping",
            "mapping",
        ],
        "UAT": [
            "uat",
            "uat scenarios",
            "user acceptance testing",
        ],
        "Defect Management": [
            "defect management",
            "production defects",
            "defect",
            "enhancement requests",
        ],
        "Stakeholder Management": [
            "stakeholder management",
            "stakeholder collaboration",
            "stakeholder/vendor coordination",
            "technical stakeholders",
        ],
        "Business Process Improvement": [
            "operational improvement",
            "process improvement",
            "streamlining",
        ],
        "AI Transformation": [
            "genai",
            "generative ai",
            "llm-powered",
            "ai-powered",
            "ai business analyst",
        ],
        "BRD/FRD Automation": [
            "brd/frd automation",
            "brd automation",
            "frd automation",
        ],
        "CR Analysis": [
            "cr analysis",
            "cr recommendation",
            "cr completeness",
        ],
    }

    ROLE_TERMS = {
        "Business Analyst": [
            "business analyst",
        ],
        "AI Business Analyst": [
            "ai business analyst",
        ],
        "Business Data Analyst": [
            "business data analyst",
        ],
        "Business Consultant": [
            "business consultant",
        ],
        "CRM Business Analyst": [
            "crm",
            "crm business requirements",
        ],
        "Insurance Business Analyst": [
            "insurance",
            "business analyst",
        ],
        "Data Migration Analyst": [
            "data migration",
            "migration",
        ],
        "AI Transformation Consultant": [
            "genai",
            "generative ai",
            "llm-powered",
            "ai-powered",
        ],
    }

    def analyze(
        self,
        text: str,
        source_cv: str,
    ) -> dict[str, Any]:

        sections = self.extract_sections(text)

        combined_text = "\n".join(
            sections.values()
        )

        skills = self.extract_skills(
            sections.get("skills", "")
        )

        tools = self.detect_terms(
            combined_text,
            self.TOOL_TERMS,
        )

        technologies = self.detect_terms(
            combined_text,
            self.TECHNOLOGY_TERMS,
        )

        methodologies = self.detect_terms(
            combined_text,
            self.METHODOLOGY_TERMS,
        )

        domains = self.detect_grouped_terms(
            combined_text,
            self.DOMAIN_TERMS,
        )

        functional_areas = self.detect_grouped_terms(
            combined_text,
            self.FUNCTIONAL_AREA_TERMS,
        )

        role_signals = self.detect_role_signals(
            combined_text
        )

        return {
            "source_cv": source_cv,

            "professional_summary": (
                sections.get(
                    "summary",
                    "",
                )
            ),

            "capabilities": {
                "skills": skills,
                "tools": tools,
                "technologies": technologies,
                "methodologies": methodologies,
                "domains": domains,
                "functional_areas": functional_areas,
                "role_signals": role_signals,
            },

            "capability_evidence": (
                self.build_capability_evidence(
                    sections
                )
            ),

            "experience": self.extract_entries(
                sections.get(
                    "experience",
                    "",
                )
            ),        }
    
    @staticmethod
    def find_evidence(
        capability: str,
        text: str,
        max_results: int = 3,
    ) -> list[str]:
        """
        Find meaningful CV lines containing the capability.

        Returns up to max_results unique lines.
        """

        if not text:
            return []

        capability_lower = capability.lower()
        matches = []
        seen = set()

        for line in text.splitlines():
            line = line.strip()

            if not line:
                continue

            if capability_lower not in line.lower():
                continue

            normalized_line = line.lower()

            if normalized_line in seen:
                continue

            seen.add(normalized_line)
            matches.append(line)

            if len(matches) >= max_results:
                break

        return matches

    @staticmethod
    def unique_evidence(
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Remove duplicate capability evidence records.

        A capability is unique by category + capability name.
        """

        seen = set()
        result = []

        for record in records:
            key = (
                record["category"].lower(),
                record["name"].lower(),
            )

            if key in seen:
                continue

            seen.add(key)
            result.append(record)

        return result


    def build_capability_evidence(
        self,
        sections: dict[str, str],
    ) -> list[dict[str, Any]]:
        """
        Build capability evidence using section-aware evidence selection.

        Evidence priority:
            1. Experience -> professional
            2. Certifications -> certification
            3. Skills -> explicit

        Technologies and tools are kept in their canonical categories
        and are not duplicated as generic skills.
        """

        evidence_records = []

        experience_text = sections.get("experience", "")
        skills_text = sections.get("skills", "")
        certifications_text = sections.get("certifications", "")

        def build_record(
            name: str,
            category: str,
            evidence: list[str],
            strength: str,
            source: str,
        ) -> None:

            if not evidence:
                return

            evidence_records.append({
                "name": name,
                "category": category,
                "evidence": evidence,
                "evidence_source": [source],
                "evidence_strength": strength,
            })

        # ---------------------------------------------------------
        # Technology evidence
        # ---------------------------------------------------------

        for technology in self.TECHNOLOGY_TERMS:

            experience_evidence = self.find_evidence(
                technology,
                experience_text,
            )

            certification_evidence = self.find_evidence(
                technology,
                certifications_text,
            )

            skills_evidence = self.find_evidence(
                technology,
                skills_text,
            )

            if experience_evidence:

                build_record(
                    name=technology,
                    category="technology",
                    evidence=experience_evidence,
                    strength="professional",
                    source="Experience",
                )

            elif certification_evidence:

                build_record(
                    name=technology,
                    category="technology",
                    evidence=certification_evidence,
                    strength="certification",
                    source="Certifications",
                )

            elif skills_evidence:

                build_record(
                    name=technology,
                    category="technology",
                    evidence=[
                        "Explicitly listed in the CV skills section."
                    ],
                    strength="explicit",
                    source="Skills",
                )

        # ---------------------------------------------------------
        # Tool evidence
        # ---------------------------------------------------------

        for tool in self.TOOL_TERMS:

            experience_evidence = self.find_evidence(
                tool,
                experience_text,
            )

            skills_evidence = self.find_evidence(
                tool,
                skills_text,
            )

            if experience_evidence:

                build_record(
                    name=tool,
                    category="tool",
                    evidence=experience_evidence,
                    strength="professional",
                    source="Experience",
                )

            elif skills_evidence:

                build_record(
                    name=tool,
                    category="tool",
                    evidence=[
                        "Explicitly listed in the CV skills section."
                    ],
                    strength="explicit",
                    source="Skills",
                )

        # ---------------------------------------------------------
        # Skill evidence
        # ---------------------------------------------------------

        # Technologies and tools already have their own canonical
        # categories. Do not duplicate them as generic skills.

        classified_capabilities = {
            technology.lower()
            for technology in self.TECHNOLOGY_TERMS
        }

        classified_capabilities.update(
            tool.lower()
            for tool in self.TOOL_TERMS
        )

        skills = self.extract_skills(
            skills_text
        )

        for skill in skills:

            if skill.lower() in classified_capabilities:
                continue

            experience_evidence = self.find_evidence(
                skill,
                experience_text,
            )

            skills_evidence = self.find_evidence(
                skill,
                skills_text,
            )

            if experience_evidence:

                build_record(
                    name=skill,
                    category="skill",
                    evidence=experience_evidence,
                    strength="professional",
                    source="Experience",
                )

            elif skills_evidence:

                build_record(
                    name=skill,
                    category="skill",
                    evidence=[
                        "Explicitly listed in the CV skills section."
                    ],
                    strength="explicit",
                    source="Skills",
                )

        return self.unique_evidence(
            evidence_records
        )

    def extract_sections(
        self,
        text: str,
    ) -> dict[str, str]:

        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        normalized_headers = {}

        for section_name, aliases in (
            self.SECTION_ALIASES.items()
        ):
            for alias in aliases:
                normalized_headers[
                    self.normalize_header(alias)
                ] = section_name

        sections = {}

        current_section = None

        for line in lines:

            normalized_line = (
                self.normalize_header(line)
            )

            if normalized_line in normalized_headers:

                current_section = (
                    normalized_headers[
                        normalized_line
                    ]
                )

                sections.setdefault(
                    current_section,
                    [],
                )

                continue

            if current_section is not None:

                sections.setdefault(
                    current_section,
                    [],
                ).append(line)

        return {
            section: "\n".join(content)
            for section, content
            in sections.items()
        }

    @staticmethod
    def normalize_header(
        value: str,
    ) -> str:

        value = value.lower().strip()

        value = re.sub(
            r"[^a-z0-9\s&/]",
            "",
            value,
        )

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value

    def extract_skills(
        self,
        text: str,
    ) -> list[str]:

        if not text:
            return []

        values = []

        for line in text.splitlines():

            line = line.strip()

            line = re.sub(
                r"^[•●▪◦\-*]\s*",
                "",
                line,
            )

            # Remove formatting artifacts such as
            # "Skills 1:" from parsed PDF text.
            line = re.sub(
                r"^skills?\s*\d*\s*:\s*",
                "",
                line,
                flags=re.IGNORECASE,
            )

            parts = re.split(
                r"[,|;]",
                line,
            )

            for part in parts:

                value = part.strip()

                if not value:
                    continue

                if value.lower() in {
                    "functional",
                    "skills",
                    "technical skills",
                }:
                    continue

                values.append(value)

        return self.unique(values)

    @staticmethod
    def detect_terms(
        text: str,
        terms: set[str],
    ) -> list[str]:

        text_lower = text.lower()

        detected = []

        for term in terms:

            if term.lower() in text_lower:

                detected.append(term)

        return sorted(
            detected,
            key=str.lower,
        )

    @staticmethod
    def detect_grouped_terms(
        text: str,
        groups: dict[str, list[str]],
    ) -> list[str]:

        text_lower = text.lower()

        detected = []

        for category, keywords in groups.items():

            for keyword in keywords:

                if keyword.lower() in text_lower:

                    detected.append(category)

                    break

        return sorted(
            set(detected),
            key=str.lower,
        )

    def detect_role_signals(
        self,
        text: str,
    ) -> list[str]:

        text_lower = text.lower()

        detected = []

        for role, keywords in self.ROLE_TERMS.items():

            if all(
                keyword.lower() in text_lower
                for keyword in keywords
            ):
                detected.append(role)

        return sorted(
            set(detected),
            key=str.lower,
        )

    @staticmethod
    def extract_entries(
        text: str,
    ) -> list[dict[str, str]]:

        if not text:
            return []

        entries = []

        for line in text.splitlines():

            line = line.strip()

            if not line:
                continue

            entries.append({
                "text": line
            })

        return entries

    @staticmethod
    def unique(
        values: list[str],
    ) -> list[str]:

        seen = set()

        result = []

        for value in values:

            key = value.lower().strip()

            if key not in seen:

                seen.add(key)

                result.append(value)

        return result