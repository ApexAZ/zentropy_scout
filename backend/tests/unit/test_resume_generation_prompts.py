"""Tests for resume_generation prompts — system prompt + builder function.

REQ-026 §4.4: The prompt is composed from template structure, persona data,
target role, page limit, emphasis preference, section selections, and voice
profile. Output format: raw markdown following the template structure.

REQ-026 §4.5: Generation constraints — truthfulness, no fabrication, voice
consistency, template adherence, page limit respect.

Tests verify:
- System prompt contains required constraint keywords
- Builder function produces prompt with all expected XML sections
- Sanitization is applied to user-controlled fields
- Page limit maps to correct word count target
- Emphasis preference is included in prompt
- Section selections control which sections appear
- Voice profile block is embedded in prompt
- Missing optional fields handled gracefully
- Truncation applied to oversized fields
"""

from unittest.mock import patch

from app.prompts.resume_generation import (
    RESUME_GENERATION_SYSTEM_PROMPT,
    build_resume_generation_prompt,
)

# Module path for patching sanitization
_SANITIZE_TARGET = "app.prompts.resume_generation.sanitize_llm_input"


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------


class TestSystemPrompt:
    """Verify system prompt contains required constraint language."""

    def test_contains_truthfulness_constraint(self) -> None:
        assert (
            "truthful" in RESUME_GENERATION_SYSTEM_PROMPT.lower()
            or "only use facts" in RESUME_GENERATION_SYSTEM_PROMPT.lower()
        )

    def test_contains_no_fabrication_constraint(self) -> None:
        prompt_lower = RESUME_GENERATION_SYSTEM_PROMPT.lower()
        assert "fabricat" in prompt_lower or "invent" in prompt_lower

    def test_contains_voice_consistency_constraint(self) -> None:
        prompt_lower = RESUME_GENERATION_SYSTEM_PROMPT.lower()
        assert "voice" in prompt_lower

    def test_contains_markdown_output_format(self) -> None:
        prompt_lower = RESUME_GENERATION_SYSTEM_PROMPT.lower()
        assert "markdown" in prompt_lower

    def test_contains_template_adherence(self) -> None:
        prompt_lower = RESUME_GENERATION_SYSTEM_PROMPT.lower()
        assert "template" in prompt_lower or "structure" in prompt_lower


# ---------------------------------------------------------------------------
# Builder — Required Fields
# ---------------------------------------------------------------------------


def _build_prompt(**overrides: object) -> str:
    """Build a prompt with sensible defaults, overriding as needed."""
    defaults: dict = {
        "template_markdown": "# {full_name}\n\n## Summary\n\n## Experience",
        "persona_summary": "Experienced software engineer with 10 years.",
        "persona_name": "Jane Doe",
        "persona_jobs_text": "### Senior Engineer — Acme Corp\nJan 2020 – Present\n- Led backend migration",
        "persona_education_text": "### B.S. Computer Science — State University\n2018",
        "persona_skills_text": "Python, PostgreSQL, Docker",
        "persona_certifications_text": "- AWS Solutions Architect",
        "page_limit": 1,
        "emphasis": "balanced",
        "include_sections": ["summary", "experience", "education", "skills"],
        "voice_profile_block": "<voice_profile>\nTONE: Professional\n</voice_profile>",
    }
    defaults.update(overrides)
    return build_resume_generation_prompt(**defaults)


class TestBuilderRequiredSections:
    """Verify builder output contains all expected sections."""

    def test_contains_template_structure(self) -> None:
        result = _build_prompt()
        assert "<template_structure>" in result
        assert "</template_structure>" in result

    def test_contains_persona_data(self) -> None:
        result = _build_prompt()
        assert "<persona_data>" in result
        assert "</persona_data>" in result

    def test_contains_voice_profile(self) -> None:
        result = _build_prompt()
        assert "<voice_profile>" in result

    def test_contains_generation_instructions(self) -> None:
        result = _build_prompt()
        assert "<generation_instructions>" in result

    def test_persona_name_in_prompt(self) -> None:
        result = _build_prompt(persona_name="Alice Smith")
        assert "Alice Smith" in result

    def test_persona_summary_in_prompt(self) -> None:
        result = _build_prompt(persona_summary="Expert in distributed systems.")
        assert "Expert in distributed systems." in result

    def test_persona_jobs_in_prompt(self) -> None:
        result = _build_prompt(persona_jobs_text="### Lead Dev — BigCo")
        assert "### Lead Dev — BigCo" in result

    def test_persona_education_in_prompt(self) -> None:
        result = _build_prompt(persona_education_text="### Ph.D. — MIT")
        assert "### Ph.D. — MIT" in result

    def test_persona_skills_in_prompt(self) -> None:
        result = _build_prompt(persona_skills_text="Rust, Go, Kubernetes")
        assert "Rust, Go, Kubernetes" in result

    def test_persona_certifications_in_prompt(self) -> None:
        result = _build_prompt(persona_certifications_text="- CKA\n- PMP")
        assert "- CKA" in result


