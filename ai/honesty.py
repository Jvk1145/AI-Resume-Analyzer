"""Deterministic guards that keep AI rewrites honest."""
import difflib
import re

from ai.schemas import Suggestion

# Numbers with optional currency prefix and %, x, k/m/b or + suffix: "40%", "$2M", "3x", "1,200+".
# Tokens glued to letters ("K8s", "S3", "EC2", "3D") are names, not metrics, and are ignored.
NUMBER_RE = re.compile(
    r"(?<![A-Za-z\d])[$₹€£]?\d[\d,]*(?:\.\d+)?(?:\s?%|x\b|[kKmMbB]\b|\+)?(?![A-Za-z\d])"
)
_BULLET_CHARS = " \t•●▪◦‣○■➢✓*-–—"


def _digits(token: str) -> str:
    """Digits (and decimal point) of a numeric token, for comparison."""
    return re.sub(r"[^\d.]", "", token).rstrip(".")


def _placeholder(token: str) -> str:
    """Placeholder that replaces an invented number."""
    if "%" in token:
        return "[X%]"
    if token[:1] in "$₹€£":
        return "[$amount]"
    return "[number]"


def find_invented_numbers(original: str, improved: str) -> list[str]:
    """Return numeric tokens in ``improved`` whose digits do not appear in ``original``."""
    known = {_digits(t) for t in NUMBER_RE.findall(original)}
    return [t.strip() for t in NUMBER_RE.findall(improved) if _digits(t) and _digits(t) not in known]


def strip_invented_numbers(original: str, improved: str) -> str:
    """Replace numbers the AI added (not present in the original bullet) with placeholders."""

    def repl(match: re.Match[str]) -> str:
        token = match.group()
        known = {_digits(t) for t in NUMBER_RE.findall(original)}
        if not _digits(token) or _digits(token) in known:
            return token
        return _placeholder(token)

    return NUMBER_RE.sub(repl, improved)


def _normalize(text: str) -> str:
    """Lowercase, strip bullet markers and collapse whitespace."""
    return re.sub(r"\s+", " ", text.strip(_BULLET_CHARS)).lower()


def is_grounded(original_bullet: str, resume_text: str, threshold: float = 0.85) -> bool:
    """True if ``original_bullet`` really appears in the resume (exactly or nearly).

    Whole-text substring matching handles bullets wrapped across lines; the
    per-line similarity fallback tolerates small copy differences.
    """
    target = _normalize(original_bullet)
    if not target:
        return False
    if target in _normalize(resume_text):
        return True
    return any(
        difflib.SequenceMatcher(None, target, _normalize(line)).ratio() >= threshold
        for line in resume_text.splitlines()
        if line.strip()
    )


def sanitize_suggestions(suggestions: list[Suggestion], resume_text: str) -> list[Suggestion]:
    """Drop suggestions whose original bullet is not in the resume and remove invented numbers."""
    clean: list[Suggestion] = []
    for sug in suggestions:
        if not is_grounded(sug.original_bullet, resume_text):
            continue
        improved = strip_invented_numbers(sug.original_bullet, sug.improved_bullet)
        clean.append(sug.model_copy(update={"improved_bullet": improved}))
    return clean
