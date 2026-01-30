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

    def test_manual_refresh_detected_when_job_search_phrases_used(self) -> None:
        """Returns True when user message contains job search intent phrases."""
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

    def test_manual_refresh_not_detected_when_unrelated_phrases_used(self) -> None:
        """Returns False when user message is unrelated to job searching."""
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

    def test_source_added_trigger_fires_when_new_source_enabled(self) -> None:
        """Returns True when current_sources contains sources not in previous."""
        from app.agents.scouter import is_source_added_trigger

        # No previous sources, now has one
        assert is_source_added_trigger(previous_sources=[], current_sources=["Adzuna"])

        # Had one, now has two
        assert is_source_added_trigger(
            previous_sources=["Adzuna"], current_sources=["Adzuna", "RemoteOK"]
        )

    def test_source_added_trigger_not_fires_when_sources_unchanged(self) -> None:
        """Returns False when no new sources were added."""
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

    def test_patterns_match_when_different_casing_used(self) -> None:
        """Patterns match job search phrases regardless of case."""
        from app.agents.scouter import MANUAL_REFRESH_PATTERNS

        test_phrases = ["FIND NEW JOBS", "Find New Jobs", "find new jobs"]
        for phrase in test_phrases:
            matched = any(p.search(phrase) for p in MANUAL_REFRESH_PATTERNS)
            assert matched, f"Pattern should match (case insensitive): {phrase}"

    def test_patterns_are_valid_compiled_regex(self) -> None:
        """Patterns are pre-compiled regex ready for efficient matching."""
        from app.agents.scouter import MANUAL_REFRESH_PATTERNS

        # Verify patterns can match - the behavior that matters
        assert any(p.search("find jobs") for p in MANUAL_REFRESH_PATTERNS)
        assert any(p.search("refresh my job list") for p in MANUAL_REFRESH_PATTERNS)
        # Verify they're compiled (enables efficient repeated matching)
        for pattern in MANUAL_REFRESH_PATTERNS:
            assert isinstance(pattern, re.Pattern)


# =============================================================================
# Polling Flow Tests (§6.2)
# =============================================================================


class TestMergeResults:
    """Tests for merging job results from multiple sources.

    REQ-007 §6.2: Normalize to common schema after parallel fetch.
    """

    def test_merge_returns_empty_list_when_no_sources_provided(self) -> None:
        """Returns empty list when source_results dict is empty."""
        from app.agents.scouter import merge_results

        result = merge_results({})
        assert result == []

    def test_merge_returns_jobs_when_single_source_provided(self) -> None:
        """Returns all jobs from single source with preserved order."""
        from app.agents.scouter import merge_results

        source_results = {
            "Adzuna": [
                {"external_id": "az-1", "job_title": "Python Developer"},
                {"external_id": "az-2", "job_title": "Data Engineer"},
            ]
        }
        result = merge_results(source_results)
        assert len(result) == 2
        assert result[0]["external_id"] == "az-1"
        assert result[1]["external_id"] == "az-2"

    def test_merge_combines_jobs_when_multiple_sources_provided(self) -> None:
        """Returns all jobs from all sources combined into single list."""
        from app.agents.scouter import merge_results

        source_results = {
            "Adzuna": [{"external_id": "az-1", "job_title": "Python Developer"}],
            "RemoteOK": [{"external_id": "rok-1", "job_title": "Remote Engineer"}],
            "TheMuse": [{"external_id": "tm-1", "job_title": "Product Manager"}],
        }
        result = merge_results(source_results)
        assert len(result) == 3

    def test_merge_excludes_jobs_when_source_returns_empty_list(self) -> None:
        """Sources with empty results contribute zero jobs to merged list."""
        from app.agents.scouter import merge_results

        source_results = {
            "Adzuna": [{"external_id": "az-1", "job_title": "Python Developer"}],
            "RemoteOK": [],  # Empty
            "TheMuse": [{"external_id": "tm-1", "job_title": "Product Manager"}],
        }
        result = merge_results(source_results)
        assert len(result) == 2

    def test_merge_adds_source_name_when_jobs_merged(self) -> None:
        """Each merged job includes source_name field for origin tracking."""
        from app.agents.scouter import merge_results

        source_results = {
            "Adzuna": [{"external_id": "az-1", "job_title": "Python Developer"}],
        }
        result = merge_results(source_results)
        assert result[0]["source_name"] == "Adzuna"


