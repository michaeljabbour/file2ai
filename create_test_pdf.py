from fpdf import FPDF

def create_test_pdf(output_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(40, 10, 'Sample PDF Document')
    pdf.ln()
    pdf.set_font('Arial', '', 12)
    pdf.multi_cell(0, 10, 'This is a sample PDF file created for testing file2ai document conversion capabilities.\n\nIt contains multiple lines of text to demonstrate text extraction and formatting preservation.')
    pdf.output(output_path)
    print(f"Test PDF created successfully at: {output_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        output_path = sys.argv[1]
    else:
        output_path = "sample.pdf"
    create_test_pdf(output_path)
