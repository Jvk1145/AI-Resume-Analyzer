import os
import random
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Gather your 4 specific OpenRouter keys into a rotating pool
OR_KEY_POOL = [
    os.getenv("OPENROUTER_API_KEY_MAIN"),
    os.getenv("OPENROUTER_API_KEY_LAGUNA"),
    os.getenv("OPENROUTER_API_KEY_NVIDIA"),
    os.getenv("OPENROUTER_API_KEY_COHERE")
]
OR_KEY_POOL = [k for k in OR_KEY_POOL if k]

def call_openrouter(prompt: str, system_prompt: str) -> str:
    """Calls OpenRouter rotating through 4 different keys with native server fallbacks and a fail-fast timeout."""
    if not OR_KEY_POOL:
        raise ValueError("No OpenRouter keys found in environment.")
        
    # Randomize the start key to balance the load across accounts
    keys_to_try = OR_KEY_POOL.copy()
    random.shuffle(keys_to_try)
    
    for idx, api_key in enumerate(keys_to_try):
        try:
            # Added a strict 10-second timeout so it skips dead or hanging API keys quickly
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1", 
                api_key=api_key,
                timeout=10.0
            )
            
            response = client.chat.completions.create(
                model="openrouter/auto", 
                extra_body={
                    "models": [
                        "nvidia/nemotron-3-ultra-550b-a55b:free", 
                        "tencent/hy3:free",                       
                        "openai/gpt-oss-120b:free",               
                        "google/gemini-2.5-flash:free"            
                    ]
                },
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"OpenRouter key instance {idx+1} failed or timed out: {e}. Trying next key...")
            continue
            
    raise RuntimeError("All keys in the OpenRouter pool failed.")