"""Tests for file validation utilities.

Security: Tests for magic byte validation, size limits, and filename sanitization.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.errors import ValidationError
from app.core.file_validation import (
    ALLOWED_MIMES,
    MAX_FILE_SIZE_BYTES,
    read_file_with_size_limit,
    sanitize_filename_for_header,
    validate_file_content,
)


class TestReadFileWithSizeLimit:
    """Tests for read_file_with_size_limit function."""

    @pytest.mark.asyncio
    async def test_reads_file_within_limit(self):
        """Should read file content when under size limit."""
        content = b"Hello, World!"
        mock_file = AsyncMock()
        mock_file.read = AsyncMock(side_effect=[content, b""])

        result = await read_file_with_size_limit(mock_file)

        assert result == content

    @pytest.mark.asyncio
    async def test_reads_file_in_chunks(self):
        """Should read file in chunks."""
        chunk1 = b"A" * 1000
        chunk2 = b"B" * 1000
        mock_file = AsyncMock()
        mock_file.read = AsyncMock(side_effect=[chunk1, chunk2, b""])

        result = await read_file_with_size_limit(mock_file)

        assert result == chunk1 + chunk2

    @pytest.mark.asyncio
    async def test_rejects_file_exceeding_limit(self):
        """Should raise ValidationError when file exceeds size limit."""
        # Create a file larger than the limit
        large_chunk = b"X" * (MAX_FILE_SIZE_BYTES + 1)
        mock_file = AsyncMock()
        mock_file.read = AsyncMock(side_effect=[large_chunk])

        with pytest.raises(ValidationError) as exc_info:
            await read_file_with_size_limit(mock_file)

        assert "File too large" in exc_info.value.message
        assert exc_info.value.details[0]["error"] == "FILE_TOO_LARGE"

    @pytest.mark.asyncio
    async def test_respects_custom_size_limit(self):
        """Should use custom size limit when provided."""
        content = b"X" * 100
        mock_file = AsyncMock()
        mock_file.read = AsyncMock(side_effect=[content])

        with pytest.raises(ValidationError) as exc_info:
            await read_file_with_size_limit(mock_file, max_size=50)

        assert "File too large" in exc_info.value.message


class TestValidateFileContent:
    """Tests for validate_file_content function."""

    def test_accepts_valid_pdf(self):
        """Should accept valid PDF content."""
        # PDF magic bytes
        pdf_content = b"%PDF-1.4 fake pdf content"

        with patch("app.core.file_validation.magic.from_buffer") as mock_magic:
            mock_magic.return_value = "application/pdf"
            result = validate_file_content(pdf_content, "resume.pdf")

        assert result == "PDF"

    def test_accepts_valid_docx(self):
        """Should accept valid DOCX content."""
        # DOCX is a ZIP file with specific structure
        docx_content = b"PK\x03\x04 fake docx content"

        with patch("app.core.file_validation.magic.from_buffer") as mock_magic:
            mock_magic.return_value = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            result = validate_file_content(docx_content, "resume.docx")

        assert result == "DOCX"

    def test_rejects_executable(self):
        """Should reject executable files even with PDF extension."""
        exe_content = b"MZ executable content"

        with patch("app.core.file_validation.magic.from_buffer") as mock_magic:
            mock_magic.return_value = "application/x-dosexec"

            with pytest.raises(ValidationError) as exc_info:
                validate_file_content(exe_content, "resume.pdf")

            assert "Invalid file content" in exc_info.value.message
            assert "application/x-dosexec" in exc_info.value.message
            assert exc_info.value.details[0]["error"] == "INVALID_FILE_CONTENT"

    def test_rejects_html(self):
        """Should reject HTML files disguised as documents."""
        html_content = b"<html><script>alert('xss')</script></html>"

        with patch("app.core.file_validation.magic.from_buffer") as mock_magic:
            mock_magic.return_value = "text/html"

            with pytest.raises(ValidationError):
                validate_file_content(html_content, "resume.pdf")

    def test_includes_detected_mime_in_error(self):
        """Should include detected MIME type in error details."""
        with patch("app.core.file_validation.magic.from_buffer") as mock_magic:
            mock_magic.return_value = "image/jpeg"

            with pytest.raises(ValidationError) as exc_info:
                validate_file_content(b"fake jpeg", "image.pdf")

            assert exc_info.value.details[0]["detected_mime"] == "image/jpeg"


class TestSanitizeFilenameForHeader:
    """Tests for sanitize_filename_for_header function."""

    def test_passes_safe_filename(self):
        """Should pass through safe filenames unchanged."""
        assert sanitize_filename_for_header("resume.pdf") == "resume.pdf"
        assert (
            sanitize_filename_for_header("my_resume_2024.docx") == "my_resume_2024.docx"
        )

    def test_removes_quotes(self):
        """Should remove quote characters."""
        assert sanitize_filename_for_header('file"name.pdf') == "filename.pdf"

    def test_removes_newlines(self):
        """Should remove newline characters (prevents header injection)."""
        assert sanitize_filename_for_header("file\nname.pdf") == "filename.pdf"
        assert sanitize_filename_for_header("file\r\nname.pdf") == "filename.pdf"

    def test_removes_backslashes(self):
        """Should remove backslash characters."""
        assert sanitize_filename_for_header("file\\name.pdf") == "filename.pdf"

    def test_removes_semicolons(self):
        """Should remove semicolons (prevents header parameter injection)."""
        assert sanitize_filename_for_header("file;name.pdf") == "filename.pdf"
        # Semicolon could be used to add extra header parameters
        assert (
            sanitize_filename_for_header("file.pdf; malicious=true")
            == "file.pdf malicious=true"
        )

    def test_removes_control_characters(self):
        """Should remove control characters."""
        assert sanitize_filename_for_header("file\x00name.pdf") == "filename.pdf"
        assert sanitize_filename_for_header("file\x1fname.pdf") == "filename.pdf"

    def test_truncates_long_filenames(self):
        """Should truncate filenames exceeding max length."""
        long_name = "a" * 300 + ".pdf"
        result = sanitize_filename_for_header(long_name)

        assert len(result) <= 200
        assert result.endswith(".pdf")

    def test_preserves_extension_when_truncating(self):
        """Should preserve file extension when truncating."""
        long_name = "a" * 250 + ".docx"
        result = sanitize_filename_for_header(long_name)

        assert result.endswith(".docx")
        assert len(result) <= 200

    def test_handles_empty_after_sanitization(self):
        """Should return 'download' if filename becomes empty."""
        assert sanitize_filename_for_header('"\r\n\\') == "download"

    def test_handles_header_injection_attempt(self):
        """Should prevent HTTP header injection attacks.

        The key security requirement is removing CRLF sequences that would
        create new header lines. The remaining text becomes part of the
        filename (harmless).
        """
        # Attempt to inject a new header via CRLF
        malicious = "file.pdf\r\nX-Injected: value"
        result = sanitize_filename_for_header(malicious)

        # CRLF removed - no new header line possible
        assert "\r" not in result
        assert "\n" not in result
        # The injection text is now just part of filename (safe)
        assert result == "file.pdfX-Injected: value"


class TestAllowedMimes:
    """Tests for ALLOWED_MIMES constant."""

    def test_pdf_is_allowed(self):
        """PDF MIME type should be in allowed list."""
        assert "application/pdf" in ALLOWED_MIMES
        assert ALLOWED_MIMES["application/pdf"] == "PDF"

    def test_docx_is_allowed(self):
        """DOCX MIME type should be in allowed list."""
        docx_mime = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert docx_mime in ALLOWED_MIMES
        assert ALLOWED_MIMES[docx_mime] == "DOCX"

    def test_only_expected_types_allowed(self):
        """Only PDF and DOCX should be allowed."""
        assert len(ALLOWED_MIMES) == 2
