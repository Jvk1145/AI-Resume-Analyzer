import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

def call_gemini(prompt: str, system_prompt: str) -> str:
    """
    Calls Gemini API directly via native REST fallback route with a strict timeout.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in the environment variables.")
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    payload = {
        "contents": [{
            "parts": [{
                "text": f"{system_prompt}\n\nUser Input:\n{prompt}"
            }]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 4000,
            "response_mime_type": "application/json" 
        }
    }
    
    headers = {"Content-Type": "application/json"}
    
    # Added a strict 10.0 second timeout to the network call
    response = requests.post(url, json=payload, headers=headers, timeout=10.0)
    
    if response.status_code != 200:
        raise RuntimeError(f"Gemini REST Endpoint Error: Code {response.status_code} - {response.text}")
        
    result_json = response.json()
    try:
        return result_json["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise ValueError("Gemini returned a response structure that could not be read.")