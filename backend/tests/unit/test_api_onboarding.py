"""Tests for Onboarding API endpoints.

REQ-019 §6.3, §7.2: Resume parsing endpoint for onboarding flow.

These tests verify:
- POST /api/v1/onboarding/resume-parse — upload PDF, return parsed data
- Authentication, file validation, error handling
"""

import io
from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.services.resume_parsing_service import (
    _EMPTY_PDF_MSG,
    _EXTRACT_FAILURE_MSG,
    _PARSE_FAILURE_MSG,
    ResumeParseResult,
    VoiceSuggestions,
)

# =============================================================================
# Test Helpers
# =============================================================================

_ENDPOINT = "/api/v1/onboarding/resume-parse"

_PATCH_MAGIC = "app.core.file_validation.magic.from_buffer"
_PATCH_PARSE_RESUME = "app.api.v1.onboarding.ResumeParsingService.parse_resume"

_PDF_MIME = "application/pdf"


def _pdf_upload(content: bytes = b"%PDF-1.4 test content") -> dict:
    """Build multipart file upload kwargs for httpx."""
    return {"files": {"file": ("resume.pdf", io.BytesIO(content), _PDF_MIME)}}


def _make_parse_result(
    *,
    voice_confidence: float = 0.85,
    raw_text: str = "John Doe\nSoftware Engineer",
) -> ResumeParseResult:
    """Build a ResumeParseResult for test assertions."""
    return ResumeParseResult(
        basic_info={"full_name": "John Doe", "email": "john@example.com"},
        work_history=(
            {
                "job_title": "Software Engineer",
                "company_name": "Acme Corp",
                "start_date": "2020-01",
                "end_date": None,
                "is_current": True,
                "bullets": ["Built APIs"],
            },
        ),
        education=(
            {
                "institution": "MIT",
                "degree": "BS",
                "field_of_study": "Computer Science",
                "graduation_date": "2019-05",
            },
        ),
        skills=({"name": "Python", "type": "Hard", "proficiency": "Expert"},),
        certifications=(
            {"name": "AWS SAA", "issuer": "Amazon", "date_obtained": "2021-06"},
        ),
        voice_suggestions=VoiceSuggestions(
            writing_style="results-focused",
            vocabulary_level="technical",
            personality_markers="collaborative, detail-oriented",
            confidence=voice_confidence,
        ),
        raw_text=raw_text,
    )


async def _post_parse(
    client: AsyncClient,
    result: ResumeParseResult,
):
    """POST a PDF with mocked magic + parse service, return response."""
    with (
        patch(_PATCH_MAGIC, return_value=_PDF_MIME),
        patch(_PATCH_PARSE_RESUME, new_callable=AsyncMock, return_value=result),
    ):
        return await client.post(_ENDPOINT, **_pdf_upload())


# =============================================================================
# Authentication
# =============================================================================


class TestResumeParseAuth:
    """Authentication tests for POST /api/v1/onboarding/resume-parse."""

    @pytest.mark.asyncio
    async def test_requires_auth(self, unauthenticated_client: AsyncClient):
        """Request without authentication returns 401."""
        response = await unauthenticated_client.post(
            _ENDPOINT,
            **_pdf_upload(),
        )
        assert response.status_code == 401


# =============================================================================
# Success Cases
# =============================================================================


class TestResumeParseSuccess:
    """Happy path tests for resume parsing endpoint."""

    @pytest.mark.asyncio
    async def test_parse_pdf_returns_200(self, client: AsyncClient):
        """Valid PDF upload returns 200 with parsed data."""
        response = await _post_parse(client, _make_parse_result())
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_response_wrapped_in_data_envelope(self, client: AsyncClient):
        """Response uses DataResponse envelope: {"data": {...}}."""
        response = await _post_parse(client, _make_parse_result())

        body = response.json()
        assert "data" in body
        assert "basic_info" in body["data"]

    @pytest.mark.asyncio
    async def test_response_contains_all_fields(self, client: AsyncClient):
        """Response includes all 7 resume parse fields."""
        response = await _post_parse(client, _make_parse_result())

        data = response.json()["data"]
        expected_keys = {
            "basic_info",
            "work_history",
            "education",
            "skills",
            "certifications",
            "voice_suggestions",
            "raw_text",
        }
        assert expected_keys == set(data.keys())

    @pytest.mark.asyncio
    async def test_basic_info_passed_through(self, client: AsyncClient):
        """basic_info from service is returned in response."""
        response = await _post_parse(client, _make_parse_result())

        data = response.json()["data"]
        assert data["basic_info"]["full_name"] == "John Doe"
        assert data["basic_info"]["email"] == "john@example.com"

    @pytest.mark.asyncio
    async def test_work_history_is_list(self, client: AsyncClient):
        """work_history tuple is serialized as JSON list."""
        response = await _post_parse(client, _make_parse_result())

        data = response.json()["data"]
        assert len(data["work_history"]) == 1
        assert data["work_history"][0]["job_title"] == "Software Engineer"

    @pytest.mark.asyncio
    async def test_voice_suggestions_with_high_confidence(self, client: AsyncClient):
        """Voice suggestions with confidence >= 0.7 are included."""
        response = await _post_parse(client, _make_parse_result(voice_confidence=0.85))

        voice = response.json()["data"]["voice_suggestions"]
        assert voice is not None
        assert voice["confidence"] == 0.85
        assert voice["writing_style"] == "results-focused"

    @pytest.mark.asyncio
    async def test_voice_suggestions_null_when_absent(self, client: AsyncClient):
        """Voice suggestions are null when service returns None."""
        result = replace(_make_parse_result(), voice_suggestions=None)
        response = await _post_parse(client, result)

        assert response.json()["data"]["voice_suggestions"] is None


