import os
from pathlib import Path
from file2ai import convert_word_to_image


def test_word_to_image_conversion():
    """Test Word to image conversion to identify WeasyPrint issues."""
    test_file = Path(__file__).parent / "test.docx"
    output_file = Path(__file__).parent / "test_output.png"

    # Create a simple test document if it doesn't exist
    if not test_file.exists():
        from docx import Document

        doc = Document()
        doc.add_paragraph("Test content for WeasyPrint conversion")
        doc.save(test_file)

    try:
        convert_word_to_image(str(test_file), str(output_file))
        print(f"Success: Converted {test_file} to {output_file}")
    except Exception as e:
        print(f"Error during conversion: {str(e)}")
        print("WeasyPrint system library dependencies:")
        os.system("pip show weasyprint")


if __name__ == "__main__":
    test_word_to_image_conversion()
