import keyboard
import time
import sys
from pathlib import Path

def record_actions():
    print("=== NBA 2K14 Automation Recorder ===")
    print("1. Switch to NBA 2K14.")
    print("2. When you are ready at the Main Menu, press 'F9' to start recording.")
    print("3. Perform the actions to start the game.")
    print("4. Press 'F10' to stop recording.")
    print("=====================================")

    # Wait for start trigger
    keyboard.wait('f9')
    print("\nRecording started... (Press F10 to stop)")
    
    events = []
    start_time = time.time()
    
    # Simple recording loop
    hook = keyboard.hook(lambda e: events.append(e))
    
    keyboard.wait('f10')
    keyboard.unhook(hook)
    
    print("\nRecording stopped.")
    
    if not events:
        print("No events recorded.")
        return

    # Process events to find key down intervals
    output = []
    last_time = start_time
    
    # We only care about 'down' events for high-level replication
    for event in events:
        if event.event_type == 'down':
            delay = event.time - last_time
            # Ignore the stop key
            if event.name == 'f10':
                continue
            output.append((event.name, delay))
            last_time = event.time

    print("\n=== RECORDED SEQUENCE ===")
    for key, delay in output:
        # Map common keys to pywinauto format
        pw_key = key
        if key == 'space': pw_key = ' '
        elif key == 'enter': pw_key = '{ENTER}'
        elif key == 'esc': pw_key = '{VK_ESCAPE}'
        elif key == 'right': pw_key = '{RIGHT}'
        elif key == 'left': pw_key = '{LEFT}'
        elif key == 'up': pw_key = '{UP}'
        elif key == 'down': pw_key = '{DOWN}'
        
        print(f"self.send('{pw_key}', delay={delay:.2f})")

    print("\nCopy the sequence above to update src/simulation/headless_runner.py")

if __name__ == "__main__":
    record_actions()
