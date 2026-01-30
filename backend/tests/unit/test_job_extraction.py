"""Tests for job posting extraction service.

REQ-007 §6.4: Skill & Culture Extraction tests.

Tests verify:
- Text truncation to 15k characters
- Skill extraction with skill_type, is_required, years_requested
- Culture text extraction (values, benefits, team environment)
- Fallback to regex extraction when LLM fails
- Proper handling of edge cases (empty text, malformed responses)
"""

import pytest

from app.providers.llm.base import TaskType
from app.providers.llm.mock_adapter import MockLLMProvider
from app.schemas.ingest import ExtractedSkill
from app.services.job_extraction import (
    _basic_extraction,
    _build_extraction_prompt,
    _parse_extraction_response,
    _parse_salary,
    extract_job_data,
)

# =============================================================================
# ExtractedSkill Schema Tests
# =============================================================================


class TestExtractedSkillSchema:
    """Tests for ExtractedSkill TypedDict structure.

    REQ-007 §6.4: Skills must have skill_type (Hard/Soft), is_required (bool),
    years_requested (int|null).
    """

    def test_extracted_skill_has_skill_name(self) -> None:
        """ExtractedSkill requires skill_name field."""
        skill: ExtractedSkill = {
            "skill_name": "Python",
            "skill_type": "Hard",
            "is_required": True,
            "years_requested": None,
        }
        assert skill["skill_name"] == "Python"

    def test_extracted_skill_has_skill_type(self) -> None:
        """ExtractedSkill requires skill_type field (Hard or Soft)."""
        skill: ExtractedSkill = {
            "skill_name": "Communication",
            "skill_type": "Soft",
            "is_required": True,
            "years_requested": None,
        }
        assert skill["skill_type"] == "Soft"

    def test_extracted_skill_has_is_required(self) -> None:
        """ExtractedSkill requires is_required field (bool)."""
        skill: ExtractedSkill = {
            "skill_name": "AWS",
            "skill_type": "Hard",
            "is_required": False,
            "years_requested": None,
        }
        assert skill["is_required"] is False

    def test_extracted_skill_has_years_requested(self) -> None:
        """ExtractedSkill can have years_requested (int or None)."""
        skill: ExtractedSkill = {
            "skill_name": "Python",
            "skill_type": "Hard",
            "is_required": True,
            "years_requested": 5,
        }
        assert skill["years_requested"] == 5

    def test_extracted_skill_years_requested_can_be_none(self) -> None:
        """ExtractedSkill years_requested can be None when not specified."""
        skill: ExtractedSkill = {
            "skill_name": "Python",
            "skill_type": "Hard",
            "is_required": True,
            "years_requested": None,
        }
        assert skill["years_requested"] is None


# =============================================================================
# Text Truncation Tests
# =============================================================================


class TestTextTruncation:
    """Tests for 15k character truncation.

    REQ-007 §6.4: Raw text can be 50k+ chars with HTML/scripts.
    Truncate to 15,000 characters for LLM extraction.
    """

    def test_prompt_includes_truncated_text(self) -> None:
        """Prompt builder includes the provided text."""
        prompt = _build_extraction_prompt("Short job posting text")
        assert "Short job posting text" in prompt

    def test_prompt_has_extraction_instructions(self) -> None:
        """Prompt includes extraction instructions."""
        prompt = _build_extraction_prompt("Any text")
        assert "skill_name" in prompt
        assert "skill_type" in prompt
        assert "is_required" in prompt
        assert "years_requested" in prompt
        assert "culture_text" in prompt

    @pytest.mark.asyncio
    async def test_extract_truncates_long_text(self, mock_llm: MockLLMProvider) -> None:
        """extract_job_data truncates text over 15k characters."""
        # Create text longer than 15k
        long_text = "x" * 20000

        # Configure mock to return valid JSON
        mock_llm.set_response(
            TaskType.EXTRACTION,
            '{"job_title": "Test", "company_name": "Test", "extracted_skills": [], "culture_text": null}',
        )

        result = await extract_job_data(long_text)

        # Should still work (truncation happens before LLM call)
        assert result is not None
        # Description snippet should be 500 chars + "..."
        assert len(result["description_snippet"]) == 503


# =============================================================================
# LLM Extraction Tests
# =============================================================================


