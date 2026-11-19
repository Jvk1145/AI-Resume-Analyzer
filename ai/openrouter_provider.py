import os
import random
import logging
from ai.secrets_loader import get_secret
import requests
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Names of your OpenRouter keys; read on each call so newly added secrets are picked up.
OR_KEY_NAMES = [
    "OPENROUTER_API_KEY_MAIN",
    "OPENROUTER_API_KEY_LAGUNA",
    "OPENROUTER_API_KEY_NVIDIA",
    "OPENROUTER_API_KEY_COHERE",
]

# Preferred free models, in order. Any that OpenRouter no longer lists are dropped automatically.
# Override with OPENROUTER_MODELS (comma-separated) in secrets.
OR_PREFERRED_MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "tencent/hy3:free",
    "openai/gpt-oss-120b:free",
    "google/gemini-2.5-flash:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-chat-v3.1:free",
]

_resolved_models = None


def _get_models() -> list:
    """Return up to 3 preferred models that OpenRouter currently lists (cached per process)."""
    global _resolved_models
    if _resolved_models is not None:
        return _resolved_models

    override = get_secret("OPENROUTER_MODELS")
    if override:
        _resolved_models = [m.strip() for m in override.split(",") if m.strip()]
        return _resolved_models

    models = OR_PREFERRED_MODELS
    try:
        resp = requests.get("https://openrouter.ai/api/v1/models", timeout=10.0)
        resp.raise_for_status()
        live = {m["id"] for m in resp.json().get("data", [])}
        alive = [m for m in OR_PREFERRED_MODELS if m in live]
        if len(alive) < 3:
            # Too few of our picks survive: top up with other free models OpenRouter lists.
            extras = sorted(m for m in live if m.endswith(":free") and m not in alive)
            alive += extras[: 3 - len(alive)]
        if alive:
            models = alive
    except Exception as e:
        logger.warning(f"Could not fetch OpenRouter model list ({e}); using defaults.")

    _resolved_models = models[:3]
    logger.info(f"OpenRouter: using models {_resolved_models}")
    return _resolved_models


def call_openrouter(prompt: str, system_prompt: str) -> str:
    """Calls OpenRouter rotating through the key pool, with server-side model fallbacks."""
    key_pool = [k for k in (get_secret(n) for n in OR_KEY_NAMES) if k]
    if not key_pool:
        raise ValueError("No OpenRouter keys found in environment or Streamlit secrets.")

    models = _get_models()

    # Randomize the start key to balance the load across accounts
    keys_to_try = key_pool.copy()
    random.shuffle(keys_to_try)

    last_error = None
    for idx, api_key in enumerate(keys_to_try):
        try:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
                timeout=45.0
            )

            response = client.chat.completions.create(
                model=models[0],
                extra_body={"models": models},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response")
            return content
        except Exception as e:
            last_error = e
            logger.warning(f"OpenRouter key instance {idx+1} failed or timed out: {e}. Trying next key...")
            continue

    raise RuntimeError(f"All keys in the OpenRouter pool failed. Last error: {last_error}")
