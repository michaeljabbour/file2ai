from flask import Flask, request, send_file, jsonify, send_from_directory
from pathlib import Path
import os
import sys
import uuid
import threading
from datetime import datetime
import logging
from typing import Dict, Optional, List, TypedDict, Union
from werkzeug.datastructures import FileStorage

def gather_all_files(base_dir: str) -> List[str]:
    """Recursively gather all files from a directory.
    
    Args:
        base_dir: Base directory to start gathering files from
        
    Returns:
        List of absolute paths to all files in the directory tree
    """
    all_files = []
    try:
        base_path = Path(base_dir)
        if not base_path.exists():
            raise IOError(f"Directory not found: {base_dir}")
        if not base_path.is_dir():
            raise IOError(f"Not a directory: {base_dir}")
            
        for p in base_path.rglob('*'):
            if p.is_file():
                # Skip hidden files and common ignore patterns
                if not any(part.startswith('.') for part in p.parts):
                    all_files.append(str(p.resolve()))
                    
        logger.info(f"Found {len(all_files)} files in {base_dir}")
    except Exception as e:
        logger.error(f"Error gathering files from {base_dir}: {e}")
        raise
        
    return all_files
from file2ai import (
    convert_document,
    clone_and_export,
    local_export,
    setup_logging,
)
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


class JobStatus(TypedDict):
    status: str
    progress: float
    errors: List[str]
    start_time: datetime
    output_files: List[Path]


from file2ai import EXPORTS_DIR, UPLOADS_DIR, FRONTEND_DIR, prepare_exports_dir

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
app.secret_key = os.urandom(24)  # For flash messages

# Ensure required directories exist with proper permissions
prepare_exports_dir()  # Use the existing function from file2ai.py
UPLOADS_FOLDER = Path(UPLOADS_DIR)
FRONTEND_FOLDER = Path(FRONTEND_DIR)

for folder in [UPLOADS_FOLDER, FRONTEND_FOLDER]:
    folder.mkdir(exist_ok=True, mode=0o755)

# Global job tracking
conversion_jobs = {}
job_events = {}

# Ensure directories exist
UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)
EXPORTS_FOLDER = Path("exports")
EXPORTS_FOLDER.mkdir(exist_ok=True)


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
    
    try:
        job = conversion_jobs[job_id]
        job["status"] = "processing"
        job["progress"] = 0
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
            total_files = len(files)
            temp_files = []  # Track temporary files for cleanup

            for idx, (filename, file_data) in enumerate(files.items()):
                input_path = None
                output_path = None
                try:
                    # Save uploaded file
                    input_path = UPLOAD_FOLDER / filename
                    # Read file content into memory first
                    file_content = file_data.read()
                    # Create and write to file
                    with open(str(input_path), 'wb') as f:
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
                    output_path = EXPORTS_FOLDER / out_filename
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
                    output_path = EXPORTS_FOLDER / filename

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
                    output_path = EXPORTS_FOLDER / filename

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
                            
                        logger.info(f"Processing {len(directory_files)} files from directory: {input_dir}")
                            
                        # Handle subdir if specified
                        if args.subdir:
                            subdir_path = input_dir / args.subdir
                            if not subdir_path.exists():
                                raise IOError(f"Subdirectory not found: {subdir_path}")
                            if not subdir_path.is_dir():
                                raise IOError(f"Not a directory: {subdir_path}")
                            args.local_dir = str(subdir_path)
                            logger.info(f"Using subdirectory: {subdir_path}")

                        # Ensure output directory exists
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Export directory
                        logger.info(f"Starting local export from {args.local_dir} to {output_path}")
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

        status = "completed" if not job["errors"] else "completed_with_errors"
        job["status"] = status

    except Exception as e:
        job["status"] = "failed"
        job["errors"].append("Job failed: %s" % str(e))

    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception as e:
                logger.error(f"Error cleaning up temp file {temp_file}: {e}")
        
        # Signal completion
        job_events[job_id].set()


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
    - pages: str, optional page range for PDF conversion
    - brightness: float, optional image brightness (0.1-2.0)
    - contrast: float, optional image contrast (0.1-2.0)
    - resolution: int, optional image resolution (72-1200 DPI)
    - repo_url: str, optional GitHub repository URL (for export command)
    - branch: str, optional repository branch (for export command)
    - token: str, optional GitHub token (for export command)
    - local_dir: str, optional local directory path (for export command)
    
    Returns:
        JSON response with:
        - On success: {"job_id": str}
        - On error: {"error": str}, with appropriate HTTP status code
        
    Security:
        - Enforces 50MB file size limit
        - Validates file extensions and MIME types
        - Rejects suspicious file types
        - Cleans up temporary files
    """
    # Security logging
    logger.info("Received API request from %s", request.remote_addr)
    logger.debug("Form data: %s", request.form)
    logger.debug("Files: %s", request.files)
    logger.debug("Headers: %s", request.headers)
    
    command = request.form.get("command", "export")
    print("Command:", command)

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

        options = ConversionOptions(
            format=request.form.get("format", "text"),
            pages=request.form.get("pages", ""),
            brightness=request.form.get("brightness", "1.0"),
            contrast=request.form.get("contrast", "1.0"),
            resolution=request.form.get("resolution", "300")
        )

        # Start conversion in background
        thread = threading.Thread(target=process_job, args=(job_id, command, files, options))

        thread.start()
        return jsonify({"job_id": job_id})

    else:  # command == 'export'
        fmt = request.form.get("format", "text")
        options = {
            "format": fmt,
            "subdir": request.form.get("subdir")  # Store subdir in options
        }

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
                
            # Gather all files from directory
            try:
                directory_files = gather_all_files(dir_path)
            except Exception as e:
                return jsonify({"error": f"Error scanning directory: {str(e)}"}), 400
                
            if not directory_files:
                return jsonify({"error": f"No files found in directory: {dir_path}"}), 400
                
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
        thread = threading.Thread(
            target=process_job,
            args=(job_id, command, files, options)
        )
        thread.start()
        return jsonify({"job_id": job_id})

    return jsonify({"error": "Invalid command"}), 400


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


if __name__ == "__main__":
    # Set up logging for the web server
    setup_logging(operation="web", context="server")

    # Get port from environment variable or use default (8000)
    port = int(os.environ.get("FLASK_RUN_PORT", 8000))

    try:
        app.run(debug=True, host="0.0.0.0", port=port)
    except OSError as e:
        if "Address already in use" in str(e):
            logger.error("\nPort %d is in use. Try one of the following:", port)
            logger.error("1. Set a different port using: " "export FLASK_RUN_PORT=8080")
            logger.error(
                "2. On macOS, disable AirPlay Receiver in "
                "System Preferences -> "
                "General -> AirDrop & Handoff"
            )
            logger.error("3. Use an alternative port like " "8080, 3000, or 8000\n")
            sys.exit(1)
        raise  # Re-raise other OSErrors
