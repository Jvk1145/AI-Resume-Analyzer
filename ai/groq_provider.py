import os
import logging
from ai.secrets_loader import get_secret
from openai import OpenAI
from dotenv import load_dotenv
from ai.model_resolver import resolve_model

load_dotenv()
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

def call_groq(prompt: str, system_prompt: str) -> str:
    """
    Calls Groq API using your active key.
    """
    api_key = get_secret("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in environment variables or Streamlit secrets.")

    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=api_key,
        timeout=60.0
    )

    model = resolve_model(
        "Groq", "GROQ_MODEL", GROQ_PREFERRED_MODELS,
        lambda: [m.id for m in client.models.list().data],
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=4000,
        response_format={"type": "json_object"}
    )

    return response.choices[0].message.content
