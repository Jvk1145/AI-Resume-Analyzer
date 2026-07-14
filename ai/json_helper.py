import json
import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def clean_and_parse_json(raw_text: str) -> Dict[str, Any]:
    """
    Cleans up typical LLM formatting issues and safely parses the text into a Python dictionary.
    """
    if not raw_text:
        raise ValueError("The AI returned an empty response.")
        
    cleaned = raw_text.strip()
    
    # 1. Strip away Markdown code blocks without using complex regex
    cleaned = cleaned.replace("```json", "")
    cleaned = cleaned.replace("```", "")
    cleaned = cleaned.strip()
    
    # 2. Find the actual boundaries of the JSON object
    start_idx = cleaned.find('{')
    end_idx = cleaned.rfind('}')
    
    if start_idx == -1 or end_idx == -1:
        raise ValueError("Could not find a valid JSON object block in the response.")
        
    json_string = cleaned[start_idx : end_idx + 1]
    
    # 3. Attempt standard parsing
    try:
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        logger.warning(f"Standard JSON parsing failed: {e}. Attempting basic text repairs...")
        
        # 4. Basic Repair: Remove common trailing commas before closing braces/brackets
        json_string = re.sub(r',\s*([\]}])', r'\1', json_string)
        
        try:
            return json.loads(json_string)
        except json.JSONDecodeError:
            # If it still fails, pass the error up so the fallback engine can switch providers
            raise ValueError("JSON string is fundamentally malformed and cannot be auto-healed.")