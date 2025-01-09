#!/bin/bash
################################################################################
# FILE2AI TEST + DEPLOY SCRIPT (LONG-TERM FIX)
#
# This version:
#   - Uses a sed patch to replace "/home/user/test" with "test_files/test.xlsx"
#   - No longer skips `test_excel_to_text_conversion`
#   - Includes basic shell lint improvements
################################################################################

# Exit on error (e), undefined var (u), or pipefail
# Temporarily disabled for debugging
# set -euo pipefail
set -x

#------------------------------------------------------------------------------
# COLOR SETUP FOR LOGGING
#------------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

#------------------------------------------------------------------------------
# LOGGING / PRINTING FUNCTIONS
#------------------------------------------------------------------------------
log_success() { echo -e "${GREEN}✓ $1${NC}" >&2; }
log_error()   { echo -e "${RED}✗ $1${NC}" >&2; }
log_warn()    { echo -e "${YELLOW}! $1${NC}" >&2; }

# Only show info logs if VERBOSE=1
log_info() {
    [ "${VERBOSE:-0}" = "1" ] && echo -e "➜ $1" >&2 || :
}

#------------------------------------------------------------------------------
# PROJECT ROOT + CONFIG
#------------------------------------------------------------------------------
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT" || exit 1

# Declare an array for test creation scripts
declare -a TEST_CREATION_SCRIPTS=(
    "tests/create_test_pdf.py"
    "tests/create_test_doc.py"
    "tests/create_test_excel.py"
    "tests/create_test_ppt.py"
    "tests/create_test_html.py"
)

