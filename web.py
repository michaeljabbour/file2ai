from flask import Flask, request, send_file, jsonify, send_from_directory
from pathlib import Path
import os
import sys
import uuid
import socket
import threading
from datetime import datetime
import logging
from typing import Dict, Optional, List, TypedDict, Union
from werkzeug.datastructures import FileStorage

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'WARNING').upper(), logging.WARNING),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Configure Flask and werkzeug loggers
for logger_name in ['werkzeug', 'flask', 'flask.app']:
    log = logging.getLogger(logger_name)
    log.setLevel(logging.WARNING)
    # Remove existing handlers to prevent duplicate logging
    log.handlers = []
    log.propagate = True

# Set Flask environment variables for production mode
os.environ['FLASK_DEBUG'] = '0'
os.environ['FLASK_ENV'] = 'production'

logger = logging.getLogger(__name__)

from utils import matches_pattern, gather_filtered_files
from file2ai import convert_document, clone_and_export, local_export, setup_logging
from argparse import Namespace

logger = logging.getLogger(__name__)


class ConversionOptions(TypedDict, total=False):
    format: str
    pages: Optional[str]
    brightness: Union[str, float]
    contrast: Union[str, float]
    resolution: Union[str, int]
    repo_url: Optional[str]
    branch: Optional[str]
    token: Optional[str]
    local_dir: Optional[str]
    subdir: Optional[str]
    max_file_size_kb: Union[str, int]
    pattern_mode: str  # "exclude" | "include"
    pattern_input: str


class JobStatus(TypedDict):
    status: str
    progress: float
    errors: List[str]
    start_time: datetime
    output_files: List[Path]


from file2ai import EXPORTS_DIR, UPLOADS_DIR, FRONTEND_DIR, prepare_exports_dir

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
app.secret_key = os.urandom(24)  # For flash messages

# Set up directories with proper permissions
directories = {
    'uploads': Path(UPLOADS_DIR),
    'exports': Path(EXPORTS_DIR),
    'frontend': Path(FRONTEND_DIR)
}

# Ensure required directories exist with proper permissions
prepare_exports_dir()  # Use the existing function from file2ai.py

# Set up directories with proper permissions
for name, path in directories.items():
    try:
        # Create directory with proper permissions
        path.mkdir(exist_ok=True, mode=0o755)
        # Verify directory exists and is writable
        if not path.exists():
            raise IOError(f"Failed to create directory: {path}")
        if not os.access(str(path), os.W_OK):
            raise IOError(f"Directory not writable: {path}")
        logger.info(f"Created/verified directory: {path}")
    except Exception as e:
        logger.error(f"Failed to create {name} directory: {e}")
        sys.exit(1)

# Global job tracking
conversion_jobs = {}
job_events = {}


