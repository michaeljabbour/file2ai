import os
from fpdf import FPDF


def create_test_pdf(output_path):
    try:
        # Ensure output directory exists and is writable
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)

        # Debug info
        print(f"Creating PDF at: {output_path}")
        print(f"Current working directory: {os.getcwd()}")
        print(f"Output directory exists: {os.path.exists(output_dir)}")
        print(f"Output directory writable: {os.access(output_dir, os.W_OK)}")

        # Create PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(40, 10, "Sample PDF Document")
        pdf.ln()
        pdf.set_font("Arial", "", 12)
        pdf.multi_cell(
            0,
            10,
            "This is a sample PDF file created for testing file2ai document conversion capabilities.\n\nIt contains multiple lines of text to demonstrate text extraction and formatting preservation.",
        )

        # Write PDF and verify
        print(f"Writing PDF to: {output_path}")
        pdf.output(output_path)

        # Verify file exists and has content
        if not os.path.exists(output_path):
            raise FileNotFoundError(f"PDF file was not created at: {output_path}")

        if os.path.getsize(output_path) == 0:
            raise ValueError(f"Created PDF file is empty: {output_path}")

        # Double check file permissions and existence
        file_stat = os.stat(output_path)
        print(f"File permissions: {oct(file_stat.st_mode)}")
        print(f"File size: {file_stat.st_size} bytes")
        print(f"File owner: {file_stat.st_uid}")
        print(f"File group: {file_stat.st_gid}")
        print(f"Test PDF created successfully at: {output_path}")

        # List directory contents after creation
        print("Directory contents after PDF creation:")
        for f in os.listdir(output_dir):
            fpath = os.path.join(output_dir, f)
            print(f"- {f}: {os.path.getsize(fpath)} bytes")

        return True
    except Exception as e:
        print(f"Error creating PDF file: {str(e)}")
        # Clean up if file exists but is invalid
        if os.path.exists(output_path):
            print(f"Removing invalid PDF file: {output_path}")
            os.remove(output_path)
        return False


if __name__ == "__main__":
    import sys
    import os

    # Ensure we're using absolute paths from project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_files_dir = os.path.join(project_root, "test_files")

    # Create test_files directory if it doesn't exist
    os.makedirs(test_files_dir, exist_ok=True)

    if len(sys.argv) > 1:
        output_path = sys.argv[1]
    else:
        output_path = os.path.join(test_files_dir, "test.pdf")

    if not create_test_pdf(output_path):
        sys.exit(1)
