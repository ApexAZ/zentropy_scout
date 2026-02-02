"""Unit tests for Growth Trajectory calculation.

REQ-008 §5.4: Growth Trajectory component (10% of Stretch Score).

Tests cover:
- Level inference from job titles
- Step up/lateral/step down scoring
- Neutral score for unknown levels
- Edge cases (empty titles, whitespace)
"""

from app.services.stretch_score import (
    STRETCH_NEUTRAL_SCORE,
    calculate_growth_trajectory,
    infer_level,
)

# =============================================================================
# Level Inference (REQ-008 §5.4)
# =============================================================================


class TestInferLevel:
    """Tests for career level inference from job titles."""

    # -------------------------------------------------------------------------
    # Junior Level Detection
    # -------------------------------------------------------------------------

    def test_junior_keyword_detected(self) -> None:
        """Titles with 'junior' map to junior level."""
        assert infer_level("Junior Software Engineer") == "junior"

    def test_jr_abbreviation_detected(self) -> None:
        """Titles with 'Jr.' abbreviation map to junior level."""
        assert infer_level("Jr. Developer") == "junior"

    def test_associate_maps_to_junior(self) -> None:
        """Titles with 'associate' map to junior level."""
        assert infer_level("Associate Product Manager") == "junior"

    def test_entry_level_maps_to_junior(self) -> None:
        """Titles with 'entry-level' map to junior level."""
        assert infer_level("Entry-Level Analyst") == "junior"

    def test_intern_maps_to_junior(self) -> None:
        """Titles with 'intern' map to junior level."""
        assert infer_level("Software Engineering Intern") == "junior"

    # -------------------------------------------------------------------------
    # Mid Level Detection
    # -------------------------------------------------------------------------

    def test_no_level_indicator_defaults_to_mid(self) -> None:
        """Titles without level indicators default to mid."""
        assert infer_level("Software Engineer") == "mid"

    def test_plain_title_maps_to_mid(self) -> None:
        """Plain role titles without seniority default to mid."""
        assert infer_level("Product Manager") == "mid"

    def test_analyst_without_prefix_maps_to_mid(self) -> None:
        """Analyst role without seniority prefix maps to mid."""
        assert infer_level("Data Analyst") == "mid"

    # -------------------------------------------------------------------------
    # Senior Level Detection
    # -------------------------------------------------------------------------

    def test_senior_keyword_detected(self) -> None:
        """Titles with 'senior' map to senior level."""
        assert infer_level("Senior Software Engineer") == "senior"

    def test_sr_abbreviation_detected(self) -> None:
        """Titles with 'Sr.' abbreviation map to senior level."""
        assert infer_level("Sr. Developer") == "senior"

    # -------------------------------------------------------------------------
    # Lead Level Detection
    # -------------------------------------------------------------------------

    def test_lead_keyword_detected(self) -> None:
        """Titles with 'lead' map to lead level."""
        assert infer_level("Engineering Lead") == "lead"

    def test_team_lead_detected(self) -> None:
        """'Team Lead' maps to lead level."""
        assert infer_level("Team Lead") == "lead"

    def test_principal_maps_to_lead(self) -> None:
        """Titles with 'principal' map to lead level."""
        assert infer_level("Principal Engineer") == "lead"

    def test_staff_maps_to_lead(self) -> None:
        """Titles with 'staff' map to lead level."""
        assert infer_level("Staff Software Engineer") == "lead"

    def test_manager_maps_to_lead(self) -> None:
        """Titles with 'manager' (non-director) map to lead level."""
        assert infer_level("Engineering Manager") == "lead"

    # -------------------------------------------------------------------------
    # Director Level Detection
    # -------------------------------------------------------------------------

    def test_director_keyword_detected(self) -> None:
        """Titles with 'director' map to director level."""
        assert infer_level("Director of Engineering") == "director"

    def test_senior_director_maps_to_director(self) -> None:
        """'Senior Director' still maps to director level."""
        assert infer_level("Senior Director of Product") == "director"

    # -------------------------------------------------------------------------
    # VP Level Detection
    # -------------------------------------------------------------------------

    def test_vp_keyword_detected(self) -> None:
        """Titles with 'VP' map to vp level."""
        assert infer_level("VP of Engineering") == "vp"

    def test_vice_president_detected(self) -> None:
        """Titles with 'Vice President' map to vp level."""
        assert infer_level("Vice President of Sales") == "vp"

    def test_svp_maps_to_vp(self) -> None:
        """'SVP' (Senior VP) maps to vp level."""
        assert infer_level("SVP of Marketing") == "vp"

    def test_evp_maps_to_vp(self) -> None:
        """'EVP' (Executive VP) maps to vp level."""
        assert infer_level("EVP of Operations") == "vp"

    # -------------------------------------------------------------------------
    # C-Level Detection
    # -------------------------------------------------------------------------

    def test_ceo_detected(self) -> None:
        """CEO maps to c_level."""
        assert infer_level("CEO") == "c_level"

    def test_cto_detected(self) -> None:
        """CTO maps to c_level."""
        assert infer_level("CTO") == "c_level"

    def test_cfo_detected(self) -> None:
        """CFO maps to c_level."""
        assert infer_level("CFO") == "c_level"

    def test_coo_detected(self) -> None:
        """COO maps to c_level."""
        assert infer_level("COO") == "c_level"

    def test_chief_keyword_detected(self) -> None:
        """Titles with 'Chief' map to c_level."""
        assert infer_level("Chief Technology Officer") == "c_level"

    def test_chief_of_staff_maps_to_lead(self) -> None:
        """'Chief of Staff' is an exception — maps to lead, not c_level."""
        assert infer_level("Chief of Staff") == "lead"

    # -------------------------------------------------------------------------
    # Edge Cases
    # -------------------------------------------------------------------------

    def test_case_insensitive(self) -> None:
        """Level inference is case-insensitive."""
        assert infer_level("SENIOR SOFTWARE ENGINEER") == "senior"
        assert infer_level("junior developer") == "junior"

    def test_empty_string_returns_none(self) -> None:
        """Empty string returns None (cannot infer)."""
        assert infer_level("") is None

    def test_whitespace_only_returns_none(self) -> None:
        """Whitespace-only string returns None."""
        assert infer_level("   ") is None

    def test_none_input_returns_none(self) -> None:
        """None input returns None."""
        assert infer_level(None) is None

    def test_multiple_levels_highest_wins(self) -> None:
        """When title has multiple level keywords, higher level takes precedence."""
        # Senior Director → director (not senior)
        assert infer_level("Senior Director") == "director"
        # Senior VP → vp (not senior)
        assert infer_level("Senior VP") == "vp"

    def test_jr_without_period_maps_to_junior(self) -> None:
        """'Jr' followed by space (no period) maps to junior."""
        assert infer_level("Jr Developer") == "junior"
        assert infer_level("Jr Software Engineer") == "junior"

    def test_standalone_vp_detected(self) -> None:
        """Standalone 'VP' is detected as vp level."""
        assert infer_level("VP") == "vp"
        assert infer_level("VP of Engineering") == "vp"

    def test_long_title_truncated(self) -> None:
        """Titles longer than max length are truncated before processing."""
        # Create a title > 500 chars but with "senior" at the start
        long_title = "Senior " + "x" * 500
        assert infer_level(long_title) == "senior"


