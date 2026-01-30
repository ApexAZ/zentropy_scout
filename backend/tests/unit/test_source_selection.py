"""Tests for agent source selection logic.

REQ-003 §4.3: Agent Source Selection.

Tests verify:
1. Remote preference prioritizes RemoteOK
2. Government target roles prioritize USAJobs
3. General case returns all enabled sources
4. Reasoning is provided for source selection
"""

from app.services.source_selection import (
    SourcePriority,
    SourceSelectionResult,
    prioritize_sources,
)

# =============================================================================
# Source Prioritization Tests
# =============================================================================


class TestPrioritizeSources:
    """Tests for prioritize_sources function.

    REQ-003 §4.3: Agent selects sources based on Persona.
    """

    def test_returns_all_enabled_sources_when_no_preference_signals(self) -> None:
        """Returns all enabled sources when no special preferences."""
        enabled_sources = ["Adzuna", "TheMuse", "RemoteOK"]

        result = prioritize_sources(
            enabled_sources=enabled_sources,
            remote_preference="No Preference",
            target_roles=[],
        )

        assert isinstance(result, SourceSelectionResult)
        assert set(result.prioritized_sources) == set(enabled_sources)

    def test_prioritizes_remoteok_when_remote_only_preference(self) -> None:
        """RemoteOK is first when remote_preference is 'Remote Only'."""
        enabled_sources = ["Adzuna", "TheMuse", "RemoteOK"]

        result = prioritize_sources(
            enabled_sources=enabled_sources,
            remote_preference="Remote Only",
            target_roles=[],
        )

        # RemoteOK should be first
        assert result.prioritized_sources[0] == "RemoteOK"
        # All sources should still be included
        assert set(result.prioritized_sources) == set(enabled_sources)

    def test_prioritizes_usajobs_when_target_roles_include_government(self) -> None:
        """USAJobs is prioritized when target_roles include government."""
        enabled_sources = ["Adzuna", "TheMuse", "USAJobs"]
        target_roles = [
            {"title": "Software Engineer", "sector": "Government"},
        ]

        result = prioritize_sources(
            enabled_sources=enabled_sources,
            remote_preference="No Preference",
            target_roles=target_roles,
        )

        # USAJobs should be first
        assert result.prioritized_sources[0] == "USAJobs"
        # All sources should still be included
        assert set(result.prioritized_sources) == set(enabled_sources)

    def test_prioritizes_usajobs_when_target_role_is_government_string(self) -> None:
        """USAJobs is prioritized when target_roles contains 'government'."""
        enabled_sources = ["Adzuna", "USAJobs"]
        # Sometimes target_roles might be simple strings
        target_roles = ["Government Analyst", "Policy Advisor"]

        result = prioritize_sources(
            enabled_sources=enabled_sources,
            remote_preference="No Preference",
            target_roles=target_roles,
        )

        # USAJobs should be first because "government" appears in role string
        assert result.prioritized_sources[0] == "USAJobs"

    def test_prioritizes_both_sources_when_remote_only_and_government(self) -> None:
        """Both RemoteOK and USAJobs prioritized when both conditions match."""
        enabled_sources = ["Adzuna", "TheMuse", "RemoteOK", "USAJobs"]
        target_roles = [{"title": "Federal IT Specialist", "sector": "Government"}]

        result = prioritize_sources(
            enabled_sources=enabled_sources,
            remote_preference="Remote Only",
            target_roles=target_roles,
        )

        # Both prioritized sources should be first (order between them not specified)
        first_two = set(result.prioritized_sources[:2])
        assert first_two == {"RemoteOK", "USAJobs"}

    def test_excludes_remoteok_from_priority_when_not_enabled(self) -> None:
        """Does not add RemoteOK if not enabled, even with remote preference."""
        enabled_sources = ["Adzuna", "TheMuse"]

        result = prioritize_sources(
            enabled_sources=enabled_sources,
            remote_preference="Remote Only",
            target_roles=[],
        )

        # Should only return enabled sources
        assert set(result.prioritized_sources) == {"Adzuna", "TheMuse"}
        assert "RemoteOK" not in result.prioritized_sources

    def test_excludes_usajobs_from_priority_when_not_enabled(self) -> None:
        """Does not add USAJobs if not enabled, even with government role."""
        enabled_sources = ["Adzuna", "TheMuse"]
        target_roles = [{"title": "Federal Analyst", "sector": "Government"}]

        result = prioritize_sources(
            enabled_sources=enabled_sources,
            remote_preference="No Preference",
            target_roles=target_roles,
        )

        # Should only return enabled sources
        assert set(result.prioritized_sources) == {"Adzuna", "TheMuse"}
        assert "USAJobs" not in result.prioritized_sources