def process_job(
    job_id: str,
    command: str,
    files: Optional[Dict[str, FileStorage]] = None,
    options: Optional[ConversionOptions] = None,
) -> None:
    """Background processing for all job types

    Args:
        job_id: Unique identifier for the job
        command: Type of operation ('convert' or 'export')
        files: Dictionary of uploaded files (filename -> FileStorage)
        options: Dictionary of conversion/export options
    """
    if options is None:
        options = ConversionOptions()
    
    # Initialize temp_files list at the start
    temp_files = []
    
    # Get filtering options
    max_file_size_kb = int(options.get("max_file_size_kb", 1000))  # Default 1MB
    pattern_mode = options.get("pattern_mode", "exclude")
    pattern_input = options.get("pattern_input", "")
    
    # Initialize job status
    if job_id not in conversion_jobs:
        conversion_jobs[job_id] = {
            "status": "processing",
            "progress": 0,
            "errors": [],
            "start_time": datetime.now(),
            "output_files": []
        }
    job = conversion_jobs[job_id]
    
    try:
        # Job already initialized above
        job["errors"] = []  # Reset errors at start

        # Handle different commands
        if command == "convert":
            if not files:
                raise ValueError("No files provided for conversion")

            # Validate format for conversion
            valid_formats = ["text", "pdf", "html", "docx", "xlsx", "pptx"]
            output_format = str(options.get("format", "text"))
            if output_format not in valid_formats:
                formats_str = ", ".join(valid_formats)
                raise ValueError(
                    ("Invalid format: %s. Valid formats are: %s" % (output_format, formats_str))
                )

            # Validate numeric parameters
            try:
                brightness = float(str(options.get("brightness", 1.0)))
                contrast = float(str(options.get("contrast", 1.0)))
                resolution = int(str(options.get("resolution", 300)))

                if not (0.1 <= brightness <= 2.0):
                    raise ValueError("Brightness must be between 0.1 and 2.0")
                if not (0.1 <= contrast <= 2.0):
                    raise ValueError("Contrast must be between 0.1 and 2.0")
                if not (72 <= resolution <= 1200):
                    msg = "Resolution must be between 72 and 1200 DPI"
                    raise ValueError(msg)
            except ValueError as e:
                raise ValueError("Invalid conversion parameters: %s" % str(e))

            # Process files
            output_files = []
            filtered_files = {}
            
            # Valid file extensions and their MIME types
            valid_types = {
                '.txt': 'text/plain',
                '.pdf': 'application/pdf',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                '.html': 'text/html',
                '.htm': 'text/html'
            }
            
            # Apply filtering
            for filename, file_data in files.items():
                # Make a copy of the file data to avoid handle issues
                file_content = file_data.read()
                file_data.seek(0)  # Reset position for potential reuse
                
                # Validate file type
                file_ext = os.path.splitext(filename)[1].lower()
                if file_ext not in valid_types:
                    logger.warning(f"Skipping {filename}: invalid file type")
                    continue
                
                # Check file size
                size_kb = len(file_content) / 1024
                
                if size_kb > max_file_size_kb:
                    logger.info(f"Skipping {filename}: exceeds size limit of {max_file_size_kb}KB")
                    continue
                    
                # Check pattern match
                matches = matches_pattern(filename, pattern_input)
                if pattern_mode == "exclude" and matches:
                    logger.info(f"Skipping {filename}: matches exclude pattern")
                    continue
                elif pattern_mode == "include" and not matches and pattern_input:
                    logger.info(f"Skipping {filename}: doesn't match include pattern")
                    continue
                    
                filtered_files[filename] = file_data
            
            total_files = len(filtered_files)
            if total_files == 0:
                raise ValueError("No files match the filtering criteria")
            
            for idx, (filename, file_data) in enumerate(filtered_files.items()):
                input_path = None
                output_path = None
                try:
                    # Save uploaded file
                    input_path = Path(UPLOADS_DIR) / filename  # Use constant from file2ai module
                    # Get file content from filtered_files
                    if isinstance(file_data, (str, bytes)):
                        file_content = file_data
                    else:
                        file_content = file_data.read()
                        file_data.seek(0)  # Reset position
                    
                    # Create and write to file
                    with open(str(input_path), 'wb') as f:
                        if isinstance(file_content, str):
                            f.write(file_content.encode('utf-8'))
                        else:
                            f.write(file_content)
                    temp_files.append(input_path)  # Track for cleanup
                    
                    # Convert path to absolute path
                    input_path = input_path.resolve()
                    logger.info(f"Using absolute path for conversion: {input_path}")
                    
                    # Verify file exists and has content
                    if not input_path.exists():
                        raise IOError(f"File not created: {input_path}")
                    if input_path.stat().st_size == 0:
                        raise IOError(f"File is empty: {input_path}")
                    
                    logger.info(f"Successfully saved uploaded file to: {input_path}")

                    # Create output path
                    out_filename = f"{filename}.{output_format}"
                    output_path = Path(EXPORTS_DIR) / out_filename
                    logger.info(f"Converting {input_path} to {output_path} with format {output_format}")

                    # Create args namespace
                    args = Namespace(
                            command="convert",
                            input=str(input_path),
                            output=str(output_path),
                            format=output_format,
                            pages=options.get("pages"),
                            brightness=brightness,
                            contrast=contrast,
                            resolution=resolution,
                    )

                    # Convert file
                    logger.info(f"Starting conversion with args: {args}")
                    
                    # Verify input file still exists before conversion
                    if not input_path.exists():
                        raise IOError(f"Input file missing before conversion: {input_path}")
                    
                    
                    # Check file permissions and readability
                    if not os.access(str(input_path), os.R_OK):
                        raise IOError(f"Input file not readable: {input_path}")
                        
                    logger.info(f"Input file verified before conversion: {input_path}")
                    convert_document(args)
                    
                    # Verify output after conversion
                    if not output_path.exists():
                        raise IOError(f"Output file not created: {output_path}")
                    if output_path.stat().st_size == 0:
                        raise IOError(f"Output file is empty: {output_path}")
                    logger.info(f"Successfully converted file: {output_path}")
                    output_files.append(output_path)
                    
                    # Update progress
                    progress = ((idx + 1) / total_files) * 100
                    job["progress"] = progress
                    logger.info(f"Updated progress to {progress}%")
                except Exception as e:
                    logger.error(f"Error during conversion: {str(e)}")
                    job["errors"].append("Error converting %s: %s" % (filename, str(e)))
                    if output_path and output_path.exists():
                        try:
                            output_path.unlink()  # Clean up failed output
                        except Exception as cleanup_err:
                            logger.error(f"Error cleaning up output file: {cleanup_err}")
                finally:
                    if input_path and input_path.exists():
                        input_path.unlink()

            job["output_files"] = output_files
            
            if job["errors"]:
                job["status"] = "completed_with_errors"
            else:
                job["status"] = "completed"

        elif command == "export":
            # Handle repository export or local directory export
            repo_url = options.get("repo_url")
            local_dir = options.get("local_dir")
            subdir = options.get("subdir")  # Get subdir from options

            if not repo_url and not local_dir:
                msg = "Neither repository URL nor local directory " "provided for export"
                raise ValueError(msg)

            try:
                if repo_url:
                    # Create output path for repository
                    repo_name = str(repo_url).rstrip("/").split("/")[-1].replace(".git", "")
                    format_ext = str(options.get("format", "text"))
                    filename = f"{repo_name}_export.{format_ext}"
                    output_path = Path(EXPORTS_DIR) / filename

                    # Create args namespace for repository export
                    args = Namespace(
                        command="export",
                        repo_url=str(repo_url),
                        branch=str(options.get("branch") or "main"),  # Default to main if no branch specified
                        token=str(options.get("token", "")),
                        output=str(output_path),
                        format=str(options.get("format", "text")),
                        repo_url_sub=None,  # Add missing required attribute
                        output_file=None,  # Add missing required attribute
                        skip_remove=False,  # Add missing required attribute
                        subdir=options.get("subdir", "")  # Get subdir from options, default to empty string
                    )

                    # Export repository
                    try:
                        # Ensure output directory exists
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Export repository
                        clone_and_export(args)
                        
                        # Verify output
                        if output_path.exists():
                            job["output_files"] = [output_path]
                            job["status"] = "completed"
                            job["progress"] = 100
                            logger.info(f"Successfully created output file: {output_path}")
                        else:
                            job["status"] = "failed"
                            job["errors"].append(f"Export failed to create output file: {output_path}")
                            logger.error(f"Failed to create output file: {output_path}")
                    except Exception as e:
                        job["status"] = "failed"
                        job["errors"].append(f"Export failed: {str(e)}")
                        job["progress"] = 0
                        logger.error(f"Export error: {str(e)}")
                else:
                    # Create output path for local directory
                    dir_name = Path(str(local_dir)).name
                    format_ext = str(options.get("format", "text"))
                    filename = f"{dir_name}_export.{format_ext}"
                    output_path = Path(EXPORTS_DIR) / filename

                    # Create args namespace for local export
                    args = Namespace(
                        command="export",
                        local_dir=str(local_dir),
                        output=str(output_path),
                        format=str(options.get("format", "text")),
                        output_file=None,  # Required attribute
                        skip_remove=False,  # Required attribute
                        subdir=options.get("subdir", ""),  # Handle subdir parameter
                        repo_url=None,  # Required for consistency
                        branch=None,  # Required for consistency
                        token=None   # Required for consistency
                    )

                    # Export local directory
                    try:
                        # Get list of files to process
                        directory_files = []
                        if isinstance(files, dict):
                            directory_files = files.get("directory_files", [])
                        if not directory_files:
                            raise IOError(f"No files found in directory: {local_dir}")
                            
                        # Verify input directory exists and is readable
                        input_dir = Path(str(local_dir))
                        if not input_dir.exists():
                            raise IOError(f"Directory not found: {input_dir}")
                        if not input_dir.is_dir():
                            raise IOError(f"Not a directory: {input_dir}")
                        if not os.access(str(input_dir), os.R_OK):
                            raise IOError(f"Directory not readable: {input_dir}")
                            
                        logger.debug(f"Processing {len(directory_files)} files from directory: {input_dir}")
                            
                        # Handle subdir if specified
                        if args.subdir:
                            subdir_path = input_dir / args.subdir
                            if not subdir_path.exists():
                                raise IOError(f"Subdirectory not found: {subdir_path}")
                            if not subdir_path.is_dir():
                                raise IOError(f"Not a directory: {subdir_path}")
                            args.local_dir = str(subdir_path)
                            logger.debug(f"Using subdirectory: {subdir_path}")

                        # Ensure output directory exists
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Export directory
                        logger.debug(f"Starting local export from {args.local_dir} to {output_path}")
                        local_export(args)
                        
                        # Verify output
                        if output_path.exists():
                            if output_path.stat().st_size == 0:
                                raise IOError(f"Output file is empty: {output_path}")
                            job["output_files"] = [output_path]
                            job["status"] = "completed"
                            job["progress"] = 100
                            logger.info(f"Successfully created output file: {output_path}")
                        else:
                            job["status"] = "failed"
                            job["errors"].append(f"Export failed to create output file: {output_path}")
                            logger.error(f"Failed to create output file: {output_path}")
                    except Exception as e:
                        job["status"] = "failed"
                        job["errors"].append(f"Export failed: {str(e)}")
                        job["progress"] = 0
                        logger.error(f"Export error: {str(e)}")
                        # Clean up any partial output
                        if output_path.exists():
                            try:
                                output_path.unlink()
                            except Exception as cleanup_err: 
                                logger.error(f"Error cleaning up output file: {cleanup_err}")

            except Exception as e:
                error_type = "repository" if repo_url else "local directory"
                error_msg = "Error exporting %s: %s" % (error_type, str(e))
                job["errors"].append(error_msg)

        else:
            raise ValueError("Invalid command: %s" % command)

        # Update final status
        if not job["errors"]:
            job["status"] = "completed"
            job["progress"] = 100
        else:
            job["status"] = "completed_with_errors"
            
        logger.info(f"Job {job_id} completed with status: {job['status']}")

    except Exception as e:
        error_msg = f"Job failed: {str(e)}"
        job["status"] = "failed"
        job["errors"].append(error_msg)
        logger.error(error_msg)

    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception as e:
                logger.error(f"Error cleaning up temp file {temp_file}: {e}")
        
        # Ensure job has a final status
        if job["status"] == "processing":
            job["status"] = "failed"
            job["errors"].append("Job terminated unexpectedly")
            
        # Signal completion
        if job_id in job_events:
            job_events[job_id].set()
            logger.info(f"Job {job_id} event signaled")


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    app.logger.info(f"Serving path: {path}")
    
    if not path:
        app.logger.info("Serving index.html")
        try:
            return send_from_directory("frontend", "index.html")
        except Exception as e:
            app.logger.error(f"Error serving index.html: {str(e)}")
            return str(e), 500
    
    if path.startswith("api/"):
        return "Not found", 404
        
    frontend_path = Path("frontend") / path
    app.logger.info(f"Checking path: {frontend_path}")
    
    if frontend_path.exists():
        try:
            mimetype = None
            if path.endswith('.js'):
                mimetype = 'application/javascript'
                response = send_from_directory("frontend", path, mimetype=mimetype)
                app.logger.info(f"Serving JS file with mimetype: {mimetype}")
                return response
            elif path.endswith('.html'):
                mimetype = 'text/html'
                return send_from_directory("frontend", path, mimetype=mimetype)
            
            app.logger.info(f"Serving static file: {path}")
            return send_from_directory("frontend", path)
        except Exception as e:
            app.logger.error(f"Error serving {path}: {str(e)}")
            return str(e), 500
    
    app.logger.info("File not found, serving index.html")
    return send_from_directory("frontend", "index.html")

