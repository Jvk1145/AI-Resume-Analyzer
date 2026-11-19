"""Detect ATS-unfriendly layout features in PDF and DOCX resumes."""
from dataclasses import asdict, dataclass, field
from typing import Any

import pdfplumber


@dataclass
class LayoutInfo:
    """Layout signals extracted from the original file."""

    source: str  # "pdf" or "docx"
    pages: int | None = None  # None when the format has no fixed pages (DOCX)
    has_tables: bool = False
    multi_column: bool = False
    has_images: bool = False
    header_footer_text: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON/cache-friendly dict."""
        return asdict(self)


def _page_is_multi_column(words: list[dict[str, Any]], width: float) -> bool:
    """Return True if a vertical gutter splits the page's words into two substantial columns.

    Looks for an x position in the middle 30-70% of the page that no word
    crosses while at least 25% of words sit on each side.
    """
    if len(words) < 40:
        return False
    total = len(words)
    for step in range(30, 71, 2):
        x = width * step / 100
        if any(w["x0"] < x < w["x1"] for w in words):
            continue
        left = sum(1 for w in words if w["x1"] <= x)
        right = total - left
        if left / total >= 0.25 and right / total >= 0.25:
            return True
    return False


def analyze_pdf_layout(path: str) -> LayoutInfo:
    """Inspect a PDF for tables, multiple columns, images and header/footer-band text."""
    info = LayoutInfo(source="pdf")
    with pdfplumber.open(path) as pdf:
        info.pages = len(pdf.pages)
        for number, page in enumerate(pdf.pages, start=1):
            tables = [t for t in page.find_tables() if len(t.rows) >= 2 and len(t.rows[0].cells) >= 2]
            if tables:
                info.has_tables = True
                info.notes.append(f"Page {number}: {len(tables)} table(s) detected.")
            if page.images:
                info.has_images = True
                info.notes.append(f"Page {number}: {len(page.images)} image(s) detected.")
            words = page.extract_words()
            if _page_is_multi_column(words, float(page.width)):
                info.multi_column = True
                info.notes.append(f"Page {number}: multi-column layout detected.")
            top_band, bottom_band = page.height * 0.035, page.height * 0.965
            if any(w["top"] < top_band or w["bottom"] > bottom_band for w in words):
                info.header_footer_text = True
                info.notes.append(f"Page {number}: text in the header/footer margin.")
    return info


def analyze_docx_layout(path: str) -> LayoutInfo:
    """Inspect a DOCX for tables, multi-column sections, images and header/footer text."""
    import docx  # local import keeps PDF-only use light
    from docx.oxml.ns import qn

    info = LayoutInfo(source="docx")
    document = docx.Document(path)
    if document.tables:
        info.has_tables = True
        info.notes.append(f"{len(document.tables)} table(s) detected.")
    if document.inline_shapes:
        info.has_images = True
        info.notes.append(f"{len(document.inline_shapes)} image(s) detected.")
    for section in document.sections:
        col_elements = section._sectPr.findall(qn("w:cols"))
        if any(int(c.get(qn("w:num"), "1")) > 1 for c in col_elements):
            info.multi_column = True
            info.notes.append("Multi-column section detected.")
        texts = [p.text for p in section.header.paragraphs + section.footer.paragraphs]
        if any(t.strip() for t in texts):
            info.header_footer_text = True
            info.notes.append("Text found in the document header/footer.")
    return info
