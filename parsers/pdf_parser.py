"""Extract text from PDF resumes."""
import pdfplumber


class NoTextError(ValueError):
    """Raised when a file has no extractable text; the message tells the user what to do."""


_IMAGE_ONLY_MSG = (
    "This PDF contains only images, so there is no text to read. It was probably scanned or exported as a "
    "picture (common with Canva or 'Print to PDF' from an image). Re-export it as a text PDF "
    "(File → Save as PDF from Word or Google Docs), or upload the .docx instead."
)
_NO_LAYER_MSG = (
    "This PDF has no readable text layer; its text may have been converted to outlines. Re-export it from "
    "Word or Google Docs with File → Save as PDF, or upload the .docx instead."
)
_BAD_FONTS_MSG = (
    "This PDF uses fonts whose text can't be decoded (it extracts as '(cid:…)' codes). Re-export it from "
    "Word or Google Docs with File → Save as PDF, or upload the .docx instead."
)


def extract_text_from_pdf(file_path: str) -> str:
    """Extract all text from a PDF, page by page.

    Falls back to word-level extraction for pages where ``extract_text``
    returns nothing.

    Raises:
        RuntimeError: if the file cannot be opened as a PDF.
        NoTextError: if the PDF has no usable text (image-only, outlined or undecodable fonts).
    """
    try:
        with pdfplumber.open(file_path) as pdf:
            pages: list[str] = []
            image_count = 0
            for page in pdf.pages:
                text = page.extract_text() or ""
                if not text.strip() and page.chars:
                    text = " ".join(w["text"] for w in page.extract_words())
                pages.append(text)
                image_count += len(page.images)
    except Exception as exc:  # noqa: BLE001 - pdfplumber raises many error types
        raise RuntimeError(f"Failed to read the PDF file: {exc}") from exc

    text = "\n".join(p for p in pages if p.strip()).strip()
    if not text:
        raise NoTextError(_IMAGE_ONLY_MSG if image_count else _NO_LAYER_MSG)
    if text.count("(cid:") > 20 and text.count("(cid:") * 8 > len(text.split()):
        raise NoTextError(_BAD_FONTS_MSG)
    return text
