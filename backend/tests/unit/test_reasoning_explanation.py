"""Tests for reasoning explanation service.

REQ-007 §8.7: Reasoning Explanation
REQ-010 §9: Agent Reasoning Output

The format_agent_reasoning function produces a user-facing markdown
explanation of generation choices — resume tailoring and story selection.
"""

from app.services.reasoning_explanation import (
    ReasoningStory,
    format_agent_reasoning,
)

# =============================================================================
# Helpers
# =============================================================================


def _story(
    title: str = "Led cloud migration",
    rationale: str = "Demonstrates cloud, AWS; quantified impact",
) -> ReasoningStory:
    """Create a ReasoningStory with defaults for concise tests."""
    return ReasoningStory(title=title, rationale=rationale)


# =============================================================================
# Header Tests
# =============================================================================


class TestHeader:
    """Tests for the opening header line."""

    def test_includes_job_title_and_company(self) -> None:
        """Header should include the job title and company name in bold."""
        result = format_agent_reasoning(
            job_title="Agile Coach",
            company_name="Innovate Corp",
            tailoring_action="use_base",
            tailoring_signal_details=[],
            stories=[],
        )

        assert "**Agile Coach**" in result
        assert "**Innovate Corp**" in result

    def test_header_is_first_line(self) -> None:
        """Header should be the first line of output."""
        result = format_agent_reasoning(
            job_title="Engineer",
            company_name="Acme",
            tailoring_action="use_base",
            tailoring_signal_details=[],
            stories=[],
        )

        first_line = result.split("\n")[0]
        assert "**Engineer**" in first_line
        assert "**Acme**" in first_line


# =============================================================================
# Resume Tailoring Section Tests
# =============================================================================


class TestResumeTailoringSection:
    """Tests for the resume tailoring explanation section."""

    def test_shows_adjustments_header_when_tailored(self) -> None:
        """Should show 'Resume Adjustments' when action is create_variant."""
        result = format_agent_reasoning(
            job_title="Engineer",
            company_name="Acme",
            tailoring_action="create_variant",
            tailoring_signal_details=["Added emphasis on SAFe"],
            stories=[],
        )

        assert "**Resume Adjustments:**" in result

    def test_shows_signal_details_as_bullets(self) -> None:
        """Each signal detail should appear as a bullet point."""
        details = [
            "Added emphasis on SAFe and enterprise transformation",
            "Reordered bullets to lead with SAFe implementation",
        ]
        result = format_agent_reasoning(
            job_title="Engineer",
            company_name="Acme",
            tailoring_action="create_variant",
            tailoring_signal_details=details,
            stories=[],
        )

        assert "- Added emphasis on SAFe and enterprise transformation" in result
        assert "- Reordered bullets to lead with SAFe implementation" in result

    def test_limits_signals_to_three(self) -> None:
        """Should show at most 3 signal details per REQ-010 §9.1."""
        details = [
            "Signal 1",
            "Signal 2",
            "Signal 3",
            "Signal 4",
        ]
        result = format_agent_reasoning(
            job_title="Engineer",
            company_name="Acme",
            tailoring_action="create_variant",
            tailoring_signal_details=details,
            stories=[],
        )

        assert "- Signal 1" in result
        assert "- Signal 2" in result
        assert "- Signal 3" in result
        assert "Signal 4" not in result

    def test_shows_no_changes_when_base_used(self) -> None:
        """Should show 'no changes needed' when action is use_base."""
        result = format_agent_reasoning(
            job_title="Engineer",
            company_name="Acme",
            tailoring_action="use_base",
            tailoring_signal_details=[],
            stories=[],
        )

        assert "no changes needed" in result.lower()

    def test_no_changes_message_does_not_show_adjustments_header(self) -> None:
        """Should not show 'Resume Adjustments' header when using base."""
        result = format_agent_reasoning(
            job_title="Engineer",
            company_name="Acme",
            tailoring_action="use_base",
            tailoring_signal_details=[],
            stories=[],
        )

        assert "**Resume Adjustments:**" not in result


# =============================================================================
# Cover Letter Stories Section Tests
# =============================================================================