# =============================================================================
# Growth Trajectory Scoring (REQ-008 §5.4)
# =============================================================================


class TestGrowthTrajectoryScoring:
    """Tests for step up/lateral/step down scoring."""

    # -------------------------------------------------------------------------
    # Step Up (Score: 100)
    # -------------------------------------------------------------------------

    def test_step_up_returns_100(self) -> None:
        """Moving up in level hierarchy returns 100."""
        score = calculate_growth_trajectory(
            current_role="Senior Software Engineer",  # senior (idx 2)
            job_title="Engineering Lead",  # lead (idx 3)
        )
        assert score == 100.0

    def test_step_up_multiple_levels(self) -> None:
        """Jumping multiple levels still returns 100."""
        score = calculate_growth_trajectory(
            current_role="Junior Developer",  # junior (idx 0)
            job_title="Director of Engineering",  # director (idx 4)
        )
        assert score == 100.0

    def test_step_up_mid_to_senior(self) -> None:
        """Mid to senior is a step up."""
        score = calculate_growth_trajectory(
            current_role="Software Engineer",  # mid (idx 1)
            job_title="Senior Engineer",  # senior (idx 2)
        )
        assert score == 100.0

    # -------------------------------------------------------------------------
    # Lateral Move (Score: 70)
    # -------------------------------------------------------------------------

    def test_lateral_move_returns_70(self) -> None:
        """Same level returns 70."""
        score = calculate_growth_trajectory(
            current_role="Senior Product Manager",  # senior (idx 2)
            job_title="Senior Software Engineer",  # senior (idx 2)
        )
        assert score == 70.0

    def test_lateral_move_both_mid(self) -> None:
        """Both mid-level titles is lateral."""
        score = calculate_growth_trajectory(
            current_role="Software Engineer",  # mid (idx 1)
            job_title="Product Manager",  # mid (idx 1)
        )
        assert score == 70.0

    def test_lateral_move_both_junior(self) -> None:
        """Both junior-level titles is lateral."""
        score = calculate_growth_trajectory(
            current_role="Junior Developer",  # junior (idx 0)
            job_title="Associate Analyst",  # junior (idx 0)
        )
        assert score == 70.0

    # -------------------------------------------------------------------------
    # Step Down (Score: 30)
    # -------------------------------------------------------------------------

    def test_step_down_returns_30(self) -> None:
        """Moving down in level hierarchy returns 30."""
        score = calculate_growth_trajectory(
            current_role="Engineering Manager",  # lead (idx 3)
            job_title="Senior Developer",  # senior (idx 2)
        )
        assert score == 30.0

    def test_step_down_multiple_levels(self) -> None:
        """Dropping multiple levels still returns 30."""
        score = calculate_growth_trajectory(
            current_role="VP of Engineering",  # vp (idx 5)
            job_title="Software Engineer",  # mid (idx 1)
        )
        assert score == 30.0

    def test_step_down_senior_to_junior(self) -> None:
        """Senior to junior is a step down."""
        score = calculate_growth_trajectory(
            current_role="Senior Engineer",  # senior (idx 2)
            job_title="Junior Developer",  # junior (idx 0)
        )
        assert score == 30.0