class TestLLMExtraction:
    """Tests for LLM-based extraction.

    REQ-007 §6.4: Uses Haiku/cheap model for high-volume extraction.
    """

    @pytest.mark.asyncio
    async def test_extract_calls_llm_with_extraction_task(
        self, mock_llm: MockLLMProvider
    ) -> None:
        """extract_job_data uses TaskType.EXTRACTION for LLM call."""
        mock_llm.set_response(
            TaskType.EXTRACTION,
            '{"job_title": "Engineer", "company_name": "Acme", "extracted_skills": [], "culture_text": null}',
        )

        await extract_job_data("Software Engineer at Acme Corp")

        # Verify TaskType.EXTRACTION was used
        assert mock_llm.last_task == TaskType.EXTRACTION

    @pytest.mark.asyncio
    async def test_extract_parses_job_title(self, mock_llm: MockLLMProvider) -> None:
        """extract_job_data extracts job_title from LLM response."""
        mock_llm.set_response(
            TaskType.EXTRACTION,
            '{"job_title": "Senior Software Engineer", "company_name": "Acme", "extracted_skills": [], "culture_text": null}',
        )

        result = await extract_job_data("Job posting text")

        assert result["job_title"] == "Senior Software Engineer"

    @pytest.mark.asyncio
    async def test_extract_parses_company_name(self, mock_llm: MockLLMProvider) -> None:
        """extract_job_data extracts company_name from LLM response."""
        mock_llm.set_response(
            TaskType.EXTRACTION,
            '{"job_title": "Engineer", "company_name": "Acme Corporation", "extracted_skills": [], "culture_text": null}',
        )

        result = await extract_job_data("Job posting text")

        assert result["company_name"] == "Acme Corporation"

    @pytest.mark.asyncio
    async def test_extract_parses_skills_with_full_structure(
        self, mock_llm: MockLLMProvider
    ) -> None:
        """extract_job_data extracts skills with skill_type, is_required, years_requested."""
        mock_llm.set_response(
            TaskType.EXTRACTION,
            """{
                "job_title": "Engineer",
                "company_name": "Acme",
                "extracted_skills": [
                    {"skill_name": "Python", "skill_type": "Hard", "is_required": true, "years_requested": 5},
                    {"skill_name": "Communication", "skill_type": "Soft", "is_required": true, "years_requested": null},
                    {"skill_name": "AWS", "skill_type": "Hard", "is_required": false, "years_requested": null}
                ],
                "culture_text": null
            }""",
        )

        result = await extract_job_data("Job posting text")

        skills = result["extracted_skills"]
        assert len(skills) == 3

        # Check Python skill
        python_skill = skills[0]
        assert python_skill["skill_name"] == "Python"
        assert python_skill["skill_type"] == "Hard"
        assert python_skill["is_required"] is True
        assert python_skill["years_requested"] == 5

        # Check Communication skill (soft skill)
        comm_skill = skills[1]
        assert comm_skill["skill_type"] == "Soft"
        assert comm_skill["is_required"] is True

        # Check AWS skill (nice-to-have)
        aws_skill = skills[2]
        assert aws_skill["is_required"] is False

    @pytest.mark.asyncio
    async def test_extract_parses_culture_text(self, mock_llm: MockLLMProvider) -> None:
        """extract_job_data extracts culture_text from LLM response."""
        mock_llm.set_response(
            TaskType.EXTRACTION,
            """{
                "job_title": "Engineer",
                "company_name": "Acme",
                "extracted_skills": [],
                "culture_text": "We value innovation and work-life balance. Remote-first culture."
            }""",
        )

        result = await extract_job_data("Job posting text")

        assert (
            result["culture_text"]
            == "We value innovation and work-life balance. Remote-first culture."
        )

    @pytest.mark.asyncio
    async def test_extract_parses_salary_info(self, mock_llm: MockLLMProvider) -> None:
        """extract_job_data extracts salary_min, salary_max, salary_currency."""
        mock_llm.set_response(
            TaskType.EXTRACTION,
            """{
                "job_title": "Engineer",
                "company_name": "Acme",
                "extracted_skills": [],
                "culture_text": null,
                "salary_min": 150000,
                "salary_max": 200000,
                "salary_currency": "USD"
            }""",
        )

        result = await extract_job_data("Job posting text")

        assert result["salary_min"] == 150000
        assert result["salary_max"] == 200000
        assert result["salary_currency"] == "USD"


# =============================================================================
# Response Parsing Tests
# =============================================================================


class TestResponseParsing:
    """Tests for _parse_extraction_response.

    Handles various LLM response formats including markdown code blocks.
    """

    def test_parse_valid_json_response(self) -> None:
        """Parse valid JSON response."""
        response = (
            '{"job_title": "Engineer", "company_name": "Acme", "extracted_skills": []}'
        )
        result = _parse_extraction_response(response)

        assert result["job_title"] == "Engineer"
        assert result["company_name"] == "Acme"

    def test_parse_json_in_markdown_code_block(self) -> None:
        """Parse JSON wrapped in ```json ... ``` block."""
        response = """Here's the extracted data:
```json
{"job_title": "Engineer", "company_name": "Acme", "extracted_skills": []}
```
"""
        result = _parse_extraction_response(response)

        assert result["job_title"] == "Engineer"

    def test_parse_json_in_plain_code_block(self) -> None:
        """Parse JSON wrapped in ``` ... ``` block (no language)."""
        response = """
```
{"job_title": "Engineer", "company_name": "Acme", "extracted_skills": []}
```
"""
        result = _parse_extraction_response(response)

        assert result["job_title"] == "Engineer"

    def test_parse_invalid_json_returns_fallback(self) -> None:
        """Invalid JSON falls back to basic extraction result."""
        response = "This is not valid JSON at all"
        result = _parse_extraction_response(response)

        # Should return a valid ExtractedJobData with null fields
        assert result["job_title"] is None
        assert result["extracted_skills"] == []

    def test_parse_missing_skills_returns_empty_list(self) -> None:
        """Missing extracted_skills field returns empty list."""
        response = '{"job_title": "Engineer", "company_name": "Acme"}'
        result = _parse_extraction_response(response)

        assert result["extracted_skills"] == []

    def test_parse_null_skills_returns_empty_list(self) -> None:
        """null extracted_skills returns empty list."""
        response = '{"job_title": "Engineer", "company_name": "Acme", "extracted_skills": null}'
        result = _parse_extraction_response(response)

        assert result["extracted_skills"] == []


