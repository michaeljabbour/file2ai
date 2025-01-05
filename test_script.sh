#!/usr/bin/env bash

# test_script.sh
# --------------------------------------------------
# Automated validation script for file2ai
#
# Usage:
#   ./test_script.sh
#
# Requirements:
#   - Python 3.x with venv module
#   - Git
#
# This script:
#   1) Creates a clean virtual environment
#   2) Installs file2ai and test dependencies
#   3) Runs pytest with coverage reporting
#   4) Performs export tests:
#      - Local directory export
#      - Remote repository export
#      - Repository subdirectory export
#   5) Validates output files:
#      - Checks file existence
#      - Verifies file structure
#      - Checks content markers
#      - Verifies sequential file naming
#
# Exit Codes:
#   0 - All tests passed
#   1 - Test or validation failure
#
# Example Output Files:
#   exports/file2ai_export.txt    - Local directory export
#   exports/docling_export.txt    - Remote repository export
#   exports/docling_export(1).txt - Subdirectory export
#
# Note: This script will clean up existing venv and exports
#       before running tests. Make sure to backup any important
#       files before running.

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Logging helpers
log_success() { echo -e "${GREEN}✓ $1${NC}"; }
log_error() { echo -e "${RED}✗ $1${NC}"; exit 1; }
log_warn() { echo -e "${YELLOW}! $1${NC}"; }
log_info() { echo -e "➜ $1"; }

# Check if sudo is available
if ! command -v sudo &> /dev/null; then
    log_warn "sudo not found - cleanup may fail if files are owned by root"
    if ! rm -rf venv logs exports launchers 2>/dev/null; then
        log_error "Permission denied. Please run with sudo or manually remove: venv logs exports launchers"
    fi
else
    # 1) Clean up old artifacts
    log_info "Cleaning up old artifacts..."
    # Use sudo only if regular rm fails
    if ! rm -rf venv logs exports launchers 2>/dev/null; then
        log_warn "Permission denied, trying with sudo..."
        sudo rm -rf venv logs exports launchers || log_error "Failed to remove directories even with sudo"
    fi
fi
log_success "Cleanup complete"

# 2) Create & activate virtual environment
log_info "Creating fresh virtual environment..."
python3 -m venv venv
source venv/bin/activate
log_success "Virtual environment created and activated"

# 3) Install package and dependencies
log_info "Installing file2ai in editable mode..."
# Capture all installation output
install_output=$(pip install --upgrade pip 2>&1) || {
    log_error "Failed to upgrade pip. Output:\n$install_output"
}
install_output=$(pip install -e . 2>&1) || {
    log_error "Failed to install file2ai. Output:\n$install_output"
}
install_output=$(pip install pytest pytest-cov flask 2>&1) || {
    log_error "Failed to install test dependencies. Output:\n$install_output"
}
log_success "Installation complete"

