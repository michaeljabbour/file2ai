#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Logging functions
log_info() { echo -e "➜ $1"; }
log_success() { echo -e "${GREEN}✓ $1${NC}"; }
log_error() { echo -e "${RED}✗ $1${NC}"; exit 1; }

# Ensure we're in the right directory
cd "$(dirname "$0")"

# Create virtual environment and install dependencies
log_info "Setting up test environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[web]" || log_error "Failed to install package"

# Setup test files
log_info "Setting up test files..."
python setup_test_files.py || log_error "Failed to setup test files"

# Start web server in background
log_info "Starting web server..."
FLASK_DEBUG=1 FLASK_ENV=development python web.py &
WEB_PID=$!
sleep 2  # Wait for server to start

# Function to cleanup
cleanup() {
    kill $WEB_PID
    deactivate
    rm -rf .venv
}
trap cleanup EXIT

# Test single file upload
log_info "Testing single file upload..."
RESPONSE=$(curl -s -F "file=@sample.docx" \
                -F "format=pdf" \
                -F "brightness=1.0" \
                -F "contrast=1.0" \
                -F "resolution=300" \
                http://localhost:5000/)

JOB_ID=$(echo $RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])")
if [ -z "$JOB_ID" ]; then
    log_error "Failed to get job ID"
fi

# Poll for completion
log_info "Waiting for conversion..."
for i in {1..30}; do
    STATUS=$(curl -s http://localhost:5000/status/$JOB_ID)
    if echo $STATUS | grep -q '"status":"completed"'; then
        break
    elif echo $STATUS | grep -q '"status":"failed"'; then
        log_error "Conversion failed"
    fi
    sleep 1
done

# Download result
log_info "Downloading converted file..."
curl -s -o test_output.pdf http://localhost:5000/download/$JOB_ID
if [ ! -f test_output.pdf ]; then
    log_error "Failed to download converted file"
fi

# Test multiple file upload
log_info "Testing multiple file upload..."
RESPONSE=$(curl -s -F "file=@sample.docx" \
                -F "file=@sample.txt" \
                -F "format=text" \
                http://localhost:5000/)

JOB_ID=$(echo $RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])")
if [ -z "$JOB_ID" ]; then
    log_error "Failed to get job ID for multiple files"
fi

# Poll for completion
log_info "Waiting for multiple file conversion..."
for i in {1..30}; do
    STATUS=$(curl -s http://localhost:5000/status/$JOB_ID)
    if echo $STATUS | grep -q '"status":"completed"'; then
        break
    elif echo $STATUS | grep -q '"status":"failed"'; then
        log_error "Multiple file conversion failed"
    fi
    sleep 1
done

# Download result
log_info "Downloading converted files..."
curl -s -o converted_files.zip http://localhost:5000/download/$JOB_ID
if [ ! -f converted_files.zip ]; then
    log_error "Failed to download converted files"
fi

# Test error handling
log_info "Testing error handling..."
RESPONSE=$(curl -s -F "file=@nonexistent.txt" http://localhost:5000/)
if ! echo $RESPONSE | grep -q "No files selected"; then
    log_error "Error handling test failed"
fi

# Cleanup test files
rm -f test_output.pdf converted_files.zip

log_success "All web interface tests passed!"
