"""Build ATS-friendly DOCX files (resume and cover letter) entirely in memory."""
import difflib
import io
import re
from typing import Any, Mapping, Optional

import docx
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT

_BULLET_CHARS = " \t•●▪◦‣○■➢✓*-–—"


def _norm(text: str) -> str:
    """Normalize a bullet for comparison: strip markers, collapse spaces, lowercase."""
    return re.sub(r"\s+", " ", text.strip(_BULLET_CHARS)).lower()


def apply_replacements(text: str, replacements: Mapping[str, str]) -> str:
    """Return the accepted rewrite for ``text`` if it matches an original bullet.

    Matching is exact after normalization, falling back to a 0.9 similarity
    ratio so small whitespace/punctuation differences from the LLM's copy of the
    bullet still match.
    """
    if not replacements:
        return text
    target = _norm(text)
    best_ratio, best = 0.0, None
    for original, improved in replacements.items():
        candidate = _norm(original)
        if candidate == target:
            return improved
        ratio = difflib.SequenceMatcher(None, candidate, target).ratio()
        if ratio > best_ratio:
            best_ratio, best = ratio, improved
    return best if best is not None and best_ratio >= 0.9 else text


def _to_bytes(document: Any) -> bytes:
    """Serialize a python-docx Document to bytes."""
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _contact_line(contact: Optional[Mapping[str, str]]) -> str:
    """Join available contact fields with separators."""
    if not contact:
        return ""
    keys = ("email", "phone", "linkedin", "github")
    return " | ".join(contact[k] for k in keys if contact.get(k))


def generate_docx(
    resume: Mapping[str, Any],
    contact: Optional[Mapping[str, str]] = None,
    replacements: Optional[Mapping[str, str]] = None,
) -> bytes:
    """Generate a clean, single-column DOCX resume.

    Args:
        resume: A ``ResumeAnalysis``-shaped dict.
        contact: Contact details extracted locally from the original text
            (never sent to an AI provider).
        replacements: Accepted ``{original_bullet: improved_bullet}`` rewrites.

    Returns:
        The DOCX file contents.
    """
    replacements = replacements or {}
    doc = docx.Document()

    heading = doc.add_heading(resume.get("name") or "Your Name", 0)
    heading.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    line = _contact_line(contact)
    if line:
        doc.add_paragraph(line).alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

    skills = resume.get("skills") or []
    if skills:
        doc.add_heading("Skills", level=1)
        doc.add_paragraph(", ".join(str(s) for s in skills))

    experience = resume.get("experience") or []
    if experience:
        doc.add_heading("Professional Experience", level=1)
        for job in experience:
            p = doc.add_paragraph()
            p.add_run(job.get("role") or "Role").bold = True
            if job.get("company"):
                p.add_run(f" | {job['company']}").italic = True
            if job.get("duration"):
                p.add_run(f" ({job['duration']})")
            for bullet in job.get("bullets") or []:
                doc.add_paragraph(apply_replacements(str(bullet), replacements), style="List Bullet")

    projects = resume.get("projects") or []
    if projects:
        doc.add_heading("Projects", level=1)
        for proj in projects:
            p = doc.add_paragraph()
            p.add_run(proj.get("name") or "Project").bold = True
            tech = proj.get("technologies") or []
            if tech:
                p.add_run(f" (Technologies: {', '.join(str(t) for t in tech)})").italic = True
            for desc_line in str(proj.get("description") or "").split("\n"):
                if desc_line.strip():
                    doc.add_paragraph(apply_replacements(desc_line, replacements), style="List Bullet")

    education = resume.get("education") or []
    if education:
        doc.add_heading("Education", level=1)
        for edu in education:
            p = doc.add_paragraph()
            p.add_run(edu.get("degree") or "Degree").bold = True
            if edu.get("institution"):
                p.add_run(f" - {edu['institution']}")
            if edu.get("year"):
                p.add_run(f" ({edu['year']})")

    return _to_bytes(doc)


def generate_cover_letter_docx(
    letter: str,
    name: str = "",
    contact: Optional[Mapping[str, str]] = None,
) -> bytes:
    """Generate a DOCX cover letter with the candidate's name and contact line on top."""
    doc = docx.Document()
    if name:
        doc.add_heading(name, level=1)
    line = _contact_line(contact)
    if line:
        doc.add_paragraph(line)
    for paragraph in re.split(r"\n\s*\n", letter.strip()):
        doc.add_paragraph(" ".join(paragraph.split()))
    return _to_bytes(doc)
