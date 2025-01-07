#!/bin/bash

# Set up colors for logging
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_success() { echo -e "${GREEN}✓ $1${NC}" >&2; }
log_error()   { echo -e "${RED}✗ $1${NC}" >&2; }
log_warn()    { echo -e "${YELLOW}! $1${NC}" >&2; }
# Only show info logs if VERBOSE is set
log_info()    { [ "${VERBOSE:-0}" = "1" ] && echo -e "➜ $1" >&2 || :; }

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
        "__pycache__"
        "*.egg-info"
        ".coverage"
        ".pytest_cache"
    )
    
    # Preserve test files and scripts
    mkdir -p tests/backup
    if [ -d "tests" ]; then
        cp -r tests/create_test_*.py tests/backup/ 2>/dev/null || true
        cp -r tests/backup/*.{pdf,docx,xlsx,pptx,html} tests/backup/ 2>/dev/null || true
    fi
    
    # Clean up each directory
    for dir in "${cleanup_dirs[@]}"; do
        if [ -e "$dir" ]; then
            log_info "Removing $dir..."
            sudo rm -rf "$dir" 2>/dev/null || {
                log_error "Failed to remove $dir even with sudo"
                return 1
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
        sudo chmod 777 "$dir" || {
            log_error "Failed to set permissions on $dir"
            return 1
        }
    done
}

# Create test files
create_test_files() {
    log_info "Creating test files..."
    # First ensure tqdm is available
    python3 -c "import tqdm" 2>/dev/null || {
        log_warn "tqdm not available, falling back to basic progress"
        for script in "${TEST_CREATION_SCRIPTS[@]}"; do
            log_info "Running $(basename "$script")..."
            python3 "$script" || log_warn "Failed to run $script"
        done
        return
    }
    
    # Use tqdm if available
    python3 - <<EOF
from tqdm import tqdm
import subprocess
import sys
import os

scripts = [
    "tests/create_test_pdf.py",
    "tests/create_test_doc.py",
    "tests/create_test_excel.py",
    "tests/create_test_ppt.py",
    "tests/create_test_html.py"
]

with tqdm(scripts, desc="Creating test files", unit="file") as pbar:
    for script in pbar:
        pbar.set_postfix_str(f"Running {os.path.basename(script)}")
        try:
            subprocess.run([sys.executable, script], check=True)
        except subprocess.CalledProcessError:
            print(f"\nWarning: Failed to run {script}", file=sys.stderr)
EOF
    
    # Copy created files to exports directory
    for script in "${TEST_CREATION_SCRIPTS[@]}"; do
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
    sudo rm -rf venv 2>/dev/null
    python3 -m venv venv || {
        log_error "Failed to create virtual environment"
        return 1
    }
    sudo chown -R $USER:$USER venv || {
        log_error "Failed to set venv ownership"
        return 1
    }
    source venv/bin/activate || {
        log_error "Failed to activate virtual environment"
        return 1
    }
    log_success "Virtual environment created and activated"
    
    # First install pip and build tools
    log_info "Upgrading pip and installing build tools..."
    python3 -m pip install --upgrade pip setuptools wheel || {
        log_error "Failed to upgrade pip and install build tools"
        return 1
    }
    
    # Install tqdm for progress bars
    python3 -m pip install tqdm || {
        log_error "Failed to install tqdm"
        return 1
    }
    
    # Now use Python for the main package installation
    python3 - <<EOF
import subprocess
import sys
import importlib.util
from tqdm import tqdm

def run_pip_install(cmd, desc):
    print(f"\n{desc}...")
    process = subprocess.run(cmd, capture_output=True, text=True)
    if process.stdout:
        print(process.stdout)
    if process.returncode != 0:
        print(f"\nError during {desc}:", file=sys.stderr)
        print(process.stderr, file=sys.stderr)
        sys.exit(1)
    elif process.stderr:
        print("\nWarnings during installation:", file=sys.stderr)
        print(process.stderr, file=sys.stderr)
    return process.stdout

def verify_package(package):
    spec = importlib.util.find_spec(package)
    if spec is None:
        raise ImportError(f"Package {package} not found")
    return True

# First install core dependencies
print("\nInstalling core dependencies...")
run_pip_install(
    [sys.executable, "-m", "pip", "install", "-v", "gitpython", "flask", "pytest"],
    "Installing core dependencies"
)

# Then install the package with all extras
print("\nInstalling package in editable mode with all extras...")
run_pip_install(
    [sys.executable, "-m", "pip", "install", "-v", "-e", ".[test,web]"],
    "Installing package with extras"
)

# Verify all critical dependencies
critical_packages = {
    'pytest': 'pytest',           # For testing
    'flask': 'flask',            # For web interface
    'gitpython': 'git',          # For git operations
    'tqdm': 'tqdm',             # For progress bars
    'python_docx': 'docx',       # For Word documents
    'openpyxl': 'openpyxl',     # For Excel files
    'python_pptx': 'pptx',      # For PowerPoint files
    'weasyprint': 'weasyprint', # For HTML/PDF conversion
    'bs4': 'bs4'               # For HTML parsing
}

print("\nVerifying all dependencies...")
missing_packages = []
with tqdm(critical_packages.items(), desc="Checking dependencies") as pbar:
    for package_name, import_name in pbar:
        pbar.set_postfix_str(f"Checking {package_name}")
        try:
            if not verify_package(import_name):
                missing_packages.append(package_name)
        except ImportError:
            missing_packages.append(package_name)

if missing_packages:
    print("\nError: The following packages are missing:", file=sys.stderr)
    for package in missing_packages:
        print(f"  - {package}", file=sys.stderr)
    print("\nTry running: pip install -e .[test,web]", file=sys.stderr)
    sys.exit(1)

print("\nAll dependencies installed successfully!")
EOF
}

# Run pytest with proper configuration
run_tests() {
    log_info "Running pytest..."
    if ! python3 -c "import pytest" 2>/dev/null; then
        log_error "pytest not found. Please install test dependencies first."
        return 1
    fi

    # Run pytest with coverage
    python3 -m pytest test_file2ai.py -v --tb=short --show-capture=no --cov=file2ai --cov-report=term-missing || {
        log_error "Some tests failed!"
        return 1
    }
    log_success "All tests passed!"
}

# Main execution
clean_old_artifacts
create_directories
setup_environment || exit 1
create_test_files
verify_test_files
backup_test_files
run_tests || exit 1
launch_frontend || exit 1
}

# Launch and test frontend
launch_frontend() {
    log_info "Verifying web dependencies..."
    python -c "import flask" || {
        log_error "Flask not found. Make sure to install with pip install -e .[test,web]"
        return 1
    }
    
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
    if echo "$response" | grep -q "File2AI"; then
        log_success "Frontend is responding correctly"
    else
        log_error "Frontend response is invalid"
        return 1
    fi
    
    # Test form submission
    log_info "Testing form submission..."
    # Create a test file for upload
    echo "Test content" > "$PROJECT_ROOT/exports/test_upload.txt"
    
    test_response=$(curl -s -X POST -F "command=convert" -F "file=@$PROJECT_ROOT/exports/test_upload.txt" "http://localhost:$FLASK_PORT")
    if echo "$test_response" | grep -q "job_id"; then
        log_success "Form submission working correctly"
    else
        log_error "Form submission failed"
        return 1
    fi
}

# Show overall progress
show_progress() {
    local current=$1
    local total=$2
    local width=50
    local percentage=$((current * 100 / total))
    local filled=$((width * current / total))
    local empty=$((width - filled))
    printf "\r${GREEN}Overall Progress:${NC} [%${filled}s%${empty}s] %d%%\n" "█" " " "$percentage"
}

# Main execution with progress tracking
main() {
    # Test exports and validation
    test_exports() {
        log_info "Testing local and remote exports..."
        
        # Test local directory export
        python file2ai.py --local-dir test_files --output-file local_export.txt || {
            log_error "Local directory export failed"
            return 1
        }
        
        # Test document conversion
        python file2ai.py convert --input test_files/test.pdf --format text || {
            log_error "Document conversion failed"
            return 1
        }
        
        log_success "Export tests completed"
    }

    # Validate outputs
    validate_outputs() {
        log_info "Validating outputs..."
        
        # Check local export output
        if [ ! -f "exports/local_export.txt" ] && [ ! -f "local_export.txt" ]; then
            log_error "Local export output not found in either exports/ or current directory"
            return 1
        fi
        
        # Check converted files
        if [ ! -f "exports/test.txt" ]; then
            log_error "Converted text file not found"
            return 1
        fi
        
        log_success "Output validation completed"
    }

    local total_steps=10
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

    test_exports
    ((current_step++))
    show_progress $current_step $total_steps

    validate_outputs
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
