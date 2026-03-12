import psutil
import time

def get_nba2k14_pid():
    """Find the nba2k14.exe process and return its PID. Returns None if not found."""
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and proc.info['name'].lower() == 'nba2k14.exe':
            return proc.info['pid']
    return None

def wait_for_process(timeout: float = 0.0, poll_interval: float = 1.0):
    """Wait for the nba2k14 process to start."""
    start_time = time.time()
    while True:
        pid = get_nba2k14_pid()
        if pid is not None:
            return pid
        if timeout > 0 and (time.time() - start_time) > timeout:
            return None
        time.sleep(poll_interval)
