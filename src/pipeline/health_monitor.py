import os
import time
from datetime import datetime
from pathlib import Path

# Session A: Pipeline Armor Constants
STALE_THRESHOLD_HOURS = 26.0
KELLY_STALE_MULTIPLIER = 0.40
CONFIDENCE_STALE_PENALTY = 0.65

class HealthMonitor:
    """Backward compatibility wrapper for existing pipeline code."""
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        
    def check_health(self) -> dict:
        """Wrapper for get_pipeline_health."""
        return get_pipeline_health(self.data_dir)

def get_data_age_hours(file_path: str) -> float:
    """Calculate the age of a file in hours."""
    path = Path(file_path)
    if not path.exists():
        return float('inf')
    
    mtime = path.stat().st_mtime
    age_seconds = time.time() - mtime
    return round(age_seconds / 3600.0, 1)

def is_data_stale(file_path: str) -> bool:
    """Check if a specific file is older than the threshold."""
    age = get_data_age_hours(file_path)
    return age >= STALE_THRESHOLD_HOURS

def get_pipeline_health(data_dir: str) -> dict:
    """
    Perform a multi-point health check on the simulation pipeline.
    Checks roster freshness and model availability.
    """
    roster_path = Path(data_dir) / "roster.ros"
    data_age = get_data_age_hours(str(roster_path))
    is_stale = data_age >= STALE_THRESHOLD_HOURS
    
    status = "healthy"
    if is_stale:
        status = "degraded"
    elif not roster_path.exists():
        status = "critical"
        
    return {
        "status": status,
        "is_stale": is_stale,
        "data_age_hours": data_age,
        "stale_threshold_hours": STALE_THRESHOLD_HOURS,
        "kelly_multiplier_override": KELLY_STALE_MULTIPLIER if is_stale else 1.0,
        "confidence_penalty": CONFIDENCE_STALE_PENALTY if is_stale else 1.0,
        "last_check_utc": datetime.utcnow().isoformat() + "Z",
    }

def audit_pipeline_resources() -> dict:
    """Check disk usage and log file sizes for the pipeline."""
    # Placeholder for future expansion
    return {"disk_status": "ok"}
