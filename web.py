from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify
from pathlib import Path
import os
import uuid
import threading
import queue
from datetime import datetime
import logging
from file2ai import convert_document, setup_logging
from argparse import Namespace

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For flash messages

# Global job tracking
conversion_jobs = {}
job_events = {}

# Ensure directories exist
UPLOAD_FOLDER = Path('uploads')
UPLOAD_FOLDER.mkdir(exist_ok=True)
EXPORTS_FOLDER = Path('exports')
EXPORTS_FOLDER.mkdir(exist_ok=True)

def process_conversion(job_id, files, options):
    """Background conversion process"""
    try:
        job = conversion_jobs[job_id]
        job['status'] = 'processing'
        job['progress'] = 0
        total_files = len(files)
        
        # Create a zip file for multiple files
        output_files = []
        
        for idx, (filename, file_data) in enumerate(files.items()):
            try:
                # Save uploaded file
                input_path = UPLOAD_FOLDER / filename
                file_data.save(str(input_path))
                
                # Create output path
                output_format = options['format']
                output_path = EXPORTS_FOLDER / f"{filename}.{output_format}"
                
                # Create args namespace
                args = Namespace(
                    command='convert',
                    input=str(input_path),
                    output=str(output_path),
                    format=output_format,
                    pages=options.get('pages'),
                    brightness=float(options.get('brightness', 1.0)),
                    contrast=float(options.get('contrast', 1.0)),
                    resolution=int(options.get('resolution', 300))
                )
                
                # Convert file
                convert_document(args)
                output_files.append(output_path)
                
                # Update progress
                job['progress'] = ((idx + 1) / total_files) * 100
                
            except Exception as e:
                job['errors'].append(f"Error converting {filename}: {str(e)}")
            finally:
                if input_path.exists():
                    input_path.unlink()
        
        job['output_files'] = output_files
        job['status'] = 'completed' if not job['errors'] else 'completed_with_errors'
        
    except Exception as e:
        job['status'] = 'failed'
        job['errors'].append(f"Conversion failed: {str(e)}")
    
    finally:
        # Signal completion
        job_events[job_id].set()

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if not request.files:
            flash('No files selected')
            return redirect(request.url)
        
        files = {f.filename: f for f in request.files.getlist('file') if f.filename}
        if not files:
            flash('No files selected')
            return redirect(request.url)
        
        # Create job
        job_id = str(uuid.uuid4())
        conversion_jobs[job_id] = {
            'status': 'queued',
            'progress': 0,
            'errors': [],
            'start_time': datetime.now(),
            'output_files': []
        }
        job_events[job_id] = threading.Event()
        
        
        # Get conversion options
        options = {
            'format': request.form.get('format', 'text'),
            'pages': request.form.get('pages', ''),
            'brightness': request.form.get('brightness', '1.0'),
            'contrast': request.form.get('contrast', '1.0'),
            'resolution': request.form.get('resolution', '300')
        }
        
        # Start conversion in background
        thread = threading.Thread(
            target=process_conversion,
            args=(job_id, files, options)
        )
        thread.start()
        
        return jsonify({'job_id': job_id})
        
    return render_template('upload.html')

@app.route('/status/<job_id>')
def get_status(job_id):
    """Get job status"""
    if job_id not in conversion_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = conversion_jobs[job_id]
    return jsonify({
        'status': job['status'],
        'progress': job['progress'],
        'errors': job['errors']
    })

@app.route('/download/<job_id>')
def download_files(job_id):
    """Download converted files"""
    if job_id not in conversion_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = conversion_jobs[job_id]
    if job['status'] not in ['completed', 'completed_with_errors']:
        return jsonify({'error': 'Job not complete'}), 400
    
    if len(job['output_files']) == 1:
        # Single file download
        output_path = job['output_files'][0]
        return send_file(
            str(output_path),
            as_attachment=True,
            download_name=output_path.name
        )
    else:
        # Multiple files - create zip
        import zipfile
        import io
        
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w') as zf:
            for output_path in job['output_files']:
                zf.write(output_path, output_path.name)
        
        memory_file.seek(0)
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name='converted_files.zip'
        )

@app.route('/cleanup/<job_id>')
def cleanup_job(job_id):
    """Clean up job files and data"""
    if job_id not in conversion_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = conversion_jobs[job_id]
    
    # Remove output files
    for output_path in job['output_files']:
        try:
            if output_path.exists():
                output_path.unlink()
        except Exception as e:
            logger.error(f"Error cleaning up {output_path}: {e}")
    
    # Remove job data
    del conversion_jobs[job_id]
    del job_events[job_id]
    
    return jsonify({'status': 'cleaned'})

if __name__ == '__main__':
    setup_logging()  # Set up logging for the web server
    app.run(debug=True, host='0.0.0.0', port=5000)
