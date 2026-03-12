import os
from typing import Optional

try:
    from anthropic import Anthropic
except ImportError:
    class Anthropic:
        def __init__(self, api_key=None): pass
        def messages(self, **kwargs): return None

class CausalExplainer:
    """Interfaces with Claude API to build narrativized causal chain scouting reports."""
    
    def __init__(self):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=self.api_key) if self.api_key else None
        
    def generate_report(self, prompt: str) -> Optional[str]:
        """Sends the structured Prompt 03 to Claude and retrieves the causal chain report."""
        if not self.client:
            return "ANTHROPIC_API_KEY not configured. Mock Mode: The simulation projects a tight matchup where the edge is derived directly from the recent momentum swing and rotational mismatches in the secondary unit."
            
        try:
            # We use haiku or sonnet for latency/cost depending on tier. 
            # Prompt 03 is highly structured so Sonnet is perfect.
            response = getattr(self.client, "messages").create(
                model="claude-sonnet-4-5",
                max_tokens=1024,
                temperature=0.3, # Keep it analytical, not creative
                system="You are an elite NBA predictive analyst writing for professional syndicates.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text
        except Exception as e:
            print(f"Failed to generate report: {e}")
            return None
