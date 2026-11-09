"""
Secure, in-memory resume text extraction.

Supports:
  - PDF (.pdf) via pypdf
  - Word (.docx) via python-docx
  - Plain Text (.txt) via UTF-8/Latin-1 decoding
"""

import io
from typing import Set

import docx
from fastapi import UploadFile
import pypdf

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
CHUNK_SIZE_BYTES = 64 * 1024  # 64 KB
SUPPORTED_EXTENSIONS: Set[str] = {".pdf", ".docx", ".txt"}


class DocumentParserError(Exception):
    """Base exception for document parsing failures."""


class UnsupportedFileTypeError(DocumentParserError):
    """Raised when the uploaded file extension is not supported."""


class FileTooLargeError(DocumentParserError):
    """Raised when the uploaded file exceeds the 5 MB size limit."""


class EmptyDocumentError(DocumentParserError):
    """Raised when no readable text could be extracted (e.g. scanned image PDF)."""


async def read_file_safely(file: UploadFile, max_bytes: int = MAX_FILE_SIZE_BYTES) -> bytes:
    """
    Read UploadFile in 64 KB chunks, aborting immediately if max_bytes is exceeded.
    Guarantees oversized files are never buffered entirely into memory.
    """
    buffer = bytearray()
    while chunk := await file.read(CHUNK_SIZE_BYTES):
        buffer.extend(chunk)
        if len(buffer) > max_bytes:
            raise FileTooLargeError("File exceeds the maximum allowed size of 5 MB.")
    return bytes(buffer)


def _extract_pdf_text(file_bytes: bytes) -> str:
    """Extract selectable text from PDF bytes using pypdf."""
    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        pages_text = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages_text.append(text.strip())
        return "\n\n".join(pages_text).strip()
    except Exception as err:
        raise DocumentParserError(f"Failed to parse PDF document: {err}") from err


def _extract_docx_text(file_bytes: bytes) -> str:
    """Extract text from Word .docx bytes using python-docx."""
    try:
        doc = docx.Document(io.BytesIO(file_bytes))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs).strip()
    except Exception as err:
        raise DocumentParserError(f"Failed to parse DOCX document: {err}") from err


def _extract_txt_text(file_bytes: bytes) -> str:
    """Decode plain text bytes with fallback encoding."""
    try:
        return file_bytes.decode("utf-8").strip()
    except UnicodeDecodeError:
        try:
            return file_bytes.decode("latin-1").strip()
        except Exception as err:
            raise DocumentParserError("Failed to decode text file as UTF-8 or Latin-1.") from err


def extract_text_from_bytes(filename: str, file_bytes: bytes) -> str:
    lower_name = filename.lower().strip()
    matched_ext = next((ext for ext in SUPPORTED_EXTENSIONS if lower_name.endswith(ext)), None)

    if not matched_ext:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise UnsupportedFileTypeError(f"Unsupported file format. Allowed formats: {allowed}")

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

