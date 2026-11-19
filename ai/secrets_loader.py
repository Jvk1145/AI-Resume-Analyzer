import os
from typing import Optional


def get_secret(name: str) -> Optional[str]:
    """
    Look up a secret by name from, in order:
      1. Environment variables (includes values loaded from a local .env file)
      2. Streamlit secrets, top level  (NAME = "...")
      3. Streamlit secrets, inside any section  ([api_keys] NAME = "...")
    """
    value = os.getenv(name)
    if value:
        return value.strip()

    try:
        import streamlit as st
        secrets = st.secrets
        if name in secrets and isinstance(secrets[name], str):
            return secrets[name].strip()
        for section in secrets.values():
            if hasattr(section, "get") and isinstance(section.get(name), str):
                return section.get(name).strip()
    except Exception:
        # No secrets.toml / not running under Streamlit.
        pass
    return None
