"""Tests for the honesty guards and the DOCX exporter."""
import io

import docx

from ai.honesty import find_invented_numbers, is_grounded, sanitize_suggestions, strip_invented_numbers
from ai.schemas import Suggestion
from exporters.docx_exporter import apply_replacements, generate_cover_letter_docx, generate_docx


def test_invented_numbers_become_placeholders() -> None:
    original = "Improved query speed on K8s and S3 in 2022"
    improved = "Improved query speed by 40% for 1,200+ users and saved $2M in 2022 on K8s and S3"
    assert find_invented_numbers(original, improved) == ["40%", "1,200+", "$2M"]
    assert strip_invented_numbers(original, improved) == (
        "Improved query speed by [X%] for [number] users and saved [$amount] in 2022 on K8s and S3"
    )


def test_numbers_from_original_are_kept() -> None:
    assert strip_invented_numbers("Cut costs by 30%", "Reduced costs by 30% through automation") == (
        "Reduced costs by 30% through automation"
    )


def test_grounding_handles_wrapped_bullets() -> None:
    resume = "• Built a pipeline that ingests\nevents from Kafka into S3"
    assert is_grounded("Built a pipeline that ingests events from Kafka into S3", resume)
    assert not is_grounded("Led a team of 40 engineers at Google", resume)


def test_sanitize_drops_ungrounded() -> None:
    suggestions = [
        Suggestion(original_bullet="Wrote unit tests", improved_bullet="Wrote 500 unit tests"),
        Suggestion(original_bullet="Invented bullet", improved_bullet="Something"),
    ]
    clean = sanitize_suggestions(suggestions, "• Wrote unit tests")
    assert len(clean) == 1
    assert clean[0].improved_bullet == "Wrote [number] unit tests"


def test_apply_replacements_exact_and_fuzzy() -> None:
    reps = {"Built the API": "Engineered the REST API"}
    assert apply_replacements("• built the  API", reps) == "Engineered the REST API"
    assert apply_replacements("Built the API.", reps) == "Engineered the REST API"
    assert apply_replacements("Wrote docs", reps) == "Wrote docs"


def _docx_text(data: bytes) -> str:
    return "\n".join(p.text for p in docx.Document(io.BytesIO(data)).paragraphs)


def test_docx_applies_accepted_rewrites_and_restores_contact() -> None:
    resume = {
        "name": "Priya",
        "skills": ["Python"],
        "experience": [
            {"role": "SE", "company": "Acme", "duration": "2022", "bullets": ["Built the API", "Wrote docs"]}
        ],
        "projects": [],
        "education": [],
    }
    data = generate_docx(
        resume,
        contact={"email": "p@example.com", "phone": "", "linkedin": "", "github": ""},
        replacements={"Built the API": "Engineered the REST API"},
    )
    text = _docx_text(data)
    assert "Engineered the REST API" in text and "Built the API" not in text
    assert "Wrote docs" in text and "p@example.com" in text


def test_cover_letter_docx_paragraphs() -> None:
    text = _docx_text(generate_cover_letter_docx("Dear Hiring Manager,\n\nPara one.\n\nSincerely,\nPriya", "Priya"))
    assert "Para one." in text and "Priya" in text
