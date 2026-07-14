# scoring/ats_score.py
from typing import Dict, Any

def calculate_ats_score(resume_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculates a deterministic ATS score out of 100 based on the structured JSON.
    """
    score_breakdown = {
        "skills": 0,       # Max 25
        "experience": 0,   # Max 30
        "education": 0,    # Max 15
        "projects": 0,     # Max 20
        "formatting": 10   # Base points for parsing successfully
    }
    
    # 1. Evaluate Skills (Max 25 points)
    # Give 3 points per skill, capped at 25.
    skills = resume_json.get("skills", [])
    score_breakdown["skills"] = min(25, len(skills) * 3)
    
    # 2. Evaluate Experience (Max 30 points)
    # Give 10 points per job, plus 2 points per bullet point.
    experience = resume_json.get("experience", [])
    exp_score = 0
    for job in experience:
        exp_score += 10
        exp_score += len(job.get("bullets", [])) * 2
    score_breakdown["experience"] = min(30, exp_score)
    
    # 3. Evaluate Education (Max 15 points)
    education = resume_json.get("education", [])
    if education:
        score_breakdown["education"] = 15
        
    # 4. Evaluate Projects (Max 20 points)
    # Give 10 points per project.
    projects = resume_json.get("projects", [])
    proj_score = 0
    for proj in projects:
        proj_score += 10
    score_breakdown["projects"] = min(20, proj_score)
    
    # Calculate Total
    total_score = sum(score_breakdown.values())
    
    return {
        "total_score": total_score,
        "breakdown": score_breakdown
    }