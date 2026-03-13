import time
import json
from datetime import datetime
from pathlib import Path

class LatencyTracker:
    def __init__(self):
        self.start_times = {}
        self.laps = {}

    def start(self, stage):
        self.start_times[stage] = time.time()

    def stop(self, stage):
        if stage in self.start_times:
            duration = time.time() - self.start_times[stage]
            self.laps[stage] = round(duration, 4)
            return duration
        return 0

    def get_report(self):
        return {
            "timestamp": datetime.now().isoformat(),
            "laps": self.laps,
            "total_latency": round(sum(self.laps.values()), 4)
        }

    def log_latency(self, log_path="data/pipeline_report.json"):
        report = self.get_report()
        if Path(log_path).exists():
            try:
                with open(log_path, 'r') as f:
                    data = json.load(f)
            except:
                data = {}
        else:
            data = {}
            
        data["latency_tracker"] = report
        with open(log_path, 'w') as f:
            json.dump(data, f, indent=4)
        return report
