#!/bin/bash
set -e

# Create Python script for progress tracking
cat > setup_progress.py << 'EOF'
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
EOF

# Start progress tracking
python3 -m pip install --quiet tqdm || exit 1
python3 setup_progress.py | (
    # Clean up old artifacts
    rm -rf file2ai.egg-info venv logs exports
    echo "success"

    # Create and activate virtual environment
    python3 -m venv venv
    source venv/bin/activate
    echo "success"

    # Install package
    pip install -e .
    echo "success"

    # Test CLI help
    python file2ai.py --help
    echo "success"

    # Test file conversions
    python create_test_files.py
    for file in test_files/*; do
        python file2ai.py convert --input "$file" --format text
    done
    echo "success"

    # Start web server
    python file2ai.py web &
    WEB_PID=$!
    sleep 2  # Give the server time to start
    echo "success"

    # Clean up
    kill $WEB_PID 2>/dev/null || true
)

# Clean up temporary progress script
rm -f setup_progress.py
