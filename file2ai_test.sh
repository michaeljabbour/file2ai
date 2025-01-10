#!/usr/bin/env bash
################################################################################
# FILE2AI TEST SCRIPT
#
# This script:
# - Sets up a virtual environment
# - Installs the package in editable mode
# - Runs basic functionality tests
################################################################################

# Exit on error
set -e

# Cleanup function to ensure web server is stopped
cleanup() {
    if [[ -n "${WEB_PID}" ]]; then
        echo "Stopping web server (PID: ${WEB_PID})"
        kill "${WEB_PID}" 2>/dev/null || true
        wait "${WEB_PID}" 2>/dev/null || true
    fi
}

# Set up cleanup trap
trap cleanup EXIT

# Ensure script is run as bash
if [ -z "$BASH" ]; then
    echo "Error: This script must be run with bash" >&2
    exit 1
fi

# Get absolute path to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

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

# Clean up old artifacts first
rm -rf file2ai.egg-info venv logs exports test_files

# Create required directories
mkdir -p test_files exports logs || {
    echo "Failed to create required directories" >&2
    exit 1
}

# Create and activate virtual environment
python3 -m venv venv || {
    echo "Failed to create virtual environment" >&2
    exit 1
}
source venv/bin/activate

# Install tqdm for progress tracking
python -m pip install --quiet tqdm || {
    echo "Failed to install tqdm" >&2
    exit 1
}

# Start progress tracking
python setup_progress.py | (
    # Report cleanup success
    echo "success"

    # Report venv creation success
    echo "success"

    # Install package with all dependencies
    python -m pip install -e . || {
        echo "Failed to install package" >&2
        exit 1
    }
    echo "success"

    # Test CLI help
    python file2ai.py --help || {
        echo "Failed to run CLI help" >&2
        exit 1
    }
    echo "success"

    # Create test files
    python create_test_files.py || {
        echo "Failed to create test files" >&2
        exit 1
    }
    echo "success"

    # Test file conversions
    for file in test_files/test.*; do
        if [ -f "$file" ]; then
            echo "Converting $file to text..."
            python file2ai.py convert --input "$file" --format text || {
                echo "Failed to convert $file" >&2
                exit 1
            }
        fi
    done
    echo "success"

    # Configure web server environment
    export FLASK_RUN_PORT=8000
    export FLASK_ENV=production
    export LOG_LEVEL=WARNING
    export WERKZEUG_LOGGER_LEVEL=WARNING
    
    # Start web server with explicit configuration
    python file2ai.py web --port 8000 --host 127.0.0.1 &
    WEB_PID=$!
    
    # Wait for server to start (up to 10 seconds)
    max_attempts=10
    attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:8000 > /dev/null; then
            echo "success"
            break
        fi
        sleep 1
        attempt=$((attempt + 1))
        if [ $attempt -eq $max_attempts ]; then
            kill $WEB_PID 2>/dev/null || true
            wait $WEB_PID 2>/dev/null || true
            echo "Failed to start web server after $max_attempts seconds" >&2
            exit 1
        fi
    done
)

# Clean up temporary progress script
rm -f setup_progress.py

# Ensure web server is stopped (backup explicit cleanup)
cleanup
