"""File validation utilities for secure file uploads.

Security: Validates file content (magic bytes), enforces size limits,
and sanitizes filenames to prevent injection attacks.
"""

import re
from typing import TYPE_CHECKING

import magic
import structlog

if TYPE_CHECKING:
    from fastapi import UploadFile

from app.core.errors import ValidationError

logger = structlog.get_logger()

# Maximum file size (10 MB)
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# Chunk size for reading files (64 KB)
CHUNK_SIZE_BYTES = 64 * 1024

# Allowed MIME types and their corresponding file types
ALLOWED_MIMES: dict[str, str] = {
    "application/pdf": "PDF",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
}


async def read_file_with_size_limit(
    file: "UploadFile",
    max_size: int = MAX_FILE_SIZE_BYTES,
) -> bytes:
    """Read file content with size limit to prevent DoS.

    Args:
        file: UploadFile from FastAPI.
        max_size: Maximum allowed file size in bytes.

    Returns:
        File content as bytes.

    Raises:
        ValidationError: If file exceeds size limit.
    """
    content = b""
    total_size = 0

    while True:
        chunk = await file.read(CHUNK_SIZE_BYTES)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > max_size:
            raise ValidationError(
                message=f"File too large. Maximum size: {max_size // (1024 * 1024)}MB",
                details=[{"field": "file", "error": "FILE_TOO_LARGE"}],
            )
        content += chunk

    return content


def validate_file_content(content: bytes, filename: str) -> str:
    """Validate file content using magic bytes (not just extension).

    Args:
        content: File binary content.
        filename: Original filename (for error messages).

    Returns:
        Detected file type ("PDF" or "DOCX").

    Raises:
        ValidationError: If file content doesn't match allowed MIME types.
    """
    detected_mime = magic.from_buffer(content, mime=True)

    if detected_mime not in ALLOWED_MIMES:
        # Log detected MIME for server-side debugging; do NOT expose to client
        logger.warning(
            "File content validation failed",
            detected_mime=detected_mime,
            filename=filename,
        )
        raise ValidationError(
            message="Invalid file type. Allowed: PDF, DOCX.",
            details=[{"field": "file", "error": "INVALID_FILE_CONTENT"}],
        )

    return ALLOWED_MIMES[detected_mime]


def sanitize_filename_for_header(filename: str, max_length: int = 200) -> str:
    """Sanitize filename for Content-Disposition header.

    Prevents HTTP header injection by removing dangerous characters.

    Args:
        filename: Original filename.
        max_length: Maximum allowed filename length.

    Returns:
        Sanitized filename safe for HTTP headers.
    """
    # Remove characters that could cause header injection
    # (quotes, newlines, carriage returns, backslashes, semicolons)
    safe = re.sub(r'["\r\n\\;]', "", filename)

    # Remove any control characters
    safe = re.sub(r"[\x00-\x1f\x7f]", "", safe)

    # Limit length to prevent header overflow
    if len(safe) > max_length:
        # Preserve extension if present
        if "." in safe:
            name, ext = safe.rsplit(".", 1)
            ext = f".{ext}"
            max_name_length = max_length - len(ext)
            safe = name[:max_name_length] + ext
        else:
            safe = safe[:max_length]

    # Fallback if sanitization results in empty string
    if not safe:
        safe = "download"

    return safe
