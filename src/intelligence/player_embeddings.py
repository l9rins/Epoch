import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import json
from pathlib import Path

EMBEDDING_DIM = 128

@dataclass
class PlayerEmbedding:
    player_id: str
    player_name: str
    team: str
    season: str
    vector: np.ndarray  # shape (128,)
    metadata: dict

    def similarity(self, other: "PlayerEmbedding") -> float:
        """Cosine similarity between two player embeddings."""
        norm_self = np.linalg.norm(self.vector)
        norm_other = np.linalg.norm(other.vector)
        if norm_self == 0 or norm_other == 0:
            return 0.0
        return float(np.dot(self.vector, other.vector) / (norm_self * norm_other))

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "team": self.team,
            "season": self.season,
            "vector": self.vector.tolist(),
            "metadata": self.metadata,
        }

def build_embedding_from_ros_player(
    player_data: dict,
    skill_values: List[float],
    tendency_values: List[float],
) -> np.ndarray:
    """
    Build a 128-dim embedding from .ROS player data.
    skill_values: 42 floats normalized 0-1
    tendency_values: 57 floats normalized 0-1
    player_data: dict with height, weight, age, etc.
    """
    vector = np.zeros(EMBEDDING_DIM)

    # Dims 0-41: Skills (normalized tier 0-13 → 0-1)
    for i, val in enumerate(skill_values[:42]):
        vector[i] = val / 13.0

    # Dims 42-98: Tendencies (normalized 0-99 → 0-1)
    for i, val in enumerate(tendency_values[:57]):
        vector[42 + i] = val / 99.0

    # Dims 99-105: Physical attributes
    height_in = player_data.get("height_inches", 78)
    weight_lb = player_data.get("weight_lbs", 215)
    age = player_data.get("age", 26)
    vector[99] = (height_in - 66) / 18.0   # normalize 66-84 inches
    vector[100] = (weight_lb - 150) / 150.0  # normalize 150-300 lbs
    vector[101] = (age - 18) / 20.0          # normalize 18-38 years
    vector[102] = player_data.get("speed_rating", 50) / 99.0
    vector[103] = player_data.get("vertical_rating", 50) / 99.0
    vector[104] = player_data.get("strength_rating", 50) / 99.0
    vector[105] = player_data.get("wingspan_proxy", 0.5)

    # Dims 106-111: Contextual performance
    vector[106] = player_data.get("home_split", 0.52)
    vector[107] = player_data.get("clutch_rating", 0.5)
    vector[108] = player_data.get("fatigue_resistance", 0.5)
    vector[109] = player_data.get("altitude_adjustment", 0.0)
    vector[110] = player_data.get("b2b_performance", 0.48)
    vector[111] = player_data.get("playoff_performance", 0.5)

    # Dims 112-117: Career trajectory
    vector[112] = min(player_data.get("games_played", 82) / 82.0, 1.0)
    vector[113] = min(player_data.get("years_in_league", 5) / 20.0, 1.0)
    vector[114] = player_data.get("injury_history_score", 0.1)
    vector[115] = (player_data.get("peak_age", 27) - 18) / 20.0
    vector[116] = player_data.get("trajectory_slope", 0.0)  # improving/declining
    vector[117] = player_data.get("consistency_score", 0.5)

    # Dims 118-123: Psychological dimensions
    vector[118] = player_data.get("confidence_index", 0.5)
    vector[119] = player_data.get("adversity_response", 0.5)
    vector[120] = player_data.get("leadership_score", 0.5)
    vector[121] = player_data.get("pressure_performance", 0.5)
    vector[122] = player_data.get("media_pressure_handling", 0.5)
    vector[123] = player_data.get("team_chemistry_contribution", 0.5)

    # Dims 124-127: Era normalization
    era_year = player_data.get("era_year", 2024)
    vector[124] = (era_year - 1950) / 75.0  # pace era
    vector[125] = max(0, (era_year - 1979)) / 45.0  # 3PT era
    vector[126] = max(0, (era_year - 1990)) / 35.0  # athleticism era
    vector[127] = max(0, (era_year - 2010)) / 15.0  # analytics era

    return vector

