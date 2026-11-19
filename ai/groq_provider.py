"""Groq provider (OpenAI-compatible endpoint) with two-key fallback."""
import logging
import os

from openai import OpenAI

from ai.keys import get_keys

logger = logging.getLogger(__name__)

# Override with GROQ_MODEL in .env when Groq retires a model.
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
TIMEOUT_SECONDS = 45.0


def call_groq(prompt: str, system_prompt: str) -> str:
    """Send a chat request to Groq, trying GROQ_API_KEY then GROQ_API_KEY_2.

    Raises:
        ValueError: if no Groq key is configured.
        Exception: the last key's error if every key fails.
    """
    keys = get_keys("GROQ_API_KEY")
    if not keys:
        raise ValueError("GROQ_API_KEY is not set.")

    last_error: Exception | None = None
    for idx, api_key in enumerate(keys, start=1):
        try:
            client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=api_key,
                timeout=TIMEOUT_SECONDS,
            )
            response = client.chat.completions.create(
                model=os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL),
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
