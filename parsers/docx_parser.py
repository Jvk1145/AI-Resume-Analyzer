"""Extract text from DOCX resumes."""
import docx


def extract_text_from_docx(file_path: str) -> str:
    """Extract paragraph and table text from a DOCX file.

    List paragraphs are prefixed with "• " so bullets stay detectable, and
    table cells are included so skills inside tables are not lost.
    """
    try:
        document = docx.Document(file_path)
    except Exception as exc:  # noqa: BLE001 - python-docx raises many error types
        raise RuntimeError(f"Failed to parse DOCX file: {exc}") from exc

    lines: list[str] = []
    for para in document.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = (para.style.name if para.style is not None else "") or ""
        lines.append(f"• {text}" if "list" in style.lower() else text)
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                lines.append(" | ".join(dict.fromkeys(cells)))
    return "\n".join(lines).strip()