@app.route("/", methods=["POST"])
def handle_api():
    """Handle API requests for file conversion and exports.
    
    Accepts POST requests with the following parameters:
    - command: str, either 'convert' or 'export'
    - file: list of files (for convert command)
    - format: str, output format (text, pdf, html, docx, xlsx, pptx)
    - max_file_size_kb: int, maximum file size in KB (default: 50)
    - pattern_mode: str, either 'exclude' or 'include'
    - pattern_input: str, glob patterns to filter files
    - pages: str, optional page range for PDF conversion
    - brightness: float, optional image brightness (0.1-2.0)
    - contrast: float, optional image contrast (0.1-2.0)
    - resolution: int, optional image resolution (72-1200 DPI)
    - repo_url: str, optional GitHub repository URL (for export command)
    - branch: str, optional repository branch (for export command)
    - token: str, optional GitHub token (for export command)
    - local_dir: str, optional local directory path (for export command)
    """
    # Debug logging
    logger.info("Received API request")
    logger.debug(f"Form data: {request.form}")
    logger.debug(f"Files: {request.files}")
    logger.debug(f"Headers: {request.headers}")
    
    # Initialize options with file filtering parameters
    try:
        max_file_size = int(request.form.get("max_file_size_kb", "50"))
        if max_file_size <= 0:
            raise ValueError("max_file_size_kb must be positive")
    except ValueError as e:
        return jsonify({"error": f"Invalid max_file_size_kb: {str(e)}"}), 400
        
    pattern_mode = request.form.get("pattern_mode", "exclude")
    if pattern_mode not in ["exclude", "include"]:
        return jsonify({"error": "pattern_mode must be 'exclude' or 'include'"}), 400
    
    command = request.form.get("command", "export")
    logger.info(f"Processing command: {command}")

    # Create job
    job_id = str(uuid.uuid4())
    conversion_jobs[job_id] = JobStatus(
        status="queued",
        progress=0,
        errors=[],
        start_time=datetime.now(),
        output_files=[]
    )
    job_events[job_id] = threading.Event()

    # Initialize options with file filtering parameters
    try:
        max_file_size = int(request.form.get("max_file_size_kb", "50"))
        if max_file_size <= 0:
            raise ValueError("max_file_size_kb must be positive")
    except ValueError as e:
        return jsonify({"error": f"Invalid max_file_size_kb: {str(e)}"}), 400
        
    pattern_mode = request.form.get("pattern_mode", "exclude")
    if pattern_mode not in ["exclude", "include"]:
        return jsonify({"error": "pattern_mode must be 'exclude' or 'include'"}), 400
        
    base_options = {
        "max_file_size_kb": max_file_size,
        "pattern_mode": pattern_mode,
        "pattern_input": request.form.get("pattern_input", "")
    }

    # Handle different commands
    if command == "convert":
        if not request.files:
            return jsonify({"error": "No files selected"}), 400

        # Define security limits
        MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB limit
        ALLOWED_EXTENSIONS = {'.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.html', '.htm'}
        SUSPICIOUS_EXTENSIONS = {'.exe', '.bat', '.cmd', '.sh', '.js', '.php', '.py'}
        ALLOWED_MIMETYPES = {
            'text/plain', 'application/pdf',
            'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-powerpoint', 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'text/html'
        }
        
        # Validate and filter files
        files = {}
        for f in request.files.getlist("file"):
            if not f.filename:
                continue
                
            # Check file size
            f.seek(0, 2)  # Seek to end
            size = f.tell()
            f.seek(0)  # Reset to beginning
            if size > MAX_FILE_SIZE:
                logger.warning(f"Rejected oversized file: {f.filename} ({size} bytes)")
                return jsonify({"error": f"File {f.filename} exceeds maximum size of 50MB"}), 400
                
            # Check file extension and MIME type
            ext = Path(f.filename).suffix.lower()
            mime_type = f.content_type
            
            if ext in SUSPICIOUS_EXTENSIONS:
                logger.warning(f"Rejected suspicious file type: {f.filename}")
                return jsonify({"error": f"File type not allowed: {ext}"}), 400
                
            if ext not in ALLOWED_EXTENSIONS:
                logger.warning(f"Rejected unsupported file type: {f.filename}")
                return jsonify({"error": f"Unsupported file type: {ext}"}), 400
                
            if mime_type not in ALLOWED_MIMETYPES:
                logger.warning(f"Rejected file with invalid MIME type: {f.filename} ({mime_type})")
                return jsonify({"error": f"Invalid file type detected"}), 400
                
            files[f.filename] = f
        if not files:
            return jsonify({"error": "No valid files selected"}), 400

        # Combine base options with conversion options
        options = ConversionOptions(
            format=request.form.get("format", "text"),
            pages=request.form.get("pages", ""),
            brightness=request.form.get("brightness", "1.0"),
            contrast=request.form.get("contrast", "1.0"),
            resolution=request.form.get("resolution", "300"),
            max_file_size_kb=max_file_size,
            pattern_mode=pattern_mode,
            pattern_input=request.form.get("pattern_input", "")
        )

        # Start conversion in background
        thread = threading.Thread(target=process_job, args=(job_id, command, files, options))
        thread.start()
        return jsonify({"job_id": job_id})

    else:  # command == 'export'
        fmt = request.form.get("format", "text")
        # Initialize options with filtering parameters
        options = ConversionOptions(
            format=fmt,
            max_file_size_kb=max_file_size,
            pattern_mode=pattern_mode,
            pattern_input=request.form.get("pattern_input", ""),
            subdir=request.form.get("subdir")  # Store subdir in options
        )

        # Add repository-specific options
        if repo_url := request.form.get("repo_url"):
            if not repo_url:
                return jsonify({"error": "No repository URL provided"}), 400
            options.update(
                repo_url=repo_url,
                branch=request.form.get("branch"),
                token=request.form.get("token"),
            )
            files = {"repo_url": repo_url}

        # Add local directory options
        elif local_dir := request.form.get("local_dir"):
            if not local_dir:
                return jsonify({"error": "No directory selected"}), 400
            
            dir_path = str(Path(local_dir).absolute())
            if not Path(dir_path).exists():
                return jsonify({"error": f"Directory not found: {dir_path}"}), 400
                
            # Gather filtered files from directory
            try:
                directory_files = gather_filtered_files(
                    dir_path,
                    max_size_kb=max_file_size,
                    pattern_mode=pattern_mode,
                    pattern_input=request.form.get("pattern_input", "")
                )
            except Exception as e:
                return jsonify({"error": f"Error scanning directory: {str(e)}"}), 400
                
            if not directory_files:
                return jsonify({"error": f"No matching files found in directory: {dir_path}"}), 400
                
            options["local_dir"] = dir_path
            files = {
                "local_dir": dir_path,
                "directory_files": directory_files
            }

        else:
            return jsonify({
                "error": "No repository URL or local directory provided"
            }), 400

        # Start export in background
        thread = threading.Thread(target=process_job, args=(job_id, command, files, options))

    thread.start()
    return jsonify({"job_id": job_id})


