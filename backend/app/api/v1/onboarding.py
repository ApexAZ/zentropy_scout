"""Onboarding API router.

REQ-019 §6.3: Resume parsing endpoint for onboarding flow.

Endpoints:
- POST /resume-parse — Upload PDF, return structured persona data.
"""

from typing import Annotated

import structlog
from fastapi import APIRouter, File, Request, UploadFile

from app.api.deps import CurrentUserId
from app.core.config import settings
from app.core.errors import ValidationError
from app.core.file_validation import read_file_with_size_limit, validate_file_content
from app.core.rate_limiting import limiter
from app.core.responses import DataResponse
from app.providers import factory
from app.services.resume_parsing_service import (
    _EMPTY_PDF_MSG,
    _EXTRACT_FAILURE_MSG,
    _PARSE_FAILURE_MSG,
    ResumeParsingService,
)

logger = structlog.get_logger()

router = APIRouter()

_PDF_FILE_TYPE = "PDF"
"""Only PDFs are supported for resume parsing (pdfplumber)."""

_SAFE_ERROR_MESSAGES = frozenset(
    {_EXTRACT_FAILURE_MSG, _EMPTY_PDF_MSG, _PARSE_FAILURE_MSG}
)
"""Known user-friendly error messages from ResumeParsingService.

Security: Only these messages are forwarded to the client. Any unexpected
ValueError gets replaced with a generic fallback to prevent information leakage.
"""


@router.post("/resume-parse")
@limiter.limit(settings.rate_limit_llm)
async def parse_resume(
    request: Request,  # noqa: ARG001
    file: Annotated[UploadFile, File(...)],
    user_id: CurrentUserId,  # noqa: ARG001
) -> DataResponse[dict]:
    """Parse uploaded PDF resume and extract structured data.

    REQ-019 §6.3, §7.2: Accepts PDF upload, extracts text via pdfplumber,
    parses with LLM, returns structured persona data for onboarding
    form pre-population.

    Args:
        request: HTTP request (required by rate limiter).
        file: Uploaded PDF file.
        user_id: Current authenticated user (injected, ensures auth).

    Returns:
        DataResponse with parsed resume fields: basic_info, work_history,
        education, skills, certifications, voice_suggestions, raw_text.

    Raises:
        ValidationError: If file is not PDF, too large, or parsing fails.
    """
    content = await read_file_with_size_limit(file)

    filename = file.filename or "unknown"
    file_type = validate_file_content(content, filename)

    if file_type != _PDF_FILE_TYPE:
        raise ValidationError(
            message="Only PDF files are supported for resume parsing.",
            details=[{"field": "file", "error": "PDF_REQUIRED"}],
        )

    provider = factory.get_llm_provider()
    service = ResumeParsingService()

    try:
        result = await service.parse_resume(content, provider)
    except ValueError as exc:
        msg = str(exc)
        if msg not in _SAFE_ERROR_MESSAGES:
            logger.warning(
                "Unexpected ValueError in resume parsing",
                error=msg[:200],
            )
            msg = _PARSE_FAILURE_MSG
        raise ValidationError(message=msg) from exc

    voice = None
    if result.voice_suggestions is not None:
        voice = {
            "writing_style": result.voice_suggestions.writing_style,
            "vocabulary_level": result.voice_suggestions.vocabulary_level,
            "personality_markers": result.voice_suggestions.personality_markers,
            "confidence": result.voice_suggestions.confidence,
        }

    return DataResponse(
        data={
            "basic_info": result.basic_info,
            "work_history": list(result.work_history),
            "education": list(result.education),
            "skills": list(result.skills),
            "certifications": list(result.certifications),
            "voice_suggestions": voice,
            "raw_text": result.raw_text,
        }
    )
