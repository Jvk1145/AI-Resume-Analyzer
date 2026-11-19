"""Tests for pydantic validation of LLM output and the provider fallback chain."""
import json

import pytest
from pydantic import ValidationError

from ai.llm_service import AllProvidersFailed, run_with_fallback
from ai.schemas import CoverLetter, InterviewPrep, ResumeAnalysis

VALID = {
    "name": "A",
    "skills": ["Python"],
    "experience": [{"role": "Dev", "company": "X", "duration": "2021", "bullets": ["Built Y"]}],
    "education": [],
    "projects": [],
    "suggestions": [{"original_bullet": "Built Y", "improved_bullet": "Engineered Y", "reason": "verb"}],
}


def test_valid_resume() -> None:
    assert ResumeAnalysis.model_validate(VALID).experience[0].bullets == ["Built Y"]


def test_lenient_type_coercion() -> None:
    data = {
        "name": None,
        "skills": "Python, SQL",
        "education": None,
        "experience": [{"role": "Dev", "duration": 2021, "bullets": "a\nb"}],
        "projects": [{"name": "P", "description": ["line 1", "line 2"]}],
    }
    model = ResumeAnalysis.model_validate(data)
    assert model.skills == ["Python", "SQL"]
    assert model.experience[0].duration == "2021"
    assert model.experience[0].bullets == ["a", "b"]
    assert model.projects[0].description == "line 1\nline 2"


def test_empty_resume_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ResumeAnalysis.model_validate({"name": "Only a name"})


def test_suggestion_requires_text() -> None:
    with pytest.raises(ValidationError):
        ResumeAnalysis.model_validate({**VALID, "suggestions": [{"original_bullet": "", "improved_bullet": "x"}]})


def test_cover_letter_length_bounds() -> None:
    assert CoverLetter(cover_letter=" ".join(["w"] * 270))
    with pytest.raises(ValidationError):
        CoverLetter(cover_letter="Too short.")


def test_interview_prep_caps_at_eight() -> None:
    questions = [{"question": f"Question {i}?", "tip": "Use your project."} for i in range(10)]
    assert len(InterviewPrep.model_validate({"questions": questions}).questions) == 8
    with pytest.raises(ValidationError):
        InterviewPrep.model_validate({"questions": questions[:2]})


def test_fallback_skips_invalid_response() -> None:
    calls: list[str] = []

    def invalid(user: str, system: str) -> str:
        calls.append("invalid")
        return '{"name": "x"}'

    def valid(user: str, system: str) -> str:
        calls.append("valid")
        return json.dumps(VALID)

    model, provider = run_with_fallback("u", "s", ResumeAnalysis, [("First", invalid), ("Second", valid)])
    assert provider == "Second" and calls == ["invalid", "valid"]
    assert model.name == "A"


def test_fallback_reports_every_failure() -> None:
    def boom(user: str, system: str) -> str:
        raise TimeoutError("slow")

    with pytest.raises(AllProvidersFailed) as excinfo:
        run_with_fallback("u", "s", ResumeAnalysis, [("A", boom), ("B", lambda u, s: "not json")])
    assert "A ->" in str(excinfo.value) and "B ->" in str(excinfo.value)
