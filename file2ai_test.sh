#!/bin/bash

# Set up colors for logging
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_success() { echo -e "${GREEN}✓ $1${NC}"; }
log_error()   { echo -e "${RED}✗ $1${NC}"; }
log_warn()    { echo -e "${YELLOW}! $1${NC}"; }
# Only show info logs if VERBOSE is set
log_info()    { [ "${VERBOSE:-0}" = "1" ] && echo -e "➜ $1" || :; }

# Set up project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT" || exit 1

# Test creation scripts
TEST_CREATION_SCRIPTS=(
    "tests/create_test_pdf.py"
    "tests/create_test_doc.py"
    "tests/create_test_excel.py"
    "tests/create_test_ppt.py"
    "tests/create_test_html.py"
)

# Clean up old artifacts
clean_old_artifacts() {
    log_info "Cleaning up old artifacts..."
    rm -rf exports/* test_files/* 2>/dev/null || true
}

# Create necessary directories
create_directories() {
    log_info "Creating necessary directories..."
    for dir in "$PROJECT_ROOT/exports" "$PROJECT_ROOT/test_files"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir" || {
                log_error "Failed to create directory: $dir"
                exit 1
            }
        fi
        chmod 777 "$dir" || log_warn "Failed to set permissions on $dir"
    done
}

# Create test files
create_test_files() {
    log_info "Creating test files..."
    for script in "${TEST_CREATION_SCRIPTS[@]}"; do
        log_info "Running $script..."
        python "$script" || log_warn "Failed to create test file using $script"
        
        # Get the output file name from the script name
        case "$script" in
            *create_test_pdf.py)  file_name="test.pdf" ;;
            *create_test_doc.py)  file_name="test.docx" ;;
            *create_test_excel.py) file_name="test.xlsx" ;;
            *create_test_ppt.py)  file_name="test.pptx" ;;
            *create_test_html.py) file_name="test.html" ;;
            *) file_name="" ;;
        esac
        
        # Copy from test_files to exports if it exists
        if [ -f "$PROJECT_ROOT/test_files/$file_name" ]; then
            cp "$PROJECT_ROOT/test_files/$file_name" "$PROJECT_ROOT/exports/" || log_warn "Failed to copy $file_name to exports"
            log_success "Created and copied $file_name"
        else
            log_warn "Test file $file_name not found in test_files directory"
        fi
    done
}

# Verify test files
verify_test_files() {
    log_info "Verifying test files..."
    for file in test.pdf test.docx test.xlsx test.pptx test.html; do
        if [ ! -f "$PROJECT_ROOT/test_files/$file" ]; then
            log_error "Test file not found: $file"
            continue
        fi
        if [ ! -s "$PROJECT_ROOT/test_files/$file" ]; then
            log_error "Test file is empty: $file"
            continue
        fi
        log_success "Verified $file"
    done
}

# Backup test files
backup_test_files() {
    log_info "Backing up test files..."
    mkdir -p "$PROJECT_ROOT/tests/backup"
    for file in test.pdf test.docx test.xlsx test.pptx test.html; do
        if [ -f "$PROJECT_ROOT/test_files/$file" ]; then
            cp "$PROJECT_ROOT/test_files/$file" "$PROJECT_ROOT/tests/backup/$file" || log_error "Failed to backup $file"
            log_success "Backed up $file"
        fi
    done
}

# Main execution
main() {
    clean_old_artifacts
    create_directories
    create_test_files
    verify_test_files
    backup_test_files
    log_success "All test files created and verified!"
}

# Run main if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main
fi
