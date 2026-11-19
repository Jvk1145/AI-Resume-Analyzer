"""Deterministic, explainable ATS score (no AI).

Each category returns points and human-readable reasons. Inputs are the raw
resume text, the parsed resume dict (used only as a bullet fallback), the
optional JD match result, and optional layout signals from the original file.

Category weights (total 100):
    contact 10, sections 15, keywords 30, action_verbs 10, quantified 15,
    bullet_quality 10, length 5, layout 5.
When there is no usable job description, the 30 keyword points are shared out
across the other categories in proportion to their weights.
"""
import math
import re
from datetime import date
from typing import Any, Mapping, Optional, TypedDict

from parsers.contact import extract_contact
from parsers.sections import detect_heading, found_sections, split_sections

WEIGHTS: dict[str, float] = {
    "contact": 10,
    "sections": 15,
    "keywords": 30,
    "action_verbs": 10,
    "quantified": 15,
    "bullet_quality": 10,
    "length": 5,
    "layout": 5,
}
LABELS: dict[str, str] = {
    "contact": "Contact information",
    "sections": "Standard sections",
    "keywords": "JD keyword coverage",
    "action_verbs": "Action verbs",
    "quantified": "Quantified achievements",
    "bullet_quality": "Bullet quality",
    "length": "Length",
    "layout": "ATS-friendly layout",
}

STRONG_VERBS: frozenset[str] = frozenset("""
accelerated achieved administered analyzed architected automated boosted built capitalized centralized
championed coached collaborated conceived conducted consolidated constructed coordinated created cut
debugged decreased delivered deployed designed developed devised diagnosed directed documented doubled
drove eliminated enabled engineered enhanced established evaluated executed expanded expedited facilitated
forecasted formulated founded generated grew guided headed identified implemented improved increased
initiated integrated introduced launched led maintained managed mentored migrated minimized modernized
monitored negotiated optimized orchestrated organized overhauled oversaw partnered pioneered planned
presented prioritized produced programmed proposed prototyped published rebuilt reduced redesigned
refactored remodeled reorganized resolved restructured revamped scaled secured simplified spearheaded
standardized streamlined strengthened supervised tested trained transformed tripled troubleshot unified
upgraded validated won wrote
""".split())

FIRST_PERSON_RE = re.compile(r"\b(i|me|my|myself)\b", re.IGNORECASE)
QUANTIFIED_RE = re.compile(r"\d|%|₹|\$|€|£")
BULLET_RE = re.compile(r"^\s*[•●▪◦‣○■➢✓*\-–—]\s*(.+)")
YEAR_RANGE_RE = re.compile(
    r"((?:19|20)\d{2})\s*(?:-|–|—|to)\s*(?:[A-Za-z]{3,9}\.?\s+)?((?:19|20)\d{2}|present|current|now|till date|date)",
    re.IGNORECASE,
)


class Category(TypedDict):
    """Score for one category."""

    label: str
    score: float
    max: float
    reasons: list[str]


def _category(key: str, ratio: float, reasons: list[str]) -> Category:
    """Build a category result from a 0-1 ratio of its base weight."""
    ratio = max(0.0, min(1.0, ratio))
    return Category(label=LABELS[key], score=round(WEIGHTS[key] * ratio, 1), max=WEIGHTS[key], reasons=reasons)


# --------------------------------------------------------------------------- bullets


def extract_bullets(raw_text: str, resume: Optional[Mapping[str, Any]] = None) -> tuple[list[str], str]:
    """Return resume bullets and where they came from.

    Bullet-marked lines in the raw text are used when at least 3 exist
    (wrapped continuation lines starting in lowercase are re-joined). Otherwise
    the parsed experience bullets and project descriptions are used.
    """
    bullets: list[str] = []
    in_bullet = False  # True while the previous line was a bullet or its continuation
    for line in raw_text.splitlines():
        match = BULLET_RE.match(line)
        if match:
            bullets.append(match.group(1).strip())
            in_bullet = True
        elif in_bullet and line.strip()[:1].islower() and not detect_heading(line):
            bullets[-1] = f"{bullets[-1]} {line.strip()}"
        else:
            in_bullet = False
    bullets = [b for b in bullets if len(b.split()) >= 2]
    if len(bullets) >= 3 or not resume:
        return bullets, "resume text"

    parsed: list[str] = []
    for job in resume.get("experience") or []:
        parsed.extend(str(b) for b in job.get("bullets") or [])
    for proj in resume.get("projects") or []:
        parsed.extend(line for line in str(proj.get("description") or "").split("\n") if line.strip())
    return (parsed, "parsed resume") if len(parsed) > len(bullets) else (bullets, "resume text")


def _first_word(bullet: str) -> str:
    """Return the lowercased first word of a bullet without punctuation."""
    words = re.findall(r"[A-Za-z]+", bullet)
    return words[0].lower() if words else ""


# --------------------------------------------------------------------------- categories


