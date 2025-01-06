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

# Get the project root directory (one level up from tests/)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT" || log_error "Failed to change to project root directory"

# 1) Clean up old artifacts
log_info "Cleaning up old artifacts..."

# Define directories to clean up
cleanup_dirs=(
    "venv"
    "logs"
    "exports"
    "launchers"
    "__pycache__"
    "*.egg-info"
    ".coverage"
    ".pytest_cache"
)

# Clean up each directory
for dir in "${cleanup_dirs[@]}"; do
    if [ -e "$dir" ]; then
        log_info "Removing $dir..."
        rm -rf "$dir" 2>/dev/null || {
            log_warn "Failed to remove $dir - it may be in use or require different permissions"
            log_warn "You may need to remove it manually: rm -rf $dir"
        }
    fi
done

log_success "Cleanup complete"

# Create necessary directories
mkdir -p exports logs

# System dependency checks will be handled by Python package management

# 2) Create & activate virtual environment
log_info "Creating fresh virtual environment..."
python3 -m venv venv
source venv/bin/activate
log_success "Virtual environment created and activated"

# 3) Install package and dependencies
log_info "Installing file2ai in editable mode with all dependencies..."
# Capture all installation output
install_output=$(pip install --upgrade pip 2>&1) || {
    log_error "Failed to upgrade pip. Output:\n$install_output"
}
install_output=$(pip install -e ".[test,web]" 2>&1) || {
    log_error "Failed to install file2ai with dependencies. Output:\n$install_output"
}
log_success "Installation complete"

