"""Page sections and tab renderers for the Streamlit app."""
from typing import Any

import pandas as pd
import streamlit as st

from exporters.docx_exporter import generate_cover_letter_docx, generate_docx
from matching.jd_matcher import display_name
from parsers.contact import extract_contact
from storage.history import clear_history, fetch_history
from ui.components import ICONS, TIPS, category_card, quick_wins, score_gauge, verdict
from ui.pipeline import cached_cover_letter, cached_interview, make_key

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

FEATURES = [
    (":material/fact_check:", "Explainable ATS score",
     "8 transparent rules with points and reasons. No black box, and the same resume always gets the same score."),
    (":material/join_inner:", "Job description match",
     "300+ skills and synonyms, sorted into required and nice-to-have, with where each was found."),
    (":material/edit_note:", "Honest rewrites",
     "AI bullet suggestions that never invent numbers. You review and accept each one."),
    (":material/shield_lock:", "Private by design",
     "Email, phone and address are redacted before any text is sent to an AI provider."),
]


# --------------------------------------------------------------------------- landing / summary


def render_hero() -> None:
    """Title and tagline."""
    st.title("AI resume analyzer", icon=":material/description:")
    st.markdown(
        "Get an **explainable ATS score**, see exactly which job skills you're missing, and improve your bullets "
        "with **honest AI rewrites**, plus a tailored cover letter and interview prep."
    )


def render_features() -> None:
    """Feature cards shown before the first analysis."""
    st.space("small")
    grid = st.grid(4, min_column_width=220, gap="medium")
    for icon, title, body in FEATURES:
        with grid.container(border=True, height="stretch"):
            st.markdown(f"### {icon}")
            st.markdown(f"**{title}**")
            st.caption(body)
    st.space("small")
    with st.container(border=True):
        st.markdown("**How it works**")
        st.markdown(
            ":blue-badge[1] Upload a PDF or DOCX resume  \n"
            ":blue-badge[2] Optionally paste the job description  \n"
            ":blue-badge[3] Review your score, missing skills and suggestions  \n"
            ":blue-badge[4] Accept rewrites and download an ATS-friendly DOCX"
        )


def _same_file_scores(file_name: str) -> list[int]:
    """ATS scores from history for this file name, oldest first."""
    return [r["ats_score"] for r in fetch_history() if r["file_name"] == file_name]


def render_summary(result: dict[str, Any]) -> None:
    """Headline metrics shown above the tabs."""
    ats, jd = result["ats"], result["jd_match"]
    scores = _same_file_scores(result["file_name"])
    delta = scores[-1] - scores[-2] if len(scores) >= 2 else None
    suggestions = result["analysis"].get("suggestions", [])

    with st.container(horizontal=True, gap="medium"):
        st.metric(
            "ATS score", f"{ats['total_score']}/100", delta=delta, border=True, icon=":material/speed:",
            chart_data=scores[-12:] if len(scores) >= 2 else None, chart_type="area",
            delta_description="vs. last analysis of this file" if delta is not None else None,
        )
        if jd and jd["jd_skill_count"]:
            st.metric("JD match", f"{jd['match_percentage']:g}%", border=True, icon=":material/join_inner:")
            st.metric("Missing required skills", len(jd["missing_required"]), border=True,
                      icon=":material/report:")
        else:
            st.metric("JD match", "—", border=True, icon=":material/join_inner:",
                      help="Paste a job description to see your match.")
            st.metric("Skills found", len(result["analysis"].get("skills", [])), border=True,
                      icon=":material/psychology:")
        st.metric("AI suggestions", len(suggestions), border=True, icon=":material/edit_note:")
    st.caption(
        f":material/description: {result['file_name']} · parsed by {result['provider']} · "
        "contact details redacted before sending"
    )


# --------------------------------------------------------------------------- tabs


def render_analysis(result: dict[str, Any]) -> None:
    """Score gauge, quick wins and per-category cards."""
    ats = result["ats"]
    score = ats["total_score"]
    label, color = verdict(score)

    left, right = st.columns([2, 3], gap="medium")
    with left, st.container(border=True, height="stretch"):
        st.markdown("**Overall ATS score**")
        score_gauge(score)
        with st.container(horizontal=True, horizontal_alignment="center"):
            st.badge(label, color=color, icon=":material/workspace_premium:")
        st.caption(
            "Computed locally with fixed rules (no AI)."
            + ("" if ats["has_jd"] else " Add a job description to include keyword coverage."),
            text_alignment="center",
        )
    with right, st.container(border=True, height="stretch"):
        st.markdown("**:material/rocket_launch: Quick wins**")
        wins = quick_wins(ats["breakdown"])
        if not wins:
            st.success("Your resume follows every rule we check. Nice work!", icon=":material/celebration:")
        for key, cat, gain in wins:
            with st.container(border=True):
                with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
                    st.markdown(f"{ICONS.get(key, '')} **{cat['label']}**", width="content")
                    st.badge(f"+{gain:g} pts possible", color="violet")
                st.caption(TIPS.get(key, ""))

    st.subheader("Score breakdown", icon=":material/insights:")
    grid = st.grid(2, min_column_width=320, gap="medium")
    for key, cat in ats["breakdown"].items():
        if not cat["max"]:
            continue
        with grid.container():
            category_card(key, cat)
    if not ats["has_jd"]:
        st.caption(":material/info: " + " ".join(ats["breakdown"]["keywords"]["reasons"]))

    if result["layout"] and result["layout"].get("notes"):
        with st.expander("Layout details", icon=":material/grid_view:"):
            for note in result["layout"]["notes"]:
                st.markdown(f"- {note}")
    with st.expander("Extracted resume data", icon=":material/data_object:"):
        st.json({k: v for k, v in result["analysis"].items() if k != "suggestions"}, expanded=False)


