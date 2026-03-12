import numpy as np
from typing import Dict, Any, List
from .schema import GraphNode, NodeType

class FeatureExtractor:
    """Extracts base features from binary objects and stats to create PyG node vectors."""
    
    @staticmethod
    def extract_player_features(player_data: Any) -> List[float]:
        """Converts raw player skills and tendencies into a normalized feature vector."""
        # For POC, assuming player_data is a dictionary matching the API payload
        features = []
        
        # Core tendencies (normalized 0-1)
        tendencies = ['TIso', 'TPNR', 'TSpotUp', 'TTransition']
        for t in tendencies:
            val = player_data.get('tendencies', {}).get(t, 50)
            features.append(val / 100.0)
            
        # Core skills (normalized 0-1, 25-99 scale maps to 0-1)
        skills = ['SSht3PT', 'SShtMR', 'SShtFT', 'SShtClose', 'SDribble', 'SPass']
        for s in skills:
            val = player_data.get('skills', {}).get(s, 70)
            features.append(max(0.0, (val - 25) / 74.0))
            
        return features

    @staticmethod
    def extract_team_features(team_stats: Dict[str, float]) -> List[float]:
        """Normalizes team season averages."""
        features = [
            team_stats.get('win_pct', 0.500),
            team_stats.get('ortg', 110.0) / 120.0,  # Normalize vs max historic ORtg
            team_stats.get('drtg', 110.0) / 120.0,
            team_stats.get('pace', 100.0) / 110.0
        ]
        return features
        
    @staticmethod
    def extract_referee_features(ref_stats: Dict[str, float]) -> List[float]:
        """Normalizes referee historical biases."""
        features = [
            ref_stats.get('foul_rate', 45.0) / 60.0,
            ref_stats.get('home_win_pct', 0.55)
        ]
        return features
