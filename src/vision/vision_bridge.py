from typing import Dict, Optional
import numpy as np
from dataclasses import dataclass
from src.vision.player_tracker import PlayerTracker
from src.vision.court_analyzer import CourtAnalyzer, CourtIntelligence
from src.simulation.memory_reader import GameState

class VisionBridge:
    def __init__(self, homography_matrix: Optional[np.ndarray] = None):
        self.tracker = PlayerTracker()
        self.analyzer = CourtAnalyzer(homography_matrix)
        
    def enrich_game_state(self, state: GameState, frame_or_intel) -> Dict:
        """
        Takes a raw GameState and either a video frame or CourtIntelligence,
        extracts vision intelligence, and returns it as a dict.
        """
        if isinstance(frame_or_intel, (np.ndarray, list)):
            # 1. Get detections
            detections = self.tracker.process_frame(frame_or_intel)
            # 2. Extract intelligence
            intelligence = self.analyzer.get_intelligence(detections)
        elif hasattr(frame_or_intel, 'defensive_spacing'):
            # It's CourtIntelligence
            intelligence = {
                "defensive_spacing": frame_or_intel.defensive_spacing,
                "paint_density": frame_or_intel.paint_density,
                "three_point_coverage": frame_or_intel.three_point_coverage,
                "pick_roll": 1 if frame_or_intel.pick_roll_detected else 0,
                "fast_break": 1 if frame_or_intel.fast_break_detected else 0,
                "open_shooter": 1 if frame_or_intel.open_shooter_detected else 0
            }
        else:
            intelligence = frame_or_intel

        # Attach to state and return the intelligence dict
        state.vision_intelligence = intelligence
        return intelligence

    def get_vision_features(self, frame: np.ndarray) -> Dict:
        """
        Helper to just get the features without a state object.
        """
        detections = self.tracker.process_frame(frame)
        return self.analyzer.get_intelligence(detections)
