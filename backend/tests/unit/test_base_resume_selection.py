"""Tests for base resume selection service.

REQ-007 §8.3: Base Resume Selection — Match role_type to job title,
fall back to is_primary.

Algorithm:
1. Fetch all base resumes for persona (status='Active' only)
2. For each base resume, match role_type to job title
3. If match found, use matched base resume
4. Fallback: use is_primary=True resume
5. If no primary, raise error
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from app.services.base_resume_selection import (
    BaseResumeSelectionResult,
    role_type_matches,
    select_base_resume,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@dataclass
class FakeBaseResume:
    """Fake base resume for testing that satisfies BaseResumeLike protocol."""

    id: UUID
    role_type: str
    is_primary: bool
    status: str = "Active"


def _make_resume(
    role_type: str = "Software Engineer",
    is_primary: bool = False,
    status: str = "Active",
) -> FakeBaseResume:
    """Create a fake base resume with defaults."""
    return FakeBaseResume(
        id=uuid4(),
        role_type=role_type,
        is_primary=is_primary,
        status=status,
    )


# =============================================================================
# Tests: role_type_matches
# =============================================================================


class TestRoleTypeMatches:
    """Tests for role_type_matches function."""

    def test_returns_true_when_exact_match(self) -> None:
        """Exact role_type matches job title."""
        assert role_type_matches("Software Engineer", "Software Engineer") is True

    def test_returns_true_when_case_differs(self) -> None:
        """Matching is case-insensitive."""
        assert role_type_matches("software engineer", "Software Engineer") is True

    def test_returns_true_when_synonym_matches(self) -> None:
        """Matching uses title normalization (synonyms)."""
        assert role_type_matches("SDE", "Software Engineer") is True

    def test_returns_true_when_seniority_prefix_normalized(self) -> None:
        """Seniority prefixes are normalized (Sr. → senior)."""
        assert (
            role_type_matches("Sr. Software Engineer", "Senior Software Engineer")
            is True
        )

    def test_returns_false_when_different_roles(self) -> None:
        """Different roles do not match."""
        assert role_type_matches("Product Manager", "Software Engineer") is False

    def test_returns_false_when_role_type_empty(self) -> None:
        """Empty role_type does not match anything."""
        assert role_type_matches("", "Software Engineer") is False

    def test_returns_false_when_job_title_empty(self) -> None:
        """Empty job title does not match anything."""
        assert role_type_matches("Software Engineer", "") is False

    def test_returns_false_when_both_empty(self) -> None:
        """Both empty does not match."""
        assert role_type_matches("", "") is False

    def test_returns_true_when_extra_whitespace(self) -> None:
        """Extra whitespace is normalized."""
        assert role_type_matches("  Software  Engineer  ", "Software Engineer") is True

    def test_returns_false_when_substring_only(self) -> None:
        """Substring of role does not count as match."""
        assert role_type_matches("Engineer", "Software Engineer") is False


# =============================================================================
# Tests: select_base_resume
# =============================================================================


class TestSelectBaseResume:
    """Tests for select_base_resume function."""

    def test_selects_role_type_match_when_resume_matches_job(self) -> None:
        """Selects resume whose role_type matches job title."""
        matching = _make_resume(role_type="Software Engineer")
        other = _make_resume(role_type="Product Manager", is_primary=True)
        resumes = [other, matching]

        result = select_base_resume(resumes, "Software Engineer")

        assert result.base_resume_id == matching.id
        assert result.match_reason == "role_type_match"

    def test_selects_primary_when_no_role_type_match(self) -> None:
        """Falls back to is_primary when no role_type match."""
        primary = _make_resume(role_type="Product Manager", is_primary=True)
        other = _make_resume(role_type="Data Scientist")
        resumes = [primary, other]

        result = select_base_resume(resumes, "Software Engineer")

        assert result.base_resume_id == primary.id
        assert result.match_reason == "primary_fallback"

    def test_prefers_role_type_match_over_primary(self) -> None:
        """Role type match is preferred even if another resume is primary."""
        primary = _make_resume(role_type="Product Manager", is_primary=True)
        matching = _make_resume(role_type="Software Engineer")
        resumes = [primary, matching]

        result = select_base_resume(resumes, "Software Engineer")

        assert result.base_resume_id == matching.id
        assert result.match_reason == "role_type_match"

    def test_selects_first_match_when_multiple_role_types_match(self) -> None:
        """When multiple resumes match role_type, first one wins."""
        first = _make_resume(role_type="Software Engineer")
        second = _make_resume(role_type="SDE")  # normalizes to software engineer
        resumes = [first, second]

        result = select_base_resume(resumes, "Software Engineer")

        assert result.base_resume_id == first.id

    def test_raises_when_no_match_and_no_primary(self) -> None:
        """Raises ValueError when no match and no primary resume."""
        other = _make_resume(role_type="Data Scientist")
        resumes = [other]

        with pytest.raises(ValueError, match="No primary base resume found"):
            select_base_resume(resumes, "Software Engineer")

    def test_raises_when_resume_list_empty(self) -> None:
        """Raises ValueError when resume list is empty."""
        with pytest.raises(ValueError, match="No active base resumes"):
            select_base_resume([], "Software Engineer")

    def test_excludes_archived_resumes_from_selection(self) -> None:
        """Archived resumes are excluded from selection."""
        archived = _make_resume(
            role_type="Software Engineer",
            status="Archived",
        )
        primary = _make_resume(role_type="Other", is_primary=True)
        resumes = [archived, primary]

        result = select_base_resume(resumes, "Software Engineer")

        # Should NOT match archived resume even though role_type matches
        assert result.base_resume_id == primary.id
        assert result.match_reason == "primary_fallback"

    def test_raises_when_all_resumes_archived(self) -> None:
        """Raises ValueError when all resumes are archived."""
        archived = _make_resume(
            role_type="Software Engineer",
            status="Archived",
        )

        with pytest.raises(ValueError, match="No active base resumes"):
            select_base_resume([archived], "Software Engineer")

    def test_returns_selection_result_when_match_found(self) -> None:
        """Result dataclass contains the selected resume ID."""
        resume = _make_resume(role_type="Software Engineer", is_primary=True)
        result = select_base_resume([resume], "Software Engineer")

        assert isinstance(result, BaseResumeSelectionResult)
        assert result.base_resume_id == resume.id

    def test_uses_normalized_matching_when_synonym_present(self) -> None:
        """Selection uses normalized matching (synonyms)."""
        resume = _make_resume(role_type="SDE")
        primary = _make_resume(role_type="Other", is_primary=True)
        resumes = [resume, primary]

        result = select_base_resume(resumes, "Software Engineer")

        assert result.base_resume_id == resume.id
        assert result.match_reason == "role_type_match"

    def test_matches_case_insensitively_when_case_differs(self) -> None:
        """Selection matching is case-insensitive."""
        resume = _make_resume(role_type="software engineer")
        resumes = [resume]

        result = select_base_resume(resumes, "SOFTWARE ENGINEER")

        assert result.base_resume_id == resume.id

    def test_selects_first_primary_when_multiple_primaries_exist(self) -> None:
        """When multiple primaries exist and no role match, first primary wins."""
        primary1 = _make_resume(role_type="Product Manager", is_primary=True)
        primary2 = _make_resume(role_type="Data Scientist", is_primary=True)
        resumes = [primary1, primary2]

        result = select_base_resume(resumes, "Software Engineer")

        assert result.base_resume_id == primary1.id
        assert result.match_reason == "primary_fallback"