# =============================================================================
# Source Priority Enum Tests
# =============================================================================


class TestSourcePriority:
    """Tests for SourcePriority enum values."""

    def test_serializes_enum_values_when_accessed(self) -> None:
        """SourcePriority enum values serialize for logging/storage."""
        assert SourcePriority.HIGH.value == "high"
        assert SourcePriority.NORMAL.value == "normal"


# =============================================================================
# Reasoning Tests
# =============================================================================


class TestSourceSelectionReasoning:
    """Tests for source selection reasoning/explanation.

    REQ-003 §4.3: Agent explains reasoning to user.
    """

    def test_includes_reasoning_for_remote_only_prioritization(self) -> None:
        """Reasoning explains RemoteOK prioritization for remote workers."""
        enabled_sources = ["Adzuna", "RemoteOK"]

        result = prioritize_sources(
            enabled_sources=enabled_sources,
            remote_preference="Remote Only",
            target_roles=[],
        )

        assert result.reasoning is not None
        assert "remote" in result.reasoning.lower()
        assert "remoteok" in result.reasoning.lower()

    def test_includes_reasoning_for_government_prioritization(self) -> None:
        """Reasoning explains USAJobs prioritization for government roles."""
        enabled_sources = ["Adzuna", "USAJobs"]
        target_roles = [{"title": "Policy Analyst", "sector": "Government"}]

        result = prioritize_sources(
            enabled_sources=enabled_sources,
            remote_preference="No Preference",
            target_roles=target_roles,
        )

        assert result.reasoning is not None
        assert "government" in result.reasoning.lower()
        assert "usajobs" in result.reasoning.lower()

    def test_includes_neutral_reasoning_when_no_special_priority(self) -> None:
        """Reasoning explains general source selection."""
        enabled_sources = ["Adzuna", "TheMuse"]

        result = prioritize_sources(
            enabled_sources=enabled_sources,
            remote_preference="No Preference",
            target_roles=[],
        )

        assert result.reasoning is not None
        # Should mention that all enabled sources are being used
        assert (
            "enabled" in result.reasoning.lower() or "all" in result.reasoning.lower()
        )


# =============================================================================
# Edge Cases
# =============================================================================


class TestSourceSelectionEdgeCases:
    """Edge case tests for source selection."""

    def test_returns_empty_list_when_no_sources_enabled(self) -> None:
        """Returns empty list when no sources enabled."""
        result = prioritize_sources(
            enabled_sources=[],
            remote_preference="Remote Only",
            target_roles=[],
        )

        assert result.prioritized_sources == []

    def test_handles_none_target_roles_gracefully(self) -> None:
        """Handles None target_roles gracefully."""
        enabled_sources = ["Adzuna"]

        # Should not raise - None is valid for target_roles
        result = prioritize_sources(
            enabled_sources=enabled_sources,
            remote_preference="No Preference",
            target_roles=None,
        )

        assert result.prioritized_sources == ["Adzuna"]

    def test_preserves_order_for_non_prioritized_sources(self) -> None:
        """Non-prioritized sources maintain their original order."""
        enabled_sources = ["TheMuse", "Adzuna", "RemoteOK"]

        result = prioritize_sources(
            enabled_sources=enabled_sources,
            remote_preference="Remote Only",
            target_roles=[],
        )

        # RemoteOK should be first, then TheMuse and Adzuna in original order
        assert result.prioritized_sources[0] == "RemoteOK"
        # Find remaining sources
        remaining = result.prioritized_sources[1:]
        assert remaining == ["TheMuse", "Adzuna"]

    def test_maintains_original_order_when_hybrid_ok_preference(self) -> None:
        """Hybrid OK preference does not prioritize RemoteOK."""
        enabled_sources = ["Adzuna", "RemoteOK", "TheMuse"]

        result = prioritize_sources(
            enabled_sources=enabled_sources,
            remote_preference="Hybrid OK",
            target_roles=[],
        )

        # Should maintain original order, no prioritization
        assert result.prioritized_sources == enabled_sources

    def test_detects_government_when_mixed_case_keywords(self) -> None:
        """Government detection is case-insensitive."""
        enabled_sources = ["Adzuna", "USAJobs"]
        target_roles = [{"title": "GOVERNMENT Analyst", "sector": "federal"}]

        result = prioritize_sources(
            enabled_sources=enabled_sources,
            remote_preference="No Preference",
            target_roles=target_roles,
        )

        # Should still prioritize USAJobs
        assert result.prioritized_sources[0] == "USAJobs"
