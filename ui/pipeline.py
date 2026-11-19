"""Analysis pipeline used by the Streamlit app (file handling, caching, orchestration)."""
import hashlib
import logging
import os
import tempfile
from typing import Any, Callable

import streamlit as st

from ai.llm_service import generate_cover_letter, generate_interview_prep, process_resume_pipeline
from ai.prompts import PROMPT_VERSION
from matching.jd_matcher import match_resume_to_jd
from parsers.docx_parser import extract_text_from_docx
from parsers.layout import analyze_docx_layout, analyze_pdf_layout
from parsers.pdf_parser import extract_text_from_pdf
from privacy.redact import redact
from scoring.ats_score import calculate_ats_score

logger = logging.getLogger(__name__)
StepFn = Callable[[str], Any]


def extract_resume(file_name: str, data: bytes) -> tuple[str, dict[str, Any] | None]:
    """Write the upload to a temp file, extract text and layout, and always delete the file.

    Returns:
        The raw text and the layout signals (None if layout analysis failed).
    """
    ext = os.path.splitext(file_name)[1].lower()
    if ext not in (".pdf", ".docx"):
        raise ValueError("Unsupported file format. Upload a PDF or DOCX.")
    fd, path = tempfile.mkstemp(suffix=ext)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        if ext == ".pdf":
            text, layout_fn = extract_text_from_pdf(path), analyze_pdf_layout
        else:
            text, layout_fn = extract_text_from_docx(path), analyze_docx_layout
        try:
            layout: dict[str, Any] | None = layout_fn(path).to_dict()
        except Exception:  # noqa: BLE001 - layout is optional; never block the analysis
            logger.exception("Layout analysis failed")
            layout = None
        return text, layout
    finally:
        try:
            os.remove(path)
        except OSError:
            logger.warning("Could not delete temp file %s", path)


def make_key(*parts: str) -> str:
    """Stable sha256 of everything that affects an AI result."""
    raw = "\x00".join((PROMPT_VERSION, *parts))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# Underscore-prefixed arguments are excluded from Streamlit's cache hashing;
# ``key`` (a hash of the resume text + JD text) identifies them.
@st.cache_data(show_spinner=False, max_entries=64)
def cached_analysis(key: str, _resume: str, _jd: str, _missing: tuple[str, ...]) -> dict[str, Any]:
    """Run the AI parsing/suggestion pipeline once per unique resume + JD."""
    analysis, provider = process_resume_pipeline(_resume, _jd, list(_missing))
    return {"analysis": analysis.model_dump(), "provider": provider}


@st.cache_data(show_spinner=False, max_entries=64)
def cached_cover_letter(key: str, _resume: str, _jd: str) -> dict[str, str]:
    """Generate a cover letter once per unique resume + JD."""
    letter, provider = generate_cover_letter(_resume, _jd)
    return {"text": letter.cover_letter, "provider": provider}


@st.cache_data(show_spinner=False, max_entries=64)
def cached_interview(key: str, _resume: str, _jd: str) -> dict[str, Any]:
    """Generate interview questions once per unique resume + JD."""
    prep, provider = generate_interview_prep(_resume, _jd)
    return {"questions": [q.model_dump() for q in prep.questions], "provider": provider}


def run_analysis(file_name: str, data: bytes, jd_text: str, step: StepFn = lambda _: None) -> dict[str, Any]:
    """Full pipeline for one upload. Only redacted text ever reaches an AI provider.

    Args:
        step: Called with a short message as each stage starts (for progress UI).
    """
    step(":material/description: Extracting text and checking layout")
    resume_text, layout = extract_resume(file_name, data)
    if not resume_text.strip():
        raise ValueError("No text could be extracted from this file. Try a text-based PDF or a .docx.")

    jd_match = None
    if jd_text.strip():
        step(":material/join_inner: Matching skills against the job description")
        jd_match = match_resume_to_jd(resume_text, jd_text)
    missing = tuple((jd_match["missing_required"] + jd_match["missing_nice"]) if jd_match else [])

    step(":material/shield_lock: Redacting email, phone and address")
    redacted_resume, redacted_jd = redact(resume_text), redact(jd_text)

    step(":material/auto_awesome: Parsing resume and writing suggestions with AI")
    key = make_key(resume_text, jd_text.strip())
    ai_result = cached_analysis(key, redacted_resume, redacted_jd, missing)

    step(":material/fact_check: Calculating ATS score")
    ats = calculate_ats_score(resume_text, ai_result["analysis"], jd_match, layout)
    return {
        "key": key,
        "file_name": file_name,
        "resume_text": resume_text,
        "redacted_resume": redacted_resume,
        "jd_text": jd_text,
        "redacted_jd": redacted_jd,
        "layout": layout,
        "jd_match": jd_match,
        "ats": ats,
        **ai_result,
    }
