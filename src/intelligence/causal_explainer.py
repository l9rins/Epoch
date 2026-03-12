import os
from typing import Optional

try:
    import google.generativeai as genai
except ImportError:
    # Dummy mock if not installed
    class mock_genai:
        def configure(self, **kwargs): pass
        def GenerativeModel(self, *args, **kwargs): return self
        def generate_content(self, *args, **kwargs): return type("obj", (object,), {"text": None})
    genai = mock_genai()

class CausalExplainer:
    """Interfaces with Gemini API to build narrativized causal chain scouting reports."""
    
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel("gemini-2.0-flash") if self.api_key else None
        
    def generate_report(self, prompt: str) -> Optional[str]:
        """Sends the structured Prompt 03 to Gemini and retrieves the causal chain report."""
        if not self.model:
            return "GEMINI_API_KEY not configured. Mock Mode: The simulation projects a tight matchup where the edge is derived directly from the recent momentum swing and rotational mismatches in the secondary unit."
            
        try:
            # We use gemini-2.0-flash for excellent reasoning and speed at a free tier.
            # Temperature acts similarly to keep responses analytical.
            generation_config = genai.types.GenerationConfig(
                temperature=0.3, # Keep it analytical, not creative
                max_output_tokens=1024,
            )
            response = self.model.generate_content(
                f"System: You are an elite NBA predictive analyst writing for professional syndicates.\n\nUser: {prompt}",
                generation_config=generation_config
            )
            return response.text
        except Exception as e:
            print(f"Failed to generate report: {e}")
            return None