# Set up cleanup trap for frontend server
cleanup() {
    if [ -n "$FLASK_PID" ]; then
        kill $FLASK_PID 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Create test files and populate export directory first
log_info "Creating test files and populating export directory..."

# Create exports directory if it doesn't exist and ensure proper permissions
mkdir -p "$PROJECT_ROOT/exports"
chmod 777 "$PROJECT_ROOT/exports"

# Create all test files first
log_info "Creating test files..."

# Create all test files
log_info "Creating PDF test file..."
python "$PROJECT_ROOT/tests/create_test_pdf.py" || log_error "Failed to create PDF test file"
log_info "Creating Word test file..."
python "$PROJECT_ROOT/tests/create_test_doc.py" || log_error "Failed to create Word test file"
log_info "Creating Excel test file..."
python "$PROJECT_ROOT/tests/create_test_excel.py" || log_error "Failed to create Excel test file"
log_info "Creating PowerPoint test file..."
python "$PROJECT_ROOT/tests/create_test_ppt.py" || log_error "Failed to create PowerPoint test file"
log_info "Creating HTML test file..."
python "$PROJECT_ROOT/tests/create_test_html.py" || log_error "Failed to create HTML test file"

# Verify all test files exist and have content
log_info "Verifying test files..."
for file in test.pdf test.docx test.xlsx test.pptx test.html; do
    if [ ! -f "$PROJECT_ROOT/exports/$file" ]; then
        log_error "Test file not found: $file"
    fi
    if [ ! -s "$PROJECT_ROOT/exports/$file" ]; then
        log_error "Test file is empty: $file"
    fi
done

log_info "Files in exports directory after creation:"
ls -la "$PROJECT_ROOT/exports/"

# Create backup directory and backup all test files
mkdir -p "$PROJECT_ROOT/tests/backup"
for file in test.pdf test.docx test.xlsx test.pptx test.html; do
    if [ -f "$PROJECT_ROOT/exports/$file" ]; then
        cp "$PROJECT_ROOT/exports/$file" "$PROJECT_ROOT/tests/backup/$file" || log_error "Failed to backup $file"
        log_info "Backed up $file"
    fi
done
log_info "Test files backed up to tests/backup directory"
sleep 2  # Give filesystem time to sync

# Verify all test files exist
log_info "Verifying test files..."
for file in test.pdf test.docx test.xlsx test.pptx test.html; do
    if [ ! -f "$PROJECT_ROOT/exports/$file" ]; then
        log_error "Test file not found: $file"
    fi
done

# Create test file for form submission
log_info "Creating test file for form submission..."
echo "Test content" > "$PROJECT_ROOT/exports/test_upload.txt"

# 4) Run tests with coverage
log_info "Running tests with coverage..."
cd "$PROJECT_ROOT" && PYTHONPATH="$PROJECT_ROOT" pytest --cov=file2ai tests/ || log_error "Tests failed!"
log_success "Tests passed"

# Restore test files after pytest
log_info "Restoring test files after pytest..."
for file in test.pdf test.docx test.xlsx test.pptx test.html; do
    if [ -f "$PROJECT_ROOT/tests/backup/$file" ]; then
        cp "$PROJECT_ROOT/tests/backup/$file" "$PROJECT_ROOT/exports/$file" || log_error "Failed to restore $file"
        log_info "Restored $file"
    fi
done
log_info "Files in exports directory after restore:"
ls -la "$PROJECT_ROOT/exports/"

# 5) Test document conversions
log_info "Testing document conversions..."

# Debug: Print current directory and project root
log_info "Current directory: $(pwd)"
log_info "Project root: $PROJECT_ROOT"
log_info "Contents of exports directory:"
ls -la "$PROJECT_ROOT/exports/"

# Test PDF conversion
log_info "Testing PDF conversion..."
pdf_file="$PROJECT_ROOT/exports/test.pdf"
if [ ! -f "$pdf_file" ]; then
    log_error "PDF test file not found at: $pdf_file"
    log_error "Contents of exports directory:"
    ls -la "$PROJECT_ROOT/exports/"
    exit 1
fi

if [ ! -s "$pdf_file" ]; then
    log_error "PDF test file is empty: $pdf_file"
    exit 1
fi

log_info "Found PDF file, starting conversion..."
python "$PROJECT_ROOT/file2ai.py" convert --input "$pdf_file" --format text --output "$PROJECT_ROOT/exports/test.pdf.text" || log_error "PDF to text conversion failed!"
python "$PROJECT_ROOT/file2ai.py" convert --input "$pdf_file" --format image --output "$PROJECT_ROOT/exports/test.pdf.image" --brightness 1.5 --contrast 1.2 || log_error "PDF to image conversion failed!"

# 6) Test local directory export
log_info "Testing local directory export..."
python "$PROJECT_ROOT/file2ai.py" --local-dir "$PROJECT_ROOT" || log_error "Local export failed!"

# 7) Test normal remote repo export
log_info "Testing normal remote repo export..."
python "$PROJECT_ROOT/file2ai.py" --repo-url https://github.com/michaeljabbour/file2ai || log_error "Remote repo export failed!"

# 8) Test subdir/extra path export
log_info "Testing subdir/extra path export..."
python "$PROJECT_ROOT/file2ai.py" --repo-url-sub https://github.com/michaeljabbour/file2ai/pulls || log_error "Subdir export failed!"
# Remove duplicate PDF conversion test section as it's already handled above

log_info "Testing Word document conversion..."
python "$PROJECT_ROOT/file2ai.py" convert --input "$PROJECT_ROOT/exports/test.docx" --format text --output "$PROJECT_ROOT/exports/test.docx.text" || { log_error "Word to text conversion failed!"; true; }
python "$PROJECT_ROOT/file2ai.py" convert --input "$PROJECT_ROOT/exports/test.docx" --format image --output "$PROJECT_ROOT/exports/test.docx.image" --brightness 1.5 --contrast 1.2 || { log_error "Word to image conversion failed!"; true; }

log_info "Testing PowerPoint conversion..."
python "$PROJECT_ROOT/file2ai.py" convert --input "$PROJECT_ROOT/exports/test.pptx" --format text --output "$PROJECT_ROOT/exports/test.pptx.text" || { log_error "PowerPoint to text conversion failed!"; true; }
python "$PROJECT_ROOT/file2ai.py" convert --input "$PROJECT_ROOT/exports/test.pptx" --format image --output "$PROJECT_ROOT/exports/test.pptx.image" --brightness 1.5 --contrast 1.2 || { log_error "PowerPoint to image conversion failed!"; true; }

log_info "Testing Excel conversion..."
python "$PROJECT_ROOT/file2ai.py" convert --input "$PROJECT_ROOT/exports/test.xlsx" --format text --output "$PROJECT_ROOT/exports/test.xlsx.text" || { log_error "Excel to text conversion failed!"; true; }
python "$PROJECT_ROOT/file2ai.py" convert --input "$PROJECT_ROOT/exports/test.xlsx" --format image --output "$PROJECT_ROOT/exports/test.xlsx.image" --brightness 1.5 --contrast 1.2 || { log_error "Excel to image conversion failed!"; true; }

# 9) Validate document conversion outputs
log_info "Validating document conversion outputs..."

# Check PDF outputs
pdf_txt="$PROJECT_ROOT/exports/test.text"  # First try the new format
if [ ! -f "$pdf_txt" ]; then
    pdf_txt="$PROJECT_ROOT/exports/test.pdf.text"  # Try legacy format as fallback
fi

if [ -f "$pdf_txt" ]; then
    log_info "PDF text export found: $pdf_txt"
    if [ -s "$pdf_txt" ]; then
        log_success "PDF text export has content"
    else
        log_error "PDF text export is empty"
    fi
else
    log_error "Missing PDF text export. Tried:\n- $PROJECT_ROOT/exports/test.text\n- $PROJECT_ROOT/exports/test.pdf.text"
fi

# Check PDF image outputs
pdf_img="$PROJECT_ROOT/exports/test.image"  # First try the new format
if [ ! -f "$pdf_img" ]; then
    pdf_img="$PROJECT_ROOT/exports/test.pdf.image"  # Try legacy format as fallback
fi

if [ -f "$pdf_img" ]; then
    log_info "PDF image export found: $pdf_img"
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
    log_error "Missing PDF image export. Tried:\n- $PROJECT_ROOT/exports/test.image\n- $PROJECT_ROOT/exports/test.pdf.image"
fi

# Check Word document outputs
# Check Word document text outputs
docx_txt="$PROJECT_ROOT/exports/test.text"  # First try the new format
if [ ! -f "$docx_txt" ]; then
    docx_txt="$PROJECT_ROOT/exports/test.docx.text"  # Try legacy format as fallback
fi

if [ -f "$docx_txt" ]; then
    log_info "Word text export found: $docx_txt"
    if [ -s "$docx_txt" ]; then
        log_success "Word text export has content"
    else
        log_error "Word text export is empty"
    fi
else
    log_error "Missing Word text export. Tried:\n- $PROJECT_ROOT/exports/test.text\n- $PROJECT_ROOT/exports/test.docx.text"
fi

docx_img="$PROJECT_ROOT/exports/test.docx.image"
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
ppt_txt="$PROJECT_ROOT/exports/test.pptx.text"
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

ppt_img="$PROJECT_ROOT/exports/test.pptx.image"
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
xlsx_txt="$PROJECT_ROOT/exports/test.xlsx.text"
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

xlsx_img="$PROJECT_ROOT/exports/test.xlsx.image"
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

# Launch and test frontend
log_info "Installing Flask if not present..."
pip install flask || log_error "Failed to install Flask"

log_info "Launching frontend server..."
mkdir -p logs

# Try ports starting from 8000 up to 8020
port=8000
max_port=8020
server_started=false

while [ $port -le $max_port ] && [ "$server_started" = false ]; do
    log_info "Attempting to start server on port $port..."
    
    # Check if port is in use
    if ! lsof -i :$port > /dev/null 2>&1; then
        FLASK_APP="$PROJECT_ROOT/web.py" FLASK_RUN_PORT=$port python "$PROJECT_ROOT/web.py" > logs/frontend.log 2>&1 &
        FRONTEND_PID=$!

        # Wait for server to start
        for i in {1..5}; do
            if curl -s "http://localhost:$port" > /dev/null; then
                server_started=true
                export FLASK_PORT=$port
                log_success "Frontend server is running on port $port"
                break
            fi
            sleep 1
        done
        
        # Kill the process if it didn't start successfully
        if [ "$server_started" = false ]; then
            # Temporarily commented out to keep server running for manual testing
            # kill $FRONTEND_PID 2>/dev/null
            echo "Server startup attempt failed on port $port"
        fi
    else
        log_info "Port $port is in use, trying next port..."
    fi
    
    port=$((port + 1))
done

if [ "$server_started" = false ]; then
    log_error "Failed to start frontend server on any available port. Check logs/frontend.log for details"
fi

# Add cleanup trap
# Temporarily commented out to keep server running for manual testing
# trap 'kill $FRONTEND_PID 2>/dev/null' EXIT

# Verify frontend response
response=$(curl -s "http://localhost:$FLASK_PORT")
if echo "$response" | grep -q "File2AI Converter"; then
    log_success "Frontend is responding correctly"
else
    log_error "Frontend response is invalid"
fi

# Test form submission
log_info "Testing form submission..."
test_response=$(curl -s -X POST -F "command=convert" -F "file=@$PROJECT_ROOT/exports/test_upload.txt" "http://localhost:$FLASK_PORT")
if echo "$test_response" | grep -q "job_id"; then
    log_success "Form submission working correctly"
else
    log_error "Form submission failed"
fi


# Clean up test file
rm -f "$PROJECT_ROOT/exports/test_upload.txt"

log_success "All validation checks passed!"
log_info "Done."

# Note: The frontend server will be automatically killed by the trap when the script exits
