## file2ai Examples

This directory contains example usage scenarios and test files for file2ai.

### Sample Project Structure

The `sample_project/` directory contains a simple Python project with:
- `main.py`: Basic functions with type hints
- `utils.py`: Utility functions demonstrating different file types

### Test Files

The `test_files/` directory contains sample files for testing document conversion:

1. **Document Samples**
   - `sample.txt`: Plain text file
   - `sample.pdf`: PDF document with formatted text
   - `sample.docx`: Word document with various formatting
   - `sample.xlsx`: Excel spreadsheet with sample data
   - `sample.pptx`: PowerPoint presentation with multiple slides
   - `sample.html`: HTML document with basic formatting

2. **Public Repository Examples**
   For additional test files, you can use these public repositories:
   - [Apache OpenOffice Documentation](https://github.com/apache/openoffice/tree/trunk/main/extras/source/templates/samples) - Various document templates
   - [Pandoc Examples](https://github.com/jgm/pandoc/tree/master/test) - Markdown and document conversion samples
   - [PDF.js Examples](https://github.com/mozilla/pdf.js/tree/master/examples) - Sample PDF files

### Usage Examples

The `demo.sh` script demonstrates different ways to use file2ai:
1. Export from a local directory
2. Export from a public GitHub repository
3. Export from a specific branch
4. Export from a private repository (with token)

To run the examples:
```bash
cd examples
chmod +x demo.sh
./demo.sh
```

Note: The private repository example requires modification with your own repository URL and token.

### Test Files Usage

To test document conversion with the provided samples:

```bash
# Convert PDF to text
python file2ai.py examples/test_files/sample.pdf

# Convert Word to PDF
python file2ai.py examples/test_files/sample.docx --format pdf

# Convert Excel to CSV
python file2ai.py examples/test_files/sample.xlsx --format csv

# Convert PowerPoint to images
python file2ai.py examples/test_files/sample.pptx --format image

# Convert HTML to text
python file2ai.py examples/test_files/sample.html
```
