import pytest
from src.pipeline.latency_tracker import LatencyTracker
from src.pipeline.resource_audit import ResourceAudit
import time

def test_latency_tracking():
    tracker = LatencyTracker()
    tracker.start("stage_1")
    time.sleep(0.1)
    tracker.stop("stage_1")
    
    report = tracker.get_report()
    assert "stage_1" in report["laps"]
    assert report["laps"]["stage_1"] >= 0.1
    assert report["total_latency"] >= 0.1

def test_resource_audit():
    audit_tool = ResourceAudit(threshold_mem_mb=10) # Set low to trigger warning if needed
    audit = audit_tool.get_audit()
    
    assert "memory_mb" in audit
    assert "cpu_percent" in audit
    assert audit["pid"] > 0
    assert audit["status"] in ["HEALTHY", "WARNING_MEM_HIGH"]
