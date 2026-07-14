import streamlit as st
import os
import tempfile

from parsers.pdf_parser import extract_text_from_pdf
from parsers.docx_parser import extract_text_from_docx
from ai.llm_service import process_resume_pipeline
from scoring.ats_score import calculate_ats_score
from matching.jd_matcher import calculate_jd_match
from exporters.docx_exporter import generate_docx

# Page Configuration
st.set_page_config(page_title="AI Resume Analyzer", page_icon="📄", layout="wide")

st.title("🤖 AI Resume Analyzer & Optimizer")
st.write("Upload your resume and (optionally) paste a Job Description to get an ATS score and AI-powered suggestions.")

# --- Sidebar Inputs ---
with st.sidebar:
    st.header("1. Upload Resume")
    uploaded_file = st.file_uploader("Choose a PDF or DOCX file", type=["pdf", "docx"])
    
    st.header("2. Job Description (Optional)")
    jd_text = st.text_area("Paste the job description here to see how well you match.", height=250)
    
    analyze_button = st.button("Analyze Resume", type="primary", use_container_width=True)

# --- Main App Logic ---
if analyze_button:
    if not uploaded_file:
        st.error("⚠️ Please upload a resume first.")
    else:
        # Step 1: Execute extraction and AI pipeline completely inside a silent spinner
        with st.spinner("Analyzing Resume with AI... Please wait."):
            try:
                file_ext = uploaded_file.name.split(".")[-1].lower()
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_file:
                    temp_file.write(uploaded_file.read())
                    temp_path = temp_file.name

                if file_ext == "pdf":
                    resume_text = extract_text_from_pdf(temp_path)
                elif file_ext == "docx":
                    resume_text = extract_text_from_docx(temp_path)
                else:
                    st.error("Unsupported file format.")
                    st.stop()
                    
                os.remove(temp_path)
                
                # Execute back-end cascade tracking silently
                resume_json = process_resume_pipeline(resume_text, jd_text)
                ats_results = calculate_ats_score(resume_json)
                
            except Exception as e:
                st.error(f"❌ An error occurred during analysis: {str(e)}")
                st.stop()

        # Step 2: Display metrics directly on the main viewport outside the loading module
        st.success("Analysis Complete!")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🎯 Overall ATS Score")
            score = ats_results.get("total_score", 0)
            
            # Subtle optimization color indicators
            if score >= 80:
                st.metric(label="Excellent Match Alignment", value=f"{score}/100")
            elif score >= 60:
                st.metric(label="Good (Needs minor additions)", value=f"{score}/100")
            else:
                st.metric(label="Critical Optimization Required", value=f"{score}/100")
                
            st.progress(score / 100)
            
            # Clean dynamic dashboard breakdown instead of raw JSON text boxes
            with st.expander("📊 View Detailed Score Breakdown", expanded=True):
                breakdown = ats_results.get("breakdown", {})
                if isinstance(breakdown, dict):
                    for category, value in breakdown.items():
                        clean_name = str(category).replace("_", " ").title()
                        if isinstance(value, (int, float)):
                            st.write(f"**{clean_name}:** {value}/100")
                            st.progress(int(value) / 100)
                        else:
                            st.write(f"**{clean_name}:** {value}")
                else:
                    st.info("No explicit metrics breakdown available.")
        
        with col2:
            if jd_text:
                st.subheader("🤝 Job Description Match")
                match_score = calculate_jd_match(resume_json)
                st.metric(label="Match Percentage", value=f"{match_score}%")
                st.progress(match_score / 100)
                
                st.markdown("**Missing Skills to Add:**")
                missing = resume_json.get("missing_skills", [])
                if missing:
                    for skill in missing:
                        st.markdown(f"- ❌ {skill}")
                else:
                    st.write("✅ Excellent! You have mapped all primary target skills.")
            else:
                st.info("💡 Tip: Paste a Job Description in the sidebar to get a keyword match score.")

        st.divider()

        # Step 3: Actionable AI Bullet Point Suggestions Section
        st.subheader("✍️ AI Bullet Point Suggestions")
        suggestions = resume_json.get("suggestions", [])
        
        if suggestions and isinstance(suggestions, list):
            for idx, sug in enumerate(suggestions):
                if isinstance(sug, dict):
                    with st.container():
                        st.markdown(f"**Suggestion {idx + 1}:**")
                        st.warning(f"**Weak:** {sug.get('original_bullet', 'N/A')}")
                        st.success(f"**Better:** {sug.get('improved_bullet', 'N/A')}")
                        st.caption(f"*Reason:* {sug.get('reason', 'Formatting enhancement suggestion.')}")
                        st.write("---")
        else:
            st.info("Your bullet points contain high structural metric velocity! No optimization rewrites suggested.")
        
        # Step 4: Native Export Download Segment
        st.divider()
        st.subheader("📥 Download ATS-Friendly Resume")
        st.write("We have automatically generated a clean, standardized version of your resume that is guaranteed to be readable by ATS software.")
        
        export_path = os.path.join(tempfile.gettempdir(), "ATS_Optimized_Resume.docx")
        generate_docx(resume_json, export_path)
        
        with open(export_path, "rb") as file:
            st.download_button(
                label="Download Resume (DOCX)",
                data=file,
                file_name="ATS_Optimized_Resume.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary"
            )

        with st.expander("View Extracted Resume Data (JSON)"):
            st.json({k: v for k, v in resume_json.items() if k != "suggestions"})