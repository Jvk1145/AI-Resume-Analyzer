"""Extract text from PDF resumes."""
import pdfplumber


def extract_text_from_pdf(file_path: str) -> str:
    """Extract all text from a PDF, page by page."""
    try:
        with pdfplumber.open(file_path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
    except Exception as exc:  # noqa: BLE001 - pdfplumber raises many error types
        raise RuntimeError(f"Failed to parse PDF file: {exc}") from exc
    return "\n".join(p for p in pages if p).strip()
