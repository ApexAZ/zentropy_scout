"""Job posting extraction service.

REQ-006 §5.6 + REQ-007 §6.4: Extract structured data from raw job text.

WHY SEPARATE SERVICE:
- Shared between ingest endpoint (sync) and Scouter agent (background)
- Abstracted from LLM provider details
- Easy to test with mocked responses
"""

import json
import logging
import re
from typing import Any, cast

from app.providers import ProviderError, factory
from app.providers.llm.base import LLMMessage, TaskType
from app.schemas.ingest import ExtractedJobData

logger = logging.getLogger(__name__)


async def extract_job_data(raw_text: str) -> ExtractedJobData:
    """Extract structured job data from raw posting text.

    REQ-007 §6.4: Uses LLM to extract structured fields from raw text.
    REQ-006 §5.6: Returns preview-ready data for ingest endpoint.

    Args:
        raw_text: Raw job posting text to extract from.

    Returns:
        ExtractedJobData with fields: job_title, company_name, location,
        salary_min, salary_max, salary_currency, employment_type,
        extracted_skills, culture_text, description_snippet.
    """
    # Truncate to 15k chars for LLM (per REQ-007 note)
    truncated_text = raw_text[:15000]

    # Get description snippet (first 500 chars)
    description_snippet = truncated_text[:500]
    if len(truncated_text) > 500:
        description_snippet += "..."

    # Try LLM extraction
    try:
        llm = factory.get_llm_provider()
        response = await llm.complete(
            messages=[
                LLMMessage(role="system", content="You are a job posting parser."),
                LLMMessage(
                    role="user", content=_build_extraction_prompt(truncated_text)
                ),
            ],
            task=TaskType.EXTRACTION,
            json_mode=True,
        )
        extracted = _parse_extraction_response(response.content or "")
    except ProviderError as e:
        # Fallback to basic regex extraction if LLM fails
        logger.warning("LLM extraction failed (%s), using fallback regex extraction", e)
        extracted = _basic_extraction(truncated_text)

    # Always include description snippet
    extracted["description_snippet"] = description_snippet

    return extracted


def _build_extraction_prompt(text: str) -> str:
    """Build the extraction prompt for LLM.

    Args:
        text: Truncated job posting text.

    Returns:
        Prompt string for extraction.
    """
    return f"""Extract structured job information from the following job posting.
Return a JSON object with these fields (use null if not found):
- job_title: string
- company_name: string
- location: string
- salary_min: integer (annual, no commas)
- salary_max: integer (annual, no commas)
- salary_currency: string (e.g., "USD", "EUR")
- employment_type: string (e.g., "Full-time", "Part-time", "Contract")
- extracted_skills: array of objects with "skill_name" and "importance_level" ("Required" or "Preferred")
- culture_text: string summarizing company culture signals

Job Posting:
{text}

Return ONLY the JSON object, no explanation."""


def _parse_extraction_response(response: str) -> ExtractedJobData:
    """Parse LLM response into structured data.

    Args:
        response: LLM response text.

    Returns:
        ExtractedJobData with parsed fields.
    """
    # Try to extract JSON from response
    try:
        # Handle responses that may have markdown code blocks
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        data: dict[str, Any] = json.loads(response.strip())

        # Ensure extracted_skills is a list
        if "extracted_skills" not in data or not isinstance(
            data["extracted_skills"], list
        ):
            data["extracted_skills"] = []

        return cast(ExtractedJobData, data)
    except (json.JSONDecodeError, IndexError):
        return _basic_extraction("")


def _basic_extraction(text: str) -> ExtractedJobData:
    """Basic regex-based extraction fallback.

    WHY FALLBACK:
    - Provides some extraction even if LLM fails
    - Better UX than returning empty preview

    Args:
        text: Job posting text.

    Returns:
        ExtractedJobData with regex-extracted fields.
    """
    result: ExtractedJobData = {
        "job_title": None,
        "company_name": None,
        "location": None,
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "employment_type": None,
        "extracted_skills": [],
        "culture_text": None,
    }

    # Try to extract salary range (e.g., "$150k-$200k", "$150,000 - $200,000")
    salary_pattern = (
        r"\$(\d{1,3}(?:,\d{3})*(?:k)?)\s*[-–]\s*\$(\d{1,3}(?:,\d{3})*(?:k)?)"
    )
    salary_match = re.search(salary_pattern, text, re.IGNORECASE)
    if salary_match:
        min_str, max_str = salary_match.groups()
        result["salary_min"] = _parse_salary(min_str)
        result["salary_max"] = _parse_salary(max_str)
        result["salary_currency"] = "USD"

    # Try to extract employment type
    emp_types = ["Full-time", "Part-time", "Contract", "Temporary", "Internship"]
    for emp_type in emp_types:
        if emp_type.lower() in text.lower():
            result["employment_type"] = emp_type
            break

    return result


def _parse_salary(salary_str: str) -> int:
    """Parse salary string to integer.

    Args:
        salary_str: Salary string like "150k" or "150,000".

    Returns:
        Annual salary as integer.
    """
    # Remove commas
    salary_str = salary_str.replace(",", "")

    # Handle "k" suffix
    if salary_str.lower().endswith("k"):
        return int(float(salary_str[:-1]) * 1000)

    return int(salary_str)