def render_jd_match(result: dict[str, Any]) -> None:
    """Weighted JD match, missing skills and where matched skills were found."""
    jd = result["jd_match"]
    if jd is None:
        st.info("Paste a job description above and analyze again to see keyword matching.",
                icon=":material/join_inner:")
        return
    if not jd["jd_skill_count"]:
        st.warning("No recognizable skills were found in the job description.", icon=":material/search_off:")
        return

    req_total, nice_total = len(jd["required"]), len(jd["nice"])
    req_hit = req_total - len(jd["missing_required"])
    nice_hit = nice_total - len(jd["missing_nice"])
    with st.container(horizontal=True, gap="medium"):
        st.metric("Weighted match", f"{jd['match_percentage']:g}%", border=True, icon=":material/percent:",
                  help="Required skills count double.")
        st.metric("Required skills", f"{req_hit}/{req_total}", border=True, icon=":material/priority_high:")
        st.metric("Nice-to-have skills", f"{nice_hit}/{nice_total}", border=True, icon=":material/star:")

    left, right = st.columns(2, gap="medium")
    with left, st.container(border=True, height="stretch"):
        st.markdown("**:material/report: Missing required**")
        if jd["missing_required"]:
            st.markdown(" ".join(f":red-badge[{display_name(s)}]" for s in jd["missing_required"]))
            st.caption("Add these only if you have real experience with them, ideally inside a bullet.")
        else:
            st.markdown(":green-badge[:material/check: All required skills found]")
    with right, st.container(border=True, height="stretch"):
        st.markdown("**:material/star_half: Missing nice-to-have**")
        if jd["missing_nice"]:
            st.markdown(" ".join(f":orange-badge[{display_name(s)}]" for s in jd["missing_nice"]))
        else:
            st.markdown(":green-badge[:material/check: All nice-to-have skills found]")

    if jd["matched"]:
        st.subheader("Matched skills", icon=":material/task_alt:")
        rows = pd.DataFrame([
            {
                "Skill": display_name(s),
                "Priority": "Required" if s in jd["required"] else "Nice to have",
                "Found in": jd["locations"].get(s, []),
            }
            for s in jd["matched"]
        ])
        st.dataframe(
            rows,
            hide_index=True,
            column_config={"Found in": st.column_config.ListColumn("Found in", help="Resume sections")},
        )


def render_suggestions(result: dict[str, Any]) -> None:
    """Editable AI rewrites with Accept checkboxes, and the DOCX export."""
    suggestions = result["analysis"].get("suggestions", [])
    prefix = result["key"][:12]
    summary = st.container()  # filled after the loop, once accepted rewrites are known
    replacements: dict[str, str] = {}

    if not suggestions:
        st.info("No rewrites were suggested for this resume.", icon=":material/thumb_up:")
    for idx, sug in enumerate(suggestions, start=1):
        with st.container(border=True):
            with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
                st.badge(f"Suggestion {idx}", color="primary", icon=":material/edit_note:")
                accepted = st.checkbox("Accept", key=f"accept_{prefix}_{idx}")
            before, after = st.columns(2, gap="medium")
            with before:
                st.caption("Original")
                st.markdown(f":gray[{sug['original_bullet']}]")
            with after:
                improved = st.text_area("Suggested rewrite (editable)", value=sug["improved_bullet"],
                                        key=f"edit_{prefix}_{idx}", height=90)
            if sug.get("reason"):
                st.caption(f":material/lightbulb: {sug['reason']}")
            if accepted and "[" in improved:
                st.warning("Replace the [placeholder] with your real figure before downloading.",
                           icon=":material/edit:")
            if accepted:
                replacements[sug["original_bullet"]] = improved

    with summary, st.container(border=True):
        with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
            with st.container(width="content", gap="xsmall"):
                st.markdown("**:material/download: ATS-friendly resume**")
                st.caption(
                    f"{len(replacements)} of {len(suggestions)} rewrites accepted · single-column DOCX · "
                    "numbers the AI invented are shown as [placeholders]"
                )
            st.download_button(
                "Download DOCX",
                data=generate_docx(result["analysis"], contact=extract_contact(result["resume_text"]),
                                   replacements=replacements),
                file_name="ATS_Optimized_Resume.docx",
                mime=DOCX_MIME,
                type="primary",
                icon=":material/download:",
            )


