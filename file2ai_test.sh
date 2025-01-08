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
            sudo rm -rf "$dir" 2>/dev/null || {
                log_warn "Failed to remove $dir - it may be in use or require different permissions"
                log_warn "You may need to remove it manually: sudo rm -rf $dir"
            }
        fi
    done
    
    log_success "Cleanup complete"
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

# Set up virtual environment and install dependencies
setup_environment() {
    log_info "Creating fresh virtual environment..."
    python3 -m venv venv || {
        log_error "Failed to create virtual environment"
        return 1
    }
    source venv/bin/activate || {
        log_error "Failed to activate virtual environment"
        return 1
    }
    log_success "Virtual environment created and activated"
    
    log_info "Installing file2ai in editable mode with all dependencies..."
    pip install --upgrade pip || log_error "Failed to upgrade pip"
    pip install -e ".[test,web]" || {
        log_error "Failed to install file2ai with dependencies"
        return 1
    }
    log_success "Installation complete"
}

# Run pytest with proper configuration
run_tests() {
    log_info "Running pytest..."
    if ! command -v pytest &> /dev/null; then
        log_error "pytest not found. Please install test dependencies first."
        return 1
    fi

    # Run pytest with progress bar and minimal output
    python -m pytest tests/test_file2ai.py -v --tb=short --show-capture=no || {
        log_error "Some tests failed!"
        return 1
    }
    log_success "All tests passed!"
}

# Launch and test frontend
launch_frontend() {
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
            
            if [ "$server_started" = false ]; then
                kill $FRONTEND_PID 2>/dev/null
                log_warn "Server startup attempt failed on port $port"
            fi
        else
            log_info "Port $port is in use, trying next port..."
        fi
        
        port=$((port + 1))
    done
    
    if [ "$server_started" = false ]; then
        log_error "Failed to start frontend server on any available port. Check logs/frontend.log for details"
        return 1
    fi
    
    # Verify frontend response
    response=$(curl -s "http://localhost:$FLASK_PORT")
    if echo "$response" | grep -q "File2AI Converter"; then
        log_success "Frontend is responding correctly"
    else
        log_error "Frontend response is invalid"
        return 1
    fi
    
    # Test form submission
    log_info "Testing form submission..."
    test_response=$(curl -s -X POST -F "command=convert" -F "file=@$PROJECT_ROOT/exports/test_upload.txt" "http://localhost:$FLASK_PORT")
    if echo "$test_response" | grep -q "job_id"; then
        log_success "Form submission working correctly"
    else
        log_error "Form submission failed"
        return 1
    fi
}

# Show progress bar
show_progress() {
    local current=$1
    local total=$2
    local width=50
    local percentage=$((current * 100 / total))
    local filled=$((width * current / total))
    local empty=$((width - filled))
    printf "\rProgress: [%${filled}s%${empty}s] %d%%" "" "" "$percentage"
}

# Main execution with progress tracking
main() {
    local total_steps=8
    local current_step=0

    show_progress $current_step $total_steps

    clean_old_artifacts
    ((current_step++))
    show_progress $current_step $total_steps

    create_directories
    ((current_step++))
    show_progress $current_step $total_steps

    setup_environment
    ((current_step++))
    show_progress $current_step $total_steps

    create_test_files
    ((current_step++))
    show_progress $current_step $total_steps

    verify_test_files
    ((current_step++))
    show_progress $current_step $total_steps

    backup_test_files
    ((current_step++))
    show_progress $current_step $total_steps

    run_tests
    ((current_step++))
    show_progress $current_step $total_steps

    launch_frontend
    ((current_step++))
    show_progress $current_step $total_steps
    echo # New line after progress bar

    log_success "All steps completed successfully!"
}

# Run main if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main
fi
