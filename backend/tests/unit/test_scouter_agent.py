"""Tests for the Scouter Agent.

REQ-007 §6: Scouter Agent

Tests verify:
- Trigger condition detection (scheduled poll, manual refresh, source added)
- Polling flow
- Source adapters
- Skill & culture extraction
- Ghost detection
- Deduplication logic
- Error handling
"""

import re
from datetime import UTC, datetime, timedelta

# =============================================================================
# Trigger Condition Tests (§6.1)
# =============================================================================


class TestTriggerConditions:
    """Tests for Scouter trigger condition detection.

    REQ-007 §6.1: Scouter triggers on:
    - Scheduled poll (based on Persona.polling_frequency)
    - Manual refresh (user clicks refresh or says "Find new jobs")
    - Source added (user enables a new job source)
    """

    def test_should_poll_when_next_poll_time_passed(self) -> None:
        """Scheduled poll triggers when next_poll_at is in the past."""
        from app.agents.scouter import should_poll

        # Poll time is in the past
        past_time = datetime.now(UTC) - timedelta(hours=1)
        assert should_poll(next_poll_at=past_time) is True

    def test_should_not_poll_when_next_poll_time_future(self) -> None:
        """Scheduled poll does NOT trigger when next_poll_at is in the future."""
        from app.agents.scouter import should_poll

        # Poll time is in the future
        future_time = datetime.now(UTC) + timedelta(hours=1)
        assert should_poll(next_poll_at=future_time) is False

    def test_should_poll_when_never_polled(self) -> None:
        """Scheduled poll triggers when next_poll_at is None (never polled)."""
        from app.agents.scouter import should_poll

        # Never polled before
        assert should_poll(next_poll_at=None) is True

    def test_is_manual_refresh_request_positive_cases(self) -> None:
        """Manual refresh detection matches expected phrases."""
        from app.agents.scouter import is_manual_refresh_request

        positive_cases = [
            "Find new jobs",
            "find new jobs please",
            "Find jobs for me",
            "find me some jobs",
            "search for jobs",
            "Search for new opportunities",
            "look for jobs",
            "Look for new positions",
            "refresh jobs",
            "Refresh my job feed",
            "update jobs",
            "Update my job list",
            "scan for jobs",
            "Scan job boards",
            "check for new jobs",
            "Check for opportunities",
        ]
        for phrase in positive_cases:
            assert is_manual_refresh_request(phrase) is True, f"Should match: {phrase}"

    def test_is_manual_refresh_request_negative_cases(self) -> None:
        """Manual refresh detection does NOT match unrelated phrases."""
        from app.agents.scouter import is_manual_refresh_request

        negative_cases = [
            "What jobs have I applied to?",
            "Show me my applications",
            "Update my resume",
            "Find my old cover letter",
            "How do I search?",
            "What is a job?",
            "Hello",
            "",
        ]
        for phrase in negative_cases:
            assert (
                is_manual_refresh_request(phrase) is False
            ), f"Should NOT match: {phrase}"

    def test_is_source_added_trigger(self) -> None:
        """Source added trigger detects newly enabled sources."""
        from app.agents.scouter import is_source_added_trigger

        # No previous sources, now has one
        assert is_source_added_trigger(previous_sources=[], current_sources=["Adzuna"])

        # Had one, now has two
        assert is_source_added_trigger(
            previous_sources=["Adzuna"], current_sources=["Adzuna", "RemoteOK"]
        )

    def test_is_source_added_trigger_no_change(self) -> None:
        """Source added trigger does NOT fire when no sources added."""
        from app.agents.scouter import is_source_added_trigger

        # Same sources
        assert not is_source_added_trigger(
            previous_sources=["Adzuna"], current_sources=["Adzuna"]
        )

        # Source removed (not added)
        assert not is_source_added_trigger(
            previous_sources=["Adzuna", "RemoteOK"], current_sources=["Adzuna"]
        )

        # Both empty
        assert not is_source_added_trigger(previous_sources=[], current_sources=[])


class TestManualRefreshPatterns:
    """Tests for the MANUAL_REFRESH_PATTERNS regex patterns.

    REQ-007 §6.1: Manual refresh triggers.
    """

    def test_patterns_are_case_insensitive(self) -> None:
        """Manual refresh patterns should match regardless of case."""
        from app.agents.scouter import MANUAL_REFRESH_PATTERNS

        test_phrases = ["FIND NEW JOBS", "Find New Jobs", "find new jobs"]
        for phrase in test_phrases:
            matched = any(p.search(phrase) for p in MANUAL_REFRESH_PATTERNS)
            assert matched, f"Pattern should match (case insensitive): {phrase}"

    def test_patterns_exist_and_are_compiled(self) -> None:
        """Manual refresh patterns should be pre-compiled regex patterns."""
        from app.agents.scouter import MANUAL_REFRESH_PATTERNS

        assert len(MANUAL_REFRESH_PATTERNS) > 0
        for pattern in MANUAL_REFRESH_PATTERNS:
            assert isinstance(pattern, re.Pattern)
