from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Any

class NodeType(Enum):
    PLAYER = "PLAYER"
    TEAM = "TEAM"
    COACH = "COACH"
    REFEREE = "REFEREE"
    ARENA = "ARENA"
    GAME = "GAME"

class EdgeType(Enum):
    PLAYS_FOR = "PLAYS_FOR"
    COACHED_BY = "COACHED_BY"
    OFFICIATED_BY = "OFFICIATED_BY"
    PLAYS_AT = "PLAYS_AT"
    MATCHUP = "MATCHUP"

@dataclass
class GraphNode:
    id: str  # Unique identifier (e.g. "player_123", "team_gsw")
    type: NodeType
    features: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    type: EdgeType
    weight: float = 1.0
    attributes: Dict[str, float] = field(default_factory=dict)
