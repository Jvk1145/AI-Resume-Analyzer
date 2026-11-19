"""Deterministic job-description matching against the whole resume text."""
import re
from functools import lru_cache
from typing import Any, Iterable

from matching.skills_db import ALL_SKILLS
from parsers.sections import split_sections

REQUIRED_WEIGHT = 2
NICE_WEIGHT = 1

REQUIRED_CUES = re.compile(
    r"\b(required|requirements?|must|mandatory|essential|need to have|minimum qualifications?|"
    r"basic qualifications?|required qualifications?)\b",
    re.IGNORECASE,
)
NICE_CUES = re.compile(
    r"\b(nice[- ]to[- ]have|preferred|bonus|plus|desirable|good[- ]to[- ]have|advantage|optional|"
    r"familiarity)\b",
    re.IGNORECASE,
)

SECTION_LABELS = {
    "skills": "Skills",
    "experience": "Experience",
    "projects": "Projects",
    "summary": "Summary",
    "education": "Education",
    "certifications": "Certifications",
}
LOCATION_ORDER = ["Skills", "Experience", "Projects", "Summary", "Education", "Certifications", "Other"]

DISPLAY_NAMES = {
    "aws": "AWS", "gcp": "GCP", "sql": "SQL", "php": "PHP", "html": "HTML", "css": "CSS", "etl": "ETL",
    "seo": "SEO", "sap": "SAP", "crm": "CRM", "erp": "ERP", "dbt": "dbt", "ios": "iOS", "jwt": "JWT",
    "sas": "SAS", "spss": "SPSS", "vba": "VBA", "tdd": "TDD", "owasp": "OWASP", "sdlc": "SDLC",
    "ci/cd": "CI/CD", "ui/ux": "UI/UX", "a/b testing": "A/B testing", "rest api": "REST API",
    "grpc": "gRPC", "mlops": "MLOps", "devops": "DevOps", "graphql": "GraphQL", "mysql": "MySQL",
    "postgresql": "PostgreSQL", "mongodb": "MongoDB", "javascript": "JavaScript", "typescript": "TypeScript",
    "github": "GitHub", "gitlab": "GitLab", "github actions": "GitHub Actions", "fastapi": "FastAPI",
    "pytorch": "PyTorch", "tensorflow": "TensorFlow", "scikit-learn": "scikit-learn", "numpy": "NumPy",
    "power bi": "Power BI", "bigquery": "BigQuery", "dynamodb": "DynamoDB", "nestjs": "NestJS",
    "next.js": "Next.js", "node.js": "Node.js", "ec2": "EC2", "s3": "S3", "aws lambda": "AWS Lambda",
    "c++": "C++", "c#": "C#", ".net": ".NET", "asp.net": "ASP.NET", "pl/sql": "PL/SQL", "t-sql": "T-SQL",
    "large language models": "Large language models (LLMs)", "llamaindex": "LlamaIndex",
    "natural language processing": "Natural language processing (NLP)", "openai api": "OpenAI API",
}


def display_name(skill: str) -> str:
    """Human-friendly name for a canonical skill."""
    return DISPLAY_NAMES.get(skill, skill[:1].upper() + skill[1:])


def _term_pattern(term: str) -> str:
    """Regex for one alias with skill-friendly word boundaries.

    ``+``/``#`` count as word characters (so "c" never matches inside "c++").
    Single-letter aliases also reject neighbouring ``&``/``-``/``'``/``.`` so
    "R&D" or "C-suite" are not read as skills. Aliases prefixed with "=" match
    only their exact casing or ALL CAPS.
    """
    case_sensitive = term.startswith("=")
    term = term.lstrip("=")
    single = len(term) == 1
    before = r"(?<![A-Za-z0-9+#&'\-.])" if single else r"(?<![A-Za-z0-9+#])"
    after = r"(?![A-Za-z0-9+#&'\-])" if single else r"(?![A-Za-z0-9+#])"

    def body(text: str) -> str:
        return r"\s+".join(re.escape(part) for part in text.split())

    if case_sensitive:
        forms = dict.fromkeys([body(term), body(term.upper())])
        return f"{before}(?:{'|'.join(forms)}){after}"
    return f"(?i:{before}{body(term)}{after})"


