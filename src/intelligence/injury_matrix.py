"""
injury_matrix.py — Epoch Engine
================================
Defines the performance degradation matrix for different injury types.
Maps (body_part, severity) → attribute multipliers.
Used by QuantumRoster to adjust player performance distributions.
"""

from enum import Enum
from typing import Dict, Tuple

class InjurySeverity(Enum):
    GRADE_1 = 1  # Minor: playable but hampered (e.g., "playing through")
    GRADE_2 = 2  # Moderate: missing games or significantly hampered
    GRADE_3 = 3  # Severe: long-term recovery, high penalty if returned early

# Category mapping for attribute groups
ATTR_GROUPS = {
    "mobility":   ["athleticism", "defense"],
    "precision":  ["shooting", "scoring"],
    "coordination": ["playmaking", "scoring"],
}

# The Matrix: (body_part, severity) -> {attr_group: multiplier}
# Standard multiplier is 1.0 (no impact)
INJURY_DEGRADATION_MATRIX = {
    # Lower Body — Mobility killers
    "ankle": {
        InjurySeverity.GRADE_1: {"mobility": 0.92, "precision": 0.98, "coordination": 0.95},
        InjurySeverity.GRADE_2: {"mobility": 0.85, "precision": 0.94, "coordination": 0.88},
        InjurySeverity.GRADE_3: {"mobility": 0.70, "precision": 0.85, "coordination": 0.75},
    },
    "knee": {
        InjurySeverity.GRADE_1: {"mobility": 0.88, "precision": 0.96, "coordination": 0.92},
        InjurySeverity.GRADE_2: {"mobility": 0.78, "precision": 0.90, "coordination": 0.82},
        InjurySeverity.GRADE_3: {"mobility": 0.55, "precision": 0.80, "coordination": 0.65},
    },
    "hamstring": {
        InjurySeverity.GRADE_1: {"mobility": 0.85, "precision": 0.98, "coordination": 0.95},
        InjurySeverity.GRADE_2: {"mobility": 0.75, "precision": 0.92, "coordination": 0.88},
        InjurySeverity.GRADE_3: {"mobility": 0.50, "precision": 0.85, "coordination": 0.70},
    },
    
    # Upper Body — Shooting/Playmaking killers
    "shoulder": {
        InjurySeverity.GRADE_1: {"precision": 0.88, "mobility": 0.96, "coordination": 0.92},
        InjurySeverity.GRADE_2: {"precision": 0.78, "mobility": 0.90, "coordination": 0.82},
        InjurySeverity.GRADE_3: {"precision": 0.55, "mobility": 0.80, "coordination": 0.65},
    },
    "wrist": {
        InjurySeverity.GRADE_1: {"precision": 0.85, "coordination": 0.85, "mobility": 0.98},
        InjurySeverity.GRADE_2: {"precision": 0.72, "coordination": 0.70, "mobility": 0.94},
        InjurySeverity.GRADE_3: {"precision": 0.45, "coordination": 0.40, "mobility": 0.85},
    },
    "finger": {
        InjurySeverity.GRADE_1: {"precision": 0.92, "coordination": 0.92, "mobility": 1.00},
        InjurySeverity.GRADE_2: {"precision": 0.82, "coordination": 0.80, "mobility": 0.98},
        InjurySeverity.GRADE_3: {"precision": 0.65, "coordination": 0.60, "mobility": 0.95},
    },
    
    # Core/Back — General degradation
    "back": {
        InjurySeverity.GRADE_1: {"mobility": 0.90, "precision": 0.90, "coordination": 0.90},
        InjurySeverity.GRADE_2: {"mobility": 0.80, "precision": 0.80, "coordination": 0.80},
        InjurySeverity.GRADE_3: {"mobility": 0.60, "precision": 0.60, "coordination": 0.60},
    },
}

def get_injury_multipliers(body_part: str, severity: InjurySeverity) -> Dict[str, float]:
    """Retrieve attribute group multipliers for a specific injury."""
    part_key = body_part.lower().strip()
    
    # Fallback to general impact if part not in matrix
    if part_key not in INJURY_DEGRADATION_MATRIX:
        impact = 1.0 - (severity.value * 0.10)
        return {"mobility": impact, "precision": impact, "coordination": impact}
        
    return INJURY_DEGRADATION_MATRIX[part_key][severity]

def calculate_attribute_impact(
    attribute_name: str, 
    multipliers: Dict[str, float]
) -> float:
    """Calculate the final multiplier for a specific attribute name."""
    attr_lower = attribute_name.lower()
    
    final_mult = 1.0
    for group, attrs in ATTR_GROUPS.items():
        if attr_lower in attrs:
            final_mult = min(final_mult, multipliers.get(group, 1.0))
            
    return final_mult

def parse_severity_from_text(text: str) -> InjurySeverity:
    """Heuristic to determine injury severity from reporter text."""
    text_lower = text.lower()
    if any(k in text_lower for k in ["severe", "grade 3", "rupture", "surgery", "out indefinitely"]):
        return InjurySeverity.GRADE_3
    if any(k in text_lower for k in ["moderate", "grade 2", "sprain", "strain", "multiple weeks"]):
        return InjurySeverity.GRADE_2
    return InjurySeverity.GRADE_1 # Default to minor/Grade 1 for general mentions

def get_injury_factor(player_name: str, body_part: str, severity_text: str) -> Dict[str, float]:
    """
    High-level entry point for the simulation.
    Returns a dict of attribute modifiers.
    """
    severity = parse_severity_from_text(severity_text)
    multipliers = get_injury_multipliers(body_part, severity)
    
    # Map to all standard attributes in QuantumRoster
    all_attrs = ["scoring", "shooting", "defense", "athleticism", "playmaking"]
    return {
        attr: calculate_attribute_impact(attr, multipliers)
        for attr in all_attrs
    }

def get_injury_impact(body_part: str, severity_text: str, position: str = "G") -> float:
    """
    Enrichment helper: Returns an aggregated health multiplier [0, 1].
    1.0 = Full health, 0.5 = severely hampered.
    Used by enrich_features.py.
    """
    factors = get_injury_factor("unused", body_part, severity_text)
    
    # Weights based on position (simplified)
    if position in ["PG", "SG", "G"]:
        weights = {"scoring": 0.3, "shooting": 0.3, "playmaking": 0.2, "defense": 0.1, "athleticism": 0.1}
    elif position in ["SF", "PF", "F"]:
        weights = {"scoring": 0.25, "shooting": 0.2, "playmaking": 0.15, "defense": 0.2, "athleticism": 0.2}
    else: # Centers
        weights = {"scoring": 0.2, "shooting": 0.05, "playmaking": 0.05, "defense": 0.4, "athleticism": 0.3}
        
    impact = sum(factors[k] * weights[k] for k in weights)
    return float(impact)
