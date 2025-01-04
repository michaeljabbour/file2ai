from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from pathlib import Path
import os
from file2ai import convert_document, setup_logging
from argparse import Namespace

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For flash messages

# Ensure exports directory exists
UPLOAD_FOLDER = Path('uploads')
UPLOAD_FOLDER.mkdir(exist_ok=True)
EXPORTS_FOLDER = Path('exports')
EXPORTS_FOLDER.mkdir(exist_ok=True)

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)

        if file:
            # Save uploaded file
            input_path = UPLOAD_FOLDER / file.filename
            file.save(str(input_path))

            # Get conversion options
            output_format = request.form.get('format', 'text')
            pages = request.form.get('pages', '')
            brightness = float(request.form.get('brightness', 1.0))
            contrast = float(request.form.get('contrast', 1.0))
            resolution = int(request.form.get('resolution', 300))

            # Create output path
            output_path = EXPORTS_FOLDER / f"converted.{output_format}"

            # Create args namespace for convert_document
            args = Namespace(
                command='convert',
                input=str(input_path),
                output=str(output_path),
                format=output_format,
                pages=pages if pages else None,
                brightness=brightness,
                contrast=contrast,
                resolution=resolution
            )

            try:
                # Perform conversion
                setup_logging()
                convert_document(args)

                # Send the converted file
                return send_file(
                    str(output_path),
                    as_attachment=True,
                    download_name=f"converted.{output_format}"
                )
            except Exception as e:
                flash(f'Error during conversion: {str(e)}')
                return redirect(request.url)
            finally:
                # Cleanup
                if input_path.exists():
                    input_path.unlink()

    return render_template('upload.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