# =============================================================================
# Neutral Score Cases (REQ-008 §5.4)
# =============================================================================


class TestNeutralScore:
    """Tests for neutral score when levels cannot be determined."""

    def test_no_current_role_returns_neutral(self) -> None:
        """No current role returns neutral score (50)."""
        score = calculate_growth_trajectory(
            current_role=None,
            job_title="Software Engineer",
        )
        assert score == STRETCH_NEUTRAL_SCORE

    def test_empty_current_role_returns_neutral(self) -> None:
        """Empty current role returns neutral score."""
        score = calculate_growth_trajectory(
            current_role="",
            job_title="Software Engineer",
        )
        assert score == STRETCH_NEUTRAL_SCORE

    def test_no_job_title_returns_neutral(self) -> None:
        """No job title returns neutral score."""
        score = calculate_growth_trajectory(
            current_role="Software Engineer",
            job_title=None,
        )
        assert score == STRETCH_NEUTRAL_SCORE

    def test_empty_job_title_returns_neutral(self) -> None:
        """Empty job title returns neutral score."""
        score = calculate_growth_trajectory(
            current_role="Software Engineer",
            job_title="",
        )
        assert score == STRETCH_NEUTRAL_SCORE

    def test_whitespace_current_role_returns_neutral(self) -> None:
        """Whitespace-only current role returns neutral."""
        score = calculate_growth_trajectory(
            current_role="   ",
            job_title="Software Engineer",
        )
        assert score == STRETCH_NEUTRAL_SCORE

    def test_whitespace_job_title_returns_neutral(self) -> None:
        """Whitespace-only job title returns neutral."""
        score = calculate_growth_trajectory(
            current_role="Software Engineer",
            job_title="   ",
        )
        assert score == STRETCH_NEUTRAL_SCORE


# =============================================================================
# Worked Examples from Spec (REQ-008 §5.4)
# =============================================================================


class TestWorkedExamples:
    """Tests verifying worked examples from REQ-008 §5.4."""

    def test_example_step_up_senior_to_lead(self) -> None:
        """Example 1: Senior Engineer → Engineering Lead.

        User's current role: 'Senior Software Engineer' (senior, idx 2)
        Job title: 'Engineering Lead' (lead, idx 3)
        Result: job_idx (3) > current_idx (2) => 100.0
        """
        score = calculate_growth_trajectory(
            current_role="Senior Software Engineer",
            job_title="Engineering Lead",
        )
        assert score == 100.0

    def test_example_lateral_senior_to_senior(self) -> None:
        """Example 2: Senior PM → Senior Engineer.

        User's current role: 'Senior Product Manager' (senior, idx 2)
        Job title: 'Senior Engineer' (senior, idx 2)
        Result: job_idx (2) == current_idx (2) => 70.0
        """
        score = calculate_growth_trajectory(
            current_role="Senior Product Manager",
            job_title="Senior Engineer",
        )
        assert score == 70.0

    def test_example_step_down_manager_to_senior(self) -> None:
        """Example 3: Engineering Manager → Senior Developer.

        User's current role: 'Engineering Manager' (lead, idx 3)
        Job title: 'Senior Developer' (senior, idx 2)
        Result: job_idx (2) < current_idx (3) => 30.0
        """
        score = calculate_growth_trajectory(
            current_role="Engineering Manager",
            job_title="Senior Developer",
        )
        assert score == 30.0

    def test_example_titles_without_explicit_level_default_to_mid(self) -> None:
        """Example 4: Titles without level keywords default to mid.

        When titles don't contain explicit level keywords (junior, senior, lead, etc.),
        they default to 'mid' level. This results in a lateral move score (70).
        """
        score = calculate_growth_trajectory(
            current_role="Technical Consultant",  # No level keyword → mid
            job_title="Solutions Architect",  # No level keyword → mid
        )
        assert score == 70.0  # Both default to mid → lateral move