class EmbeddingSpace:
    """
    Manages a collection of player embeddings and enables
    similarity search, chemistry analysis, and counterfactuals.
    """
    def __init__(self, storage_path: str = "data/player_embeddings.json"):
        self.storage_path = Path(storage_path)
        self.embeddings: Dict[str, PlayerEmbedding] = {}
        self._load()

    def _load(self):
        if self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    data = json.load(f)
                for player_id, entry in data.items():
                    self.embeddings[player_id] = PlayerEmbedding(
                        player_id=entry["player_id"],
                        player_name=entry["player_name"],
                        team=entry["team"],
                        season=entry["season"],
                        vector=np.array(entry["vector"]),
                        metadata=entry.get("metadata", {}),
                    )
            except Exception as e:
                print(f"Embedding load warning: {e}")

    def save(self):
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, "w") as f:
            json.dump(
                {pid: e.to_dict() for pid, e in self.embeddings.items()},
                f
            )

    def add(self, embedding: PlayerEmbedding):
        self.embeddings[embedding.player_id] = embedding

    def find_similar(
        self,
        player_id: str,
        top_k: int = 5,
        exclude_same_season: bool = True,
    ) -> List[Tuple[PlayerEmbedding, float]]:
        """Find top_k most similar players by cosine similarity."""
        if player_id not in self.embeddings:
            return []
        query = self.embeddings[player_id]
        scores = []
        for pid, emb in self.embeddings.items():
            if pid == player_id:
                continue
            if exclude_same_season and emb.season == query.season:
                continue
            scores.append((emb, query.similarity(emb)))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def compute_lineup_chemistry(
        self, player_ids: List[str]
    ) -> dict:
        """
        Add all player vectors. Analyze geometry for synergy vs redundancy.
        High vector variance = complementary skills (synergy).
        Low vector variance = overlapping skills (redundancy).
        """
        vectors = []
        for pid in player_ids:
            if pid in self.embeddings:
                vectors.append(self.embeddings[pid].vector)
        if len(vectors) < 2:
            return {"synergy_score": 0.5, "redundancy_score": 0.5, "chemistry_vector": []}

        matrix = np.stack(vectors)
        team_vector = matrix.mean(axis=0)

        # Variance across dimensions = skill diversity
        variance_per_dim = matrix.var(axis=0)
        synergy_score = float(np.mean(variance_per_dim) * 10)
        synergy_score = max(0.0, min(1.0, synergy_score))

        # Pairwise cosine similarities = redundancy
        similarities = []
        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                v1, v2 = vectors[i], vectors[j]
                sim = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8))
                similarities.append(sim)
        redundancy_score = float(np.mean(similarities)) if similarities else 0.5

        return {
            "synergy_score": round(synergy_score, 4),
            "redundancy_score": round(redundancy_score, 4),
            "chemistry_vector": team_vector.tolist(),
            "player_count": len(vectors),
        }

    def counterfactual(
        self,
        roster_ids: List[str],
        remove_id: str,
        add_id: str,
    ) -> dict:
        """
        Compute team vector change from swapping one player for another.
        Returns delta vector and human-readable impact summary.
        """
        original_vectors = [
            self.embeddings[pid].vector
            for pid in roster_ids
            if pid in self.embeddings
        ]
        if not original_vectors:
            return {"impact": "insufficient data"}

        original_team = np.mean(original_vectors, axis=0)

        # Swap
        new_ids = [pid for pid in roster_ids if pid != remove_id] + [add_id]
        new_vectors = [
            self.embeddings[pid].vector
            for pid in new_ids
            if pid in self.embeddings
        ]
        if not new_vectors:
            return {"impact": "insufficient data"}

        new_team = np.mean(new_vectors, axis=0)
        delta = new_team - original_team

        # Identify most impacted dimensions
        top_dims = np.argsort(np.abs(delta))[-5:][::-1]
        
        impact_summary = []
        for dim in top_dims:
            if dim < 42:
                label = f"skill_dim_{dim}"
            elif dim < 99:
                label = f"tendency_dim_{dim-42}"
            elif dim < 106:
                label = f"physical_dim_{dim-99}"
            else:
                label = f"meta_dim_{dim-106}"
            direction = "+" if delta[dim] > 0 else "-"
            impact_summary.append(f"{direction}{abs(delta[dim]):.3f} {label}")

        return {
            "vector_delta_magnitude": float(np.linalg.norm(delta)),
            "top_impacts": impact_summary,
            "team_improvement": float(np.mean(delta)),
        }

    def seed_with_defaults(self, n_players: int = 50):
        """
        Seeds the embedding space with synthetic player embeddings
        for testing when real .ROS data is not available.
        """
        np.random.seed(42)
        player_archetypes = [
            ("elite_scorer", [0.9, 0.85, 0.8] + [0.5]*39, [0.7]*57),
            ("defensive_anchor", [0.5, 0.6, 0.4] + [0.5]*39, [0.3]*57),
            ("playmaker", [0.7, 0.9, 0.6] + [0.5]*39, [0.8]*57),
            ("3point_specialist", [0.6, 0.5, 0.95] + [0.5]*39, [0.6]*57),
            ("two_way_wing", [0.75, 0.7, 0.75] + [0.5]*39, [0.6]*57),
        ]

        names = [
            "Stephen Curry", "LeBron James", "Kevin Durant",
            "Giannis Antetokounmpo", "Nikola Jokic",
            "Joel Embiid", "Luka Doncic", "Jayson Tatum",
            "Anthony Davis", "Devin Booker",
        ]

        for i in range(min(n_players, 50)):
            archetype_name, skills, tendencies = player_archetypes[i % len(player_archetypes)]
            noise = np.random.normal(0, 0.05, EMBEDDING_DIM)
            player_data = {
                "height_inches": 75 + (i % 12),
                "weight_lbs": 190 + (i % 80),
                "age": 22 + (i % 16),
                "speed_rating": 50 + (i % 49),
                "vertical_rating": 45 + (i % 50),
                "strength_rating": 40 + (i % 55),
                "clutch_rating": 0.3 + (i % 7) * 0.1,
                "era_year": 2024,
            }
            vec = build_embedding_from_ros_player(player_data, skills, tendencies)
            vec = np.clip(vec + noise, 0, 1)
            name = names[i % len(names)] + (f" ({i})" if i >= len(names) else "")
            emb = PlayerEmbedding(
                player_id=f"player_{i:03d}",
                player_name=name,
                team=["GSW", "LAL", "BOS", "MIA", "DEN"][i % 5],
                season="2024-25",
                vector=vec,
                metadata={"archetype": archetype_name},
            )
            self.add(emb)
        self.save()
        print(f"Seeded {len(self.embeddings)} player embeddings")
