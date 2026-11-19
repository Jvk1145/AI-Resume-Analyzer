"""Regex-based contact detection, shared by ATS scoring, redaction and DOCX export."""
import re

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Broad candidate; real phones are confirmed by digit count (10-15) so that
# year ranges like "2019 - 2021" are never treated as phone numbers.
PHONE_CANDIDATE_RE = re.compile(r"(?<![\w/])\+?\(?\d[\d\s().-]{7,}\d(?![\w/])")

LINKEDIN_RE = re.compile(r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/[^\s|,;)]+", re.IGNORECASE)
GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[^\s|,;)]+", re.IGNORECASE)


# Keys: "email", "phone", "linkedin", "github" (empty string when absent).
Contact = dict[str, str]


def find_phones(text: str) -> list[str]:
    """Return phone-number substrings (10-15 digits) found in ``text``."""
    phones = []
    for match in PHONE_CANDIDATE_RE.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if 10 <= len(digits) <= 15:
            phones.append(match.group().strip())
    return phones


def extract_contact(text: str) -> Contact:
    """Extract the first email, phone, LinkedIn and GitHub URL from raw resume text."""
    email = EMAIL_RE.search(text)
    phones = find_phones(text)
    linkedin = LINKEDIN_RE.search(text)
    github = GITHUB_RE.search(text)
    return {
        "email": email.group() if email else "",
        "phone": phones[0] if phones else "",
        "linkedin": linkedin.group().rstrip(".") if linkedin else "",
        "github": github.group().rstrip(".") if github else "",
    }
