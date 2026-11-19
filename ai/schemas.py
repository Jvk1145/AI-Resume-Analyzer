"""Pydantic models that every LLM response must satisfy.

Models are lenient about *types* (numbers become strings, ``null`` becomes an
empty value, a list description is joined) but strict about *shape*: a response
that carries no usable resume content fails validation, which makes the
fallback chain move on to the next provider.
"""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _to_str(value: Any) -> str:
    """Coerce scalars/None to a stripped string; join lists with newlines."""
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(_to_str(v) for v in value if v is not None).strip()
    return str(value).strip()


def _to_str_list(value: Any) -> list[str]:
    """Coerce None / a single string / a list of anything into a list of non-empty strings."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p for p in value.replace("\r", "").split("\n")]
        if len(parts) == 1:
            parts = value.split(",")
        return [p.strip(" \t•-*") for p in parts if p.strip(" \t•-*")]
    if isinstance(value, list):
        return [s for s in (_to_str(v) for v in value) if s]
    return [_to_str(value)]


class _Lenient(BaseModel):
    """Base model: ignore unknown keys and coerce simple types."""

    model_config = ConfigDict(extra="ignore")


class Experience(_Lenient):
    """One job or role."""

    role: str = ""
    company: str = ""
    duration: str = ""
    bullets: list[str] = Field(default_factory=list)

    coerce_str_fields = field_validator("role", "company", "duration", mode="before")(_to_str)
    coerce_list_fields = field_validator("bullets", mode="before")(_to_str_list)


class Education(_Lenient):
    """One degree or qualification."""

    degree: str = ""
    institution: str = ""
    year: str = ""

    coerce_str_fields = field_validator("degree", "institution", "year", mode="before")(_to_str)


class Project(_Lenient):
    """One project."""

    name: str = ""
    technologies: list[str] = Field(default_factory=list)
    description: str = ""

    coerce_str_fields = field_validator("name", "description", mode="before")(_to_str)
    coerce_list_fields = field_validator("technologies", mode="before")(_to_str_list)


class Suggestion(_Lenient):
    """A proposed rewrite of one resume bullet."""

    original_bullet: str = Field(min_length=1)
    improved_bullet: str = Field(min_length=1)
    reason: str = ""

    coerce_str_fields = field_validator("original_bullet", "improved_bullet", "reason", mode="before")(_to_str)


class ResumeAnalysis(_Lenient):
    """Structured resume data plus rewrite suggestions returned by the LLM."""

    name: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    suggestions: list[Suggestion] = Field(default_factory=list)

    coerce_name = field_validator("name", mode="before")(_to_str)
    coerce_skills = field_validator("skills", mode="before")(_to_str_list)

    @field_validator("experience", "education", "projects", "suggestions", mode="before")
    @classmethod
    def _none_to_list(cls, value: Any) -> Any:
        """Treat ``null`` as an empty list and drop non-dict items."""
        if value is None:
            return []
        if isinstance(value, list):
            return [v for v in value if isinstance(v, dict)]
        return value

    @model_validator(mode="after")
    def _must_have_content(self) -> "ResumeAnalysis":
        """Reject responses that contain no resume content at all."""
        if not (self.skills or self.experience or self.education or self.projects):
            raise ValueError("LLM response contains no skills, experience, education or projects.")
        return self


class CoverLetter(_Lenient):
    """A generated cover letter."""

    cover_letter: str

    coerce_text = field_validator("cover_letter", mode="before")(_to_str)

    @field_validator("cover_letter")
    @classmethod
    def _reasonable_length(cls, value: str) -> str:
        """Accept roughly 150-450 words (the prompt asks for 250-300)."""
        words = len(value.split())
        if not 150 <= words <= 450:
            raise ValueError(f"Cover letter has {words} words; expected about 250-300.")
        return value


class InterviewQuestion(_Lenient):
    """One likely interview question with an answering tip."""

    question: str = Field(min_length=5)
    tip: str = Field(min_length=5)

    coerce_str_fields = field_validator("question", "tip", mode="before")(_to_str)


class InterviewPrep(_Lenient):
    """A set of interview questions (the prompt asks for 8)."""

    questions: list[InterviewQuestion] = Field(min_length=5)

    @field_validator("questions")
    @classmethod
    def _cap_at_eight(cls, value: list[InterviewQuestion]) -> list[InterviewQuestion]:
        """Keep at most 8 questions."""
        return value[:8]
