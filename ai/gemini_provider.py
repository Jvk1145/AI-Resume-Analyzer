"""Google Gemini provider (REST API) with two-key fallback."""
import logging
import os
from typing import Any

import requests

from ai.keys import get_keys

logger = logging.getLogger(__name__)

# Override with GEMINI_MODEL in .env when Google retires a model.
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
TIMEOUT_SECONDS = 45.0


def _call_once(api_key: str, prompt: str, system_prompt: str) -> str:
    """Make one generateContent request with a single key.

    The key goes in the ``x-goog-api-key`` header (never the URL) so it cannot
    leak through logged URLs or error messages.
    """
    model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload: dict[str, Any] = {
        "contents": [{"parts": [{"text": f"{system_prompt}\n\nUser Input:\n{prompt}"}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 4000,
            "response_mime_type": "application/json",
        },
    }
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}

    response = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT_SECONDS)
    if response.status_code != 200:
        logger.warning("Gemini error body: %s", response.text[:500])
        raise RuntimeError(f"Gemini HTTP {response.status_code} (model '{model}')")
    try:
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, ValueError) as exc:
        raise ValueError("Gemini returned a response structure that could not be read.") from exc


def call_gemini(prompt: str, system_prompt: str) -> str:
    """Send a request to Gemini, trying GEMINI_API_KEY then GEMINI_API_KEY_2.

    Raises:
        ValueError: if no Gemini key is configured.
        Exception: the last key's error if every key fails.
    """
    keys = get_keys("GEMINI_API_KEY")
    if not keys:
        raise ValueError("GEMINI_API_KEY is not set.")

    last_error: Exception | None = None
    for idx, api_key in enumerate(keys, start=1):
        try:
            return _call_once(api_key, prompt, system_prompt)
        except Exception as exc:  # noqa: BLE001 - try the next key
            logger.warning("Gemini key #%d failed: %s", idx, exc)
            last_error = exc
    assert last_error is not None
    raise last_error