class TestCalculateNextPollTime:
    """Tests for calculating next poll time.

    REQ-007 §6.2: Update polling state after poll completes.
    """

    def test_next_poll_scheduled_24_hours_later_when_daily_frequency(self) -> None:
        """Returns datetime 24 hours after current_time for daily frequency."""
        from app.agents.scouter import calculate_next_poll_time

        now = datetime.now(UTC)
        next_poll = calculate_next_poll_time(now, frequency="daily")

        expected = now + timedelta(hours=24)
        # Allow 1 second tolerance for test execution time
        assert abs((next_poll - expected).total_seconds()) < 1

    def test_next_poll_scheduled_12_hours_later_when_twice_daily_frequency(
        self,
    ) -> None:
        """Returns datetime 12 hours after current_time for twice_daily frequency."""
        from app.agents.scouter import calculate_next_poll_time

        now = datetime.now(UTC)
        next_poll = calculate_next_poll_time(now, frequency="twice_daily")

        expected = now + timedelta(hours=12)
        assert abs((next_poll - expected).total_seconds()) < 1

    def test_next_poll_scheduled_7_days_later_when_weekly_frequency(self) -> None:
        """Returns datetime 7 days after current_time for weekly frequency."""
        from app.agents.scouter import calculate_next_poll_time

        now = datetime.now(UTC)
        next_poll = calculate_next_poll_time(now, frequency="weekly")

        expected = now + timedelta(days=7)
        assert abs((next_poll - expected).total_seconds()) < 1

    def test_next_poll_defaults_to_daily_when_unknown_frequency(self) -> None:
        """Returns datetime 24 hours later when frequency string is unrecognized."""
        from app.agents.scouter import calculate_next_poll_time

        now = datetime.now(UTC)
        next_poll = calculate_next_poll_time(now, frequency="unknown_value")

        expected = now + timedelta(hours=24)
        assert abs((next_poll - expected).total_seconds()) < 1


class TestPollingFlowState:
    """Tests for polling flow state management.

    REQ-007 §6.2: Polling flow orchestration.
    """

    def test_state_initialized_with_empty_lists_when_created(self) -> None:
        """Returns ScouterState dict with user/persona IDs and empty job lists."""
        from app.agents.scouter import create_scouter_state

        state = create_scouter_state(
            user_id="user-123",
            persona_id="persona-456",
            enabled_sources=["Adzuna", "RemoteOK"],
        )

        assert state["user_id"] == "user-123"
        assert state["persona_id"] == "persona-456"
        assert state["enabled_sources"] == ["Adzuna", "RemoteOK"]
        assert state["discovered_jobs"] == []
        assert state["processed_jobs"] == []
        assert state["error_sources"] == []

    def test_source_error_recorded_when_source_fails(self) -> None:
        """Appends source_name to error_sources list in state."""
        from app.agents.scouter import record_source_error

        state = {
            "enabled_sources": ["Adzuna", "RemoteOK"],
            "discovered_jobs": [],
            "processed_jobs": [],
            "error_sources": [],
        }

        updated_state = record_source_error(state, source_name="Adzuna")

        assert "Adzuna" in updated_state["error_sources"]
        assert len(updated_state["error_sources"]) == 1

    def test_source_error_not_duplicated_when_already_recorded(self) -> None:
        """Returns state unchanged if source_name already in error_sources."""
        from app.agents.scouter import record_source_error

        state = {
            "enabled_sources": ["Adzuna", "RemoteOK"],
            "discovered_jobs": [],
            "processed_jobs": [],
            "error_sources": ["Adzuna"],
        }

        updated_state = record_source_error(state, source_name="Adzuna")

        assert updated_state["error_sources"].count("Adzuna") == 1
