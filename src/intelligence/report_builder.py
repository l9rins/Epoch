from typing import Dict, Any

class ReportBuilder:
    """Builds the structured Prompt 03 for Claude to generate Causal Chain reports."""
    
    @staticmethod
    def construct_prompt(game_id: str, game_context: Dict[str, Any], predictions: Dict[str, Any]) -> str:
        """
        Assembles all prediction, simulation, and graph data into the 
        standard Prompt 03 layout for the LLM.
        """
        home = game_context.get("home_team", "HOME")
        away = game_context.get("away_team", "AWAY")
        
        # Extract predictions
        wp = predictions.get("win_probability", 0.5)
        favored = home if wp >= 0.5 else away
        edge_pct = max(wp, 1.0 - wp) * 100
        
        proj_home = predictions.get("projected_home", 0)
        proj_away = predictions.get("projected_away", 0)
        
        # Placeholder for graph insights
        graph_insight = predictions.get("graph_insight", "No specific relational anomalies detected.")
        
        prompt = f"""
You are the Epoch Engine Lead Data Scientist. Generate a Causal Chain Scouting Report 
for the upcoming {away} at {home} game (ID: {game_id}).

Do not hallucinate stats. Base your analysis completely on the following simulation outputs:

## Simulation Engine Output
- Favored: {favored} ({edge_pct:.1f}%)
- Projected Score: {home} {proj_home} - {away} {proj_away}
- Ensemble Agreement: {predictions.get("ensemble_agreement", "8/8 models")}

## Relational Graph (System B) Output
- {graph_insight}

## Medical / Context
- Rest Advantage: {game_context.get("rest_advantage", "None")}
- Key Injuries: {game_context.get("injuries", "None")}

Format your response exactly as 4 paragraphs:
Paragraph 1: THE EDGE (What the simulation sees that the market doesn't)
Paragraph 2: THE MECHANISM (The causal chain: e.g. injury -> matchup -> advantage)
Paragraph 3: THE SIGNALS (What confirms this from the ensemble/graph)
Paragraph 4: THE RISKS (Top 2 things that could invalidate the prediction)
"""
        return prompt.strip()
