"""Turn any supported upload into text, layout signals and a note on how it was read."""
import logging
import os
import tempfile
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from parsers.docx_parser import extract_text_from_docx
from parsers.layout import LayoutInfo, analyze_docx_layout, analyze_pdf_layout
from parsers.ocr import ocr_images, render_pdf_pages, to_png
from parsers.pdf_parser import NoTextError, extract_text_from_pdf

logger = logging.getLogger(__name__)

TEXT_TYPES = {".txt", ".md"}
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"}
SUPPORTED_TYPES = [".pdf", ".docx", *sorted(TEXT_TYPES), *sorted(IMAGE_TYPES)]

MIN_WORDS = 40  # fewer words than this in a text layer suggests most content is an image

OcrFn = Callable[[list[tuple[bytes, str]]], str]


@dataclass
class ReadResult:
    """Text extracted from an upload plus how it was obtained."""

    text: str
    layout: Optional[dict[str, Any]]
    method: str  # "text", "Tesseract OCR" or "Gemini OCR"
    notes: list[str] = field(default_factory=list)

    @property
    def used_ocr(self) -> bool:
        """True if the text came from OCR rather than a text layer."""
        return self.method != "text"


def _decode_text(data: bytes) -> str:
    """Decode a plain-text upload, tolerating common encodings."""
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _docx_images(path: str) -> list[bytes]:
    """Return embedded images of a DOCX as PNG bytes (for resumes pasted in as a picture)."""
    import docx

    pngs = []
    for rel in docx.Document(path).part.rels.values():
        if "image" in rel.reltype:
            try:
                pngs.append(to_png(rel.target_part.blob))
            except Exception:  # noqa: BLE001 - skip EMF/WMF and other unreadable formats
                continue
    return pngs


def _image_only_layout(source: str, pages: Optional[int]) -> dict[str, Any]:
    """Layout signals for a resume that has no text layer."""
    return LayoutInfo(
        source=source, pages=pages, has_images=True,
        notes=["The resume is an image with no text layer. Most ATS software reads nothing from it."],
    ).to_dict() | {"image_only": True}


def read_resume(file_name: str, data: bytes, gemini_ocr: Optional[OcrFn] = None) -> ReadResult:
    """Read any supported resume file.

    Order: text layer (PDF/DOCX/TXT) → OCR (Tesseract, then Gemini) for scans,
    image-only PDFs, picture-only DOCX files and image uploads.

    Raises:
        ValueError: for unsupported file types.
        parsers.ocr.OCRUnavailable: if an image-based file can't be OCR'd.
        RuntimeError: if the file is corrupt.
    """
    ext = os.path.splitext(file_name)[1].lower()
    if ext not in SUPPORTED_TYPES:
        raise ValueError(
            f"'{ext or file_name}' files aren't supported. Upload a PDF, DOCX, TXT or an image (PNG/JPG). "
            "For old .doc files, open them in Word and save as .docx."
        )

    if ext in TEXT_TYPES:
        return ReadResult(_decode_text(data).strip(), None, "text")

    if ext in IMAGE_TYPES:
        text, method = ocr_images([to_png(data)], gemini_ocr)
        return ReadResult(text, _image_only_layout("image", 1), method)

    fd, path = tempfile.mkstemp(suffix=ext)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        layout_fn = analyze_pdf_layout if ext == ".pdf" else analyze_docx_layout
        try:
            text = extract_text_from_pdf(path) if ext == ".pdf" else extract_text_from_docx(path)
        except NoTextError:
            pngs = render_pdf_pages(data) if ext == ".pdf" else _docx_images(path)
            text, method = ocr_images(pngs, gemini_ocr)
            pages = len(pngs) if ext == ".pdf" else None
            return ReadResult(text, _image_only_layout(ext.lstrip("."), pages), method)
        if len(text.split()) < MIN_WORDS:
            # Mostly-image resume (e.g. only the name is real text): OCR and keep the richer result.
            try:
                pngs = render_pdf_pages(data) if ext == ".pdf" else _docx_images(path)
                ocr_text, method = ocr_images(pngs, gemini_ocr)
                if len(ocr_text.split()) > len(text.split()):
                    return ReadResult(ocr_text, _image_only_layout(ext.lstrip("."), None), method)
            except Exception:  # noqa: BLE001 - keep the short text layer if OCR fails
                logger.warning("OCR of short-text file failed", exc_info=True)
        try:
            layout: Optional[dict[str, Any]] = layout_fn(path).to_dict()
        except Exception:  # noqa: BLE001 - layout is optional; never block the analysis
            logger.exception("Layout analysis failed")
            layout = None
        return ReadResult(text, layout, "text")
    finally:
        try:
            os.remove(path)
        except OSError:
            logger.warning("Could not delete temp file %s", path)

