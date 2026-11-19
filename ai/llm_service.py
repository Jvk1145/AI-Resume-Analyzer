"""Provider fallback chain with JSON repair and pydantic validation."""
import logging
from typing import Callable, Optional, TypeVar

from pydantic import BaseModel, ValidationError

from ai import prompts
from ai.gemini_provider import call_gemini
from ai.groq_provider import call_groq
from ai.json_helper import clean_and_parse_json
from ai.honesty import sanitize_suggestions
from ai.schemas import CoverLetter, InterviewPrep, ResumeAnalysis

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)
ProviderFn = Callable[[str, str], str]

# Fallback order. Each entry: (display name, provider function).
PROVIDERS: list[tuple[str, ProviderFn]] = [
    ("Groq", call_groq),
    ("Gemini", call_gemini),
]


class AllProvidersFailed(RuntimeError):
    """Raised when no provider returned a valid, schema-conforming response."""


def _short_error(exc: Exception, limit: int = 160) -> str:
    """Return a one-line, truncated error description safe to show in the UI."""
    if isinstance(exc, ValidationError):
        return f"response failed schema validation ({exc.error_count()} error(s))"
    text = " ".join(str(exc).split())
    return f"{type(exc).__name__}: {text[:limit]}{'...' if len(text) > limit else ''}"


def run_with_fallback(
    user_prompt: str,
    system_prompt: str,
    schema: type[ModelT],
    providers: Optional[list[tuple[str, ProviderFn]]] = None,
) -> tuple[ModelT, str]:
    """Call providers in order until one returns JSON that validates against ``schema``.

    A provider is skipped on a network/API error, unparseable JSON, or a
    pydantic validation failure.

    Returns:
        The validated model and the name of the provider that produced it.

    Raises:
        AllProvidersFailed: listing one short reason per provider.
    """
    errors: list[str] = []
    for name, call in providers if providers is not None else PROVIDERS:
        try:
            logger.info("Attempting %s...", name)
            data = clean_and_parse_json(call(user_prompt, system_prompt))
            return schema.model_validate(data), name
        except Exception as exc:  # noqa: BLE001 - any failure moves to the next provider
            logger.warning("%s failed: %s", name, exc)
            errors.append(f"{name} -> {_short_error(exc)}")
    raise AllProvidersFailed("All AI providers failed:\n" + "\n".join(f"- {e}" for e in errors))


def process_resume_pipeline(
    resume_text: str,
    jd_text: Optional[str] = None,
    missing_skills: Optional[list[str]] = None,
) -> tuple[ResumeAnalysis, str]:
    """Parse a (redacted) resume and produce honest rewrite suggestions.

    Suggestions whose original bullet is not in the resume are dropped, and
    numbers the AI invented are replaced with placeholders.

    Args:
        resume_text: Resume text with contact details already redacted.
        jd_text: Optional job description.
        missing_skills: JD skills the deterministic matcher did not find.

    Returns:
        The validated analysis and the provider name.
    """
    if jd_text and jd_text.strip():
        missing = ", ".join(missing_skills) if missing_skills else "none"
        payload = (
            f"JOB DESCRIPTION:\n{jd_text}\n\nJD SKILLS MISSING FROM THE RESUME: {missing}\n\n"
            f"RESUME TEXT:\n{resume_text}"
        )
        analysis, provider = run_with_fallback(payload, prompts.SYSTEM_PROMPT_WITH_JD, ResumeAnalysis)
    else:
        analysis, provider = run_with_fallback(resume_text, prompts.SYSTEM_PROMPT_RESUME_ONLY, ResumeAnalysis)
    analysis.suggestions = sanitize_suggestions(analysis.suggestions, resume_text)
    return analysis, provider


def generate_cover_letter(resume_text: str, jd_text: str) -> tuple[CoverLetter, str]:
    """Write a 250-300 word cover letter from a (redacted) resume and a job description."""
    payload = f"JOB DESCRIPTION:\n{jd_text}\n\nRESUME TEXT:\n{resume_text}"
    return run_with_fallback(payload, prompts.SYSTEM_PROMPT_COVER_LETTER, CoverLetter)


def generate_interview_prep(resume_text: str, jd_text: Optional[str] = None) -> tuple[InterviewPrep, str]:
    """Produce 8 likely interview questions with tips grounded in the candidate's experience."""
    jd_part = f"JOB DESCRIPTION:\n{jd_text}\n\n" if jd_text and jd_text.strip() else ""
    payload = f"{jd_part}RESUME TEXT:\n{resume_text}"
    return run_with_fallback(payload, prompts.SYSTEM_PROMPT_INTERVIEW, InterviewPrep)
