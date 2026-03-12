import os
from groq import Groq

def generate_causal_explanation(prompt: str) -> str:
    """
    Generate a causal explanation for a game using Groq.
    Falls back to a static message if API is unavailable.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return "Causal explanation unavailable — GROQ_API_KEY not configured."
    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Causal explanation unavailable: {e}"