def score_contact(raw_text: str) -> Category:
    """Email 4, phone 3, LinkedIn or GitHub 3."""
    contact = extract_contact(raw_text)
    points, reasons = 0.0, []
    for field, pts, name in (("email", 4, "Email"), ("phone", 3, "Phone number")):
        if contact[field]:
            points += pts
            reasons.append(f"✓ {name} found.")
        else:
            reasons.append(f"✗ No {name.lower()} found (-{pts}).")
    profiles = [n for n, f in (("LinkedIn", "linkedin"), ("GitHub", "github")) if contact[f]]
    if profiles:
        points += 3
        reasons.append(f"✓ {' and '.join(profiles)} profile found.")
    else:
        reasons.append("✗ No LinkedIn or GitHub URL found (-3).")
    return _category("contact", points / 10, reasons)


def score_sections(raw_text: str) -> Category:
    """Summary, Skills, Experience-or-Projects and Education: 3.75 points each."""
    present = found_sections(raw_text)
    checks = [
        ("Summary/Objective", "summary" in present),
        ("Skills", "skills" in present),
        ("Experience or Projects", bool({"experience", "projects"} & present)),
        ("Education", "education" in present),
    ]
    reasons = [f"✓ {name} section found." if ok else f"✗ No '{name}' heading found." for name, ok in checks]
    return _category("sections", sum(ok for _, ok in checks) / len(checks), reasons)


def score_keywords(jd_match: Optional[Mapping[str, Any]]) -> Category:
    """Weighted JD skill coverage (required skills count double)."""
    pct = float(jd_match.get("match_percentage", 0)) if jd_match else 0.0
    total = int(jd_match.get("jd_skill_count", 0)) if jd_match else 0
    matched = len(jd_match.get("matched", [])) if jd_match else 0
    reasons = [f"{matched} of {total} skills from the job description found ({pct:.0f}% weighted)."]
    missing_req = list(jd_match.get("missing_required", [])) if jd_match else []
    if missing_req:
        reasons.append("✗ Missing required: " + ", ".join(missing_req[:8]))
    missing_nice = list(jd_match.get("missing_nice", [])) if jd_match else []
    if missing_nice:
        reasons.append("Missing nice-to-have: " + ", ".join(missing_nice[:8]))
    return _category("keywords", pct / 100, reasons)


def score_action_verbs(bullets: list[str]) -> Category:
    """Share of bullets starting with a strong action verb; full marks at 80%."""
    if not bullets:
        return _category("action_verbs", 0, ["✗ No bullet points detected."])
    weak = [b for b in bullets if _first_word(b) not in STRONG_VERBS]
    ratio = 1 - len(weak) / len(bullets)
    reasons = [f"{len(bullets) - len(weak)} of {len(bullets)} bullets start with a strong action verb (target 80%)."]
    reasons += [f"Weak start: “{b[:70]}”" for b in weak[:3]]
    return _category("action_verbs", ratio / 0.8, reasons)


def score_quantified(bullets: list[str]) -> Category:
    """Share of bullets containing a number, %, ₹ or $; full marks at 50%."""
    if not bullets:
        return _category("quantified", 0, ["✗ No bullet points detected."])
    with_numbers = [b for b in bullets if QUANTIFIED_RE.search(b)]
    ratio = len(with_numbers) / len(bullets)
    reasons = [f"{len(with_numbers)} of {len(bullets)} bullets include a number or metric (target 50%)."]
    if ratio < 0.5:
        reasons.append("Add measurable results: %, time saved, users, revenue, team size.")
    return _category("quantified", ratio / 0.5, reasons)


def score_bullet_quality(bullets: list[str]) -> Category:
    """Share of bullets that are 8-30 words and avoid first person; full marks at 80%."""
    if not bullets:
        return _category("bullet_quality", 0, ["✗ No bullet points detected."])
    short = [b for b in bullets if len(b.split()) < 8]
    long = [b for b in bullets if len(b.split()) > 30]
    first_person = [b for b in bullets if FIRST_PERSON_RE.search(b)]
    bad = {id(b) for b in short + long + first_person}
    ratio = 1 - len(bad) / len(bullets)
    reasons = [f"{len(bullets) - len(bad)} of {len(bullets)} bullets are 8-30 words without “I/me/my” (target 80%)."]
    if short:
        reasons.append(f"{len(short)} bullet(s) under 8 words.")
    if long:
        reasons.append(f"{len(long)} bullet(s) over 30 words.")
    if first_person:
        reasons.append(f"{len(first_person)} bullet(s) use first person.")
    return _category("bullet_quality", ratio / 0.8, reasons)


def estimate_years_experience(raw_text: str, today: Optional[date] = None) -> float:
    """Estimate total years of experience from year ranges in the Experience section.

    Overlapping ranges are merged; "Present"/"Current" means the current year.
    """
    current_year = (today or date.today()).year
    experience = split_sections(raw_text).get("experience", "")
    spans: list[tuple[int, int]] = []
    for start, end in YEAR_RANGE_RE.findall(experience):
        end_year = current_year if not end[:1].isdigit() else int(end)
        if int(start) <= end_year:
            spans.append((int(start), end_year))
    total, last_end = 0.0, None
    for start, end in sorted(spans):
        if last_end is not None and start < last_end:
            start = last_end
        if end > start:
            total += end - start
        last_end = max(last_end or end, end)
    return float(total)


