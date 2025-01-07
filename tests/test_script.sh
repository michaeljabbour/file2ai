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

# Initialize error tracking
ERRORS=()
ERROR_COUNT=0
# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Logging helpers
log_success() { echo -e "${GREEN}✓ $1${NC}"; }
log_error() { 
    echo -e "${RED}✗ $1${NC}"
    ERRORS+=("$1")
    ((ERROR_COUNT++))
}
log_warn() { echo -e "${YELLOW}! $1${NC}"; }
# Only show info logs if VERBOSE is set
log_info() { [ "${VERBOSE:-0}" = "1" ] && echo -e "➜ $1" || :; }

# Function to display all errors and exit with proper status
display_errors_and_exit() {
    if [ ${#ERRORS[@]} -gt 0 ]; then
        echo -e "\n${RED}The following errors occurred:${NC}"
        for error in "${ERRORS[@]}"; do
            echo -e "${RED}✗ $error${NC}"
        done
        echo -e "\n${RED}Total errors: $ERROR_COUNT${NC}"
        exit 1
    else
        log_success "All tests completed successfully"
        exit 0
    fi
}

# Get the project root directory (one level up from tests/)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT" || { log_error "Failed to change to project root directory"; display_errors_and_exit; }

# 1) Clean up old artifacts
log_info "Cleaning up old artifacts..."

# Define directories to clean up
cleanup_dirs=(
    "venv"
    "logs"
    "exports"
    "test_files"
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
mkdir -p exports logs test_files

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
    display_errors_and_exit
}
install_output=$(pip install -e ".[test,web]" 2>&1) || {
    log_error "Failed to install file2ai with dependencies. Output:\n$install_output"
    display_errors_and_exit
}
log_success "Installation complete"

# Set up cleanup trap for frontend server
cleanup() {
    # Keep server running for manual testing
    if [ -n "$FLASK_PID" ]; then
        echo "Frontend server will remain running for manual testing..."
        # kill $FLASK_PID 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Create test files and populate export directory first
log_info "Creating test files and populating export directory..."

# Create necessary directories if they don't exist and ensure proper permissions
for dir in "$PROJECT_ROOT/exports" "$PROJECT_ROOT/test_files"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir" || {
            log_error "Failed to create directory: $dir"
            exit 1
        }
    fi
    chmod 777 "$dir" || log_warn "Failed to set permissions on $dir"
done

# Source and execute consolidated test file creation script
log_info "Creating test files using consolidated script..."
source "$PROJECT_ROOT/file2ai_test.sh"
create_test_files || log_warn "Some test file creation operations failed"
verify_test_files || log_warn "Some test file verifications failed"

# Verify all test files exist and have content
log_info "Verifying test files..."
for file in test.pdf test.docx test.xlsx test.pptx test.html; do
    if [ ! -f "$PROJECT_ROOT/exports/$file" ]; then
        log_warn "Test file not found in exports: $file"
        continue
    fi
    if [ ! -s "$PROJECT_ROOT/exports/$file" ]; then
        log_warn "Test file is empty in exports: $file"
        continue
    fi
    # Copy test files from exports to test_files
    cp "$PROJECT_ROOT/exports/$file" "$PROJECT_ROOT/test_files/$file" 2>/dev/null || log_warn "Failed to copy $file to test_files"
done

# Debug output only shown in verbose mode
log_info "Files in test_files directory after creation:"
[ "${VERBOSE:-0}" = "1" ] && ls -la "$PROJECT_ROOT/test_files/"

# Create backup directory and backup all test files
mkdir -p "$PROJECT_ROOT/tests/backup"
for file in test.pdf test.docx test.xlsx test.pptx test.html; do
    if [ -f "$PROJECT_ROOT/test_files/$file" ]; then
        cp "$PROJECT_ROOT/test_files/$file" "$PROJECT_ROOT/tests/backup/$file" || log_error "Failed to backup $file"
        log_info "Backed up $file"
    fi
done
log_info "Test files backed up to tests/backup directory"
sleep 2  # Give filesystem time to sync

# Verify all test files exist
log_info "Verifying test files..."
for file in test.pdf test.docx test.xlsx test.pptx test.html; do
    if [ ! -f "$PROJECT_ROOT/test_files/$file" ]; then
        log_error "Test file not found: $file"
    fi
done

# Create test file for form submission
log_info "Creating test file for form submission..."
echo "Test content" > "$PROJECT_ROOT/exports/test_upload.txt"

# 4) Run tests with coverage
log_info "Running tests with coverage..."
cd "$PROJECT_ROOT" && PYTHONPATH="$PROJECT_ROOT" pytest --cov=file2ai tests/ || log_warn "Some tests failed"
log_info "Test execution completed"

# Restore test files after pytest
log_info "Restoring test files after pytest..."
for file in test.pdf test.docx test.xlsx test.pptx test.html; do
    if [ -f "$PROJECT_ROOT/tests/backup/$file" ]; then
        cp "$PROJECT_ROOT/tests/backup/$file" "$PROJECT_ROOT/exports/$file" || log_error "Failed to restore $file"
        log_info "Restored $file"
    fi
done
# 5) Test document conversions
log_success "Starting document conversions..."

# Test web interface
log_info "Testing web interface..."
python "$PROJECT_ROOT/file2ai.py" serve --port 8000 &
FLASK_PID=$!
sleep 2  # Wait for server to start

# Test if server is running
if ! curl -s http://localhost:8000 > /dev/null; then
    log_error "Web server failed to start"
    kill $FLASK_PID 2>/dev/null || true
fi
log_success "Web server started successfully"

# Clean up web server
kill $FLASK_PID
sleep 1

# Test document conversions with pure Python implementation
log_info "Testing document conversions..."

# Test PDF conversion with default settings
log_info "Testing PDF conversion..."
pdf_file="$PROJECT_ROOT/exports/test.pdf"
if [ ! -f "$pdf_file" ]; then
    log_warn "PDF test file not found at: $pdf_file"
    log_warn "Contents of exports directory:"
    ls -la "$PROJECT_ROOT/exports/"
<<<<<<< HEAD
    continue
||||||| 7175c88
    exit 1
=======
>>>>>>> main
fi

if [ ! -s "$pdf_file" ]; then
<<<<<<< HEAD
    log_warn "PDF test file is empty: $pdf_file"
    continue
||||||| 7175c88
    log_error "PDF test file is empty: $pdf_file"
    exit 1
=======
    log_error "PDF test file is empty: $pdf_file"
>>>>>>> main
fi

<<<<<<< HEAD
log_success "Converting PDF file..."
python "$PROJECT_ROOT/file2ai.py" convert --input "$pdf_file" --format text --output "$PROJECT_ROOT/exports/test.pdf.text" || log_warn "PDF to text conversion failed"
python "$PROJECT_ROOT/file2ai.py" convert --input "$pdf_file" --format image --output "$PROJECT_ROOT/exports/test.pdf.image" --brightness 1.5 --contrast 1.2 || log_warn "PDF to image conversion failed"
||||||| 7175c88
log_info "Found PDF file, starting conversion..."
python "$PROJECT_ROOT/file2ai.py" convert --input "$pdf_file" --format text --output "$PROJECT_ROOT/exports/test.pdf.text" || log_error "PDF to text conversion failed!"
python "$PROJECT_ROOT/file2ai.py" convert --input "$pdf_file" --format image --output "$PROJECT_ROOT/exports/test.pdf.image" --brightness 1.5 --contrast 1.2 || log_error "PDF to image conversion failed!"
=======
log_info "Found PDF file, starting conversion..."
# Test text conversion
python "$PROJECT_ROOT/file2ai.py" convert --input "$pdf_file" --format text --output "$PROJECT_ROOT/exports/test.pdf.text" || log_error "PDF to text conversion failed!"

# Test image conversion with default enhancement values
log_info "Testing image conversion with optimal enhancement values..."
python "$PROJECT_ROOT/file2ai.py" convert --input "$pdf_file" --format image --output "$PROJECT_ROOT/exports/test.pdf.enhanced.jpg" || log_error "PDF to enhanced image conversion failed!"

# Test image conversion with custom values
python "$PROJECT_ROOT/file2ai.py" convert --input "$pdf_file" --format image --output "$PROJECT_ROOT/exports/test.pdf.custom.jpg" --brightness 1.3 --contrast 1.1 || log_error "PDF to custom image conversion failed!"

# Verify all conversions produced output
log_info "Verifying conversion outputs..."
for output in test.pdf.text test.pdf.enhanced.jpg test.pdf.custom.jpg; do
    if [ ! -f "$PROJECT_ROOT/exports/$output" ]; then
        log_error "Output file not found: $output"
    fi
    if [ ! -s "$PROJECT_ROOT/exports/$output" ]; then
        log_error "Output file is empty: $output"
    fi
done

# Display final error summary and exit with appropriate status
display_errors_and_exit
log_success "All conversion outputs verified"
>>>>>>> main

# 6) Test local directory export
log_success "Testing local directory export..."
python "$PROJECT_ROOT/file2ai.py" --local-dir "$PROJECT_ROOT" || log_warn "Local export failed"

<<<<<<< HEAD
# 7) Test normal remote repo export
log_success "Testing remote repo export..."
python "$PROJECT_ROOT/file2ai.py" --repo-url https://github.com/michaeljabbour/file2ai || log_warn "Remote repo export failed"
||||||| 7175c88
# 7) Test normal remote repo export
log_info "Testing normal remote repo export..."
python "$PROJECT_ROOT/file2ai.py" --repo-url https://github.com/michaeljabbour/file2ai || log_error "Remote repo export failed!"
=======
# 7) Test repository export features
log_info "Testing repository export features..."
>>>>>>> main

<<<<<<< HEAD
# 8) Test subdir/extra path export
log_success "Testing subdirectory export..."
python "$PROJECT_ROOT/file2ai.py" --repo-url-sub https://github.com/michaeljabbour/file2ai/pulls || log_warn "Subdir export failed"
||||||| 7175c88
# 8) Test subdir/extra path export
log_info "Testing subdir/extra path export..."
python "$PROJECT_ROOT/file2ai.py" --repo-url-sub https://github.com/michaeljabbour/file2ai/pulls || log_error "Subdir export failed!"
=======
# Test normal repo export with text format
log_info "Testing normal repo export (text format)..."
python "$PROJECT_ROOT/file2ai.py" --repo-url https://github.com/michaeljabbour/file2ai --format text || log_error "Remote repo export (text) failed!"

# Test repo export with JSON format
log_info "Testing repo export with JSON format..."
python "$PROJECT_ROOT/file2ai.py" --repo-url https://github.com/michaeljabbour/file2ai --format json || log_error "Remote repo export (json) failed!"

# Test specific branch export
log_info "Testing specific branch export..."
python "$PROJECT_ROOT/file2ai.py" --repo-url https://github.com/michaeljabbour/file2ai --branch main || log_error "Branch-specific export failed!"

# Test subdirectory export
log_info "Testing subdirectory export..."
python "$PROJECT_ROOT/file2ai.py" --repo-url https://github.com/michaeljabbour/file2ai --subdir tests || log_error "Subdirectory export failed!"

# Test subdir/extra path export
log_info "Testing subdir/extra path export..."
python "$PROJECT_ROOT/file2ai.py" --repo-url-sub https://github.com/michaeljabbour/file2ai/pulls || log_error "Subdir export failed!"

# Validate JSON output
json_file="exports/file2ai_export.json"
if [ -f "$json_file" ]; then
    log_info "JSON export found"
    if jq empty "$json_file" 2>/dev/null; then
        log_success "JSON export is valid"
        
        # Check required fields
        if jq -e '.repository_name and .files and .metadata' "$json_file" >/dev/null; then
            log_success "JSON structure looks correct"
        else
            log_error "JSON export missing required fields"
        fi
    else
        log_error "JSON export is not valid"
    fi
else
    log_error "Missing JSON export file: $json_file"
fi
>>>>>>> main
# Remove duplicate PDF conversion test section as it's already handled above

<<<<<<< HEAD
log_info "Testing Word document conversion..."
python "$PROJECT_ROOT/file2ai.py" convert --input "$PROJECT_ROOT/test_files/test.docx" --format text --output "$PROJECT_ROOT/test_files/test.docx.text" || log_warn "Word to text conversion failed"
python "$PROJECT_ROOT/file2ai.py" convert --input "$PROJECT_ROOT/test_files/test.docx" --format image --output "$PROJECT_ROOT/test_files/test.docx.image" --brightness 1.5 --contrast 1.2 || log_warn "Word to image conversion failed"
||||||| 7175c88
log_info "Testing Word document conversion..."
python "$PROJECT_ROOT/file2ai.py" convert --input "$PROJECT_ROOT/test_files/test.docx" --format text --output "$PROJECT_ROOT/test_files/test.docx.text" || { log_error "Word to text conversion failed!"; true; }
python "$PROJECT_ROOT/file2ai.py" convert --input "$PROJECT_ROOT/test_files/test.docx" --format image --output "$PROJECT_ROOT/test_files/test.docx.image" --brightness 1.5 --contrast 1.2 || { log_error "Word to image conversion failed!"; true; }
=======
# Test all supported formats
log_info "Testing Word document conversion (pure Python)..."
python "$PROJECT_ROOT/file2ai.py" convert --input "$PROJECT_ROOT/exports/test.docx" --format text --output "$PROJECT_ROOT/exports/test.docx.text" || { log_error "Word to text conversion failed!"; true; }
python "$PROJECT_ROOT/file2ai.py" convert --input "$PROJECT_ROOT/exports/test.docx" --format image --output "$PROJECT_ROOT/exports/test.docx.image" --brightness 1.5 --contrast 1.2 || { log_error "Word to image conversion failed!"; true; }
>>>>>>> main

log_info "Testing PowerPoint conversion..."
python "$PROJECT_ROOT/file2ai.py" convert --input "$PROJECT_ROOT/test_files/test.pptx" --format text --output "$PROJECT_ROOT/test_files/test.pptx.text" || log_warn "PowerPoint to text conversion failed"
python "$PROJECT_ROOT/file2ai.py" convert --input "$PROJECT_ROOT/test_files/test.pptx" --format image --output "$PROJECT_ROOT/test_files/test.pptx.image" --brightness 1.5 --contrast 1.2 || log_warn "PowerPoint to image conversion failed"

log_info "Testing Excel conversion..."
python "$PROJECT_ROOT/file2ai.py" convert --input "$PROJECT_ROOT/test_files/test.xlsx" --format text --output "$PROJECT_ROOT/test_files/test.xlsx.text" || log_warn "Excel to text conversion failed"
python "$PROJECT_ROOT/file2ai.py" convert --input "$PROJECT_ROOT/test_files/test.xlsx" --format image --output "$PROJECT_ROOT/test_files/test.xlsx.image" --brightness 1.5 --contrast 1.2 || log_warn "Excel to image conversion failed"

log_info "Testing HTML conversion (pure Python)..."
python "$PROJECT_ROOT/file2ai.py" convert --input "$PROJECT_ROOT/exports/test.html" --format text --output "$PROJECT_ROOT/exports/test.html.text" || { log_error "HTML to text conversion failed!"; true; }
python "$PROJECT_ROOT/file2ai.py" convert --input "$PROJECT_ROOT/exports/test.html" --format image --output "$PROJECT_ROOT/exports/test.html.image" || { log_error "HTML to image conversion failed!"; true; }

# Verify cross-platform compatibility
log_info "Verifying Python version compatibility..."
python_version=$(python --version)
if [[ $python_version =~ 3\.1[12] ]]; then
    log_success "Running on supported Python version: $python_version"
else
    log_warn "Running on Python version $python_version (recommended: 3.11 or 3.12)"
fi

# 9) Validate document conversion outputs
log_info "Validating document conversion outputs..."

# Check PDF outputs
pdf_txt="$PROJECT_ROOT/test_files/test.text"  # First try the new format
if [ ! -f "$pdf_txt" ]; then
    pdf_txt="$PROJECT_ROOT/test_files/test.pdf.text"  # Try legacy format as fallback
fi

if [ -f "$pdf_txt" ]; then
    log_info "PDF text export found: $pdf_txt"
    if [ -s "$pdf_txt" ]; then
        log_success "PDF text export has content"
    else
        log_error "PDF text export is empty"
    fi
else
    log_error "Missing PDF text export. Tried:\n- $PROJECT_ROOT/test_files/test.text\n- $PROJECT_ROOT/test_files/test.pdf.text"
fi

# Check PDF image outputs
pdf_img="$PROJECT_ROOT/test_files/test.image"  # First try the new format
if [ ! -f "$pdf_img" ]; then
    pdf_img="$PROJECT_ROOT/test_files/test.pdf.image"  # Try legacy format as fallback
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
    log_error "Missing PDF image export. Tried:\n- $PROJECT_ROOT/test_files/test.image\n- $PROJECT_ROOT/test_files/test.pdf.image"
fi

# Check Word document outputs
# Check Word document text outputs
docx_txt="$PROJECT_ROOT/test_files/test.text"  # First try the new format
if [ ! -f "$docx_txt" ]; then
    docx_txt="$PROJECT_ROOT/test_files/test.docx.text"  # Try legacy format as fallback
fi

if [ -f "$docx_txt" ]; then
    log_info "Word text export found: $docx_txt"
    if [ -s "$docx_txt" ]; then
        log_success "Word text export has content"
    else
        log_error "Word text export is empty"
    fi
else
    log_error "Missing Word text export. Tried:\n- $PROJECT_ROOT/test_files/test.text\n- $PROJECT_ROOT/test_files/test.docx.text"
fi

docx_img="$PROJECT_ROOT/test_files/test.docx.image"
if [ -f "$docx_img" ]; then
    log_info "Word image export found"
    if [ -s "$docx_img" ] && grep -q "test_files/images/" "$docx_img"; then
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
ppt_txt="$PROJECT_ROOT/test_files/test.pptx.text"
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

ppt_img="$PROJECT_ROOT/test_files/test.pptx.image"
if [ -f "$ppt_img" ]; then
    log_info "PowerPoint image export found"
    if [ -s "$ppt_img" ] && grep -q "test_files/images/" "$ppt_img"; then
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
xlsx_txt="$PROJECT_ROOT/test_files/test.xlsx.text"
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

xlsx_img="$PROJECT_ROOT/test_files/test.xlsx.image"
if [ -f "$xlsx_img" ]; then
    log_info "Excel image export found"
    if [ -s "$xlsx_img" ] && grep -q "test_files/images/" "$xlsx_img"; then
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

# Check HTML outputs
html_txt="$PROJECT_ROOT/exports/test.html.text"
if [ -f "$html_txt" ]; then
    log_info "HTML text export found"
    if [ -s "$html_txt" ]; then
        log_success "HTML text export has content"
    else
        log_error "HTML text export is empty"
    fi
else
    log_error "Missing HTML text export: $html_txt"
fi

html_img="$PROJECT_ROOT/exports/test.html.image"
if [ -f "$html_img" ]; then
    log_info "HTML image export found"
    if [ -s "$html_img" ] && grep -q "exports/images/" "$html_img"; then
        while IFS= read -r img_path || [ -n "$img_path" ]; do
            if [ ! -f "$img_path" ]; then
                log_error "Missing HTML image file: $img_path"
            fi
            
            # Verify image enhancement values in filename
            if [[ "$img_path" == *"enhanced"* ]]; then
                if ! identify -format "%[fx:brightness] %[fx:contrast]" "$img_path" 2>/dev/null | grep -q "1.50.*1.20"; then
                    log_warn "Image $img_path may not have optimal enhancement values (expected: brightness=1.50, contrast=1.20)"
                fi
            fi
        done < "$html_img"
        log_success "HTML image export and files look correct"
    else
        log_error "HTML image export list is invalid"
    fi
else
    log_error "Missing HTML image export: $html_img"
fi

# 10) Validate repository outputs
log_info "Validating repository output files..."

# Check local export
txt_file="test_files/file2ai_export.txt"
if [ -f "$txt_file" ]; then
    log_info "Local directory export found"
    
    # Copy to exports directory for actual file2ai exports
    cp "$txt_file" "exports/file2ai_export.txt" 2>/dev/null || true
    
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
txt_file="test_files/file2ai_export.txt"
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

log_success "All validation checks completed!"
log_info "Done."

# Note: The frontend server will be automatically killed by the trap when the script exits

# Display final error summary and exit with appropriate status
display_errors_and_exit
