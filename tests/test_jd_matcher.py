"""Tests for skill extraction, required/nice detection and resume locations."""
from fixtures import JD_TEXT, STRONG_RESUME
from matching.jd_matcher import extract_jd_skills, find_skills, locate_skills, match_resume_to_jd
from matching.skills_db import skill_count


def test_database_size() -> None:
    assert skill_count() >= 300


def test_synonyms_normalize_to_canonical() -> None:
    found = find_skills("Worked with JS, ML, Postgres, React.js, k8s and sklearn")
    for skill in ("javascript", "machine learning", "postgresql", "react", "kubernetes", "scikit-learn"):
        assert skill in found


def test_symbols_and_short_names() -> None:
    found = find_skills("Languages: C++, C#, Go and R")
    assert {"c++", "c#", "go", "r"} <= set(found)
    assert "c" not in found  # "C" inside "C++"/"C#" is not plain C


def test_english_words_are_not_skills() -> None:
    found = find_skills("We react quickly, go the extra mile, excel at R&D and brief the C-suite.")
    assert not {"react", "go", "excel", "r", "c"} & set(found)


def test_required_vs_nice_from_headings() -> None:
    skills = extract_jd_skills(JD_TEXT)
    assert skills["python"] == "required"
    assert skills["postgresql"] == "required"
    assert skills["kubernetes"] == "nice"
    assert skills["graphql"] == "nice"


def test_required_vs_nice_from_sentence_cues() -> None:
    skills = extract_jd_skills("You must know Java. Experience with Kotlin is a plus. We use Git daily.")
    assert skills == {"java": "required", "kotlin": "nice", "git": "nice"}


def test_required_wins_when_repeated() -> None:
    assert extract_jd_skills("Docker is a plus.\nDocker is mandatory.")["docker"] == "required"


def test_location_detection() -> None:
    locations = locate_skills(STRONG_RESUME, ["django", "react", "python", "docker"])
    assert locations["django"] == ["Skills", "Experience"]
    assert locations["react"] == ["Projects"]
    assert "Skills" in locations["python"]


def test_skill_only_in_experience_counts_as_matched() -> None:
    resume = "SKILLS\nPython\n\nEXPERIENCE\n• Deployed services with Kubernetes on AWS"
    result = match_resume_to_jd(resume, "Required: Python, Kubernetes")
    assert result["missing_required"] == []
    assert result["locations"]["kubernetes"] == ["Experience"]


def test_weighted_percentage() -> None:
    resume = "SKILLS\nPython, Kubernetes"
    jd = "Requirements:\nPython\nDocker\nNice to have:\nKubernetes\nGraphQL"
    result = match_resume_to_jd(resume, jd)
    # matched: python (2) + kubernetes (1) = 3 of a total 2 + 2 + 1 + 1 = 6
    assert result["match_percentage"] == 50.0
    assert result["missing_required"] == ["docker"]
    assert result["missing_nice"] == ["graphql"]


def test_empty_jd() -> None:
    result = match_resume_to_jd(STRONG_RESUME, "We are a friendly team.")
    assert result["jd_skill_count"] == 0
    assert result["match_percentage"] == 0.0
