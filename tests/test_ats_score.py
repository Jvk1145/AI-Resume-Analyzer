"""Tests for the deterministic ATS engine, one block per category."""
from datetime import date

import pytest

from fixtures import JD_TEXT, STRONG_RESUME, WEAK_RESUME
from matching.jd_matcher import match_resume_to_jd
from scoring import ats_score as ats


def test_contact_full_and_missing() -> None:
    assert ats.score_contact(STRONG_RESUME)["score"] == 10
    empty = ats.score_contact("Jane Doe\nSoftware engineer")
    assert empty["score"] == 0
    assert any("email" in r.lower() for r in empty["reasons"])


def test_contact_partial_points() -> None:
    assert ats.score_contact("jane@example.com\ngithub.com/jane")["score"] == 7  # email 4 + profile 3


def test_contact_year_range_is_not_a_phone() -> None:
    assert ats.score_contact("Worked 2019 - 2021 at Acme")["score"] == 0


def test_sections_all_and_partial() -> None:
    assert ats.score_sections(STRONG_RESUME)["score"] == 15
    partial = ats.score_sections("EXPERIENCE\nDid things\n\nEDUCATION\nBSc")
    assert partial["score"] == 7.5
    assert any("Skills" in r and "✗" in r for r in partial["reasons"])


def test_sections_projects_count_as_experience() -> None:
    cat = ats.score_sections("Projects\n- Built an app")
    assert any("✓ Experience or Projects" in r for r in cat["reasons"])


def test_keywords_uses_weighted_match() -> None:
    match = match_resume_to_jd(STRONG_RESUME, JD_TEXT)
    cat = ats.score_keywords(match)
    assert cat["max"] == 30
    assert cat["score"] == pytest.approx(30 * match["match_percentage"] / 100, abs=0.1)


def test_action_verbs() -> None:
    strong = ["Built a thing", "Led a team", "Reduced costs", "Designed APIs", "Automated tests"]
    assert ats.score_action_verbs(strong)["score"] == 10
    weak = ["Responsible for the website", "Worked on stuff", "Helped team", "Was involved in QA"]
    assert ats.score_action_verbs(weak)["score"] == 0
    assert ats.score_action_verbs([])["score"] == 0


def test_quantified_achievements() -> None:
    bullets = ["Cut costs by 30%", "Saved $2M annually", "Built an app", "Wrote documentation"]
    assert ats.score_quantified(bullets)["score"] == 15  # 50% quantified = full marks
    assert ats.score_quantified(["Built an app", "Wrote docs"])["score"] == 0
    assert ats.score_quantified(["Grew revenue by ₹5 lakh", "Built UI"])["score"] == 15


def test_bullet_quality_length_and_first_person() -> None:
    good = ["Designed and shipped a REST API used by four internal teams every day"] * 4
    assert ats.score_bullet_quality(good)["score"] == 10
    bad = ["Did QA", "I built the entire platform myself from scratch over many weekends"]
    cat = ats.score_bullet_quality(bad)
    assert cat["score"] == 0
    assert any("first person" in r for r in cat["reasons"])
    assert any("under 8 words" in r for r in cat["reasons"])


def test_years_of_experience_merges_overlaps() -> None:
    text = "EXPERIENCE\nA | 2018 - 2020\nB | Jan 2019 – Dec 2021\n\nEDUCATION\nBSc 2010 - 2014"
    assert ats.estimate_years_experience(text, today=date(2024, 1, 1)) == 3.0


def test_length_junior_two_pages_penalized() -> None:
    text = "EXPERIENCE\nIntern | 2023 - 2024\n" + "word " * 500
    one_page = ats.score_length(text, pages=1)
    two_pages = ats.score_length(text, pages=2)
    assert one_page["score"] == 5
    assert one_page["score"] > two_pages["score"]


def test_layout_penalties() -> None:
    assert ats.score_layout({"has_tables": False})["score"] == 5
    cat = ats.score_layout(
        {"has_tables": True, "multi_column": True, "has_images": True, "header_footer_text": True}
    )
    assert cat["score"] == 0
    assert len(cat["reasons"]) == 4
    assert ats.score_layout({"has_images": True})["score"] == 4


def test_total_without_jd_redistributes_weight() -> None:
    result = ats.calculate_ats_score(STRONG_RESUME, layout={"pages": 1})
    assert result["has_jd"] is False
    assert result["breakdown"]["keywords"]["max"] == 0
    assert sum(c["max"] for c in result["breakdown"].values()) == pytest.approx(100, abs=0.5)


def test_total_with_jd_and_ordering() -> None:
    match = match_resume_to_jd(STRONG_RESUME, JD_TEXT)
    strong = ats.calculate_ats_score(STRONG_RESUME, jd_match=match, layout={"pages": 1})
    weak = ats.calculate_ats_score(WEAK_RESUME, jd_match=match_resume_to_jd(WEAK_RESUME, JD_TEXT))
    assert strong["has_jd"] is True
    assert sum(c["max"] for c in strong["breakdown"].values()) == 100
    assert 0 <= weak["total_score"] < strong["total_score"] <= 100
    for cat in strong["breakdown"].values():
        assert {"score", "max", "reasons"} <= set(cat)
        assert 0 <= cat["score"] <= cat["max"]


def test_bullets_fall_back_to_parsed_resume() -> None:
    parsed = {"experience": [{"bullets": ["Built A", "Led B", "Cut C by 10%"]}], "projects": []}
    bullets, source = ats.extract_bullets("No bullet markers here", parsed)
    assert source == "parsed resume"
    assert len(bullets) == 3


def test_wrapped_bullets_are_joined() -> None:
    text = "• Built a pipeline that ingests\nevents from Kafka into S3\n• Led a team of four\n• Cut costs by 10%"
    bullets, _ = ats.extract_bullets(text)
    assert bullets[0] == "Built a pipeline that ingests events from Kafka into S3"