# Set up cleanup trap for frontend server
cleanup() {
    if [ -n "$FLASK_PID" ]; then
        kill $FLASK_PID 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Launch frontend server
log_info "Launching frontend server..."
python web.py &
FLASK_PID=$!

# Wait for server to start
sleep 2

# Test frontend server response
response=$(curl -s http://localhost:5000)
if [[ $response == *"File2AI Converter"* ]]; then
    log_success "Frontend server launched successfully"
else
    log_error "Frontend server failed to launch properly"
fi

# Create test file for form submission
log_info "Creating test file for form submission..."
echo "Test content" > test_upload.txt

# Test form submission
log_info "Testing form submission..."
test_response=$(curl -s -X POST -F "command=convert" -F "format=text" -F "file=@test_upload.txt" http://localhost:5000)
if [[ $test_response == *"job_id"* ]]; then
    log_success "Form submission test passed"
else
    log_error "Form submission test failed"
    log_error "Response: $test_response"
fi

# Clean up test file
rm -f test_upload.txt

# 4) Run tests with coverage
log_info "Running tests with coverage..."
pytest --cov=file2ai tests/ || log_error "Tests failed!"
log_success "Tests passed"

# 5) Test local directory export
log_info "Testing local directory export..."
python file2ai.py --local-dir . || log_error "Local export failed!"

# 6) Test normal remote repo export
log_info "Testing normal remote repo export..."
python file2ai.py --repo-url https://github.com/michaeljabbour/file2ai || log_error "Remote repo export failed!"

# 7) Test subdir/extra path export
log_info "Testing subdir/extra path export..."
python file2ai.py --repo-url-sub https://github.com/michaeljabbour/file2ai/pulls || log_error "Subdir export failed!"

# 8) Test document conversions
log_info "Testing PDF conversion..."
python file2ai.py convert --input attachments/paper.pdf --format text || log_error "PDF to text conversion failed!"
python file2ai.py convert --input attachments/paper.pdf --format image --brightness 1.5 --contrast 1.2 || log_error "PDF to image conversion failed!"

log_info "Testing Word document conversion..."
python file2ai.py convert --input attachments/paper.docx --format text || { log_error "Word to text conversion failed!"; true; }
python file2ai.py convert --input attachments/paper.docx --format image --brightness 1.5 --contrast 1.2 || { log_error "Word to image conversion failed!"; true; }

log_info "Testing PowerPoint conversion..."
python file2ai.py convert --input attachments/writing_the_research_paper.pptx --format text || { log_error "PowerPoint to text conversion failed!"; true; }
python file2ai.py convert --input attachments/writing_the_research_paper.pptx --format image --brightness 1.5 --contrast 1.2 || { log_error "PowerPoint to image conversion failed!"; true; }

log_info "Testing Excel conversion..."
python file2ai.py convert --input "attachments/Research+data+_+figshare.xlsx" --format text || { log_error "Excel to text conversion failed!"; true; }
python file2ai.py convert --input "attachments/Research+data+_+figshare.xlsx" --format image --brightness 1.5 --contrast 1.2 || { log_error "Excel to image conversion failed!"; true; }

# 9) Validate document conversion outputs
log_info "Validating document conversion outputs..."

# Check PDF outputs
pdf_txt="exports/paper.text"
if [ -f "$pdf_txt" ]; then
    log_info "PDF text export found"
    if [ -s "$pdf_txt" ]; then
        log_success "PDF text export has content"
    else
        log_error "PDF text export is empty"
    fi
else
    log_error "Missing PDF text export: $pdf_txt"
fi

pdf_img="exports/paper.image"
if [ -f "$pdf_img" ]; then
    log_info "PDF image export found"
    if [ -s "$pdf_img" ] && grep -q "exports/images/" "$pdf_img"; then
        # Check if actual image files exist
        while IFS= read -r img_path || [ -n "$img_path" ]; do
            if [ ! -f "$img_path" ]; then
                log_error "Missing PDF image file: $img_path"
            fi
        done < "$pdf_img"
        log_success "PDF image export and files look correct"
    else
        log_error "PDF image export list is invalid"
    fi
else
    log_error "Missing PDF image export: $pdf_img"
fi

# Check Word document outputs
docx_txt="exports/paper.text"
if [ -f "$docx_txt" ]; then
    log_info "Word text export found"
    if [ -s "$docx_txt" ]; then
        log_success "Word text export has content"
    else
        log_error "Word text export is empty"
    fi
else
    log_error "Missing Word text export: $docx_txt"
fi

docx_img="exports/paper.image"
if [ -f "$docx_img" ]; then
    log_info "Word image export found"
    if [ -s "$docx_img" ] && grep -q "exports/images/" "$docx_img"; then
        while IFS= read -r img_path || [ -n "$img_path" ]; do
            if [ ! -f "$img_path" ]; then
                log_error "Missing Word image file: $img_path"
            fi
        done < "$docx_img"
        log_success "Word image export and files look correct"
    else
        log_error "Word image export list is invalid"
    fi
else
    log_error "Missing Word image export: $docx_img"
fi

# Check PowerPoint outputs
ppt_txt="exports/writing_the_research_paper.text"
if [ -f "$ppt_txt" ]; then
    log_info "PowerPoint text export found"
    if [ -s "$ppt_txt" ]; then
        log_success "PowerPoint text export has content"
    else
        log_error "PowerPoint text export is empty"
    fi
else
    log_error "Missing PowerPoint text export: $ppt_txt"
fi

ppt_img="exports/writing_the_research_paper.image"
if [ -f "$ppt_img" ]; then
    log_info "PowerPoint image export found"
    if [ -s "$ppt_img" ] && grep -q "exports/images/" "$ppt_img"; then
        while IFS= read -r img_path || [ -n "$img_path" ]; do
            if [ ! -f "$img_path" ]; then
                log_error "Missing PowerPoint image file: $img_path"
            fi
        done < "$ppt_img"
        log_success "PowerPoint image export and files look correct"
    else
        log_error "PowerPoint image export list is invalid"
    fi
else
    log_error "Missing PowerPoint image export: $ppt_img"
fi

# Check Excel outputs
xlsx_txt="exports/Research+data+_+figshare.text"
if [ -f "$xlsx_txt" ]; then
    log_info "Excel text export found"
    if [ -s "$xlsx_txt" ]; then
        log_success "Excel text export has content"
    else
        log_error "Excel text export is empty"
    fi
else
    log_error "Missing Excel text export: $xlsx_txt"
fi

xlsx_img="exports/Research+data+_+figshare.image"
if [ -f "$xlsx_img" ]; then
    log_info "Excel image export found"
    if [ -s "$xlsx_img" ] && grep -q "exports/images/" "$xlsx_img"; then
        while IFS= read -r img_path || [ -n "$img_path" ]; do
            if [ ! -f "$img_path" ]; then
                log_error "Missing Excel image file: $img_path"
            fi
        done < "$xlsx_img"
        log_success "Excel image export and files look correct"
    else
        log_error "Excel image export list is invalid"
    fi
else
    log_error "Missing Excel image export: $xlsx_img"
fi

# 10) Validate repository outputs
log_info "Validating repository output files..."

# Check local export
txt_file="exports/file2ai_export.txt"
if [ -f "$txt_file" ]; then
    log_info "Local directory export found"
    
    # Basic content validation
    if grep -q "Generated by file2ai" "$txt_file" && \
       grep -q "Directory Structure:" "$txt_file" && \
       grep -q "=" "$txt_file"; then
        log_success "Local export structure looks correct"
    else
        log_error "Local export structure is invalid"
    fi
    
    # Check file size
    size=$(wc -c < "$txt_file")
    if [ "$size" -gt 100 ]; then
        log_success "Local export has reasonable size ($size bytes)"
    else
        log_error "Local export seems too small ($size bytes)"
    fi
else
    log_error "Missing local export file: $txt_file"
fi

# Check remote repo export
txt_file="exports/file2ai_export.txt"
if [ -f "$txt_file" ]; then
    log_info "Remote repo text export found"
    
    # Basic content validation
    if grep -q "Generated by file2ai" "$txt_file" && \
       grep -q "Directory Structure:" "$txt_file" && \
       grep -q "=" "$txt_file"; then
        log_success "Text export structure looks correct"
    else
        log_error "Text export structure is invalid"
    fi
    
    # Check file size
    size=$(wc -c < "$txt_file")
    if [ "$size" -gt 1000 ]; then
        log_success "Text export has reasonable size ($size bytes)"
    else
        log_error "Text export seems too small ($size bytes)"
    fi
else
    log_error "Missing text export file: $txt_file"
fi

# Check subdir export
subdir_file="exports/file2ai_export(1).txt"
if [ -f "$subdir_file" ]; then
    log_info "Subdir export found"
    if grep -q "Generated by file2ai" "$subdir_file"; then
        log_success "Subdir export structure looks correct"
    else
        log_error "Subdir export structure is invalid"
    fi
else
    log_error "Missing subdir export file: $subdir_file"
fi

# 11) Launch and test frontend
log_info "Installing Flask if not present..."
pip install flask || log_error "Failed to install Flask"

log_info "Launching frontend server..."
mkdir -p logs
FLASK_APP=web.py python web.py > logs/frontend.log 2>&1 &
FRONTEND_PID=$!

# Add cleanup trap
trap 'kill $FRONTEND_PID 2>/dev/null' EXIT

# Wait for server to start
log_info "Waiting for frontend server to start..."
for i in {1..30}; do
    if curl -s http://localhost:5000 > /dev/null; then
        log_success "Frontend server is running"
        break
    fi
    if [ $i -eq 30 ]; then
        log_error "Frontend server failed to start. Check logs/frontend.log for details"
    fi
    sleep 1
done

# Verify frontend response
response=$(curl -s http://localhost:5000)
if echo "$response" | grep -q "File2AI Converter"; then
    log_success "Frontend is responding correctly"
else
    log_error "Frontend response is invalid"
fi

# Test form submission
log_info "Testing form submission..."
test_response=$(curl -s -X POST -F "command=convert" -F "file=@create_test_pdf.py" http://localhost:5000)
if echo "$test_response" | grep -q "job_id"; then
    log_success "Form submission working correctly"
else
    log_error "Form submission failed"
fi

log_success "All validation checks passed!"
log_info "Done."

# Note: The frontend server will be automatically killed by the trap when the script exits