class TestCoverLetterStoriesSection:
    """Tests for the cover letter stories explanation section."""

    def test_shows_stories_header(self) -> None:
        """Should show 'Cover Letter Stories' header when stories exist."""
        result = format_agent_reasoning(
            job_title="Engineer",
            company_name="Acme",
            tailoring_action="use_base",
            tailoring_signal_details=[],
            stories=[_story()],
        )

        assert "**Cover Letter Stories:**" in result

    def test_shows_story_title_in_italic(self) -> None:
        """Each story title should appear in italics."""
        result = format_agent_reasoning(
            job_title="Engineer",
            company_name="Acme",
            tailoring_action="use_base",
            tailoring_signal_details=[],
            stories=[_story(title="Turned around failing project")],
        )

        assert "*Turned around failing project*" in result

    def test_shows_story_rationale(self) -> None:
        """Each story should include its selection rationale."""
        result = format_agent_reasoning(
            job_title="Engineer",
            company_name="Acme",
            tailoring_action="use_base",
            tailoring_signal_details=[],
            stories=[_story(rationale="Demonstrates leadership; aligns with culture")],
        )

        assert "Demonstrates leadership; aligns with culture" in result

    def test_shows_multiple_stories(self) -> None:
        """Should show all selected stories."""
        stories = [
            _story(title="Story A", rationale="Rationale A"),
            _story(title="Story B", rationale="Rationale B"),
        ]
        result = format_agent_reasoning(
            job_title="Engineer",
            company_name="Acme",
            tailoring_action="use_base",
            tailoring_signal_details=[],
            stories=stories,
        )

        assert "*Story A*" in result
        assert "Rationale A" in result
        assert "*Story B*" in result
        assert "Rationale B" in result

    def test_no_stories_section_when_empty(self) -> None:
        """Should not show stories header when no stories selected."""
        result = format_agent_reasoning(
            job_title="Engineer",
            company_name="Acme",
            tailoring_action="use_base",
            tailoring_signal_details=[],
            stories=[],
        )

        assert "**Cover Letter Stories:**" not in result


# =============================================================================
# Review Prompt Tests
# =============================================================================


class TestReviewPrompt:
    """Tests for the closing review prompt."""

    def test_ends_with_review_prompt(self) -> None:
        """Output should end with the review prompt."""
        result = format_agent_reasoning(
            job_title="Engineer",
            company_name="Acme",
            tailoring_action="use_base",
            tailoring_signal_details=[],
            stories=[_story()],
        )

        assert result.strip().endswith("Ready for your review!")


# =============================================================================
# Combined Output Tests
# =============================================================================


