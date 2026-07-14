import os
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

def call_groq(prompt: str, system_prompt: str) -> str:
    """
    Calls Groq API using your active key with a strict timeout.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in the environment variables.")

    # Added a strict 10.0 second timeout to prevent hanging
    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=api_key,
        timeout=10.0
    )
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=4000,
        response_format={"type": "json_object"}
    )
    
    return response.choices[0].message.content