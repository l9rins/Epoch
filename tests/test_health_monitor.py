import pytest
import os
import time
from pathlib import Path
from src.pipeline.health_monitor import get_data_age_hours, is_data_stale, get_pipeline_health

def test_data_age_missing_file():
    # Large value for missing file
    assert get_data_age_hours("non_existent_file_xyz_123") == float('inf')

def test_data_age_fresh_file(tmp_path):
    f = tmp_path / "test.ros"
    f.write_text("dummy")
    # Fresh file should be < 1 hour
    assert get_data_age_hours(str(f)) < 1.0

def test_data_age_stale_file(tmp_path):
    f = tmp_path / "test.ros"
    f.write_text("dummy")
    # Set mtime to 30 hours ago
    stale_time = time.time() - (30 * 3600)
    os.utime(str(f), (stale_time, stale_time))
    assert get_data_age_hours(str(f)) >= 30.0
    assert is_data_stale(str(f)) is True

def test_pipeline_health_healthy(tmp_path):
    f = tmp_path / "roster.ros"
    f.write_text("dummy")
    health = get_pipeline_health(str(tmp_path))
    assert health["status"] == "healthy"
    assert health["is_stale"] is False
    assert health["kelly_multiplier_override"] == 1.0

def test_pipeline_health_degraded(tmp_path):
    f = tmp_path / "roster.ros"
    f.write_text("dummy")
    # 30 hours is over the 26h threshold
    stale_time = time.time() - (30 * 3600)
    os.utime(str(f), (stale_time, stale_time))
    
    health = get_pipeline_health(str(tmp_path))
    assert health["status"] == "degraded"
    assert health["is_stale"] is True
    assert health["data_age_hours"] >= 30.0
    assert health["kelly_multiplier_override"] == 0.40
    assert health["confidence_penalty"] == 0.65
