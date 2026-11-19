import os
import requests
import logging
from ai.secrets_loader import get_secret
from dotenv import load_dotenv
from ai.model_resolver import resolve_model

load_dotenv()
logger = logging.getLogger(__name__)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

# Tried in order; the first one Gemini currently serves is used. Override with GEMINI_MODEL.
GEMINI_PREFERRED_MODELS = [
    "gemini-3.8-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash",
]

def _list_gemini_models(api_key: str):
    resp = requests.get(f"{GEMINI_BASE}/models", headers={"x-goog-api-key": api_key},
                        params={"pageSize": 1000}, timeout=10.0)
    resp.raise_for_status()
    return [
        m["name"].removeprefix("models/")
        for m in resp.json().get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]

def call_gemini(prompt: str, system_prompt: str) -> str:
    """
    Calls Gemini API directly via the native REST route.
    """
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in environment variables or Streamlit secrets.")

    model = resolve_model(
        "Gemini", "GEMINI_MODEL", GEMINI_PREFERRED_MODELS,
        lambda: _list_gemini_models(api_key),
    )

    url = f"{GEMINI_BASE}/models/{model}:generateContent"

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

    # Key goes in a header rather than the URL so it never shows up in logged URLs.
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}

    response = requests.post(url, json=payload, headers=headers, timeout=60.0)

    if response.status_code != 200:
        raise RuntimeError(f"Gemini REST Endpoint Error ({model}): Code {response.status_code} - {response.text}")

    result_json = response.json()
    try:
        return result_json["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise ValueError("Gemini returned a response structure that could not be read.")
