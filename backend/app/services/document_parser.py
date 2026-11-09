"""
In-memory resume text extraction.

Supports:
  - PDF (.pdf) via pypdf
  - Word (.docx) via python-docx
  - Plain Text (.txt) via UTF-8 decoding

"""

import io
from typing import Set

import docx
import pypdf

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
SUPPORTED_EXTENSIONS: Set[str] = {".pdf", ".docx", ".txt"}


class DocumentParserError(Exception):
    """Base exception for document parsing failures."""


class UnsupportedFileTypeError(DocumentParserError):
    """Raised when the uploaded file extension is not supported."""


class FileTooLargeError(DocumentParserError):
    """Raised when the uploaded file exceeds the size cap."""


class EmptyDocumentError(DocumentParserError):
    """Raised when no readable text could be extracted (e.g. scanned image PDF)."""


def _extract_pdf_text(file_bytes: bytes) -> str:
    """Extract selectable text from PDF bytes using pypdf."""
    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        pages_text = []
        for idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages_text.append(text.strip())
        return "\n\n".join(pages_text).strip()
    except Exception as err:
        raise DocumentParserError(f"Failed to parse PDF file: {err}") from err


def _extract_docx_text(file_bytes: bytes) -> str:
    try:
        doc = docx.Document(io.BytesIO(file_bytes))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs).strip()
    except Exception as err:
        raise DocumentParserError(f"Failed to parse DOCX file: {err}") from err


def _extract_txt_text(file_bytes: bytes) -> str:
    try:
        return file_bytes.decode("utf-8").strip()
    except UnicodeDecodeError:
        try:
            return file_bytes.decode("latin-1").strip()
        except Exception as err:
            raise DocumentParserError("Failed to decode text file as UTF-8 or Latin-1.") from err


def extract_text_from_file(filename: str, file_bytes: bytes) -> str:
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise FileTooLargeError("File exceeds the maximum allowed size of 5 MB.")

    lower_name = filename.lower().strip()
    matched_ext = next((ext for ext in SUPPORTED_EXTENSIONS if lower_name.endswith(ext)), None)

    if not matched_ext:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise UnsupportedFileTypeError(f"Unsupported file type. Allowed formats: {allowed}")

    if matched_ext == ".pdf":
        extracted = _extract_pdf_text(file_bytes)
    elif matched_ext == ".docx":
        extracted = _extract_docx_text(file_bytes)
    elif matched_ext == ".txt":
        extracted = _extract_txt_text(file_bytes)
    else:
        raise UnsupportedFileTypeError(f"Unhandled file extension: {matched_ext}")

    if not extracted:
        raise EmptyDocumentError(
            "No extractable text found in document. Scanned image-only PDFs without OCR are not supported."
        )

    return extracted

