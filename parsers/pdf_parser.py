# parsers/pdf_parser.py
import pdfplumber

def extract_text_from_pdf(file_path: str) -> str:
    """Extracts all text from a given PDF file path."""
    extracted_text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                  extracted_text += text + "\n"
        return extracted_text.strip()
    except Exception as e:
        raise RuntimeError(f"Failed to parse PDF file: {str(e)}")