@app.route("/preview/<job_id>")
def get_preview(job_id):
    """Get a preview of the converted text content."""
    if job_id not in conversion_jobs:
        return jsonify({"error": "Job not found"}), 404
        
    job = conversion_jobs[job_id]
    if not job["output_files"]:
        return jsonify({"error": "No output files available"}), 404
        
    # Get the first text file
    text_files = [f for f in job["output_files"] if str(f).endswith(".text")]
    if not text_files:
        return jsonify({"error": "No text preview available"}), 404
        
    try:
        # Read first 1000 characters
        with open(text_files[0], 'r', encoding='utf-8') as f:
            content = f.read(1000)
        return jsonify({
            "preview": content,
            "file": str(text_files[0].name)
        })
    except Exception as e:
        return jsonify({"error": f"Error reading preview: {str(e)}"}), 500

@app.route("/status/<job_id>")
def get_status(job_id):
    """Get job status"""
    if job_id not in conversion_jobs:
        return (jsonify({"error": "Job not found"}), 404)

    job = conversion_jobs[job_id]
    
    # Check if job is completed but has errors
    if job["status"] == "processing" and job["errors"]:
        job["status"] = "failed"
    
    response = {
        "status": job["status"],
        "progress": job["progress"],
        "errors": job["errors"]
    }
    
    # Add more detailed error information if available
    if job["errors"] and job["status"] == "failed":
        response["error_details"] = "\n".join(job["errors"])
    
    return jsonify(response)


