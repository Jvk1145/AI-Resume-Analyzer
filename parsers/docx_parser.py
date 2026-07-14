# parsers/docx_parser.py
import docx

def extract_text_from_docx(file_path: str) -> str:
    """Extracts all paragraph text from a given DOCX file path."""
    try:
        doc = docx.Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text)
        return "\n".join(full_text).strip()
    except Exception as e:
        raise RuntimeError(f"Failed to parse DOCX file: {str(e)}")