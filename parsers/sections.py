"""Split raw resume text into canonical sections using heading detection."""
import re

# Canonical section -> heading words/phrases that introduce it.
SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "summary": ("summary", "professional summary", "profile", "objective", "career objective", "about me",
                "about", "professional profile", "career summary"),
    "skills": ("skills", "technical skills", "core skills", "key skills", "skill set", "skillset",
               "core competencies", "competencies", "technologies", "tech stack", "tools", "expertise"),
    "experience": ("experience", "work", "work experience", "professional experience", "employment",
                   "employment history", "work history", "internships", "internship", "career history"),
    "projects": ("projects", "personal projects", "academic projects", "key projects", "project work",
                 "selected projects"),
    "education": ("education", "academic background", "academics", "qualifications",
                  "educational qualifications", "academic qualifications"),
    "certifications": ("certifications", "certificates", "licenses", "courses", "training"),
    "achievements": ("achievements", "awards", "honors", "accomplishments", "extracurricular",
                     "activities", "publications", "volunteering", "languages", "interests", "hobbies"),
}

_ALIAS_TO_SECTION = {alias: section for section, aliases in SECTION_ALIASES.items() for alias in aliases}
# Longest aliases first so "work experience" wins over "experience".
_ALIASES_BY_LENGTH = sorted(_ALIAS_TO_SECTION, key=len, reverse=True)
_WEAK_INLINE_LABELS = {"tools", "technologies", "tech stack", "expertise", "languages", "about",
                       "training", "courses", "activities", "interests", "competencies"}
_INLINE_HEADING_RE =re.compile(r"^([A-Za-z &/]{3,40})\s*[:\-–|]\s*(.+)$")


def _clean(line: str) -> str:
    """Lowercase a line and strip bullets, punctuation and extra spaces."""
    line = re.sub(r"[^a-z &/]", " ", line.lower())
    return re.sub(r"\s+", " ", line).strip()


def detect_heading(line: str) -> tuple[str, str] | None:
    """Return ``(section, trailing_content)`` if ``line`` is a section heading.

    Recognizes standalone headings ("TECHNICAL SKILLS", "Experience:") and
    inline ones ("Skills: Python, SQL"), where the trailing content is kept.
    """
    stripped = line.strip()
    if not stripped or len(stripped) > 60:
        return None

    inline = _INLINE_HEADING_RE.match(stripped)
    if inline:
        label = _clean(inline.group(1))
        # "Technologies: React, Node" under a project must not start a new section.
        if label in _ALIAS_TO_SECTION and label not in _WEAK_INLINE_LABELS:
            return _ALIAS_TO_SECTION[label], inline.group(2).strip()

    cleaned = _clean(stripped)
    if not cleaned or len(cleaned.split()) > 4:
        return None
    if cleaned in _ALIAS_TO_SECTION:
        return _ALIAS_TO_SECTION[cleaned], ""
    # Short all-caps headings such as "TECHNICAL SKILLS & TOOLS".
    if stripped.isupper() or stripped.istitle():
        for alias in _ALIASES_BY_LENGTH:
            if re.search(rf"\b{re.escape(alias)}\b", cleaned):
                return _ALIAS_TO_SECTION[alias], ""
    return None


def split_sections(text: str) -> dict[str, str]:
    """Split resume text into ``{section: text}``.

    Text before the first heading goes to ``"header"``; repeated headings are
    concatenated.
    """
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in text.splitlines():
        heading = detect_heading(line)
        if heading:
            current, rest = heading
            sections.setdefault(current, [])
            if rest:
                sections[current].append(rest)
        else:
            sections[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def found_sections(text: str) -> set[str]:
    """Return the canonical section names that have a heading in ``text``."""
    return {name for name in split_sections(text) if name != "header"}
