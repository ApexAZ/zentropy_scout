"""Tests for the Ghostwriter Agent utility functions.

REQ-007 §8: Ghostwriter Agent

Tests verify:
- Trigger condition detection (auto-draft, manual request, regeneration)
"""


# =============================================================================
# Trigger Condition Tests (§8.1)
# =============================================================================


class TestShouldAutoDraft:
    """Tests for auto-draft trigger condition.

    REQ-007 §8.1: Auto-draft triggers when fit_score >= persona.auto_draft_threshold.
    """

    def test_triggers_when_score_equals_threshold(self) -> None:
        """Auto-draft triggers when fit_score == threshold (boundary)."""
        from app.agents.ghostwriter import should_auto_draft

        assert should_auto_draft(fit_score=90.0, threshold=90) is True

    def test_triggers_when_score_exceeds_threshold(self) -> None:
        """Auto-draft triggers when fit_score > threshold."""
        from app.agents.ghostwriter import should_auto_draft

        assert should_auto_draft(fit_score=95.0, threshold=90) is True

    def test_does_not_trigger_when_score_below_threshold(self) -> None:
        """Auto-draft does NOT trigger when fit_score < threshold."""
        from app.agents.ghostwriter import should_auto_draft

        assert should_auto_draft(fit_score=85.0, threshold=90) is False

    def test_does_not_trigger_when_threshold_is_none(self) -> None:
        """Auto-draft does NOT trigger when threshold is None (disabled)."""
        from app.agents.ghostwriter import should_auto_draft

        assert should_auto_draft(fit_score=95.0, threshold=None) is False

    def test_does_not_trigger_when_fit_score_is_none(self) -> None:
        """Auto-draft does NOT trigger when fit_score is None (not scored)."""
        from app.agents.ghostwriter import should_auto_draft

        assert should_auto_draft(fit_score=None, threshold=90) is False

    def test_does_not_trigger_when_both_none(self) -> None:
        """Auto-draft does NOT trigger when both values are None."""
        from app.agents.ghostwriter import should_auto_draft

        assert should_auto_draft(fit_score=None, threshold=None) is False

    def test_triggers_with_zero_threshold(self) -> None:
        """Auto-draft triggers when threshold is 0 (always draft)."""
        from app.agents.ghostwriter import should_auto_draft

        assert should_auto_draft(fit_score=0.0, threshold=0) is True

    def test_does_not_trigger_with_zero_score_and_positive_threshold(self) -> None:
        """Auto-draft does NOT trigger when score is 0 and threshold > 0."""
        from app.agents.ghostwriter import should_auto_draft

        assert should_auto_draft(fit_score=0.0, threshold=50) is False


class TestIsDraftRequest:
    """Tests for manual draft request detection.

    REQ-007 §8.1: Manual request triggers when user says
    "Draft materials for this job" or similar phrases.
    """

    def test_detects_draft_materials_phrases(self) -> None:
        """Returns True for common draft materials phrases."""
        from app.agents.ghostwriter import is_draft_request

        positive_cases = [
            "Draft materials for this job",
            "draft materials for this job",
            "Draft materials",
            "draft a resume for this job",
            "Draft a cover letter",
            "draft resume",
            "Draft cover letter for this position",
            "Write a resume for this job",
            "write a cover letter",
            "write materials for this role",
            "Generate a resume",
            "generate a cover letter",
            "generate materials for this job",
            "Create a resume for this position",
            "create a cover letter",
            "prepare materials for this job",
            "Prepare a resume",
        ]
        for phrase in positive_cases:
            assert is_draft_request(phrase) is True, f"Should match: {phrase}"

    def test_does_not_detect_unrelated_phrases(self) -> None:
        """Returns False for unrelated messages."""
        from app.agents.ghostwriter import is_draft_request

        negative_cases = [
            "What jobs have I applied to?",
            "Show me my applications",
            "Find new jobs",
            "How is my resume?",
            "Hello",
            "",
            "Tell me about the draft",
            "What materials do I need?",
        ]
        for phrase in negative_cases:
            assert is_draft_request(phrase) is False, f"Should NOT match: {phrase}"

    def test_handles_empty_message(self) -> None:
        """Returns False for empty string."""
        from app.agents.ghostwriter import is_draft_request

        assert is_draft_request("") is False


class TestIsRegenerationRequest:
    """Tests for regeneration request detection.

    REQ-007 §8.1: Regeneration triggers when user says
    "Try a different approach" or similar feedback phrases.
    """

    def test_detects_regeneration_phrases(self) -> None:
        """Returns True for common regeneration phrases."""
        from app.agents.ghostwriter import is_regeneration_request

        positive_cases = [
            "Try a different approach",
            "try a different approach",
            "Try again",
            "try again please",
            "Regenerate",
            "regenerate the resume",
            "regenerate the cover letter",
            "Redo this",
            "redo the resume",
            "Start over",
            "start over with the cover letter",
            "Give me another version",
            "give me another version please",
            "Make it different",
            "Try something else",
        ]
        for phrase in positive_cases:
            assert is_regeneration_request(phrase) is True, f"Should match: {phrase}"

    def test_does_not_detect_unrelated_phrases(self) -> None:
        """Returns False for unrelated messages."""
        from app.agents.ghostwriter import is_regeneration_request

        negative_cases = [
            "Draft materials for this job",
            "What jobs have I applied to?",
            "Find new jobs",
            "Hello",
            "",
            "This is good, approve it",
            "I like this version",
            "Can you try to find a job?",
        ]
        for phrase in negative_cases:
            assert is_regeneration_request(phrase) is False, (
                f"Should NOT match: {phrase}"
            )

    def test_handles_empty_message(self) -> None:
        """Returns False for empty string."""
        from app.agents.ghostwriter import is_regeneration_request

        assert is_regeneration_request("") is False


# =============================================================================
# Input Truncation Tests (Security — §5)
# =============================================================================


class TestInputTruncation:
    """Tests that regex-matched functions truncate input to prevent ReDoS."""

    def test_is_draft_request_ignores_pattern_beyond_2000_chars(self) -> None:
        """is_draft_request truncates so patterns beyond 2000 chars are ignored."""
        from app.agents.ghostwriter import is_draft_request

        padding = "x" * 2000
        message = padding + " draft a resume"
        assert is_draft_request(message) is False

    def test_is_draft_request_matches_within_2000_chars(self) -> None:
        """is_draft_request still matches patterns within the first 2000 chars."""
        from app.agents.ghostwriter import is_draft_request

        message = "draft a resume" + " x" * 1000
        assert is_draft_request(message) is True

    def test_is_regeneration_request_ignores_pattern_beyond_2000_chars(self) -> None:
        """is_regeneration_request truncates so patterns beyond 2000 chars are ignored."""
        from app.agents.ghostwriter import is_regeneration_request

        padding = "x" * 2000
        message = padding + " try again"
        assert is_regeneration_request(message) is False

    def test_is_regeneration_request_matches_within_2000_chars(self) -> None:
        """is_regeneration_request still matches patterns within the first 2000 chars."""
        from app.agents.ghostwriter import is_regeneration_request

        message = "try again" + " x" * 1000
        assert is_regeneration_request(message) is True