@lru_cache(maxsize=1)
def _compiled() -> list[tuple[str, re.Pattern[str]]]:
    """Compile one combined pattern per canonical skill (cached)."""
    compiled = []
    for canonical, aliases in ALL_SKILLS.items():
        sensitive = {a.lstrip("=").lower() for a in aliases if a.startswith("=")}
        terms = list(aliases)
        if canonical.lower() not in sensitive:
            terms.insert(0, canonical)
        pattern = "|".join(_term_pattern(t) for t in terms)
        compiled.append((canonical, re.compile(pattern)))
    return compiled


def find_skills(text: str) -> list[str]:
    """Return canonical skills found in ``text``, ordered by first appearance."""
    hits: list[tuple[int, str]] = []
    for canonical, pattern in _compiled():
        match = pattern.search(text)
        if match:
            hits.append((match.start(), canonical))
    return [skill for _, skill in sorted(hits)]


def _is_heading(line: str) -> bool:
    """Short line ending in ':' or written in capitals."""
    stripped = line.strip().strip("*#").strip()
    return 0 < len(stripped.split()) <= 6 and (stripped.endswith(":") or stripped.isupper())


def extract_jd_skills(jd_text: str) -> dict[str, str]:
    """Return ``{skill: "required" | "nice"}`` for skills found in the job description.

    A skill is *required* if it appears in a sentence with words like
    required/must/mandatory, or under a heading such as "Requirements:" /
    "Must have:". Cues like preferred/nice to have/plus override that for their
    sentence. Everything else is *nice to have*. If a skill appears more than
    once, any required mention wins.
    """
    result: dict[str, str] = {}
    mode = "nice"
    for line in jd_text.splitlines():
        if _is_heading(line):
            mode = "nice" if NICE_CUES.search(line) else "required" if REQUIRED_CUES.search(line) else "nice"
        for sentence in re.split(r"(?<=[.;!?])\s+", line):
            if not sentence.strip():
                continue
            if NICE_CUES.search(sentence):
                level = "nice"
            elif REQUIRED_CUES.search(sentence):
                level = "required"
            else:
                level = mode
            for skill in find_skills(sentence):
                if result.get(skill) != "required":
                    result[skill] = level
    return result


def locate_skills(resume_text: str, skills: Iterable[str]) -> dict[str, list[str]]:
    """Return ``{skill: [section labels]}`` for each skill found anywhere in the resume."""
    sections = split_sections(resume_text)
    wanted = set(skills)
    patterns = {canonical: pattern for canonical, pattern in _compiled() if canonical in wanted}
    locations: dict[str, list[str]] = {}
    for name, text in sections.items():
        label = SECTION_LABELS.get(name, "Other")
        for skill, pattern in patterns.items():
            if pattern.search(text):
                locations.setdefault(skill, [])
                if label not in locations[skill]:
                    locations[skill].append(label)
    for skill in locations:
        locations[skill].sort(key=LOCATION_ORDER.index)
    return locations


def match_resume_to_jd(resume_text: str, jd_text: str) -> dict[str, Any]:
    """Compare the whole resume text with the JD's skills.

    Weighted match % = matched weight / total weight, with required skills
    weighted 2 and nice-to-have skills weighted 1.

    Returns:
        ``{"match_percentage", "jd_skill_count", "required", "nice", "matched",
        "missing_required", "missing_nice", "locations"}`` (skill names are canonical).
    """
    jd_skills = extract_jd_skills(jd_text)
    locations = locate_skills(resume_text, jd_skills)
    required = [s for s, lvl in jd_skills.items() if lvl == "required"]
    nice = [s for s, lvl in jd_skills.items() if lvl == "nice"]
    matched = [s for s in jd_skills if s in locations]

    total = REQUIRED_WEIGHT * len(required) + NICE_WEIGHT * len(nice)
    got = sum(REQUIRED_WEIGHT if jd_skills[s] == "required" else NICE_WEIGHT for s in matched)
    return {
        "match_percentage": round(100 * got / total, 1) if total else 0.0,
        "jd_skill_count": len(jd_skills),
        "required": required,
        "nice": nice,
        "matched": matched,
        "missing_required": [s for s in required if s not in locations],
        "missing_nice": [s for s in nice if s not in locations],
        "locations": locations,
    }
