"""Helpers for reading provider API keys from env vars, .env or Streamlit secrets."""
from dotenv import load_dotenv

from ai.secrets_loader import get_secret

load_dotenv()


def get_keys(base_name: str) -> list[str]:
    """Return the configured keys for a provider, in priority order.

    Reads ``<BASE>`` and ``<BASE>_2`` (e.g. GROQ_API_KEY, GROQ_API_KEY_2) from
    environment variables / .env first, then Streamlit secrets, skipping any
    that are unset or blank.
    """
    keys = [get_secret(name) for name in (base_name, f"{base_name}_2")]
    return [k for k in keys if k]
