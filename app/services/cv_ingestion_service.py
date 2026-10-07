from pathlib import Path
from typing import Any

from app.readers.cv_reader import CVReader
from app.services.cv_profile_analyzer import CVProfileAnalyzer
from app.services.capability_normalizer import CapabilityNormalizer
from app.services.candidate_profile_service import (
    CandidateProfileService,
)


class CVIngestionService:
    """
    End-to-end CV ingestion service.

    Responsibilities:
    - Accept a CV file supplied by the application
    - Validate the file
    - Extract CV text
    - Analyze the CV
    - Normalize detected capabilities
    - Create a versioned candidate profile
    - Merge capabilities cumulatively
    - Calculate capability delta
    """

    SUPPORTED_EXTENSIONS = {
        ".pdf",
        ".docx",
    }

    def __init__(
        self,
        cv_reader: CVReader | None = None,
        profile_analyzer: CVProfileAnalyzer | None = None,
        profile_service: CandidateProfileService | None = None,
    ):
        self.cv_reader = (
            cv_reader
            or CVReader()
        )

        self.profile_analyzer = (
            profile_analyzer
            or CVProfileAnalyzer()
        )

        self.profile_service = (
            profile_service
            or CandidateProfileService()
        )

    def validate_cv(
        self,
        cv_path: Path,
    ) -> None:
        """
        Validate that the supplied file exists and
        has a supported CV format.
        """

        if not cv_path.exists():
            raise FileNotFoundError(
                f"CV file not found: {cv_path}"
            )

        if not cv_path.is_file():
            raise ValueError(
                f"CV path is not a file: {cv_path}"
            )

        extension = cv_path.suffix.lower()

        if extension not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported CV format: {extension}. "
                f"Supported formats: "
                f"{sorted(self.SUPPORTED_EXTENSIONS)}"
            )

    def ingest(
        self,
        cv_path: str | Path,
    ) -> dict[str, Any]:
        """
        Ingest a CV and create/update the candidate profile.

        Parameters
        ----------
        cv_path:
            Path supplied by the application/UI after
            the user uploads or selects a CV.

        Returns
        -------
        dict
            The generated versioned candidate profile.
        """

        cv_path = Path(cv_path)

        self.validate_cv(cv_path)

        # -------------------------------------------------
        # 1. Read CV
        # -------------------------------------------------

        cv_text = self.cv_reader.read(
            cv_path
        )

        if not cv_text.strip():
            raise ValueError(
                "CV contains no readable text."
            )

        # -------------------------------------------------
        # 2. Analyze CV
        # -------------------------------------------------

        profile = self.profile_analyzer.analyze(
            text=cv_text,
            source_cv=cv_path.name,
        )

        # -------------------------------------------------
        # 3. Normalize capabilities
        # -------------------------------------------------

        profile = CapabilityNormalizer.normalize_profile(
            profile
        )

        # -------------------------------------------------
        # 4. Save versioned profile
        # -------------------------------------------------

        saved_profile = (
            self.profile_service.save_profile(
                profile
            )
        )

        return saved_profile


if __name__ == "__main__":

    print("=" * 60)
    print("JOBPILOT CV INGESTION SERVICE")
    print("=" * 60)

    print()
    print(
        "This service expects the application/UI to provide "
        "the uploaded CV path."
    )

    print()
    print(
        "Supported formats:"
    )

    print(
        "  - PDF"
    )

    print(
        "  - DOCX"
    )