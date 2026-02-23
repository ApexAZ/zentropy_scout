"""Tests for data availability checks.

REQ-010 §8.1: Insufficient Data edge cases.

Five scenarios:
1. No achievement stories → skip cover letter
2. Voice profile incomplete → use defaults + warning
3. No matching stories (all scores < 20) → use top 2 + disclaimer
4. Job posting minimal (< 2 skills) → generic approach + flag
5. No culture_text → skip culture alignment section
"""

from dataclasses import replace

from app.services.data_availability import check_data_availability

# =============================================================================
# Scenario 1: No Achievement Stories
# =============================================================================


class TestNoAchievementStories:
    """REQ-010 §8.1: No achievement stories → skip cover letter."""

    def test_skip_cover_letter_when_zero_stories(self) -> None:
        """Should set can_generate_cover_letter=False when no stories."""
        result = check_data_availability(
            achievement_story_count=0,
            missing_voice_fields=(),
            extracted_skills_count=5,
            has_culture_text=True,
        )
        assert result.can_generate_cover_letter is False

    def test_warning_explains_no_stories(self) -> None:
        """Should include a warning explaining why cover letter is skipped."""
        result = check_data_availability(
            achievement_story_count=0,
            missing_voice_fields=(),
            extracted_skills_count=5,
            has_culture_text=True,
        )
        assert any("achievement stor" in w.lower() for w in result.warnings)

    def test_can_generate_cover_letter_with_stories(self) -> None:
        """Should allow cover letter when stories exist."""
        result = check_data_availability(
            achievement_story_count=3,
            missing_voice_fields=(),
            extracted_skills_count=5,
            has_culture_text=True,
        )
        assert result.can_generate_cover_letter is True

    def test_single_story_still_allows_cover_letter(self) -> None:
        """Even 1 story should allow cover letter generation."""
        result = check_data_availability(
            achievement_story_count=1,
            missing_voice_fields=(),
            extracted_skills_count=5,
            has_culture_text=True,
        )
        assert result.can_generate_cover_letter is True


# =============================================================================
# Scenario 2: Voice Profile Incomplete
# =============================================================================


class TestVoiceProfileIncomplete:
    """REQ-010 §8.1: Voice profile incomplete → defaults + warning."""

    def test_warning_when_required_fields_missing(self) -> None:
        """Should warn when required voice profile fields are missing."""
        result = check_data_availability(
            achievement_story_count=3,
            missing_voice_fields=("tone", "sentence_style"),
            extracted_skills_count=5,
            has_culture_text=True,
        )
        assert result.voice_profile_incomplete is True
        assert any("voice profile" in w.lower() for w in result.warnings)

    def test_no_warning_when_all_fields_present(self) -> None:
        """Should not warn when all required fields are present."""
        result = check_data_availability(
            achievement_story_count=3,
            missing_voice_fields=(),
            extracted_skills_count=5,
            has_culture_text=True,
        )
        assert result.voice_profile_incomplete is False

    def test_warning_lists_missing_field_names(self) -> None:
        """Warning should mention which fields are missing."""
        result = check_data_availability(
            achievement_story_count=3,
            missing_voice_fields=("tone",),
            extracted_skills_count=5,
            has_culture_text=True,
        )
        assert any("tone" in w.lower() for w in result.warnings)


# =============================================================================
# Scenario 3: No Matching Stories (all scores < 20)
# =============================================================================


