"""Tests for resume template service.

REQ-025 §6.2–§6.4, §8: Tests cover markdown validation logic
used during template creation and update.
"""

import pytest

from app.core.errors import ValidationError
from app.services.rendering.resume_template_service import validate_template_markdown


class TestValidateTemplateMarkdown:
    """Test validate_template_markdown()."""

    def test_accepts_valid_markdown_with_heading(self):
        """Markdown with ATX heading is valid."""
        validate_template_markdown("# My Resume\n\nSome content here.")

    def test_accepts_multiple_heading_levels(self):
        """All ATX heading levels are accepted."""
        validate_template_markdown("## Experience\n\n### Job 1")

    def test_accepts_heading_with_leading_whitespace(self):
        """Leading whitespace before # is tolerated."""
        validate_template_markdown("  # Indented Heading\n\nContent")

    def test_rejects_empty_string(self):
        """Empty string raises ValidationError."""
        with pytest.raises(ValidationError, match="empty"):
            validate_template_markdown("")

    def test_rejects_whitespace_only(self):
        """Whitespace-only content raises ValidationError."""
        with pytest.raises(ValidationError, match="empty"):
            validate_template_markdown("   \n\n  ")

    def test_rejects_no_heading(self):
        """Content without any heading raises ValidationError."""
        with pytest.raises(ValidationError, match="heading"):
            validate_template_markdown("Just some plain text\nwithout any headings.")

    def test_accepts_heading_at_line_start(self):
        """A # at line start always counts as a heading.

        Note: We use a simple line-starts-with-# check, not full AST parsing.
        """
        validate_template_markdown("# Real heading\n\n- item 1")

    def test_accepts_template_with_placeholders(self):
        """Template with {placeholder} markers is valid."""
        content = "# {full_name}\n\n## Experience\n\n- {bullet_1}"
        validate_template_markdown(content)