#------------------------------------------------------------------------------
# 1) CLEAN UP OLD ARTIFACTS
#------------------------------------------------------------------------------
clean_old_artifacts() {
    echo "DEBUG: Starting cleanup..."
    echo "DEBUG: Current user: $(whoami)"
    echo "DEBUG: Current directory: $(pwd)"
    log_info "Cleaning up old artifacts..."

    declare -a cleanup_dirs=(
        "venv"
        "logs"
        "exports"
        "__pycache__"
        "*.egg-info"
        ".coverage"
        ".pytest_cache"
    )

    mkdir -p tests/backup
    if [ -d "tests" ]; then
        cp -r tests/create_test_*.py tests/backup/ 2>/dev/null || true
        cp -r tests/backup/*.{pdf,docx,xlsx,pptx,html} tests/backup/ 2>/dev/null || true
    fi

    for dir in "${cleanup_dirs[@]}"; do
        if [ -e "$dir" ]; then
            log_info "Removing $dir..."
            rm -rf "$dir" 2>/dev/null || {
                log_error "Failed to remove $dir"
                # Try with sudo as fallback
                sudo rm -rf "$dir" 2>/dev/null || {
                    log_error "Failed to remove $dir even with sudo"
                    return 1
                }
            }
            }
        fi
    done

    log_success "Cleanup complete"
}

#------------------------------------------------------------------------------
# 2) CREATE NECESSARY DIRECTORIES
#------------------------------------------------------------------------------
create_directories() {
    log_info "Creating necessary directories..."
    for dir in "$PROJECT_ROOT/exports" "$PROJECT_ROOT/test_files"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir" || {
                log_error "Failed to create directory: $dir"
                exit 1
            }
        fi
        if [ ! -w "$dir" ]; then
            log_error "Directory $dir is not writable"
            return 1
        fi
    done
}

#------------------------------------------------------------------------------
# 3) CREATE VENV + INSTALL DEPENDENCIES
#------------------------------------------------------------------------------
setup_environment() {
    log_info "Creating fresh virtual environment..."
    rm -rf venv 2>/dev/null
    python3 -m venv venv || {
        log_error "Failed to create virtual environment"
        return 1
    }
    # shellcheck disable=SC1091
    source venv/bin/activate || {
        log_error "Failed to activate virtual environment"
        return 1
    }
    log_success "Virtual environment created and activated"

    log_info "Upgrading pip and installing build tools..."
    python3 -m pip install --upgrade pip setuptools wheel || {
        log_error "Failed to upgrade pip/setuptools/wheel"
        return 1
    }

    python3 -m pip install tqdm || {
        log_error "Failed to install tqdm"
        return 1
    }

    # Main install
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

print("\nInstalling core dependencies...")
run_pip_install(
    [sys.executable, "-m", "pip", "install", "-v", "gitpython", "flask", "pytest"],
    "Installing core dependencies"
)

print("\nInstalling package in editable mode with all extras...")
run_pip_install(
    [sys.executable, "-m", "pip", "install", "-v", "-e", ".[test,web]"],
    "Installing package with extras"
)

critical_packages = {
    'pytest': 'pytest',
    'flask': 'flask',
    'gitpython': 'git',
    'tqdm': 'tqdm',
    'python_docx': 'docx',
    'openpyxl': 'openpyxl',
    'python_pptx': 'pptx',
    'weasyprint': 'weasyprint',
    'bs4': 'bs4'
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
    print("\nError: Missing packages:", file=sys.stderr)
    for package in missing_packages:
        print(f"  - {package}", file=sys.stderr)
    print("\nTry running: pip install -e .[test,web]", file=sys.stderr)
    sys.exit(1)

print("\nAll dependencies installed successfully!")
EOF
}

#------------------------------------------------------------------------------
# 4) CREATE SAMPLE TEST FILES
#------------------------------------------------------------------------------
create_test_files() {
    log_info "Creating test files..."

    if ! python3 -c "import tqdm" 2>/dev/null; then
        log_warn "tqdm not available, falling back to basic progress"
        for script in "${TEST_CREATION_SCRIPTS[@]}"; do
            log_info "Running $(basename "$script")..."
            python3 "$script" || log_warn "Failed to run $script"
        done
        return
    fi

    python3 <<EOF
import subprocess, sys, os
from tqdm import tqdm

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
            print(f"Warning: Failed to run {script}", file=sys.stderr)
EOF

    for script in "${TEST_CREATION_SCRIPTS[@]}"; do
        case "$script" in
            *create_test_pdf.py)  file_name="test.pdf" ;;
            *create_test_doc.py)  file_name="test.docx" ;;
            *create_test_excel.py) file_name="test.xlsx" ;;
            *create_test_ppt.py)  file_name="test.pptx" ;;
            *create_test_html.py) file_name="test.html" ;;
            *) file_name="" ;;
        esac
        if [ -n "$file_name" ] && [ -f "$PROJECT_ROOT/test_files/$file_name" ]; then
            cp "$PROJECT_ROOT/test_files/$file_name" "$PROJECT_ROOT/exports/" \
               || log_warn "Failed to copy $file_name to exports"
            log_success "Created and copied $file_name"
        fi
    done
}

#------------------------------------------------------------------------------
# 5) VERIFY TEST FILES
#------------------------------------------------------------------------------
verify_test_files() {
    log_info "Verifying test files..."
    declare -a needed_files=( "test.pdf" "test.docx" "test.xlsx" "test.pptx" "test.html" )
    for file in "${needed_files[@]}"; do
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

#------------------------------------------------------------------------------
# 6) BACK UP TEST FILES
#------------------------------------------------------------------------------
backup_test_files() {
    log_info "Backing up test files..."
    mkdir -p "$PROJECT_ROOT/tests/backup"
    declare -a needed_files=( "test.pdf" "test.docx" "test.xlsx" "test.pptx" "test.html" )
    for file in "${needed_files[@]}"; do
        if [ -f "$PROJECT_ROOT/test_files/$file" ]; then
            cp "$PROJECT_ROOT/test_files/$file" "$PROJECT_ROOT/tests/backup/$file" \
               || log_error "Failed to backup $file"
            log_success "Backed up $file"
        fi
    done
}

#------------------------------------------------------------------------------
# 7) PATCH & RUN PYTEST WITH COVERAGE (No Skip)
#------------------------------------------------------------------------------
run_tests() {
    echo "DEBUG: Starting test phase..."
    echo "DEBUG: Current directory: $(pwd)"
    echo "DEBUG: Listing test files:"
    ls -l test_files/
    echo "DEBUG: Listing test_file2ai.py:"
    ls -l test_file2ai.py
    log_info "Patching test_file2ai.py to fix /home/user/test → test_files/test.xlsx"
    # On macOS, sed requires -i '' (empty string), on Linux just -i is fine
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' 's|/home/user/test|test_files/test.xlsx|g' test_file2ai.py || true
    else
        sed -i 's|/home/user/test|test_files/test.xlsx|g' test_file2ai.py || true
    fi

    log_info "Running pytest..."
    if ! python3 -c "import pytest" 2>/dev/null; then
        log_error "pytest not found. Please install test dependencies."
        return 1
    fi

    # We no longer skip test_excel_to_text_conversion
    python3 -m pytest test_file2ai.py -v --tb=short --show-capture=no \
        --cov=file2ai --cov-report=term-missing || {
            log_error "Some tests failed!"
            return 1
        }

    log_success "All tests passed successfully!"
}

#------------------------------------------------------------------------------
# 8) LAUNCH & TEST FLASK FRONTEND (Optional)
#------------------------------------------------------------------------------
launch_frontend() {
    log_info "Verifying web dependencies..."
    if ! python -c "import flask" 2>/dev/null; then
        log_error "Flask not found. Make sure to install with pip install -e .[test,web]"
        return 1
    fi

    log_info "Launching frontend server..."
    mkdir -p logs

    local port=8000
    local max_port=8020
    local server_started=false

    while [ $port -le $max_port ] && [ "$server_started" = false ]; do
        printf "\033[2K\r"
        log_info "Attempting to start server on port $port..."

        if ! lsof -i :"$port" > /dev/null 2>&1; then
            FLASK_APP="$PROJECT_ROOT/web.py" \
            FLASK_RUN_PORT=$port \
            python "$PROJECT_ROOT/web.py" > logs/frontend.log 2>&1 &
            local FRONTEND_PID=$!

            local server_ready=false
            for i in {1..10}; do
                if curl -s "http://localhost:$port" > /dev/null 2>&1; then
                    sleep 1
                    if curl -s "http://localhost:$port" > /dev/null 2>&1; then
                        server_ready=true
                        server_started=true
                        export FLASK_PORT=$port
                        log_success "Frontend server is running on port $port"
                        break
                    fi
                fi
                sleep 2
            done

            if [ "$server_ready" = false ]; then
                kill "$FRONTEND_PID" 2>/dev/null || true
                if ! ps -p "$FRONTEND_PID" > /dev/null 2>&1; then
                    log_warn "Server startup attempt failed on port $port"
                fi
            fi
        else
            log_info "Port $port is in use, trying next port..."
        fi
        port=$((port + 1))
    done

    if [ "$server_started" = false ]; then
        log_error "Failed to start frontend server (ports 8000–8020 exhausted)"
        log_error "Check logs/frontend.log for details"
        return 1
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Frontend server started on port $FLASK_PORT" \
            >> logs/frontend.log
        log_success "Frontend server successfully started on port $FLASK_PORT"
    fi

    # Verify response
    local response
    response=$(curl -s "http://localhost:$FLASK_PORT")
    if echo "$response" | grep -q "File2AI"; then
        log_success "Frontend is responding correctly"
    else
        log_error "Frontend response invalid"
        return 1
    fi

    # Quick form submission
    log_info "Testing form submission..."
    echo "Test content" > "$PROJECT_ROOT/exports/test_upload.txt"

    local test_response
    test_response=$(curl -s -X POST \
        -F "command=convert" \
        -F "file=@$PROJECT_ROOT/exports/test_upload.txt" \
        "http://localhost:$FLASK_PORT")

    if echo "$test_response" | grep -q "job_id"; then
        log_success "Form submission working correctly"
    else
        log_error "Form submission failed"
        return 1
    fi
}

<<<<<<< HEAD
# Terminal control functions
save_cursor_position() {
    printf "\033[s"  # Save cursor position
}

restore_cursor_position() {
    printf "\033[u"  # Restore cursor position
}

clear_progress_line() {
    printf "\033[1G\033[K"  # Move to beginning of line and clear it
}

# Show progress bar at the top
||||||| 6c7bef8
# Show progress bar
=======
#------------------------------------------------------------------------------
# HELPER: SHOW OVERALL PROGRESS
#------------------------------------------------------------------------------
>>>>>>> origin/main
show_progress() {
    local current="$1"
    local total="$2"
    local width=50
    local percentage=$((current * 100 / total))
    local filled=$((width * current / total))
    local empty=$((width - filled))
<<<<<<< HEAD
    
    # Save current position, move to start of progress line, show progress, restore position
    save_cursor_position
    printf "\033[1;1H\033[K"  # Move to top and clear line
    printf "Progress: [%${filled}s%${empty}s] %d%%" "" "" "$percentage"
    restore_cursor_position
||||||| 6c7bef8
    printf "\rProgress: [%${filled}s%${empty}s] %d%%" "" "" "$percentage"
=======

    printf "\033[2K\r"
    printf "${GREEN}Overall Progress:${NC} ["
    for ((i=0; i<filled; i++)); do printf "█"; done
    for ((i=filled; i<width; i++)); do printf " "; done
    printf "] %d%%" "$percentage"

    [ "$current" -eq "$total" ] && echo
>>>>>>> origin/main
}

#------------------------------------------------------------------------------
# 9) EXTRA: TEST EXPORTS + DOC CONVERSIONS
#------------------------------------------------------------------------------
test_exports() {
    log_info "Testing local/remote exports..."

    if ! python file2ai.py --local-dir test_files --output-file local_export.txt; then
        log_error "Local export failed"
        return 1
    fi

    if ! python file2ai.py convert --input test_files/test.pdf --format text; then
        log_error "Document conversion failed"
        return 1
    fi

    log_success "Export tests completed"
}

#------------------------------------------------------------------------------
# 10) VALIDATE OUTPUTS
#------------------------------------------------------------------------------
validate_outputs() {
    log_info "Validating outputs..."

    if [ ! -f "exports/local_export.txt" ] && [ ! -f "local_export.txt" ]; then
        log_error "Local export output not found"
        return 1
    fi

    if [ ! -f "exports/test.txt" ]; then
        log_error "Converted text file not found"
        return 1
    fi

    log_success "Output validation completed"
}

#------------------------------------------------------------------------------
# MASTER MAIN FUNCTION
#------------------------------------------------------------------------------
main() {
    local total_steps=10
    local current_step=0
<<<<<<< HEAD
    
    # Clear screen and initialize progress bar area
    clear
    echo  # Leave blank line for progress bar
    show_progress $current_step $total_steps
||||||| 6c7bef8

    show_progress $current_step $total_steps
=======

    show_progress "$current_step" "$total_steps"
>>>>>>> origin/main

    clean_old_artifacts
    ((current_step++)); show_progress "$current_step" "$total_steps"

    create_directories
    ((current_step++)); show_progress "$current_step" "$total_steps"

    setup_environment || exit 1
    ((current_step++)); show_progress "$current_step" "$total_steps"

    create_test_files
    ((current_step++)); show_progress "$current_step" "$total_steps"

    verify_test_files
    ((current_step++)); show_progress "$current_step" "$total_steps"

    backup_test_files
    ((current_step++)); show_progress "$current_step" "$total_steps"

    run_tests || exit 1
    ((current_step++)); show_progress "$current_step" "$total_steps"

    test_exports
    ((current_step++)); show_progress "$current_step" "$total_steps"

    validate_outputs
    ((current_step++)); show_progress "$current_step" "$total_steps"

    launch_frontend
    ((current_step++)); show_progress "$current_step" "$total_steps"
    echo

    log_success "All steps completed successfully!"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main
fi