class TestCombinedOutput:
    """Tests for complete reasoning output matching REQ-010 §9.2 example."""

    def test_full_example_with_tailoring_and_stories(self) -> None:
        """Full output with tailoring and stories per REQ-010 §9.2."""
        stories = [
            _story(
                title="Turned around failing project",
                rationale="Demonstrates leadership; aligns with company culture",
            ),
            _story(
                title="Scaled Agile adoption",
                rationale="Demonstrates SAFe, Agile Coaching; quantified impact",
            ),
        ]
        result = format_agent_reasoning(
            job_title="Agile Coach",
            company_name="Innovate Corp",
            tailoring_action="create_variant",
            tailoring_signal_details=[
                'Summary missing key terms: added emphasis on "SAFe" and '
                '"enterprise transformation"',
                "Reordered bullets in TechCorp role to lead with SAFe "
                "implementation (was position 4)",
            ],
            stories=stories,
        )

        assert "**Agile Coach**" in result
        assert "**Innovate Corp**" in result
        assert "**Resume Adjustments:**" in result
        assert "SAFe" in result
        assert "*Turned around failing project*" in result
        assert "*Scaled Agile adoption*" in result
        assert "Ready for your review!" in result

    def test_minimal_output_no_tailoring_no_stories(self) -> None:
        """Minimal output with no tailoring and no stories."""
        result = format_agent_reasoning(
            job_title="Analyst",
            company_name="DataCo",
            tailoring_action="use_base",
            tailoring_signal_details=[],
            stories=[],
        )

        assert "**Analyst**" in result
        assert "**DataCo**" in result
        assert "no changes needed" in result.lower()
        assert "Ready for your review!" in result


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and input validation."""

    def test_empty_job_title(self) -> None:
        """Should handle empty job title gracefully."""
        result = format_agent_reasoning(
            job_title="",
            company_name="Acme",
            tailoring_action="use_base",
            tailoring_signal_details=[],
            stories=[],
        )

        # Should still produce valid output
        assert "**Acme**" in result
        assert "Ready for your review!" in result

    def test_empty_company_name(self) -> None:
        """Should handle empty company name gracefully."""
        result = format_agent_reasoning(
            job_title="Engineer",
            company_name="",
            tailoring_action="use_base",
            tailoring_signal_details=[],
            stories=[],
        )

        assert "**Engineer**" in result
        assert "Ready for your review!" in result

    def test_empty_signal_detail_string(self) -> None:
        """Should skip empty signal detail strings."""
        result = format_agent_reasoning(
            job_title="Engineer",
            company_name="Acme",
            tailoring_action="create_variant",
            tailoring_signal_details=["Real signal", "", "Another signal"],
            stories=[],
        )

        assert "- Real signal" in result
        assert "- Another signal" in result
        # Should not have an empty bullet
        assert "- \n" not in result

    def test_empty_story_title(self) -> None:
        """Should handle story with empty title."""
        result = format_agent_reasoning(
            job_title="Engineer",
            company_name="Acme",
            tailoring_action="use_base",
            tailoring_signal_details=[],
            stories=[_story(title="", rationale="Some rationale")],
        )

        assert "Some rationale" in result

    def test_empty_story_rationale(self) -> None:
        """Should handle story with empty rationale."""
        result = format_agent_reasoning(
            job_title="Engineer",
            company_name="Acme",
            tailoring_action="use_base",
            tailoring_signal_details=[],
            stories=[_story(title="Story Title", rationale="")],
        )

        assert "*Story Title*" in result

    def test_returns_string(self) -> None:
        """Should always return a string."""
        result = format_agent_reasoning(
            job_title="Engineer",
            company_name="Acme",
            tailoring_action="use_base",
            tailoring_signal_details=[],
            stories=[],
        )

        assert isinstance(result, str)
        assert len(result) > 0

    def test_unknown_tailoring_action_treated_as_use_base(self) -> None:
        """Unknown tailoring action should be treated like use_base."""
        result = format_agent_reasoning(
            job_title="Engineer",
            company_name="Acme",
            tailoring_action="unknown_action",
            tailoring_signal_details=[],
            stories=[],
        )

        assert "no changes needed" in result.lower()
        assert "**Resume Adjustments:**" not in result


# =============================================================================
# Safety Bound Tests
# =============================================================================


class TestSanitization:
    """Tests for text sanitization in reasoning output."""

    def test_strips_html_angle_brackets(self) -> None:
        """Should strip < and > from user-controlled text."""
        result = format_agent_reasoning(
            job_title="<script>alert(1)</script>Engineer",
            company_name="Acme<br>Corp",
            tailoring_action="use_base",
            tailoring_signal_details=[],
            stories=[],
        )

        assert "<" not in result
        assert ">" not in result
        assert "script" in result  # Text preserved, just brackets removed

    def test_strips_newlines_from_values(self) -> None:
        """Should replace newlines with spaces to prevent structure injection."""
        result = format_agent_reasoning(
            job_title="Engineer\nEvil Header",
            company_name="Acme",
            tailoring_action="use_base",
            tailoring_signal_details=[],
            stories=[],
        )

        assert "\n" not in result.split("\n")[0].replace("**", "").split("at")[0]
        assert "Engineer Evil Header" in result

    def test_sanitizes_story_titles(self) -> None:
        """Should sanitize story titles embedded in markdown."""
        result = format_agent_reasoning(
            job_title="Engineer",
            company_name="Acme",
            tailoring_action="use_base",
            tailoring_signal_details=[],
            stories=[_story(title="<img>Bad Story")],
        )

        assert "<" not in result
        assert "imgBad Story" in result

    def test_sanitizes_signal_details(self) -> None:
        """Should sanitize signal detail text."""
        result = format_agent_reasoning(
            job_title="Engineer",
            company_name="Acme",
            tailoring_action="create_variant",
            tailoring_signal_details=["Normal detail", "<script>evil</script>"],
            stories=[],
        )

        assert "<" not in result

    def test_truncates_long_text(self) -> None:
        """Should truncate excessively long text values."""
        long_title = "A" * 1000
        result = format_agent_reasoning(
            job_title=long_title,
            company_name="Acme",
            tailoring_action="use_base",
            tailoring_signal_details=[],
            stories=[],
        )

        # The title in the output should be bounded (500 chars max)
        assert "A" * 501 not in result


class TestSafetyBounds:
    """Tests for input safety bounds."""

    def test_limits_stories_to_ten(self) -> None:
        """Should not render more than 10 stories (safety bound)."""
        stories = [_story(title=f"Story {i}") for i in range(15)]
        result = format_agent_reasoning(
            job_title="Engineer",
            company_name="Acme",
            tailoring_action="use_base",
            tailoring_signal_details=[],
            stories=stories,
        )

        assert "*Story 9*" in result
        assert "*Story 10*" not in result
