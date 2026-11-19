"""Groq provider (OpenAI-compatible endpoint) with two-key fallback and model auto-discovery."""
import logging

from openai import OpenAI

from ai.keys import get_keys
from ai.model_resolver import resolve_model

logger = logging.getLogger(__name__)

# Tried in order; the first one Groq currently serves is used. Override with GROQ_MODEL.
GROQ_PREFERRED_MODELS = [
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "qwen/qwen3-32b",
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
]
TIMEOUT_SECONDS = 60.0


def call_groq(prompt: str, system_prompt: str) -> str:
    """Send a chat request to Groq, trying GROQ_API_KEY then GROQ_API_KEY_2.

    Raises:
        ValueError: if no Groq key is configured.
        Exception: the last key's error if every key fails.
    """
    keys = get_keys("GROQ_API_KEY")
    if not keys:
        raise ValueError("GROQ_API_KEY is not set in environment variables or Streamlit secrets.")

    last_error: Exception | None = None
    for idx, api_key in enumerate(keys, start=1):
        try:
            client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key, timeout=TIMEOUT_SECONDS)
            model = resolve_model(
                "Groq", "GROQ_MODEL", GROQ_PREFERRED_MODELS,
                lambda: [m.id for m in client.models.list().data],
            )
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=4000,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001 - try the next key
            logger.warning("Groq key #%d failed: %s", idx, exc)
            last_error = exc
    assert last_error is not None
    raise last_error
