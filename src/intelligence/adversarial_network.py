import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import json
from pathlib import Path

@dataclass
class GameFeatures:
    """Feature vector for one game prediction."""
    home_win_pct: float
    away_win_pct: float
    home_rest_days: float
    away_rest_days: float
    home_ortg: float
    away_ortg: float
    home_drtg: float
    away_drtg: float
    momentum_home: float
    momentum_away: float
    pace_differential: float
    injury_impact_home: float  # 0=healthy, 1=decimated
    injury_impact_away: float
    referee_foul_rate: float
    is_back_to_back_home: float
    is_back_to_back_away: float

    def to_array(self) -> np.ndarray:
        return np.array([
            self.home_win_pct, self.away_win_pct,
            self.home_rest_days / 7.0, self.away_rest_days / 7.0,
            self.home_ortg / 120.0, self.away_ortg / 120.0,
            self.home_drtg / 120.0, self.away_drtg / 120.0,
            self.momentum_home, self.momentum_away,
            self.pace_differential / 10.0,
            self.injury_impact_home, self.injury_impact_away,
            self.referee_foul_rate,
            self.is_back_to_back_home, self.is_back_to_back_away,
        ], dtype=np.float32)

@dataclass
class OracleModel:
    """
    The predictor. Linear model with learned weights.
    Deliberately simple so Adversary can find blind spots.
    """
    weights: np.ndarray = field(
        default_factory=lambda: np.array([
            0.15, -0.15,   # win pct
            0.05, -0.05,   # rest days
            0.12, -0.12,   # ortg
            -0.10, 0.10,   # drtg
            0.08, -0.08,   # momentum
            0.03,          # pace diff
            -0.18, 0.18,   # injury impact
            0.02,          # referee
            -0.06, 0.06,   # b2b
        ], dtype=np.float32)
    )
    bias: float = 0.57  # home court advantage prior

    def predict(self, features: GameFeatures) -> float:
        x = features.to_array()
        raw = self.bias + float(np.dot(self.weights, x))
        return max(0.05, min(0.95, raw))

    def update_weights(self, gradient: np.ndarray, lr: float = 0.01):
        self.weights = self.weights + lr * gradient

@dataclass
class AdversaryAgent:
    """
    Finds game types where Oracle is systematically wrong.
    Generates adversarial examples by perturbing features in
    directions that maximize Oracle prediction error.
    """
    attack_history: List[dict] = field(default_factory=list)
    blind_spots: Dict[str, float] = field(default_factory=dict)

    def find_blind_spot(
        self,
        oracle: OracleModel,
        game_features: GameFeatures,
        true_outcome: float,
        perturbation_scale: float = 0.1,
    ) -> Tuple[GameFeatures, float]:
        """
        Use gradient-based attack to find feature perturbation
        that maximizes Oracle prediction error.
        Returns adversarial features and the error magnitude.
        """
        x = game_features.to_array()
        oracle_pred = oracle.predict(game_features)
        original_error = abs(oracle_pred - true_outcome)

        best_x = x.copy()
        best_error = original_error

        # FGSM-style attack: perturb in direction of gradient
        for _ in range(10):
            # Numerical gradient
            grad = np.zeros_like(x)
            for i in range(len(x)):
                x_plus = x.copy()
                x_plus[i] += 0.01

                class PerturbedFeatures:
                    def to_array(self_inner):
                        return x_plus
                perturbed_pred = oracle.bias + float(np.dot(oracle.weights, x_plus))
                perturbed_pred = max(0.05, min(0.95, perturbed_pred))
                grad[i] = (abs(perturbed_pred - true_outcome) - original_error) / 0.01

            # Step in direction that increases error
            x_adv = x + perturbation_scale * np.sign(grad)
            x_adv = np.clip(x_adv, 0, 1)

            class AdvFeatures:
                def to_array(self_inner):
                    return x_adv

            adv_pred = oracle.bias + float(np.dot(oracle.weights, x_adv))
            adv_pred = max(0.05, min(0.95, adv_pred))
            adv_error = abs(adv_pred - true_outcome)

            if adv_error > best_error:
                best_error = adv_error
                best_x = x_adv

        # Identify which features were most perturbed
        delta = best_x - x
        most_attacked = int(np.argmax(np.abs(delta)))
        feature_names = [
            "home_win_pct", "away_win_pct", "home_rest", "away_rest",
            "home_ortg", "away_ortg", "home_drtg", "away_drtg",
            "momentum_home", "momentum_away", "pace_diff",
            "injury_home", "injury_away", "referee_foul",
            "b2b_home", "b2b_away"
        ]
        blind_spot_name = feature_names[most_attacked] if most_attacked < len(feature_names) else f"dim_{most_attacked}"
        self.blind_spots[blind_spot_name] = self.blind_spots.get(blind_spot_name, 0) + best_error

        self.attack_history.append({
            "blind_spot": blind_spot_name,
            "error_magnitude": best_error,
            "original_error": original_error,
        })

        return game_features, best_error

