import cv2
import numpy as np
import time
from src.vision.vision_bridge import VisionBridge
from src.simulation.memory_reader import GameState

def test_full_vision_pipeline():
    print("=== Vision Pipeline Integration Test ===")
    
    # 1. Initialize Bridge
    # Use identity matrix for testing
    bridge = VisionBridge(np.eye(3))
    print("VisionBridge initialized.")
    
    # 2. Create Dummy Frame (1080p black frame)
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    
    # 3. Create Dummy State
    state = GameState(
        timestamp=time.time(),
        quarter=1,
        clock=720.0,
        home_score=0,
        away_score=0,
        possession=0
    )
    
    # 4. Enrich State
    print("Enriching state with vision intelligence...")
    vi = bridge.enrich_game_state(state, frame)
    print(f"Features Extracted: {vi}")
    
    expected_keys = [
        "defensive_spacing", "paint_density", 
        "three_point_coverage", "pick_roll", 
        "fast_break", "open_shooter"
    ]
    
    for key in expected_keys:
        assert key in vi, f"Missing key: {key}"
        
    print("\nVISION PIPELINE VERIFIED!")

if __name__ == "__main__":
    try:
        test_full_vision_pipeline()
    except Exception as e:
        print(f"TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
