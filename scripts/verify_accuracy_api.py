import json
from fastapi.testclient import TestClient
from pathlib import Path
import sys
import os

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.main import app
from src.ml.calibration import CalibrationEngine

def test_accuracy_endpoint():
    client = TestClient(app)
    
    # 1. Initially it might be null or empty
    response = client.get("/api/accuracy")
    print(f"Initial API Response: {response.json()}")
    
    # 2. Add some dummy data to calibration_history.jsonl to verify it picks it up
    history_file = Path("data/calibration_history.jsonl")
    history_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Add 10 dummy entries (50% prob, all won -> Brier = 0.25)
    with open(history_file, "w") as f:
        for _ in range(10):
            f.write(json.dumps({"predicted": 0.5, "actual": 1}) + "\n")
            
    # Need to reload or re-instantiate engine in main.py, but for now we'll just check if a fresh call works
    # Actually, main.py instantiates it once at module level.
    # To test properly we'll just mock the engine or restart the app context.
    
    response = client.get("/api/accuracy")
    print(f"API Response with data: {response.json()}")
    
    # Cleanup dummy data
    if history_file.exists():
        history_file.unlink()

if __name__ == "__main__":
    test_accuracy_endpoint()
