from dataclasses import dataclass, field
from typing import Any


@dataclass
class CapabilityEvidence:
    """
    Represents a candidate capability together with the evidence
    supporting that capability.

    This prevents JobPilot from treating every CV keyword as
    equivalent professional experience.
    """

    name: str

    category: str

    evidence: list[str] = field(
        default_factory=list
    )

    evidence_source: list[str] = field(
        default_factory=list
    )

    evidence_strength: str = "explicit"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "evidence": self.evidence,
            "evidence_source": self.evidence_source,
            "evidence_strength": self.evidence_strength,
        }