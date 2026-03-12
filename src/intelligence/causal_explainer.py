import os
from google import genai

def generate_causal_explanation(prompt: str) -> str:
    """
    Generate a causal explanation for a game using Gemini.
    Falls back to a static message if API is unavailable.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "Causal explanation unavailable — GEMINI_API_KEY not configured."
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"Causal explanation unavailable: {e}"
