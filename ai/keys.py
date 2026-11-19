"""Helpers for reading provider API keys from environment variables."""
import os

from dotenv import load_dotenv

load_dotenv()


def get_keys(base_name: str) -> list[str]:
    """Return the configured keys for a provider, in priority order.

    Reads ``<BASE>`` and ``<BASE>_2`` (e.g. GROQ_API_KEY, GROQ_API_KEY_2),
    skipping any that are unset or blank.
    """
    names = [base_name, f"{base_name}_2"]
    return [v.strip() for v in (os.getenv(n) for n in names) if v and v.strip()]
