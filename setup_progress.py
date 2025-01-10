from tqdm import tqdm
import time
import sys

steps = [
    "Cleaning up old artifacts",
    "Creating virtual environment",
    "Installing package",
    "Testing CLI help",
    "Testing file conversions",
    "Starting web server"
]

with tqdm(total=len(steps), desc="Setup Progress", position=0) as pbar:
    for step in steps:
        pbar.set_postfix_str(step)
        # Read step result from stdin
        result = sys.stdin.readline().strip()
        if result != "success":
            print(f"\nError during {step}", file=sys.stderr)
            sys.exit(1)
        pbar.update(1)
        time.sleep(0.1)  # Small delay for visibility
