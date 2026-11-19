"""Reusable UI building blocks."""
from typing import Any, Literal

import streamlit as st


BadgeColor = Literal["red", "orange", "yellow", "blue", "green", "violet", "gray", "grey", "primary"]

GREEN, ORANGE, RED = "#16A34A", "#F59E0B", "#DC2626"

TIPS: dict[str, str] = {
    "contact": "Put your email, phone and a LinkedIn or GitHub URL at the top.",
    "sections": "Use standard headings: Summary, Skills, Experience, Education.",
    "keywords": "Add missing job skills you genuinely have, in Skills and in your bullets.",
    "action_verbs": "Start every bullet with a strong verb such as Built, Led or Reduced.",
    "quantified": "Add real numbers: %, time saved, users, revenue or team size.",
    "bullet_quality": "Keep bullets to 8-30 words and drop “I” and “my”.",
    "length": "Aim for 1 page under 3 years of experience, and never more than 2.",
    "layout": "Use a single column with no tables, images or header/footer text.",
}

ICONS: dict[str, str] = {
    "contact": ":material/contact_mail:",
    "sections": ":material/view_agenda:",
    "keywords": ":material/key:",
    "action_verbs": ":material/bolt:",
    "quantified": ":material/monitoring:",
    "bullet_quality": ":material/format_list_bulleted:",
    "length": ":material/straighten:",
    "layout": ":material/grid_view:",
}


def score_color(score: float) -> str:
    """Hex color for a 0-100 score."""
    return GREEN if score >= 80 else ORANGE if score >= 60 else RED


def verdict(score: float) -> tuple[str, BadgeColor]:
    """Short verdict label and badge color for a 0-100 score."""
    if score >= 80:
        return "Strong resume", "green"
    if score >= 60:
        return "Good, room to improve", "orange"
    return "Needs work", "red"


def ratio_status(ratio: float) -> tuple[str, BadgeColor]:
    """Badge label and color for a category's score/max ratio."""
    if ratio >= 0.8:
        return "Great", "green"
    if ratio >= 0.5:
        return "Improve", "orange"
    return "Fix", "red"


def score_gauge(score: int) -> None:
    """Semi-circular gauge for the overall ATS score."""
    spec = {
        "series": [
            {
                "type": "gauge",
                "startAngle": 210,
                "endAngle": -30,
                "min": 0,
                "max": 100,
                "radius": "95%",
                "center": ["50%", "58%"],
                "progress": {"show": True, "width": 16, "roundCap": True,
                             "itemStyle": {"color": score_color(score)}},
                "axisLine": {"roundCap": True, "lineStyle": {"width": 16, "color": [[1, "rgba(127,127,127,0.18)"]]}},
                "axisTick": {"show": False},
                "splitLine": {"show": False},
                "axisLabel": {"show": False},
                "pointer": {"show": False},
                "anchor": {"show": False},
                "title": {"show": True, "offsetCenter": [0, "32%"], "fontSize": 14},
                "detail": {"valueAnimation": True, "offsetCenter": [0, "-2%"], "fontSize": 52,
                           "fontWeight": 700, "formatter": "{value}"},
                "data": [{"value": score, "name": "out of 100"}],
            }
        ]
    }
    st.echarts_chart(spec, height=250, alt=f"ATS score {score} out of 100")


def category_card(key: str, cat: dict[str, Any]) -> None:
    """Bordered card showing one ATS category's points, status and reasons."""
    ratio = cat["score"] / cat["max"] if cat["max"] else 0.0
    label, color = ratio_status(ratio)
    with st.container(border=True, height="stretch"):
        with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
            st.markdown(f"{ICONS.get(key, '')} **{cat['label']}**", width="content")
            st.badge(f"{cat['score']:g} / {cat['max']:g}", color=color)
        st.progress(min(ratio, 1.0))
        for reason in cat["reasons"]:
            st.caption(reason)
        if ratio < 0.8 and key in TIPS:
            st.caption(f":material/tips_and_updates: {TIPS[key]}")


def quick_wins(breakdown: dict[str, Any], limit: int = 3) -> list[tuple[str, dict[str, Any], float]]:
    """Return the categories with the most points left to gain."""
    gaps = [
        (key, cat, round(cat["max"] - cat["score"], 1))
        for key, cat in breakdown.items()
        if cat["max"] and cat["max"] - cat["score"] >= 0.5
    ]
    return sorted(gaps, key=lambda g: g[2], reverse=True)[:limit]
