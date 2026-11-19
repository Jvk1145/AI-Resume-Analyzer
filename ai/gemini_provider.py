"""Google Gemini provider (REST API) with two-key fallback and model auto-discovery."""
import logging
from typing import Any

import requests

from ai.keys import get_keys
from ai.model_resolver import resolve_model

logger = logging.getLogger(__name__)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
# Tried in order; the first one Gemini currently serves is used. Override with GEMINI_MODEL.
GEMINI_PREFERRED_MODELS = [
    "gemini-3.8-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash",
]
TIMEOUT_SECONDS = 60.0


def _list_gemini_models(api_key: str) -> list[str]:
    """Return model IDs that support generateContent for this key."""
    resp = requests.get(f"{GEMINI_BASE}/models", headers={"x-goog-api-key": api_key},
                        params={"pageSize": 1000}, timeout=10.0)
    resp.raise_for_status()
    return [
        m["name"].removeprefix("models/")
        for m in resp.json().get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]


def _call_once(api_key: str, prompt: str, system_prompt: str) -> str:
    """Make one JSON-mode generateContent request with a single key."""
    parts = [{"text": f"{system_prompt}\n\nUser Input:\n{prompt}"}]
    config = {"temperature": 0.2, "maxOutputTokens": 4000, "response_mime_type": "application/json"}
    return _generate(api_key, parts, config)


def _generate(api_key: str, parts: list[dict[str, Any]], config: dict[str, Any]) -> str:
    """POST one generateContent request and return the first text part.

    The key goes in the ``x-goog-api-key`` header (never the URL), and the raw
    error body is only logged, never shown in the UI.
    """
    model = resolve_model("Gemini", "GEMINI_MODEL", GEMINI_PREFERRED_MODELS,
                          lambda: _list_gemini_models(api_key))
    payload: dict[str, Any] = {"contents": [{"parts": parts}], "generationConfig": config}
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    response = requests.post(f"{GEMINI_BASE}/models/{model}:generateContent", json=payload,
                             headers=headers, timeout=TIMEOUT_SECONDS)
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
        raise ValueError("GEMINI_API_KEY is not set in environment variables or Streamlit secrets.")

    last_error: Exception | None = None
    for idx, api_key in enumerate(keys, start=1):
        try:
            return _call_once(api_key, prompt, system_prompt)
        except Exception as exc:  # noqa: BLE001 - try the next key
            logger.warning("Gemini key #%d failed: %s", idx, exc)
            last_error = exc
    assert last_error is not None
    raise last_error


OCR_PROMPT = (
    "Transcribe ALL text in these resume page images exactly as written, top to bottom, page by page. "
    "Keep section headings on their own lines, keep line breaks, and start each bullet point with '• '. "
    "Do not summarize, correct, translate or add anything. Output only the transcribed text."
)


def transcribe_images(images: list[tuple[bytes, str]]) -> str:
    """OCR resume page images with Gemini vision, trying each configured key.

    Args:
        images: ``(image_bytes, mime_type)`` pairs, e.g. PNG pages of a scanned PDF.

    Raises:
        ValueError: if no Gemini key is configured.
        Exception: the last key's error if every key fails.
    """
    import base64

    keys = get_keys("GEMINI_API_KEY")
    if not keys:
        raise ValueError("GEMINI_API_KEY is not set in environment variables or Streamlit secrets.")
    parts: list[dict[str, Any]] = [{"text": OCR_PROMPT}]
    parts += [{"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode("ascii")}}
              for data, mime in images]
    config = {"temperature": 0.0, "maxOutputTokens": 8000}

    last_error: Exception | None = None
    for idx, api_key in enumerate(keys, start=1):
        try:
            return _generate(api_key, parts, config)
        except Exception as exc:  # noqa: BLE001 - try the next key
            logger.warning("Gemini OCR key #%d failed: %s", idx, exc)
            last_error = exc
    assert last_error is not None
    raise last_error