def render_cover_letter(result: dict[str, Any]) -> None:
    """Generate, edit and download a cover letter."""
    if not result["jd_text"].strip():
        st.info("A cover letter needs a job description. Paste one above and analyze again.",
                icon=":material/mail:")
        return
    store: dict[str, dict[str, str]] = st.session_state.setdefault("cover_letters", {})
    letter = store.get(result["key"])

    with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
        st.caption("A 250-300 word letter built only from facts in your resume, tailored to this job.")
        clicked = st.button("Regenerate" if letter else "Generate cover letter", type="primary",
                            icon=":material/auto_awesome:")
    if clicked:
        with st.spinner("Writing your cover letter..."):
            try:
                store[result["key"]] = cached_cover_letter(
                    make_key("cover", result["resume_text"], result["jd_text"].strip()),
                    result["redacted_resume"], result["redacted_jd"],
                )
                letter = store[result["key"]]
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc), title="Cover letter failed")
    if not letter:
        return
    with st.container(border=True):
        text = st.text_area("Your cover letter (editable)", value=letter["text"], height=440,
                            key=f"letter_{result['key'][:12]}")
        with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
            st.badge(f"{len(text.split())} words", color="gray", icon=":material/notes:")
            st.download_button(
                "Download DOCX",
                data=generate_cover_letter_docx(text, result["analysis"].get("name", ""),
                                                extract_contact(result["resume_text"])),
                file_name="Cover_Letter.docx",
                mime=DOCX_MIME,
                icon=":material/download:",
            )


def render_interview(result: dict[str, Any]) -> None:
    """Generate 8 likely interview questions with tips."""
    store: dict[str, dict[str, Any]] = st.session_state.setdefault("interviews", {})
    prep = store.get(result["key"])
    basis = "your resume and this job description" if result["jd_text"].strip() else "your resume"

    with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
        st.caption(f"8 likely questions based on {basis}, each with a tip that draws on your own experience.")
        clicked = st.button("Regenerate" if prep else "Generate questions", type="primary",
                            icon=":material/record_voice_over:")
    if clicked:
        with st.spinner("Preparing interview questions..."):
            try:
                store[result["key"]] = cached_interview(
                    make_key("interview", result["resume_text"], result["jd_text"].strip()),
                    result["redacted_resume"], result["redacted_jd"],
                )
                prep = store[result["key"]]
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc), title="Interview prep failed")
    if not prep:
        return
    for idx, item in enumerate(prep["questions"], start=1):
        with st.expander(f"{idx}. {item['question']}", expanded=idx == 1, icon=":material/help:"):
            st.markdown(f":material/lightbulb: **How to answer:** {item['tip']}")


def render_history() -> None:
    """Score trend, summary metrics and a table of past analyses."""
    records = fetch_history()
    if not records:
        st.info("No analyses yet. Your results will appear here after each analysis.", icon=":material/history:")
        return
    df = pd.DataFrame(records)
    df["Date"] = pd.to_datetime(df["created_at"])
    scores = df["ats_score"].tolist()

    with st.container(horizontal=True, gap="medium"):
        st.metric("Analyses", len(df), border=True, icon=":material/history:")
        st.metric("Best score", f"{max(scores)}/100", border=True, icon=":material/emoji_events:")
        st.metric("Latest score", f"{scores[-1]}/100", border=True, icon=":material/speed:",
                  delta=scores[-1] - scores[-2] if len(scores) >= 2 else None,
                  chart_data=scores[-20:] if len(scores) >= 2 else None, chart_type="area")

    with st.container(border=True):
        st.markdown("**Score over time**")
        chart = df.rename(columns={"ats_score": "ATS score", "jd_match": "JD match %"})
        st.line_chart(chart, x="Date", y=["ATS score", "JD match %"], y_label="Score", height=300,
                      alt="ATS score and JD match percentage over time")

    table = pd.DataFrame({
        "Date": df["Date"],
        "File": df["file_name"],
        "ATS score": df["ats_score"],
        "JD match %": df["jd_match"],
        "Top missing skills": df["missing_skills"].map(lambda s: [display_name(x) for x in s]),
    }).sort_values("Date", ascending=False)
    st.dataframe(
        table,
        hide_index=True,
        column_config={
            "Date": st.column_config.DatetimeColumn("Date", format="D MMM YYYY, h:mm a"),
            "ATS score": st.column_config.ProgressColumn("ATS score", min_value=0, max_value=100, format="%d"),
            "JD match %": st.column_config.ProgressColumn("JD match", min_value=0, max_value=100, format="%.0f%%"),
            "Top missing skills": st.column_config.ListColumn("Top missing skills"),
        },
    )
    with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
        st.caption(":material/lock: Stored locally in data/history.db: scores and file names only, never resume text.")
        with st.popover("Clear history", icon=":material/delete:"):
            st.markdown("Delete all saved analyses?")
            if st.button("Yes, delete", type="primary"):
                clear_history()
                st.rerun()