# =============================================================================
# File Validation
# =============================================================================


class TestResumeParseFileValidation:
    """File validation tests for resume parsing endpoint."""

    @pytest.mark.asyncio
    async def test_rejects_non_pdf_file(self, client: AsyncClient):
        """DOCX file (not PDF) returns 400."""
        docx_mime = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        with patch(_PATCH_MAGIC, return_value=docx_mime):
            response = await client.post(
                _ENDPOINT,
                files={
                    "file": (
                        "resume.docx",
                        io.BytesIO(b"PK\x03\x04"),
                        "application/octet-stream",
                    )
                },
            )

        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "PDF" in body["error"]["message"]

    @pytest.mark.asyncio
    async def test_rejects_text_file(self, client: AsyncClient):
        """Text file returns 400 from MIME validation."""
        with patch(_PATCH_MAGIC, return_value="text/plain"):
            response = await client.post(
                _ENDPOINT,
                files={"file": ("resume.txt", io.BytesIO(b"plain text"), "text/plain")},
            )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_no_file_returns_error(self, client: AsyncClient):
        """Missing file field returns 4xx error."""
        response = await client.post(_ENDPOINT)

        assert response.status_code in (400, 422)


# =============================================================================
# Error Handling
# =============================================================================


class TestResumeParseErrors:
    """Error handling tests for resume parsing endpoint."""

    @pytest.mark.asyncio
    async def test_extraction_failure_returns_400(self, client: AsyncClient):
        """PDF text extraction failure returns 400 with user-friendly message."""
        with (
            patch(_PATCH_MAGIC, return_value=_PDF_MIME),
            patch(
                _PATCH_PARSE_RESUME,
                new_callable=AsyncMock,
                side_effect=ValueError(_EXTRACT_FAILURE_MSG),
            ),
        ):
            response = await client.post(_ENDPOINT, **_pdf_upload())

        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "skip this step" in body["error"]["message"]

    @pytest.mark.asyncio
    async def test_llm_failure_returns_400(self, client: AsyncClient):
        """LLM parsing failure returns 400 with user-friendly message."""
        with (
            patch(_PATCH_MAGIC, return_value=_PDF_MIME),
            patch(
                _PATCH_PARSE_RESUME,
                new_callable=AsyncMock,
                side_effect=ValueError(_PARSE_FAILURE_MSG),
            ),
        ):
            response = await client.post(_ENDPOINT, **_pdf_upload())

        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "skip this step" in body["error"]["message"]

    @pytest.mark.asyncio
    async def test_empty_pdf_returns_400(self, client: AsyncClient):
        """Empty PDF (no text) returns 400."""
        with (
            patch(_PATCH_MAGIC, return_value=_PDF_MIME),
            patch(
                _PATCH_PARSE_RESUME,
                new_callable=AsyncMock,
                side_effect=ValueError(_EMPTY_PDF_MSG),
            ),
        ):
            response = await client.post(_ENDPOINT, **_pdf_upload())

        assert response.status_code == 400
        body = response.json()
        assert "No text could be extracted" in body["error"]["message"]

    @pytest.mark.asyncio
    async def test_oversized_file_returns_400(self, client: AsyncClient):
        """File exceeding size limit returns 400."""
        with (
            patch(_PATCH_MAGIC, return_value=_PDF_MIME),
            patch(
                _PATCH_PARSE_RESUME,
                new_callable=AsyncMock,
                side_effect=ValueError("File exceeds 10 MB limit."),
            ),
        ):
            response = await client.post(_ENDPOINT, **_pdf_upload())

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_unexpected_valueerror_gets_safe_fallback(self, client: AsyncClient):
        """Unexpected ValueError uses generic fallback, not raw message."""
        with (
            patch(_PATCH_MAGIC, return_value=_PDF_MIME),
            patch(
                _PATCH_PARSE_RESUME,
                new_callable=AsyncMock,
                side_effect=ValueError("Internal pdfplumber traceback detail"),
            ),
        ):
            response = await client.post(_ENDPOINT, **_pdf_upload())

        assert response.status_code == 400
        body = response.json()
        # Should NOT contain the raw internal error message
        assert "pdfplumber" not in body["error"]["message"]
        # Should contain the generic fallback
        assert "skip this step" in body["error"]["message"]
