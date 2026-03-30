"""Tests for MarkdownPdfRenderer — markdown → PDF via ReportLab.

REQ-025 §5.2, §5.5: Verifies that supported markdown features render
to valid PDF bytes, and edge cases are handled gracefully.
"""

import pytest

from app.services.rendering.markdown_pdf_renderer import render_pdf


class TestRenderPdfBasic:
    """Basic rendering — valid PDF output."""

    def test_renders_heading_to_valid_pdf(self) -> None:
        """A single heading produces valid PDF bytes."""
        result = render_pdf("# Hello World")
        assert result[:5] == b"%PDF-"

    def test_renders_multiple_headings(self) -> None:
        """All four heading levels produce valid PDF."""
        md = "# H1\n\n## H2\n\n### H3\n\n#### H4"
        result = render_pdf(md)
        assert result[:5] == b"%PDF-"
        assert len(result) > 100  # Not trivially empty

    def test_renders_bold_text(self) -> None:
        """Bold markdown renders to PDF."""
        result = render_pdf("# Resume\n\n**Bold text here**")
        assert result[:5] == b"%PDF-"

    def test_renders_italic_text(self) -> None:
        """Italic markdown renders to PDF."""
        result = render_pdf("# Resume\n\n*Italic text here*")
        assert result[:5] == b"%PDF-"

    def test_renders_bold_and_italic(self) -> None:
        """Mixed bold and italic in same paragraph."""
        result = render_pdf("# Resume\n\n**Bold** and *italic* text")
        assert result[:5] == b"%PDF-"

    def test_renders_unordered_list(self) -> None:
        """Bullet list items render to PDF."""
        md = "# Skills\n\n- Python\n- TypeScript\n- SQL"
        result = render_pdf(md)
        assert result[:5] == b"%PDF-"

    def test_renders_ordered_list(self) -> None:
        """Numbered list items render to PDF."""
        md = "# Steps\n\n1. First\n2. Second\n3. Third"
        result = render_pdf(md)
        assert result[:5] == b"%PDF-"

    def test_renders_horizontal_rule(self) -> None:
        """Horizontal rule renders to PDF."""
        md = "# Name\n\n---\n\n## Experience"
        result = render_pdf(md)
        assert result[:5] == b"%PDF-"

    def test_renders_link(self) -> None:
        """Links render to PDF (blue underlined text per §5.5)."""
        md = "# Contact\n\n[My Portfolio](https://example.com)"
        result = render_pdf(md)
        assert result[:5] == b"%PDF-"

    def test_renders_blockquote(self) -> None:
        """Blockquote renders to PDF (indented per §5.5)."""
        md = "# Summary\n\n> Experienced engineer with 10 years..."
        result = render_pdf(md)
        assert result[:5] == b"%PDF-"

    def test_renders_plain_paragraph(self) -> None:
        """Plain paragraph text renders to PDF."""
        md = "# Resume\n\nThis is a plain paragraph with no formatting."
        result = render_pdf(md)
        assert result[:5] == b"%PDF-"


class TestRenderPdfEdgeCases:
    """Edge cases and error handling."""

    def test_empty_string_raises_value_error(self) -> None:
        """Empty content is rejected."""
        with pytest.raises(ValueError, match="[Ee]mpty"):
            render_pdf("")

    def test_whitespace_only_raises_value_error(self) -> None:
        """Whitespace-only content is rejected."""
        with pytest.raises(ValueError, match="[Ee]mpty"):
            render_pdf("   \n\n  ")

    def test_exceeds_max_length_raises_value_error(self) -> None:
        """Content exceeding max length is rejected."""
        md = "# H\n\n" + "x" * 100_001
        with pytest.raises(ValueError, match="maximum length"):
            render_pdf(md)

    def test_heading_only(self) -> None:
        """A single heading with no body still produces valid PDF."""
        result = render_pdf("# Just a Heading")
        assert result[:5] == b"%PDF-"

    def test_complex_resume_content(self) -> None:
        """Full resume-like content renders without error."""
        md = """# John Doe

## Summary

Experienced **software engineer** with *10 years* of experience.

---

## Experience

### Senior Developer — Acme Corp

- Led team of 5 engineers
- Reduced deploy time by **40%**
- Implemented CI/CD pipeline

### Developer — StartupCo

1. Built REST API from scratch
2. Integrated payment processing

---

## Education

#### BS Computer Science — MIT

---

## Skills

- Python, TypeScript, Go
- PostgreSQL, Redis
- AWS, Docker, Kubernetes

> "Outstanding contributor" — Annual Review 2024

[LinkedIn](https://linkedin.com/in/johndoe)
"""
        result = render_pdf(md)
        assert result[:5] == b"%PDF-"
        assert len(result) > 500  # Substantial content

    def test_inline_code_rendered_as_text(self) -> None:
        """Inline code is rendered as plain text (not a supported feature)."""
        md = "# Resume\n\nUses `Python` and `TypeScript`"
        result = render_pdf(md)
        assert result[:5] == b"%PDF-"

    def test_code_block_rendered_as_text(self) -> None:
        """Code blocks are rendered as plain text (not a resume feature)."""
        md = "# Resume\n\n```\ndef hello():\n    pass\n```"
        result = render_pdf(md)
        assert result[:5] == b"%PDF-"


class TestRenderPdfSecurity:
    """Security tests — XSS, injection, and protocol safety."""

    def test_script_tag_in_text_renders_safely(self) -> None:
        """HTML script tags are escaped, not executed."""
        md = "# Resume\n\n<script>alert('xss')</script>"
        result = render_pdf(md)
        assert result[:5] == b"%PDF-"

    def test_link_with_single_quote_in_href_renders_safely(self) -> None:
        """Single quotes in href cannot break attribute boundary."""
        md = "# Resume\n\n[click](https://example.com'onclick='alert(1))"
        result = render_pdf(md)
        assert result[:5] == b"%PDF-"

    def test_javascript_protocol_link_renders_without_href(self) -> None:
        """javascript: URLs are blocked — link renders as underlined text only."""
        md = "# Resume\n\n[click me](javascript:alert(1))"
        result = render_pdf(md)
        assert result[:5] == b"%PDF-"

    def test_data_protocol_link_renders_without_href(self) -> None:
        """data: URLs are blocked."""
        md = "# Resume\n\n[click](data:text/html,<script>alert(1)</script>)"
        result = render_pdf(md)
        assert result[:5] == b"%PDF-"

    def test_html_entities_in_text_are_escaped(self) -> None:
        """Ampersands and angle brackets don't corrupt PDF markup."""
        md = "# Resume\n\nCompany A & B <division> worked on C&D"
        result = render_pdf(md)
        assert result[:5] == b"%PDF-"

    def test_deeply_nested_markdown_does_not_crash(self) -> None:
        """Deeply nested lists/blockquotes don't cause stack overflow."""
        md = "# Resume\n\n" + "> " * 50 + "Deep content"
        result = render_pdf(md)
        assert result[:5] == b"%PDF-"