@dataclass
class MarketAgent:
    """
    Simulates market efficiency pressure.
    Tracks which edges Oracle finds and "prices them in"
    over time, forcing Oracle to find deeper edges.
    """
    priced_in_edges: Dict[str, float] = field(default_factory=dict)
    market_efficiency: float = 0.55  # starts below fully efficient

    def price_in(self, edge_type: str, edge_magnitude: float):
        """Record that a type of edge has been discovered and priced in."""
        current = self.priced_in_edges.get(edge_type, 0.0)
        # Market becomes more efficient over time for this edge type
        self.priced_in_edges[edge_type] = min(1.0, current + edge_magnitude * 0.1)
        self.market_efficiency = min(0.95, self.market_efficiency + 0.001)

    def get_remaining_edge(self, edge_type: str, raw_edge: float) -> float:
        """How much of this edge remains after market adjustment."""
        priced = self.priced_in_edges.get(edge_type, 0.0)
        return raw_edge * (1.0 - priced)

    def get_efficiency_report(self) -> dict:
        return {
            "market_efficiency": self.market_efficiency,
            "priced_in_edges": dict(sorted(
                self.priced_in_edges.items(),
                key=lambda x: x[1], reverse=True
            )),
            "remaining_alpha_edges": {
                k: round(1.0 - v, 3)
                for k, v in self.priced_in_edges.items()
                if v < 0.8
            }
        }

def run_adversarial_training_cycle(
    oracle: OracleModel,
    adversary: AdversaryAgent,
    market: MarketAgent,
    training_games: List[Tuple[GameFeatures, float]],
    cycles: int = 100,
) -> dict:
    """
    Run N adversarial training cycles.
    Each cycle:
    1. Oracle predicts on training games
    2. Adversary finds blind spots
    3. Oracle updates weights to cover blind spots
    4. Market prices in discovered edges
    Returns training history and final Oracle weights.
    """
    history = []
    total_error = 0.0

    for cycle in range(cycles):
        cycle_error = 0.0
        weight_gradient = np.zeros_like(oracle.weights)

        for features, true_outcome in training_games:
            # Oracle prediction
            pred = oracle.predict(features)
            error = pred - true_outcome
            cycle_error += abs(error)

            # Adversary attack
            _, blind_spot_error = adversary.find_blind_spot(
                oracle, features, true_outcome
            )

            # Compute gradient for Oracle weight update
            x = features.to_array()
            weight_gradient += -error * x  # gradient descent

            # Market prices in the edge if Oracle found one
            edge_magnitude = abs(pred - 0.5)
            if edge_magnitude > 0.1:
                market.price_in("win_pct_edge", edge_magnitude)
            if features.injury_impact_home > 0.3 or features.injury_impact_away > 0.3:
                market.price_in("injury_edge", edge_magnitude)
            if features.is_back_to_back_home > 0.5 or features.is_back_to_back_away > 0.5:
                market.price_in("fatigue_edge", edge_magnitude * 0.5)

        # Update Oracle weights
        avg_gradient = weight_gradient / max(len(training_games), 1)
        oracle.update_weights(avg_gradient, lr=0.005)

        avg_error = cycle_error / max(len(training_games), 1)
        total_error += avg_error

        if cycle % 10 == 0:
            history.append({
                "cycle": cycle,
                "avg_error": round(avg_error, 4),
                "market_efficiency": round(market.market_efficiency, 4),
                "blind_spots_found": len(adversary.blind_spots),
            })

    # Top blind spots Oracle needs to address
    top_blind_spots = sorted(
        adversary.blind_spots.items(),
        key=lambda x: x[1], reverse=True
    )[:5]

    return {
        "cycles_completed": cycles,
        "final_avg_error": round(total_error / cycles, 4),
        "top_blind_spots": [
            {"feature": k, "total_error": round(v, 4)}
            for k, v in top_blind_spots
        ],
        "market_report": market.get_efficiency_report(),
        "training_history": history,
        "final_weights": oracle.weights.tolist(),
    }

def build_adversarial_system() -> Tuple[OracleModel, AdversaryAgent, MarketAgent]:
    """Initialize all three agents."""
    return OracleModel(), AdversaryAgent(), MarketAgent()

def generate_synthetic_training_games(n: int = 500) -> List[Tuple[GameFeatures, float]]:
    """Generate synthetic training games for adversarial training."""
    np.random.seed(42)
    games = []
    for _ in range(n):
        home_win_pct = np.random.uniform(0.3, 0.7)
        away_win_pct = np.random.uniform(0.3, 0.7)
        features = GameFeatures(
            home_win_pct=float(home_win_pct),
            away_win_pct=float(away_win_pct),
            home_rest_days=float(np.random.choice([1, 2, 3, 4, 5])),
            away_rest_days=float(np.random.choice([1, 2, 3, 4, 5])),
            home_ortg=float(np.random.uniform(105, 120)),
            away_ortg=float(np.random.uniform(105, 120)),
            home_drtg=float(np.random.uniform(105, 120)),
            away_drtg=float(np.random.uniform(105, 120)),
            momentum_home=float(np.random.uniform(0, 1)),
            momentum_away=float(np.random.uniform(0, 1)),
            pace_differential=float(np.random.uniform(-5, 5)),
            injury_impact_home=float(np.random.uniform(0, 0.5)),
            injury_impact_away=float(np.random.uniform(0, 0.5)),
            referee_foul_rate=float(np.random.uniform(0.85, 1.15)),
            is_back_to_back_home=float(np.random.random() < 0.2),
            is_back_to_back_away=float(np.random.random() < 0.2),
        )
        # True outcome: home wins based on win pct differential + noise
        home_prob = 0.57 + (home_win_pct - away_win_pct) * 0.5
        home_prob -= features.injury_impact_home * 0.2
        home_prob += features.injury_impact_away * 0.2
        home_prob -= features.is_back_to_back_home * 0.04
        home_prob = max(0.05, min(0.95, home_prob))
        true_outcome = float(np.random.random() < home_prob)
        games.append((features, true_outcome))
    return games
