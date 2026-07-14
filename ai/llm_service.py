import logging
from typing import Dict, Any, Optional
from ai.openrouter_provider import call_openrouter
from ai.groq_provider import call_groq
from ai.sambanova_provider import call_sambanova
from ai.gemini_provider import call_gemini
from ai.json_helper import clean_and_parse_json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Heavily reinforced system prompts to fight LLM laziness and force bullet generation
SYSTEM_PROMPT_RESUME_ONLY = """You are an expert ATS (Applicant Tracking System) parser. You MUST extract EVERY SINGLE DETAIL from the resume without summarizing, omitting, or truncating content. 
Return a strict JSON object with these exact keys:
- "name" (string)
- "email" (string)
- "phone" (string)
- "skills" (array of strings)
- "experience" (array of objects with "role", "company", "duration", and "bullets" array of strings. DO NOT skip or summarize any bullet points!)
- "education" (array of objects with "degree", "institution", "year")
- "projects" (array of objects with "name", "technologies" array, "description" string)
- "suggestions" (array of objects with "original_bullet", "improved_bullet", "reason"). YOU MUST PROVIDE AT LEAST 3 DETAILED, ACTIONABLE BULLET POINT SUGGESTIONS.
Do not leave any arrays empty if the data exists in the text."""

SYSTEM_PROMPT_WITH_JD = """You are an expert ATS optimization engine. Compare the provided resume text against the Job Description. 
Return a strict JSON object matching the core layout (name, email, phone, skills, experience, education, projects). 
Additionally, you MUST include:
- "match_percentage": (integer) A number from 0 to 100 representing how well the overall resume matches the JD.
- "missing_skills": (array of strings) Core keywords from the JD missing in the resume. IMPORTANT: Scan the ENTIRE resume (Experience and Projects) before deciding a skill is missing!
- "suggestions": (array of objects with "original_bullet", "improved_bullet", "reason"). YOU MUST PROVIDE AT LEAST 3 TAILORED SUGGESTIONS showing how to rewrite weak lines to better match the keywords requested in the JD.
Do not summarize the experience sections. Extract all original bullets completely."""

def process_resume_pipeline(resume_text: str, jd_text: Optional[str] = None) -> Dict[str, Any]:
    if jd_text and jd_text.strip():
        combined_payload = f"JOB DESCRIPTION:\n{jd_text}\n\nRESUME TEXT:\n{resume_text}"
        return analyze_resume(combined_payload, SYSTEM_PROMPT_WITH_JD)
    else:
        return analyze_resume(resume_text, SYSTEM_PROMPT_RESUME_ONLY)

def analyze_resume(resume_text: str, system_prompt: str) -> Dict[str, Any]:
    errors = []
    
    # Tier 1: OpenRouter
    try:
        logger.info("🚀 [Tier 1] Attempting OpenRouter Cluster (NVIDIA/Tencent)...")
        response = call_openrouter(resume_text, system_prompt)
        return _parse_json_response(response)
    except Exception as e:
        errors.append(f"OpenRouter: {str(e)}")
        logger.warning("⚠️ OpenRouter failed. Falling back to Groq...")

    # Tier 2: Groq
    try:
        logger.info("⚡ [Tier 2] Attempting Groq...")
        response = call_groq(resume_text, system_prompt)
        return _parse_json_response(response)
    except Exception as e:
        errors.append(f"Groq: {str(e)}")
        logger.warning("⚠️ Groq failed. Falling back to SambaNova...")

    # Tier 3: SambaNova
    try:
        logger.info("🧠 [Tier 3] Attempting SambaNova...")
        response = call_sambanova(resume_text, system_prompt)
        return _parse_json_response(response)
    except Exception as e:
        errors.append(f"SambaNova: {str(e)}")
        logger.warning("⚠️ SambaNova failed. Falling back to Gemini...")

    # Tier 4: Gemini (Safety Net)
    try:
        logger.info("🛡️ [Tier 4] Attempting Gemini Safety Net...")
        response = call_gemini(resume_text, system_prompt)
        return _parse_json_response(response)
    except Exception as e:
        errors.append(f"Gemini: {str(e)}")
        
    raise RuntimeError("ALL CHANNELS FAILED:\n" + " | ".join(errors))

def _parse_json_response(response_text: str) -> Dict[str, Any]:
    return clean_and_parse_json(response_text)