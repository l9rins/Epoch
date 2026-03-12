import os
import google.generativeai as genai
from pathlib import Path

# Load key from environment
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.0-flash"

genai.configure(api_key=GEMINI_API_KEY)

def generate_causal_explanation(prompt: str) -> str:
    """
    Generate a causal explanation for a game using Gemini.
    Falls back to a static message if API is unavailable.
    """
    if not GEMINI_API_KEY:
        return "Causal explanation unavailable — GEMINI_API_KEY not configured."
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Causal explanation unavailable: {e}"