class TestNoMatchingStories:
    """REQ-010 §8.1: All story scores < 20 → use top 2 + disclaimer."""

    def test_low_match_when_all_scores_below_threshold(self) -> None:
        """Should flag low match when all story scores < 20."""
        result = check_data_availability(
            achievement_story_count=3,
            missing_voice_fields=(),
            extracted_skills_count=5,
            has_culture_text=True,
            top_story_scores=(15.0, 10.0, 5.0),
        )
        assert result.has_low_match_stories is True

    def test_warning_for_low_match_stories(self) -> None:
        """Should include a disclaimer warning for low-match stories."""
        result = check_data_availability(
            achievement_story_count=3,
            missing_voice_fields=(),
            extracted_skills_count=5,
            has_culture_text=True,
            top_story_scores=(15.0, 10.0),
        )
        assert any(
            "match" in w.lower() or "relevance" in w.lower() for w in result.warnings
        )

    def test_no_low_match_when_any_score_above_threshold(self) -> None:
        """Should not flag low match when at least one score >= 20."""
        result = check_data_availability(
            achievement_story_count=3,
            missing_voice_fields=(),
            extracted_skills_count=5,
            has_culture_text=True,
            top_story_scores=(25.0, 10.0),
        )
        assert result.has_low_match_stories is False

    def test_no_low_match_when_scores_not_provided(self) -> None:
        """Should not flag low match when scores haven't been calculated."""
        result = check_data_availability(
            achievement_story_count=3,
            missing_voice_fields=(),
            extracted_skills_count=5,
            has_culture_text=True,
        )
        assert result.has_low_match_stories is False

    def test_no_low_match_with_empty_scores(self) -> None:
        """Should not flag low match when scores tuple is empty."""
        result = check_data_availability(
            achievement_story_count=3,
            missing_voice_fields=(),
            extracted_skills_count=5,
            has_culture_text=True,
            top_story_scores=(),
        )
        assert result.has_low_match_stories is False

    def test_score_at_exact_threshold_is_not_low(self) -> None:
        """Score exactly at threshold (20) should NOT be flagged as low."""
        result = check_data_availability(
            achievement_story_count=2,
            missing_voice_fields=(),
            extracted_skills_count=5,
            has_culture_text=True,
            top_story_scores=(20.0, 15.0),
        )
        assert result.has_low_match_stories is False


# =============================================================================
# Scenario 4: Job Posting Minimal
# =============================================================================


class TestJobPostingMinimal:
    """REQ-010 §8.1: < 2 extracted skills → generic approach + flag."""

    def test_minimal_when_less_than_two_skills(self) -> None:
        """Should flag minimal job posting when < 2 extracted skills."""
        result = check_data_availability(
            achievement_story_count=3,
            missing_voice_fields=(),
            extracted_skills_count=1,
            has_culture_text=True,
        )
        assert result.is_minimal_job_posting is True

    def test_minimal_when_zero_skills(self) -> None:
        """Should flag minimal job posting when 0 extracted skills."""
        result = check_data_availability(
            achievement_story_count=3,
            missing_voice_fields=(),
            extracted_skills_count=0,
            has_culture_text=True,
        )
        assert result.is_minimal_job_posting is True

    def test_warning_for_minimal_job_posting(self) -> None:
        """Should include a warning about generic approach."""
        result = check_data_availability(
            achievement_story_count=3,
            missing_voice_fields=(),
            extracted_skills_count=1,
            has_culture_text=True,
        )
        assert any(
            "review" in w.lower() or "generic" in w.lower() for w in result.warnings
        )

    def test_not_minimal_when_enough_skills(self) -> None:
        """Should not flag when >= 2 extracted skills."""
        result = check_data_availability(
            achievement_story_count=3,
            missing_voice_fields=(),
            extracted_skills_count=2,
            has_culture_text=True,
        )
        assert result.is_minimal_job_posting is False


# =============================================================================
# Scenario 5: No Culture Text
# =============================================================================


class TestNoCultureText:
    """REQ-010 §8.1: No culture_text → skip culture alignment."""

    def test_skip_culture_when_no_culture_text(self) -> None:
        """Should set skip_culture_alignment=True when no culture_text."""
        result = check_data_availability(
            achievement_story_count=3,
            missing_voice_fields=(),
            extracted_skills_count=5,
            has_culture_text=False,
        )
        assert result.skip_culture_alignment is True

    def test_no_skip_culture_when_culture_text_present(self) -> None:
        """Should not skip culture alignment when culture_text exists."""
        result = check_data_availability(
            achievement_story_count=3,
            missing_voice_fields=(),
            extracted_skills_count=5,
            has_culture_text=True,
        )
        assert result.skip_culture_alignment is False

    def test_warning_for_missing_culture_text(self) -> None:
        """Should include a warning when culture text is missing."""
        result = check_data_availability(
            achievement_story_count=3,
            missing_voice_fields=(),
            extracted_skills_count=5,
            has_culture_text=False,
        )
        assert any("culture" in w.lower() for w in result.warnings)


