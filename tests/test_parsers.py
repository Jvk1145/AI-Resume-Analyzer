"""Tests for DOCX text extraction (text boxes, headers, tables) and no-text errors."""
from pathlib import Path

import docx
import pytest
from docx.oxml import parse_xml

from parsers.docx_parser import extract_text_from_docx
from parsers.pdf_parser import NoTextError

_TEXTBOX_RUN = (
    '<w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:v="urn:schemas-microsoft-com:vml"><w:pict><v:shape><v:textbox><w:txbxContent>'
    "<w:p><w:r><w:t>Python, Django, Docker</w:t></w:r></w:p>"
    "</w:txbxContent></v:textbox></v:shape></w:pict></w:r>"
)


def _save(document: docx.document.Document, path: Path) -> str:
    document.save(str(path))
    return str(path)


def test_text_box_header_and_table_text_are_extracted(tmp_path: Path) -> None:
    document = docx.Document()
    document.sections[0].header.paragraphs[0].text = "Priya Sharma | priya@example.com"
    document.add_paragraph("SKILLS")
    document.add_paragraph()._p.append(parse_xml(_TEXTBOX_RUN))
    document.add_paragraph("Built a REST API", style="List Bullet")
    document.add_table(rows=1, cols=1).cell(0, 0).text = "B.Tech, VIT University"

    text = extract_text_from_docx(_save(document, tmp_path / "cv.docx"))
    lines = text.splitlines()
    assert lines[0] == "Priya Sharma | priya@example.com"  # header comes first
    assert "Python, Django, Docker" in lines  # text box
    assert "• Built a REST API" in lines  # list paragraph marked as bullet
    assert "B.Tech, VIT University" in lines  # table cell


def test_empty_docx_raises_helpful_error(tmp_path: Path) -> None:
    with pytest.raises(NoTextError, match="no readable text"):
        extract_text_from_docx(_save(docx.Document(), tmp_path / "empty.docx"))


def test_corrupt_file_raises_runtime_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.docx"
    bad.write_bytes(b"not a docx")
    with pytest.raises(RuntimeError):
        extract_text_from_docx(str(bad))