def score_length(raw_text: str, pages: Optional[int]) -> Category:
    """Pages (3 pts) and word count (2 pts), judged against years of experience."""
    words = len(raw_text.split())
    years = estimate_years_experience(raw_text)
    junior = years < 3
    estimated = pages is None
    page_count = pages if pages is not None else max(1, math.ceil(words / 550))
    page_note = f"~{page_count} page(s) (estimated from word count)" if estimated else f"{page_count} page(s)"
    reasons = [f"About {years:.0f} year(s) of experience detected; {page_note}; {words} words."]

    if junior:
        page_pts = 3 if page_count == 1 else 1.5 if page_count == 2 else 0
        target = "1 page is ideal with under 3 years of experience."
        low, high = 300, 700
    else:
        page_pts = 3 if page_count <= 2 else 0
        target = "Keep it to 2 pages at most."
        low, high = 400, 1100
    reasons.append(("✓ " if page_pts == 3 else "✗ ") + target)

    if low <= words <= high:
        word_pts = 2
        reasons.append(f"✓ Word count is in the {low}-{high} range.")
    elif 200 <= words < low or high < words <= high * 1.3:
        word_pts = 1
        reasons.append(f"Word count is a little outside the {low}-{high} range.")
    else:
        word_pts = 0
        reasons.append(f"✗ Word count is far outside the {low}-{high} range.")
    return _category("length", (page_pts + word_pts) / 5, reasons)


def score_layout(layout: Optional[Mapping[str, Any]]) -> Category:
    """Start at 5; tables -2, multiple columns -2, images -1, header/footer text -1."""
    if not layout:
        return _category("layout", 1, ["Layout could not be checked for this file."])
    if layout.get("image_only"):
        return _category("layout", 0, [
            "✗ The resume is an image with no text layer, so most ATS software reads nothing from it (-5).",
            "It was read here with OCR. Export it from Word or Google Docs as a text PDF to fix this.",
        ])
    points, reasons = 5.0, []
    checks = (
        ("has_tables", 2, "Tables found: many ATS parsers read table cells out of order."),
        ("multi_column", 2, "Multi-column layout: text may be read across columns."),
        ("has_images", 1, "Images/icons found: ATS cannot read them."),
        ("header_footer_text", 1, "Text in the header/footer area is often skipped by ATS."),
    )
    for key, penalty, message in checks:
        if layout.get(key):
            points -= penalty
            reasons.append(f"✗ {message} (-{penalty})")
    if points == 5:
        reasons.append("✓ Single-column layout with no tables, images or header/footer text.")
    return _category("layout", points / 5, reasons)


# --------------------------------------------------------------------------- total


def calculate_ats_score(
    raw_text: str,
    resume: Optional[Mapping[str, Any]] = None,
    jd_match: Optional[Mapping[str, Any]] = None,
    layout: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Compute the 0-100 ATS score.

    Args:
        raw_text: Original (unredacted) resume text.
        resume: Parsed resume dict; used only when raw text has few bullet markers.
        jd_match: Output of ``matching.jd_matcher.match_resume_to_jd`` or None.
        layout: ``LayoutInfo.to_dict()`` for the uploaded file, or None.

    Returns:
        ``{"total_score": int, "has_jd": bool,
        "breakdown": {key: {"label", "score", "max", "reasons"}}}``
    """
    bullets, source = extract_bullets(raw_text, resume)
    breakdown: dict[str, Category] = {
        "contact": score_contact(raw_text),
        "sections": score_sections(raw_text),
        "keywords": score_keywords(jd_match),
        "action_verbs": score_action_verbs(bullets),
        "quantified": score_quantified(bullets),
        "bullet_quality": score_bullet_quality(bullets),
        "length": score_length(raw_text, layout.get("pages") if layout else None),
        "layout": score_layout(layout),
    }
    if bullets:
        breakdown["action_verbs"]["reasons"].append(f"Bullets read from the {source}.")

    has_jd = bool(jd_match and jd_match.get("jd_skill_count"))
    if not has_jd:
        scale = 100 / (100 - WEIGHTS["keywords"])
        for key, cat in breakdown.items():
            if key == "keywords":
                continue
            cat["score"] = round(cat["score"] * scale, 1)
            cat["max"] = round(cat["max"] * scale, 1)
        note = ("No job description provided" if not jd_match
                else "No recognizable skills found in the job description")
        breakdown["keywords"] = Category(
            label=LABELS["keywords"], score=0, max=0,
            reasons=[f"{note}; its 30 points were shared across the other categories."],
        )

    total = round(sum(cat["score"] for cat in breakdown.values()))
    return {"total_score": int(min(100, total)), "has_jd": has_jd, "breakdown": breakdown}
