from pathlib import Path

from docx import Document
from pypdf import PdfReader


class CVReader:
    """
    Reads CV documents and extracts their textual content.

    Supported formats:
    - DOCX
    - PDF
    """

    SUPPORTED_EXTENSIONS = {
        ".docx",
        ".pdf",
    }

    def read(self, file_path: Path) -> str:
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(
                f"CV file not found: {file_path}"
            )

        extension = file_path.suffix.lower()

        if extension not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported CV format: {extension}. "
                f"Supported formats: "
                f"{sorted(self.SUPPORTED_EXTENSIONS)}"
            )

        if extension == ".docx":
            return self._read_docx(file_path)

        if extension == ".pdf":
            return self._read_pdf(file_path)

        raise ValueError(
            f"Unsupported CV format: {extension}"
        )

    @staticmethod
    def _read_docx(file_path: Path) -> str:

        document = Document(file_path)

        paragraphs = []

        for paragraph in document.paragraphs:

            text = paragraph.text.strip()

            if text:
                paragraphs.append(text)

        return "\n".join(paragraphs)

    @staticmethod
    def _read_pdf(file_path: Path) -> str:

        reader = PdfReader(file_path)

        pages = []

        for page in reader.pages:

            text = page.extract_text()

            if text:
                pages.append(text.strip())

        return "\n".join(pages)