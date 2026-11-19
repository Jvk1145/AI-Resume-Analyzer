"""Streamlit entry point for the AI Resume Analyzer.

Flow: upload -> local text + layout extraction -> deterministic JD match and
ATS score -> redaction -> AI parsing/suggestions (cached) -> tabs.
Pipeline code lives in ``ui/pipeline.py``; page sections in ``ui/views.py``.
"""
import logging

import streamlit as st

from storage.history import add_record, fetch_history
from ui import views
from ui.pipeline import run_analysis

logging.basicConfig(level=logging.INFO)

st.set_page_config(
    page_title="AI Resume Analyzer",
    page_icon=":material/description:",
    layout="wide",
)

# --------------------------------------------------------------------------- sidebar

with st.sidebar:
    st.markdown("### :material/description: Resume analyzer")
    st.caption("Explainable ATS scoring and honest AI help.")
    with st.expander("How scoring works", icon=":material/help:"):
        st.markdown(
            "- Contact info: 10\n- Standard sections: 15\n- JD keywords: 30\n- Action verbs: 10\n"
            "- Quantified results: 15\n- Bullet quality: 10\n- Length: 5\n- ATS-friendly layout: 5"
        )
        st.caption("No job description? The 30 keyword points are shared across the other categories.")
    st.caption(":material/shield_lock: Email, phone and street address are redacted before any AI call.")
    if st.session_state.get("result") and st.button("Start over", icon=":material/restart_alt:", width="stretch"):
        st.session_state.pop("result", None)
        st.rerun()

# --------------------------------------------------------------------------- inputs

current = st.session_state.get("result")
views.render_hero()

input_box = (
    st.expander("Analyze another resume or job description", icon=":material/upload_file:")
    if current
    else st.container(border=True)
)
with input_box:
    upload_col, jd_col = st.columns([2, 3], gap="medium")
    with upload_col:
        uploaded_file = st.file_uploader(
            "Resume", type=["pdf", "docx"], key="resume_file",
            help="PDF or DOCX. Scanned images can't be read.",
        )
    with jd_col:
        jd_input = st.text_area(
            "Job description (optional)", key="jd_text", height=150,
            placeholder="Paste the job description to see your match, missing skills and a tailored cover letter.",
        )
    analyze_clicked = st.button(
        "Analyze resume", type="primary", icon=":material/auto_awesome:", width="stretch",
        disabled=uploaded_file is None,
    )

if analyze_clicked and uploaded_file is not None:
    with st.status("Analyzing your resume...", expanded=True) as status:
        try:
            new_result = run_analysis(uploaded_file.name, uploaded_file.getvalue(), jd_input, step=status.write)
            jd = new_result["jd_match"]
            add_record(
                file_name=uploaded_file.name,
                ats_score=new_result["ats"]["total_score"],
                jd_match=jd["match_percentage"] if jd and jd["jd_skill_count"] else None,
                missing_skills=(jd["missing_required"] + jd["missing_nice"]) if jd else [],
            )
            st.session_state["result"] = new_result
            status.update(label="Analysis complete", state="complete", expanded=False)
            st.session_state["just_analyzed"] = True
            st.rerun()  # collapse the input card and show results
        except Exception as exc:  # noqa: BLE001 - show any failure to the user
            status.update(label="Analysis failed", state="error", expanded=True)
            st.error(str(exc), title="Something went wrong")

# --------------------------------------------------------------------------- results

current = st.session_state.get("result")
if st.session_state.pop("just_analyzed", False):
    st.toast("Analysis complete", icon=":material/check_circle:")

if not current:
    views.render_features()
    if fetch_history():
        st.subheader("Your progress", icon=":material/history:")
        views.render_history()
else:
    views.render_summary(current)
    tabs = st.tabs([
        ":material/analytics: Analysis",
        ":material/join_inner: JD match",
        ":material/edit_note: Suggestions",
        ":material/mail: Cover letter",
        ":material/forum: Interview prep",
        ":material/history: History",
    ])
    renderers = (
        views.render_analysis,
        views.render_jd_match,
        views.render_suggestions,
        views.render_cover_letter,
        views.render_interview,
    )
    for tab, render in zip(tabs[:5], renderers):
        with tab:
            render(current)
    with tabs[5]:
        views.render_history()