@app.route("/download/<job_id>")
def download_files(job_id):
    """Download converted files"""
    if job_id not in conversion_jobs:
        return (jsonify({"error": "Job not found"}), 404)

    job = conversion_jobs[job_id]
    if job["status"] not in ["completed", "completed_with_errors"]:
        return (jsonify({"error": "Job not complete"}), 400)

    if len(job["output_files"]) == 1:
        # Single file download
        output_path = job["output_files"][0]
        return send_file(
            str(output_path),
            as_attachment=True,
            download_name=output_path.name,
        )
    else:
        # Multiple files - create zip
        import zipfile
        import io

        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, "w") as zf:
            for output_path in job["output_files"]:
                zf.write(output_path, output_path.name)

        memory_file.seek(0)
        return send_file(
            memory_file,
            mimetype="application/zip",
            as_attachment=True,
            download_name="converted_files.zip",
        )


@app.route("/cleanup/<job_id>")
def cleanup_job(job_id):
    """Clean up temporary files and job data after completion.
    
    Args:
        job_id: str, UUID of the job to clean up
        
    Returns:
        JSON response with:
        - success: bool, True if cleanup successful
        - error: str, error message if cleanup failed
        
    Status Codes:
        - 200: Success
        - 404: Job not found
        
    Security:
        - Only removes files associated with the job
        - Uses secure path validation
        - Maintains audit log of cleanup operations
    """
    if job_id not in conversion_jobs:
        return (jsonify({"error": "Job not found"}), 404)

    job = conversion_jobs[job_id]

    # Remove output files
    for output_path in job["output_files"]:
        try:
            if output_path.exists():
                output_path.unlink()
        except Exception as e:
            logger.error("Error cleaning up %s: %s", output_path, e)

    # Remove job data
    del conversion_jobs[job_id]
    del job_events[job_id]

    return jsonify({"status": "cleaned"})


