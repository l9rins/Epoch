import subprocess
import sys
from pathlib import Path

tests = [
    "tests/test_binary.py",
    "tests/test_ml.py",
    "tests/test_phase8.py",
    "tests/test_signal.py",
    "tests/test_simulation.py",
    "tests/test_translation.py"
]

total_passed = 0
all_output = []

for test in tests:
    print(f"Running {test}...")
    result = subprocess.run([sys.executable, "-m", "pytest", test, "-v"], capture_output=True, text=True)
    all_output.append(result.stdout)
    print(result.stdout)
    if result.returncode != 0:
        print(f"Error in {test}:")
        print(result.stderr)

print("\n=== SUMMARY OF ALL TESTS ===")
# Count total passed tests from all outputs
import re
passed_matches = re.findall(r"(\d+) passed", "\n".join(all_output))
total_passed = sum(int(m) for m in passed_matches)
print(f"Total Tests Passed: {total_passed}")
