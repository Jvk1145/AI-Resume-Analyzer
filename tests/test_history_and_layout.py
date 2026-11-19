"""Tests for SQLite history and DOCX layout detection."""
from datetime import datetime
from pathlib import Path

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from parsers.layout import analyze_docx_layout
from storage.history import add_record, clear_history, fetch_history


def test_history_roundtrip(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    add_record("b.pdf", 80, 65.5, ["docker"], db_path=db, created_at=datetime(2026, 2, 1))
    add_record("a.pdf", 70, None, [], db_path=db, created_at=datetime(2026, 1, 1))
    rows = fetch_history(db)
    assert [r["file_name"] for r in rows] == ["a.pdf", "b.pdf"]  # oldest first
    assert rows[1]["missing_skills"] == ["docker"]
    assert rows[0]["jd_match"] is None
    clear_history(db)
    assert fetch_history(db) == []


def test_docx_layout_detection(tmp_path: Path) -> None:
    plain = docx.Document()
    plain.add_paragraph("Experience")
    plain.save(str(tmp_path / "plain.docx"))
    info = analyze_docx_layout(str(tmp_path / "plain.docx"))
    assert not (info.has_tables or info.multi_column or info.header_footer_text)

    fancy = docx.Document()
    fancy.add_table(rows=2, cols=2)
    cols = OxmlElement("w:cols")
    cols.set(qn("w:num"), "2")
    fancy.sections[0]._sectPr.append(cols)
    fancy.sections[0].header.paragraphs[0].text = "Header"
    fancy.save(str(tmp_path / "fancy.docx"))
    info = analyze_docx_layout(str(tmp_path / "fancy.docx"))
    assert info.has_tables and info.multi_column and info.header_footer_text
