def calculate_jd_match(resume_json: dict) -> float:
    """
    Safely calculates or extracts the Job Description match percentage.
    """
    # 1. First, try to get the score directly if the LLM provided it
    if "match_percentage" in resume_json:
        try:
            return float(resume_json["match_percentage"])
        except (ValueError, TypeError):
            pass
            
    # 2. Fallback Mathematical Calculation (If LLM forgot to include the score)
    missing_skills = resume_json.get("missing_skills", [])
    existing_skills = resume_json.get("skills", [])
    
    missing_count = len(missing_skills) if isinstance(missing_skills, list) else 0
    existing_count = len(existing_skills) if isinstance(existing_skills, list) else 0
    
    total_skills = missing_count + existing_count
    
    if total_skills == 0:
        return 0.0 # Prevent division by zero if no skills are found anywhere
        
    # Calculate percentage based on how many required skills the user actually has
    calculated_score = (existing_count / total_skills) * 100.0
    
    # Cap the maximum fallback score at 95% (always leave room for improvement)
    return round(min(calculated_score, 95.0), 1)