# =============================================================================
# Fallback Extraction Tests
# =============================================================================


class TestFallbackExtraction:
    """Tests for _basic_extraction regex fallback.

    REQ-007 §6.4: Provides basic extraction when LLM fails.
    """

    def test_basic_extraction_extracts_salary_range_usd(self) -> None:
        """Extract salary range with $ and k suffix."""
        text = "Salary: $150k-$200k per year"
        result = _basic_extraction(text)

        assert result["salary_min"] == 150000
        assert result["salary_max"] == 200000
        assert result["salary_currency"] == "USD"

    def test_basic_extraction_extracts_salary_range_full_numbers(self) -> None:
        """Extract salary range with full numbers."""
        text = "Compensation: $150,000 - $200,000"
        result = _basic_extraction(text)

        assert result["salary_min"] == 150000
        assert result["salary_max"] == 200000

    def test_basic_extraction_extracts_employment_type_fulltime(self) -> None:
        """Extract Full-time employment type."""
        text = "This is a Full-time position"
        result = _basic_extraction(text)

        assert result["employment_type"] == "Full-time"

    def test_basic_extraction_extracts_employment_type_contract(self) -> None:
        """Extract Contract employment type."""
        text = "Contract role, 6 months initially"
        result = _basic_extraction(text)

        assert result["employment_type"] == "Contract"

    def test_basic_extraction_extracts_employment_type_parttime(self) -> None:
        """Extract Part-time employment type."""
        text = "Part-time, 20 hours per week"
        result = _basic_extraction(text)

        assert result["employment_type"] == "Part-time"

    def test_basic_extraction_returns_empty_skills(self) -> None:
        """Basic extraction returns empty skills list (regex can't extract skills)."""
        text = "Senior Python Developer with 5+ years experience"
        result = _basic_extraction(text)

        assert result["extracted_skills"] == []

    def test_basic_extraction_returns_null_fields_when_not_found(self) -> None:
        """Basic extraction returns None for fields not found."""
        text = "Generic job posting"
        result = _basic_extraction(text)

        assert result["job_title"] is None
        assert result["company_name"] is None
        assert result["location"] is None
        assert result["culture_text"] is None


# =============================================================================
# Salary Parsing Tests
# =============================================================================


class TestSalaryParsing:
    """Tests for _parse_salary helper."""

    def test_parse_salary_with_k_suffix(self) -> None:
        """Parse salary with k suffix."""
        assert _parse_salary("150k") == 150000
        assert _parse_salary("150K") == 150000

    def test_parse_salary_with_commas(self) -> None:
        """Parse salary with comma separators."""
        assert _parse_salary("150,000") == 150000
        assert _parse_salary("1,500,000") == 1500000

    def test_parse_salary_plain_number(self) -> None:
        """Parse plain salary number."""
        assert _parse_salary("150000") == 150000


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_extract_empty_text_still_works(
        self, mock_llm: MockLLMProvider
    ) -> None:
        """Empty text still returns a valid result."""
        mock_llm.set_response(
            TaskType.EXTRACTION,
            '{"job_title": null, "company_name": null, "extracted_skills": [], "culture_text": null}',
        )

        result = await extract_job_data("")

        assert result is not None
        assert result["extracted_skills"] == []

    @pytest.mark.asyncio
    async def test_extract_includes_description_snippet(
        self, mock_llm: MockLLMProvider
    ) -> None:
        """Extract always includes description_snippet."""
        mock_llm.set_response(
            TaskType.EXTRACTION,
            '{"job_title": "Test", "company_name": "Test", "extracted_skills": [], "culture_text": null}',
        )

        result = await extract_job_data("This is the job posting text.")

        assert "description_snippet" in result
        assert result["description_snippet"] == "This is the job posting text."

    @pytest.mark.asyncio
    async def test_extract_description_snippet_truncates_at_500(
        self, mock_llm: MockLLMProvider
    ) -> None:
        """Description snippet truncates at 500 chars with ellipsis."""
        mock_llm.set_response(
            TaskType.EXTRACTION,
            '{"job_title": "Test", "company_name": "Test", "extracted_skills": [], "culture_text": null}',
        )

        long_text = "x" * 600
        result = await extract_job_data(long_text)

        assert len(result["description_snippet"]) == 503  # 500 + "..."
        assert result["description_snippet"].endswith("...")