# =============================================================================
# Combined Scenarios & Result Structure
# =============================================================================


class TestDataAvailabilityResult:
    """Tests for DataAvailabilityResult structure."""

    def test_result_is_frozen_dataclass(self) -> None:
        """DataAvailabilityResult should be immutable."""
        result = check_data_availability(
            achievement_story_count=3,
            missing_voice_fields=(),
            extracted_skills_count=5,
            has_culture_text=True,
        )
        updated = replace(result, can_generate_cover_letter=False)
        assert result.can_generate_cover_letter is True
        assert updated.can_generate_cover_letter is False

    def test_no_warnings_when_all_data_present(self) -> None:
        """Should have zero warnings when all data is sufficient."""
        result = check_data_availability(
            achievement_story_count=3,
            missing_voice_fields=(),
            extracted_skills_count=5,
            has_culture_text=True,
        )
        assert len(result.warnings) == 0

    def test_all_flags_false_when_data_sufficient(self) -> None:
        """All degradation flags should be False when data is sufficient."""
        result = check_data_availability(
            achievement_story_count=3,
            missing_voice_fields=(),
            extracted_skills_count=5,
            has_culture_text=True,
        )
        assert result.can_generate_cover_letter is True
        assert result.voice_profile_incomplete is False
        assert result.has_low_match_stories is False
        assert result.is_minimal_job_posting is False
        assert result.skip_culture_alignment is False


class TestMultipleInsufficientDataScenarios:
    """Tests for combinations of insufficient data."""

    def test_multiple_warnings_accumulate(self) -> None:
        """Multiple issues should produce multiple warnings."""
        result = check_data_availability(
            achievement_story_count=0,
            missing_voice_fields=("tone",),
            extracted_skills_count=1,
            has_culture_text=False,
        )
        # No stories + voice incomplete + minimal job + no culture = 4 warnings
        assert len(result.warnings) >= 4

    def test_worst_case_all_flags_set(self) -> None:
        """All flags should be set when all data is insufficient."""
        result = check_data_availability(
            achievement_story_count=0,
            missing_voice_fields=("tone", "sentence_style"),
            extracted_skills_count=0,
            has_culture_text=False,
            top_story_scores=(5.0,),
        )
        assert result.can_generate_cover_letter is False
        assert result.voice_profile_incomplete is True
        assert result.has_low_match_stories is True
        assert result.is_minimal_job_posting is True
        assert result.skip_culture_alignment is True

    def test_no_stories_overrides_low_match_check(self) -> None:
        """When no stories at all, low match check is irrelevant."""
        result = check_data_availability(
            achievement_story_count=0,
            missing_voice_fields=(),
            extracted_skills_count=5,
            has_culture_text=True,
            top_story_scores=(5.0,),
        )
        # No stories means can't generate cover letter
        assert result.can_generate_cover_letter is False
        # Low match is still flagged since scores were provided
        assert result.has_low_match_stories is True


# =============================================================================
# Input Validation
# =============================================================================


class TestInputValidation:
    """Tests for input validation on check_data_availability."""

    def test_negative_story_count_treated_as_zero(self) -> None:
        """Negative story count should be treated as zero."""
        result = check_data_availability(
            achievement_story_count=-1,
            missing_voice_fields=(),
            extracted_skills_count=5,
            has_culture_text=True,
        )
        assert result.can_generate_cover_letter is False

    def test_negative_skills_count_treated_as_zero(self) -> None:
        """Negative skills count should be treated as zero."""
        result = check_data_availability(
            achievement_story_count=3,
            missing_voice_fields=(),
            extracted_skills_count=-1,
            has_culture_text=True,
        )
        assert result.is_minimal_job_posting is True
