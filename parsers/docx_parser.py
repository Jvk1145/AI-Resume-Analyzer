"""Extract text from DOCX resumes, including text boxes, tables and headers."""
import docx
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from parsers.pdf_parser import NoTextError

# Text boxes are stored twice (modern + legacy fallback); skip the fallback copy.
_MC_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"


def _paragraph_lines(element, parent) -> list[str]:  # type: ignore[no-untyped-def]
    """Return text for every paragraph under ``element`` in document order.

    Covers body text, table cells and text boxes. List paragraphs are prefixed
    with "• " so bullets stay detectable by the ATS scorer.
    """
    lines: list[str] = []
    for p_el in element.iter(qn("w:p")):
        if any(a.tag == _MC_FALLBACK for a in p_el.iterancestors()):
            continue
        para = Paragraph(p_el, parent)
        text = para.text.strip()
        if not text:
            continue
        style = ""
        try:
            style = (para.style.name if para.style is not None else "") or ""
        except (KeyError, ValueError):
            pass
        is_list = "list" in style.lower() or p_el.find(f".//{qn('w:numPr')}") is not None
        lines.append(f"• {text}" if is_list and not text.startswith(("•", "-", "*")) else text)
    return lines


def extract_text_from_docx(file_path: str) -> str:
    """Extract all readable text from a DOCX file.

    Header text (where many templates put the name and contact details) comes
    first, then the body, including tables and text boxes.

    Raises:
        RuntimeError: if the file cannot be opened as a DOCX.
        NoTextError: if the document contains no text.
    """
    try:
        document = docx.Document(file_path)
    except Exception as exc:  # noqa: BLE001 - python-docx raises many error types
        raise RuntimeError(f"Failed to read the DOCX file: {exc}") from exc

    lines: list[str] = []
    for section in document.sections:
        for part in (section.header, section.footer):
            if not part.is_linked_to_previous or section is document.sections[0]:
                lines.extend(_paragraph_lines(part._element, part))
    lines.extend(_paragraph_lines(document.element.body, document))

    deduped = [line for i, line in enumerate(lines) if i == 0 or line != lines[i - 1]]
    text = "\n".join(deduped).strip()
    if not text:
        raise NoTextError(
            "This Word file contains no readable text. If your resume is a picture inside the document, "
            "recreate it as normal text, or upload a text-based PDF."
        )
    return text
