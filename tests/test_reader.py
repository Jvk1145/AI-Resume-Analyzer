"""Tests for reading any upload type, including the OCR fallbacks (no network: OCR is faked)."""
import io
from pathlib import Path

import docx
import pytest
from PIL import Image

import parsers.ocr as ocr
from parsers.ocr import OCRUnavailable
from parsers.reader import read_resume
from scoring.ats_score import score_layout

OCR_TEXT = "Priya Sharma\nSKILLS\nPython, Django\nEXPERIENCE\n• Built a REST API used by 4 teams " + "word " * 40


def fake_ocr(images: list[tuple[bytes, str]]) -> str:
    """Stand-in for Gemini OCR: checks it received PNG pages and returns fixed text."""
    assert images and all(mime == "image/png" for _, mime in images)
    return OCR_TEXT


def failing_ocr(images: list[tuple[bytes, str]]) -> str:
    raise RuntimeError("quota exceeded")


@pytest.fixture(autouse=True)
def no_tesseract(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make tests deterministic whether or not Tesseract is installed."""
    monkeypatch.setattr(ocr, "ocr_tesseract", lambda pngs: None)


def _png(width: int = 200, height: int = 100) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def _blank_pdf() -> bytes:
    """A valid one-page PDF with no text layer (like a scanned or image-only resume)."""
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>"]
    out, offsets = b"%PDF-1.4\n", []
    for number, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 4\n0000000000 65535 f \n" + b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    return out + b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF"


def test_plain_text_upload() -> None:
    result = read_resume("cv.txt", "Priya Sharma\nSKILLS\nPython".encode("utf-8"))
    assert result.method == "text" and "Python" in result.text and not result.used_ocr


def test_unsupported_type_has_helpful_message() -> None:
    with pytest.raises(ValueError, match="save as .docx"):
        read_resume("cv.doc", b"binary")


def test_image_upload_uses_ocr() -> None:
    result = read_resume("cv.jpg", _png(), gemini_ocr=fake_ocr)
    assert result.method == "Gemini OCR" and result.used_ocr
    assert "Built a REST API" in result.text
    assert result.layout and result.layout["image_only"]


def test_image_only_pdf_falls_back_to_ocr() -> None:
    result = read_resume("scan.pdf", _blank_pdf(), gemini_ocr=fake_ocr)
    assert result.method == "Gemini OCR"
    assert result.layout and result.layout["image_only"] and result.layout["pages"] == 1


def test_picture_only_docx_falls_back_to_ocr(tmp_path: Path) -> None:
    image_path = tmp_path / "page.png"
    image_path.write_bytes(_png(400, 600))
    document = docx.Document()
    document.add_picture(str(image_path))
    buffer = io.BytesIO()
    document.save(buffer)
    result = read_resume("cv.docx", buffer.getvalue(), gemini_ocr=fake_ocr)
    assert result.method == "Gemini OCR" and "Python, Django" in result.text


def test_text_docx_does_not_use_ocr() -> None:
    document = docx.Document()
    for line in ["Priya Sharma", "EXPERIENCE"] + [f"• Built feature {i} for the payments platform team" for i in range(8)]:
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    result = read_resume("cv.docx", buffer.getvalue(), gemini_ocr=failing_ocr)
    assert result.method == "text" and "payments platform" in result.text


def test_ocr_failure_gives_clear_error() -> None:
    with pytest.raises(OCRUnavailable, match="GEMINI_API_KEY"):
        read_resume("scan.png", _png(), gemini_ocr=failing_ocr)


def test_image_only_layout_scores_zero() -> None:
    cat = score_layout({"image_only": True, "has_images": True})
    assert cat["score"] == 0 and "image" in cat["reasons"][0]
