from dataclasses import dataclass, field
from typing import Any


@dataclass
class CandidateProfile:
    """
    Versioned representation of the candidate's professional profile.

    The profile is cumulative. New CV versions can add capabilities
    without deleting previously established capabilities.
    """

    profile_version: str

    generated_at: str

    source_cv: str

    professional_summary: str = ""

    skills: list[str] = field(default_factory=list)

    tools: list[str] = field(default_factory=list)

    technologies: list[str] = field(default_factory=list)

    methodologies: list[str] = field(default_factory=list)

    domains: list[str] = field(default_factory=list)

    functional_areas: list[str] = field(default_factory=list)

    experience: list[dict[str, Any]] = field(
        default_factory=list
    )

    projects: list[dict[str, Any]] = field(
        default_factory=list
    )

    certifications: list[dict[str, Any]] = field(
        default_factory=list
    )

    education: list[dict[str, Any]] = field(
        default_factory=list
    )

    role_signals: list[str] = field(
        default_factory=list
    )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the candidate profile into a JSON-compatible
        dictionary.
        """

        return {
            "profile_version": self.profile_version,
            "generated_at": self.generated_at,
            "source_cv": self.source_cv,
            "professional_summary": self.professional_summary,

            "capabilities": {
                "skills": self.skills,
                "tools": self.tools,
                "technologies": self.technologies,
                "methodologies": self.methodologies,
                "domains": self.domains,
                "functional_areas": self.functional_areas,
            },

            "experience": self.experience,
            "projects": self.projects,
            "certifications": self.certifications,
            "education": self.education,
            "role_signals": self.role_signals,
        }