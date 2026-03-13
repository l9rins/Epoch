import psutil
import os
import json
from datetime import datetime
from pathlib import Path

class ResourceAudit:
    def __init__(self, threshold_mem_mb=500):
        self.threshold_mem_mb = threshold_mem_mb
        self.process = psutil.Process(os.getpid())

    def get_audit(self):
        mem_info = self.process.memory_info()
        mem_mb = mem_info.rss / (1024 * 1024)
        cpu_perc = self.process.cpu_percent(interval=0.1)
        
        status = "HEALTHY"
        if mem_mb > self.threshold_mem_mb:
            status = "WARNING_MEM_HIGH"
            
        return {
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "memory_mb": round(mem_mb, 2),
            "cpu_percent": cpu_perc,
            "pid": os.getpid()
        }

    def log_audit(self, log_path="data/pipeline_report.json"):
        audit = self.get_audit()
        # Ensure directory exists
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Read existing or start fresh
        if Path(log_path).exists():
            try:
                with open(log_path, 'r') as f:
                    data = json.load(f)
            except:
                data = {}
        else:
            data = {}
            
        data["resource_audit"] = audit
        with open(log_path, 'w') as f:
            json.dump(data, f, indent=4)
        return audit
