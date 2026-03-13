from pywinauto import Application
import psutil

def get_nba2k14_pid():
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and proc.info['name'].lower() == 'nba2k14.exe':
            return proc.info['pid']
    return None

pid = get_nba2k14_pid()
if pid:
    print(f"Found NBA 2K14 PID: {pid}")
    try:
        app = Application().connect(process=pid)
        print("Connected!")
        window = app.top_window()
        print(f"Window title: {window.texts()}")
    except Exception as e:
        print(f"Error: {e}")
else:
    print("NBA 2K14 not found.")