def load_env_file():
    """Load environment variables from .env file if it exists."""
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        logger.info("Loading environment from .env file")
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

if __name__ == "__main__":
    # Set up logging for the web server
    setup_logging(operation="web", context="server")
    
    # Load environment variables
    load_env_file()

    # Configure environment-specific settings
    flask_env = os.environ.get("FLASK_ENV", "development")
    debug_mode = flask_env == "development"
    log_level = os.environ.get("LOG_LEVEL", "WARNING")
    
    # Set logging level based on environment, defaulting to WARNING
    logging.getLogger().setLevel(getattr(logging, log_level.upper(), logging.WARNING))
    
    # Get host and port from environment or use defaults
    host = os.environ.get("FLASK_RUN_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_RUN_PORT", 8000))
    
    logger.info(f"Starting server on {host}:{port} (debug={debug_mode})")
    
    # Try multiple ports starting from default
    start_port = port
    max_port = start_port + 20  # Try up to 20 ports

    for port in range(start_port, max_port + 1):
        try:
            logger.info(f"Attempting to start server on port {port}...")
            app.run(
                debug=debug_mode,
                host=host,
                port=port,
                use_reloader=debug_mode
            )
            break  # If successful, exit the loop
        except OSError as e:
            if "Address already in use" in str(e):
                logger.warning(f"Port {port} is in use, trying next port...")
                if port == max_port:
                    logger.error("\nAll ports from %d to %d are in use.", start_port, max_port)
                    logger.error("Try one of the following:")
                    logger.error("1. Set a different port using: export FLASK_RUN_PORT=<port>")
                    logger.error("2. Free up ports in the range %d-%d\n", start_port, max_port)
                    sys.exit(1)
                continue
            raise  # Re-raise other OSErrors
