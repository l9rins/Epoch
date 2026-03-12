import numpy as np
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class CourtIntelligence:
    defensive_spacing: float
    paint_density: float
    three_point_coverage: float
    pick_roll_detected: bool
    fast_break_detected: bool
    open_shooter_detected: bool


@dataclass
class Point3D:
    x: float
    y: float
    z: float = 0.0

class CourtAnalyzer:
    def __init__(self, homography_matrix: np.ndarray = None):
        # Default 3x3 identity if none provided (for pass-through testing)
        self.homography = homography_matrix if homography_matrix is not None else np.eye(3)
        
        # Standard court dimensions (ft)
        # 0,0 is baseline center usually
        self.COURT_WIDTH = 50.0 
        self.COURT_LENGTH = 94.0
        self.PAINT_WIDTH = 16.0
        self.PAINT_DEPTH = 19.0
        
    def project_detections(self, detections: List[List[float]]) -> List[Point3D]:
        """
        Project screen detections (x, y) to court coordinates (X, Y) using homography.
        Expects detections as list of [x1, y1, x2, y2, track_id]
        """
        projected = []
        for det in detections:
            # Use feet/bottom center of bounding box for projection
            u = (det[0] + det[2]) / 2.0
            v = det[3]
            
            p = np.array([u, v, 1.0]).reshape(3, 1)
            p_court = np.dot(self.homography, p)
            p_court /= p_court[2] # Normalize w
            
            projected.append(Point3D(x=float(p_court[0]), y=float(p_court[1])))
            
        return projected

    def calculate_spacing(self, players: List[Point3D]) -> float:
        """
        Calculate average spacing (inter-player distance).
        Simplified: mean distance between all player pairs.
        """
        if len(players) < 2:
            return 50.0 # Default
            
        distances = []
        for i, p1 in enumerate(players):
            for p2 in players[i+1:]:
                dist = np.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)
                distances.append(dist)
        
        return float(np.mean(distances)) if distances else 50.0

    def calculate_paint_density(self, players: List[Point3D]) -> int:
        """
        Count players in the key/paint area.
        Key area: Width 16ft (-8 to 8), Depth 19ft (0 to 19).
        """
        count = 0
        for p in players:
            if -8.0 <= p.x <= 8.0 and 0.0 <= p.y <= 19.0:
                count += 1
        return count

    def detect_open_shooter(self, players: List[Point3D]) -> bool:
        """
        Detect if any player has > 10ft of space from others.
        """
        for i, p1 in enumerate(players):
            nearest_dist = float('inf')
            for j, p2 in enumerate(players):
                if i == j: continue
                dist = np.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)
                if dist < nearest_dist:
                    nearest_dist = dist
            
            if nearest_dist > 10.0:
                return True
        return False

    def get_intelligence(self, detections) -> Dict:
        """
        Process detections and return a dictionary of spatial features.
        """
        # Convert supervision detections or raw coords to list if needed
        # Assuming detections has .xyxy and possibly .tracker_id
        coords = detections.xyxy
        players = self.project_detections(coords)
        
        return {
            "defensive_spacing": round(self.calculate_spacing(players), 1),
            "paint_density": self.calculate_paint_density(players),
            "three_point_coverage": 50.0, # Placeholder
            "pick_roll": 0, # Placeholder
            "fast_break": 0, # Placeholder
            "open_shooter": 1 if self.detect_open_shooter(players) else 0
        }