# ---------------------------------------------------------------------------
# Builder — Page Limit Mapping
# ---------------------------------------------------------------------------


class TestPageLimitMapping:
    """Verify page limit maps to correct word count target."""

    def test_one_page_target(self) -> None:
        result = _build_prompt(page_limit=1)
        assert "350" in result

    def test_two_page_target(self) -> None:
        result = _build_prompt(page_limit=2)
        assert "700" in result

    def test_three_page_target(self) -> None:
        result = _build_prompt(page_limit=3)
        assert "1050" in result


# ---------------------------------------------------------------------------
# Builder — Emphasis
# ---------------------------------------------------------------------------


class TestEmphasis:
    """Verify emphasis preference appears in the prompt."""

    def test_technical_emphasis(self) -> None:
        result = _build_prompt(emphasis="technical")
        assert "technical" in result.lower()

    def test_leadership_emphasis(self) -> None:
        result = _build_prompt(emphasis="leadership")
        assert "leadership" in result.lower()

    def test_balanced_emphasis(self) -> None:
        result = _build_prompt(emphasis="balanced")
        assert "balanced" in result.lower()

    def test_industry_specific_emphasis(self) -> None:
        result = _build_prompt(emphasis="industry-specific")
        assert "industry-specific" in result.lower()


# ---------------------------------------------------------------------------
# Builder — Section Selections
# ---------------------------------------------------------------------------


class TestSectionSelections:
    """Verify section selections control prompt content."""

    def test_all_sections_included(self) -> None:
        result = _build_prompt(
            include_sections=[
                "summary",
                "experience",
                "education",
                "skills",
                "certifications",
            ],
        )
        assert "summary" in result.lower()
        assert "experience" in result.lower()
        assert "education" in result.lower()
        assert "skills" in result.lower()
        assert "certifications" in result.lower()

    def test_subset_sections(self) -> None:
        result = _build_prompt(
            include_sections=["summary", "experience"],
        )
        instructions = result.split("<generation_instructions>")[1]
        assert "summary" in instructions.lower()
        assert "experience" in instructions.lower()


# ---------------------------------------------------------------------------
# Builder — Voice Profile
# ---------------------------------------------------------------------------


class TestVoiceProfileEmbedding:
    """Verify voice profile block is embedded as-is."""

    def test_voice_block_embedded(self) -> None:
        block = (
            "<voice_profile>\nTONE: Casual\nSTYLE: Short sentences\n</voice_profile>"
        )
        result = _build_prompt(voice_profile_block=block)
        assert block in result

    def test_empty_voice_block_handled(self) -> None:
        result = _build_prompt(voice_profile_block="")
        # Should not crash, prompt should still be valid
        assert "<persona_data>" in result


# ---------------------------------------------------------------------------
# Builder — Sanitization
# ---------------------------------------------------------------------------


class TestSanitization:
    """Verify sanitization is applied to user-controlled fields."""

    def test_persona_name_sanitized(self) -> None:
        with patch(_SANITIZE_TARGET, side_effect=lambda x: f"[CLEAN]{x}") as mock:
            result = _build_prompt(persona_name="Jane")
            # sanitize_llm_input should have been called
            assert mock.called
            assert "[CLEAN]Jane" in result

    def test_persona_summary_sanitized(self) -> None:
        with patch(_SANITIZE_TARGET, side_effect=lambda x: f"[CLEAN]{x}") as mock:
            _build_prompt(persona_summary="My summary")
            # Verify it was called with the summary
            call_args = [str(c) for c in mock.call_args_list]
            assert any("My summary" in arg for arg in call_args)

    def test_template_markdown_sanitized(self) -> None:
        with patch(_SANITIZE_TARGET, side_effect=lambda x: f"[CLEAN]{x}") as mock:
            _build_prompt(template_markdown="# Resume")
            call_args = [str(c) for c in mock.call_args_list]
            assert any("# Resume" in arg for arg in call_args)


# ---------------------------------------------------------------------------
# Builder — Truncation
# ---------------------------------------------------------------------------


class TestTruncation:
    """Verify oversized fields are truncated."""

    def test_long_summary_truncated(self) -> None:
        long_summary = "x" * 10000
        result = _build_prompt(persona_summary=long_summary)
        # Should not contain the full 10k string
        assert len(result) < 15000

    def test_long_jobs_text_truncated(self) -> None:
        long_jobs = "y" * 20000
        result = _build_prompt(persona_jobs_text=long_jobs)
        assert len(result) < 30000
