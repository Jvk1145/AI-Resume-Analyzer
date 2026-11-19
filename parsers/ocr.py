"""OCR for image-based resumes: local Tesseract first, Gemini vision as fallback."""
import io
import logging
from typing import Callable, Optional

from PIL import Image

logger = logging.getLogger(__name__)

MAX_PAGES = 5  # resumes are short; cap work and API payload size
RENDER_SCALE = 2.0  # ~144 DPI, enough for OCR without huge images


class OCRUnavailable(RuntimeError):
    """Raised when no OCR engine could read the file."""


def render_pdf_pages(data: bytes, max_pages: int = MAX_PAGES) -> list[bytes]:
    """Render the first pages of a PDF to PNG bytes."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    try:
        pngs = []
        for index in range(min(len(pdf), max_pages)):
            image = pdf[index].render(scale=RENDER_SCALE).to_pil()
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            pngs.append(buffer.getvalue())
        return pngs
    finally:
        pdf.close()


def to_png(data: bytes) -> bytes:
    """Convert any PIL-readable image (JPG, WEBP, BMP, TIFF, GIF...) to PNG bytes."""
    with Image.open(io.BytesIO(data)) as image:
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="PNG")
        return buffer.getvalue()


def ocr_tesseract(pngs: list[bytes]) -> Optional[str]:
    """OCR with a local Tesseract install; returns None if Tesseract isn't available."""
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
    except Exception:  # noqa: BLE001 - package or binary missing
        return None
    pages = []
    for png in pngs:
        with Image.open(io.BytesIO(png)) as image:
            pages.append(pytesseract.image_to_string(image))
    return "\n".join(pages).strip()


def ocr_images(
    pngs: list[bytes],
    gemini_ocr: Optional[Callable[[list[tuple[bytes, str]]], str]] = None,
) -> tuple[str, str]:
    """Read text from page images.

    Tries local Tesseract first (private, free), then Gemini vision.

    Returns:
        ``(text, method)`` where method is "Tesseract OCR" or "Gemini OCR".

    Raises:
        OCRUnavailable: if neither engine produced text.
    """
    if not pngs:
        raise OCRUnavailable("The file contains no pages or images to read.")

    text = ocr_tesseract(pngs)
    if text and len(text.split()) >= 20:
        return text, "Tesseract OCR"

    if gemini_ocr is None:
        from ai.gemini_provider import transcribe_images

        gemini_ocr = transcribe_images
    try:
        text = gemini_ocr([(png, "image/png") for png in pngs]).strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini OCR failed: %s", exc)
        raise OCRUnavailable(
            "This resume is an image, and it couldn't be read: Tesseract isn't installed and Gemini OCR "
            "failed. Add a working GEMINI_API_KEY, or upload a text-based PDF or .docx."
        ) from exc
    if not text:
        raise OCRUnavailable("No text was found in the images. Is the resume blank or very low resolution?")
    return text, "Gemini OCR"
