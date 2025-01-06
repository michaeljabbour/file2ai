from flask import Flask, render_template, request, send_file, jsonify
from pathlib import Path
import os
import sys
import uuid
import threading
from datetime import datetime
import logging
from typing import Dict, Optional, List, TypedDict, Union
from werkzeug.datastructures import FileStorage
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


app = Flask(__name__)
app.secret_key = os.urandom(24)  # For flash messages

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
    try:
        job = conversion_jobs[job_id]
        job["status"] = "processing"
        job["progress"] = 0

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

            for idx, (filename, file_data) in enumerate(files.items()):
                try:
                    # Save uploaded file
                    input_path = UPLOAD_FOLDER / filename
                    file_data.save(str(input_path))

                    # Create output path
                    out_filename = f"{filename}.{output_format}"
                    output_path = EXPORTS_FOLDER / out_filename

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
                    convert_document(args)
                    output_files.append(output_path)

                    # Update progress
                    progress = ((idx + 1) / total_files) * 100
                    job["progress"] = progress

                except Exception as e:
                    job["errors"].append("Error converting %s: %s" % (filename, str(e)))
                finally:
                    if input_path.exists():
                        input_path.unlink()

            job["output_files"] = output_files

        elif command == "export":
            # Handle repository export or local directory export
            repo_url = options.get("repo_url")
            local_dir = options.get("local_dir")

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
                        branch=str(options.get("branch", "")),
                        token=str(options.get("token", "")),
                        output=str(output_path),
                        format=str(options.get("format", "text")),
                    )

                    # Export repository
                    clone_and_export(args)
                    job["output_files"] = [output_path]
                    job["progress"] = 100
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
                    )

                    # Export local directory
                    local_export(args)
                    job["output_files"] = [output_path]
                    job["progress"] = 100

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
        # Signal completion
        job_events[job_id].set()


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        command = request.form.get("command", "export")

        # Create job
        job_id = str(uuid.uuid4())
        conversion_jobs[job_id] = JobStatus(
            status="queued", progress=0, errors=[], start_time=datetime.now(), output_files=[]
        )
        job_events[job_id] = threading.Event()

        # Handle different commands
        if command == "convert":
            if not request.files:
                return jsonify({"error": "No files selected"}), 400

            files = {f.filename: f for f in request.files.getlist("file") if f.filename}
            if not files:
                return jsonify({"error": "No files selected"}), 400

            options = ConversionOptions(
                format=request.form.get("format", "text"),
                pages=request.form.get("pages", ""),
                brightness=request.form.get("brightness", "1.0"),
                contrast=request.form.get("contrast", "1.0"),
                resolution=request.form.get("resolution", "300"),
            )

            # Start conversion in background
            thread = threading.Thread(target=process_job, args=(job_id, command, files, options))

        else:  # command == 'export'
            fmt = request.form.get("format", "text")
            options = ConversionOptions(format=fmt)

            # Add repository-specific options
            if repo_url := request.form.get("repo_url"):
                options.update(
                    repo_url=repo_url,
                    branch=request.form.get("branch"),
                    token=request.form.get("token"),
                )

            # Add local directory options
            elif request.form.get("local_dir"):
                if not request.files:
                    return jsonify({"error": "No directory selected"}), 400

                # Get the first file's directory path
                first_file = next(iter(request.files.values()))
                dir_path = str(Path(first_file.filename).parent)
                options["local_dir"] = dir_path

            else:
                return (jsonify({"error": ("No repository URL or local directory provided")}), 400)

            # Start export in background
            thread = threading.Thread(target=process_job, args=(job_id, command, None, options))

        thread.start()
        return jsonify({"job_id": job_id})

    return render_template("index.html")


@app.route("/status/<job_id>")
def get_status(job_id):
    """Get job status"""
    if job_id not in conversion_jobs:
        return (jsonify({"error": "Job not found"}), 404)

    job = conversion_jobs[job_id]
    return jsonify({"status": job["status"], "progress": job["progress"], "errors": job["errors"]})


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
    """Clean up job files and data"""
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
