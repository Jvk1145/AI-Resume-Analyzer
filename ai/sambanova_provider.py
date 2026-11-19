import os
import logging
from openai import OpenAI
from dotenv import load_dotenv
from ai.model_resolver import resolve_model

load_dotenv()
logger = logging.getLogger(__name__)

# Tried in order; the first one SambaNova currently serves is used. Override with SAMBANOVA_MODEL.
SAMBANOVA_PREFERRED_MODELS = [
    "Meta-Llama-3.3-70B-Instruct",
    "DeepSeek-V3.1",
    "gpt-oss-120b",
    "Llama-4-Maverick-17B-128E-Instruct",
    "Qwen3-32B",
    "Meta-Llama-3.1-8B-Instruct",
]

def call_sambanova(prompt: str, system_prompt: str) -> str:
    """
    Calls SambaNova Cloud API with your active key.
    """
    api_key = os.getenv("SAMBANOVA_API_KEY")
    if not api_key:
        raise ValueError("SAMBANOVA_API_KEY is not set in the environment variables.")

    client = OpenAI(
        base_url="https://api.sambanova.ai/v1",
        api_key=api_key,
        timeout=60.0
    )

    model = resolve_model(
        "SambaNova", "SAMBANOVA_MODEL", SAMBANOVA_PREFERRED_MODELS,
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
