import os
import logging
from typing import Callable, Iterable, List, Optional

logger = logging.getLogger(__name__)

# Model IDs containing any of these are not general chat models (speech, safety, embeddings...).
_NON_CHAT_HINTS = ("whisper", "tts", "guard", "embed", "rerank", "vision", "audio", "moderation", "playai", "orpheus", "safeguard")

_cache: dict = {}


def resolve_model(
    provider: str,
    env_var: str,
    preferred: Iterable[str],
    list_models: Callable[[], List[str]],
) -> str:
    """
    Pick the model to call for a provider.

    1. An explicit override in `env_var` (e.g. set in Streamlit secrets) always wins.
    2. Otherwise ask the provider which models are live, and use the first preferred one that exists.
    3. If none of the preferred models exist, fall back to the first live chat model.
    4. If the model list can't be fetched, use the first preferred model.

    The result is cached for the life of the process so discovery runs once per provider.
    """
    override = os.getenv(env_var)
    if override:
        return override.strip()

    if provider in _cache:
        return _cache[provider]

    preferred = list(preferred)
    chosen: Optional[str] = None
    try:
        available = list_models()
        available_lower = {m.lower(): m for m in available}
        for candidate in preferred:
            if candidate.lower() in available_lower:
                chosen = available_lower[candidate.lower()]
                break
        if chosen is None:
            chat_models = [m for m in available if not any(h in m.lower() for h in _NON_CHAT_HINTS)]
            if chat_models:
                chosen = chat_models[0]
                logger.warning(f"{provider}: none of the preferred models are available; using '{chosen}'.")
    except Exception as e:
        logger.warning(f"{provider}: could not list models ({e}); using default preference.")

    if chosen is None:
        chosen = preferred[0]

    logger.info(f"{provider}: using model '{chosen}'")
    _cache[provider] = chosen
    return chosen
