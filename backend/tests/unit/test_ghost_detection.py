"""Tests for ghost detection service.

REQ-007 §6.5 + REQ-003 §7: Ghost Detection tests.

Tests verify:
- Ghost score formula: weighted sum of 5 signals
- Days open scoring: 0-30=0, 31-60=50, 60+=100
- Repost count scoring: 0=0, 1=30, 2=60, 3+=100
- Missing fields scoring: salary, deadline, location
- Requirement mismatch scoring: seniority vs years
- Vagueness scoring (LLM-based, mock in tests)
- JSONB ghost_signals structure
"""

from datetime import date, timedelta

import pytest

from app.providers.llm.base import TaskType

# WHY GHOST_DETECTION: Vagueness assessment is part of ghost detection pipeline,
# uses TaskType.GHOST_DETECTION for model routing (Haiku for cost efficiency).
from app.providers.llm.mock_adapter import MockLLMProvider
from app.services.ghost_detection import (
    GhostSignals,
    calculate_days_open_score,
    calculate_ghost_score,
    calculate_missing_fields_score,
    calculate_repost_score,
    calculate_requirement_mismatch_score,
    calculate_vagueness_score,
    generate_ghost_warning,
)

# =============================================================================
# Days Open Score Tests (30% weight)
# =============================================================================


class TestDaysOpenScore:
    """Tests for days_open scoring.

    REQ-003 §7.2: 0-30 days=0, 31-60 days=50, 60+ days=100.
    """

    def test_fresh_posting_zero_days(self) -> None:
        """Posting from today scores 0."""
        today = date.today()
        assert calculate_days_open_score(posted_date=today) == 0

    def test_fresh_posting_under_30_days(self) -> None:
        """Posting under 30 days old scores 0."""
        posted = date.today() - timedelta(days=15)
        assert calculate_days_open_score(posted_date=posted) == 0

    def test_fresh_posting_exactly_30_days(self) -> None:
        """Posting exactly 30 days old scores 0 (boundary)."""
        posted = date.today() - timedelta(days=30)
        assert calculate_days_open_score(posted_date=posted) == 0

    def test_moderate_posting_31_days(self) -> None:
        """Posting at 31 days scores 50 (boundary)."""
        posted = date.today() - timedelta(days=31)
        assert calculate_days_open_score(posted_date=posted) == 50

    def test_moderate_posting_45_days(self) -> None:
        """Posting at 45 days scores 50."""
        posted = date.today() - timedelta(days=45)
        assert calculate_days_open_score(posted_date=posted) == 50

    def test_moderate_posting_60_days(self) -> None:
        """Posting exactly 60 days old scores 50 (boundary)."""
        posted = date.today() - timedelta(days=60)
        assert calculate_days_open_score(posted_date=posted) == 50

    def test_stale_posting_61_days(self) -> None:
        """Posting at 61 days scores 100 (boundary)."""
        posted = date.today() - timedelta(days=61)
        assert calculate_days_open_score(posted_date=posted) == 100

    def test_very_stale_posting_90_days(self) -> None:
        """Posting at 90 days scores 100."""
        posted = date.today() - timedelta(days=90)
        assert calculate_days_open_score(posted_date=posted) == 100

    def test_missing_posted_date_uses_first_seen(self) -> None:
        """When posted_date is None, use first_seen_date."""
        first_seen = date.today() - timedelta(days=45)
        assert (
            calculate_days_open_score(posted_date=None, first_seen_date=first_seen)
            == 50
        )

    def test_both_dates_missing_returns_zero(self) -> None:
        """When both dates are None, return 0 (benefit of doubt)."""
        assert calculate_days_open_score(posted_date=None, first_seen_date=None) == 0


# =============================================================================
# Repost Count Score Tests (30% weight)
# =============================================================================


class TestRepostScore:
    """Tests for repost_count scoring.

    REQ-003 §7.2: 0=0, 1=30, 2=60, 3+=100.
    """

    def test_first_posting_scores_zero(self) -> None:
        """First posting (0 reposts) scores 0."""
        assert calculate_repost_score(repost_count=0) == 0

    def test_one_repost_scores_30(self) -> None:
        """One repost scores 30."""
        assert calculate_repost_score(repost_count=1) == 30

    def test_two_reposts_scores_60(self) -> None:
        """Two reposts scores 60."""
        assert calculate_repost_score(repost_count=2) == 60

    def test_three_reposts_scores_100(self) -> None:
        """Three reposts scores 100."""
        assert calculate_repost_score(repost_count=3) == 100

    def test_many_reposts_caps_at_100(self) -> None:
        """More than 3 reposts still scores 100 (capped)."""
        assert calculate_repost_score(repost_count=10) == 100


# =============================================================================
# Missing Fields Score Tests (10% weight)
# =============================================================================


class TestMissingFieldsScore:
    """Tests for missing critical fields scoring.

    REQ-003 §7.2: Missing salary, deadline, location each add ~33 points.
    """

    def test_all_fields_present_scores_zero(self) -> None:
        """All critical fields present scores 0."""
        score = calculate_missing_fields_score(
            salary_min=100000,
            salary_max=150000,
            application_deadline=date.today() + timedelta(days=30),
            location="New York, NY",
        )
        assert score == 0

    def test_missing_salary_only(self) -> None:
        """Missing salary (both min and max) adds ~33 points."""
        score = calculate_missing_fields_score(
            salary_min=None,
            salary_max=None,
            application_deadline=date.today() + timedelta(days=30),
            location="New York, NY",
        )
        # One of three fields missing = 33
        assert score == 33

    def test_missing_deadline_only(self) -> None:
        """Missing deadline adds ~33 points."""
        score = calculate_missing_fields_score(
            salary_min=100000,
            salary_max=150000,
            application_deadline=None,
            location="New York, NY",
        )
        assert score == 33

    def test_missing_location_only(self) -> None:
        """Missing location adds ~33 points."""
        score = calculate_missing_fields_score(
            salary_min=100000,
            salary_max=150000,
            application_deadline=date.today() + timedelta(days=30),
            location=None,
        )
        assert score == 33

    def test_missing_two_fields(self) -> None:
        """Missing two fields adds ~67 points."""
        score = calculate_missing_fields_score(
            salary_min=None,
            salary_max=None,
            application_deadline=None,
            location="New York, NY",
        )
        # Two of three fields missing = 67
        assert score == 67

    def test_all_fields_missing(self) -> None:
        """All critical fields missing scores 100."""
        score = calculate_missing_fields_score(
            salary_min=None,
            salary_max=None,
            application_deadline=None,
            location=None,
        )
        assert score == 100

    def test_partial_salary_counts_as_present(self) -> None:
        """Having either salary_min or salary_max counts as having salary."""
        score = calculate_missing_fields_score(
            salary_min=100000,
            salary_max=None,
            application_deadline=date.today() + timedelta(days=30),
            location="New York, NY",
        )
        assert score == 0  # salary_min is present, so salary is present


# =============================================================================
# Requirement Mismatch Score Tests (10% weight)
# =============================================================================


class TestRequirementMismatchScore:
    """Tests for seniority/experience mismatch scoring.

    REQ-003 §7.2: Mismatch between seniority level and years requested
    scores 100, otherwise 0.
    """

    def test_no_mismatch_senior_5_years(self) -> None:
        """Senior with 5+ years is not a mismatch."""
        score = calculate_requirement_mismatch_score(
            seniority_level="Senior",
            years_experience_min=5,
        )
        assert score == 0

    def test_mismatch_senior_1_year(self) -> None:
        """Senior with only 1-2 years requested is a mismatch."""
        score = calculate_requirement_mismatch_score(
            seniority_level="Senior",
            years_experience_min=1,
        )
        assert score == 100

    def test_no_mismatch_entry_no_years(self) -> None:
        """Entry level with no years specified is not a mismatch."""
        score = calculate_requirement_mismatch_score(
            seniority_level="Entry",
            years_experience_min=None,
        )
        assert score == 0

    def test_mismatch_entry_10_years(self) -> None:
        """Entry level asking for 10 years is a mismatch."""
        score = calculate_requirement_mismatch_score(
            seniority_level="Entry",
            years_experience_min=10,
        )
        assert score == 100

    def test_no_seniority_level_returns_zero(self) -> None:
        """Missing seniority level returns 0 (can't determine mismatch)."""
        score = calculate_requirement_mismatch_score(
            seniority_level=None,
            years_experience_min=5,
        )
        assert score == 0

    def test_mid_level_3_years_no_mismatch(self) -> None:
        """Mid level with 3 years is reasonable, no mismatch."""
        score = calculate_requirement_mismatch_score(
            seniority_level="Mid",
            years_experience_min=3,
        )
        assert score == 0

    def test_lead_2_years_mismatch(self) -> None:
        """Lead level with only 2 years requested is suspicious."""
        score = calculate_requirement_mismatch_score(
            seniority_level="Lead",
            years_experience_min=2,
        )
        assert score == 100

    def test_executive_3_years_mismatch(self) -> None:
        """Executive with only 3 years requested is a mismatch."""
        score = calculate_requirement_mismatch_score(
            seniority_level="Executive",
            years_experience_min=3,
        )
        assert score == 100


# =============================================================================
# Vagueness Score Tests (20% weight)
# =============================================================================


class TestVaguenessScore:
    """Tests for description vagueness scoring.

    REQ-003 §7.2: LLM assesses vagueness on 0-100 scale.
    """

    @pytest.mark.asyncio
    async def test_vagueness_calls_llm(self, mock_llm: MockLLMProvider) -> None:
        """calculate_vagueness_score uses LLM for assessment."""
        mock_llm.set_response(TaskType.GHOST_DETECTION, "30")

        await calculate_vagueness_score("This is a detailed job description...")

        assert mock_llm.last_task == TaskType.GHOST_DETECTION

    @pytest.mark.asyncio
    async def test_vagueness_parses_numeric_response(
        self, mock_llm: MockLLMProvider
    ) -> None:
        """Vagueness score parses LLM numeric response."""
        mock_llm.set_response(TaskType.GHOST_DETECTION, "45")

        score = await calculate_vagueness_score("Some job description text")

        assert score == 45

    @pytest.mark.asyncio
    async def test_vagueness_handles_text_with_number(
        self, mock_llm: MockLLMProvider
    ) -> None:
        """Vagueness score extracts number from LLM text response."""
        mock_llm.set_response(
            TaskType.GHOST_DETECTION,
            "Based on my analysis, the vagueness score is 75.",
        )

        score = await calculate_vagueness_score("Vague description here")

        assert score == 75

    @pytest.mark.asyncio
    async def test_vagueness_clamps_to_100(self, mock_llm: MockLLMProvider) -> None:
        """Vagueness score clamps values over 100."""
        mock_llm.set_response(TaskType.GHOST_DETECTION, "150")

        score = await calculate_vagueness_score("Some text")

        assert score == 100

    @pytest.mark.asyncio
    async def test_vagueness_clamps_to_zero(self, mock_llm: MockLLMProvider) -> None:
        """Vagueness score clamps negative values to 0."""
        mock_llm.set_response(TaskType.GHOST_DETECTION, "-10")

        score = await calculate_vagueness_score("Some text")

        assert score == 0

    @pytest.mark.asyncio
    async def test_vagueness_invalid_response_returns_default(
        self, mock_llm: MockLLMProvider
    ) -> None:
        """Invalid LLM response returns default score of 50 (middle)."""
        mock_llm.set_response(TaskType.GHOST_DETECTION, "No numbers here")

        score = await calculate_vagueness_score("Some text")

        assert score == 50


# =============================================================================
# Full Ghost Score Calculation Tests
# =============================================================================


class TestCalculateGhostScore:
    """Tests for full ghost score calculation.

    REQ-003 §7.2: Weighted sum of all signals.
    """

    @pytest.mark.asyncio
    async def test_fresh_job_all_fields_scores_low(
        self, mock_llm: MockLLMProvider
    ) -> None:
        """Fresh job with all fields and low vagueness scores near 0."""
        mock_llm.set_response(TaskType.GHOST_DETECTION, "10")  # Low vagueness

        signals = await calculate_ghost_score(
            posted_date=date.today(),
            first_seen_date=date.today(),
            repost_count=0,
            salary_min=100000,
            salary_max=150000,
            application_deadline=date.today() + timedelta(days=30),
            location="New York, NY",
            seniority_level="Senior",
            years_experience_min=5,
            description="Detailed job description with specific requirements...",
        )

        # days_open=0*0.30 + repost=0*0.30 + vagueness=10*0.20 + missing=0*0.10 + mismatch=0*0.10
        # = 0 + 0 + 2 + 0 + 0 = 2
        assert signals.ghost_score == 2
        assert signals.days_open_score == 0
        assert signals.repost_score == 0
        assert signals.vagueness_score == 10
        assert signals.missing_fields_score == 0
        assert signals.requirement_mismatch_score == 0

    @pytest.mark.asyncio
    async def test_stale_reposted_job_scores_high(
        self, mock_llm: MockLLMProvider
    ) -> None:
        """Stale job with reposts and missing fields scores high."""
        mock_llm.set_response(TaskType.GHOST_DETECTION, "80")  # High vagueness

        signals = await calculate_ghost_score(
            posted_date=date.today() - timedelta(days=90),
            first_seen_date=date.today() - timedelta(days=90),
            repost_count=3,
            salary_min=None,
            salary_max=None,
            application_deadline=None,
            location=None,
            seniority_level="Senior",
            years_experience_min=1,  # Mismatch
            description="We're hiring!",
        )

        # days_open=100*0.30 + repost=100*0.30 + vagueness=80*0.20 + missing=100*0.10 + mismatch=100*0.10
        # = 30 + 30 + 16 + 10 + 10 = 96
        assert signals.ghost_score == 96
        assert signals.days_open_score == 100
        assert signals.repost_score == 100
        assert signals.vagueness_score == 80
        assert signals.missing_fields_score == 100
        assert signals.requirement_mismatch_score == 100

    @pytest.mark.asyncio
    async def test_moderate_job_scores_mid_range(
        self, mock_llm: MockLLMProvider
    ) -> None:
        """Job with some warning signs scores in mid range."""
        mock_llm.set_response(TaskType.GHOST_DETECTION, "50")  # Medium vagueness

        signals = await calculate_ghost_score(
            posted_date=date.today() - timedelta(days=45),  # 50 score
            first_seen_date=date.today() - timedelta(days=45),
            repost_count=1,  # 30 score
            salary_min=None,  # missing
            salary_max=None,
            application_deadline=None,  # missing
            location="Remote",  # present
            seniority_level="Mid",
            years_experience_min=3,  # No mismatch
            description="Some description with moderate detail.",
        )

        # days_open=50*0.30 + repost=30*0.30 + vagueness=50*0.20 + missing=67*0.10 + mismatch=0*0.10
        # = 15 + 9 + 10 + 6.7 + 0 = 40.7 -> 41 (rounded)
        assert signals.ghost_score == 41
        assert signals.days_open_score == 50
        assert signals.repost_score == 30
        assert signals.missing_fields_score == 67

    @pytest.mark.asyncio
    async def test_ghost_signals_structure(self, mock_llm: MockLLMProvider) -> None:
        """GhostSignals contains all required fields for JSONB storage."""
        mock_llm.set_response(TaskType.GHOST_DETECTION, "30")

        signals = await calculate_ghost_score(
            posted_date=date.today() - timedelta(days=47),
            first_seen_date=date.today() - timedelta(days=47),
            repost_count=2,
            salary_min=None,
            salary_max=None,
            application_deadline=None,
            location="Remote",
            seniority_level="Mid",
            years_experience_min=3,
            description="Some description.",
        )

        # Check all fields are present per REQ-003 §7.5
        assert hasattr(signals, "days_open")
        assert hasattr(signals, "days_open_score")
        assert hasattr(signals, "repost_count")
        assert hasattr(signals, "repost_score")
        assert hasattr(signals, "vagueness_score")
        assert hasattr(signals, "missing_fields")
        assert hasattr(signals, "missing_fields_score")
        assert hasattr(signals, "requirement_mismatch")
        assert hasattr(signals, "requirement_mismatch_score")
        assert hasattr(signals, "calculated_at")
        assert hasattr(signals, "ghost_score")

    @pytest.mark.asyncio
    async def test_ghost_signals_to_dict(self, mock_llm: MockLLMProvider) -> None:
        """GhostSignals can be converted to dict for JSONB storage."""
        mock_llm.set_response(TaskType.GHOST_DETECTION, "30")

        signals = await calculate_ghost_score(
            posted_date=date.today() - timedelta(days=47),
            first_seen_date=date.today() - timedelta(days=47),
            repost_count=2,
            salary_min=None,
            salary_max=None,
            application_deadline=None,
            location=None,
            seniority_level=None,
            years_experience_min=None,
            description="Some description.",
        )

        signals_dict = signals.to_dict()

        assert isinstance(signals_dict, dict)
        assert "days_open" in signals_dict
        assert "ghost_score" in signals_dict
        assert "calculated_at" in signals_dict
        assert "missing_fields" in signals_dict
        assert isinstance(signals_dict["missing_fields"], list)


# =============================================================================
# Agent Communication Tests (REQ-003 §7.4)
# =============================================================================


class TestGhostWarningMessage:
    """Tests for ghost detection agent communication.

    REQ-003 §7.3-7.4: Agent generates appropriate warning messages
    based on ghost score thresholds.
    """

    def test_warning_returns_none_when_score_is_fresh(self) -> None:
        """Ghost score 0-25 (Fresh) returns no warning."""
        signals = GhostSignals(
            days_open=10,
            days_open_score=0,
            repost_count=0,
            repost_score=0,
            vagueness_score=20,
            missing_fields=[],
            missing_fields_score=0,
            requirement_mismatch=False,
            requirement_mismatch_score=0,
            ghost_score=4,  # Fresh (0-25)
        )

        message = generate_ghost_warning(signals)

        assert message is None

    def test_warning_is_light_when_score_is_moderate(self) -> None:
        """Ghost score 26-50 (Moderate) returns light warning."""
        signals = GhostSignals(
            days_open=45,
            days_open_score=50,
            repost_count=1,
            repost_score=30,
            vagueness_score=30,
            missing_fields=["salary"],
            missing_fields_score=33,
            requirement_mismatch=False,
            requirement_mismatch_score=0,
            ghost_score=35,  # Moderate (26-50)
        )

        message = generate_ghost_warning(signals)

        assert message is not None
        assert "45 days" in message
        assert "reposted" in message.lower() or "repost" in message.lower()
        assert "35" in message  # ghost score

    def test_warning_recommends_verification_when_score_is_elevated(self) -> None:
        """Ghost score 51-75 (Elevated) returns clear warning with verification recommendation."""
        signals = GhostSignals(
            days_open=47,
            days_open_score=50,
            repost_count=2,
            repost_score=60,
            vagueness_score=40,
            missing_fields=["salary", "deadline"],
            missing_fields_score=67,
            requirement_mismatch=False,
            requirement_mismatch_score=0,
            ghost_score=65,  # Elevated (51-75)
        )

        message = generate_ghost_warning(signals)

        assert message is not None
        assert "47 days" in message
        assert "twice" in message.lower() or "2" in message
        assert "65" in message  # ghost score
        assert "verify" in message.lower()

    def test_warning_suggests_skipping_when_score_is_high_risk(self) -> None:
        """Ghost score 76-100 (High Risk) returns strong warning suggesting skip."""
        signals = GhostSignals(
            days_open=90,
            days_open_score=100,
            repost_count=3,
            repost_score=100,
            vagueness_score=80,
            missing_fields=["salary", "deadline", "location"],
            missing_fields_score=100,
            requirement_mismatch=True,
            requirement_mismatch_score=100,
            ghost_score=96,  # High Risk (76-100)
        )

        message = generate_ghost_warning(signals)

        assert message is not None
        assert "90 days" in message
        assert "96" in message  # ghost score
        assert "skip" in message.lower() or "caution" in message.lower()

    def test_warning_returns_none_when_score_is_exactly_25(self) -> None:
        """Ghost score exactly 25 returns no warning (boundary)."""
        signals = GhostSignals(
            days_open=20,
            days_open_score=0,
            repost_count=0,
            repost_score=0,
            vagueness_score=50,
            missing_fields=["salary"],
            missing_fields_score=33,
            requirement_mismatch=False,
            requirement_mismatch_score=0,
            ghost_score=25,  # Boundary (should be Fresh)
        )

        message = generate_ghost_warning(signals)

        assert message is None

    def test_warning_returns_message_when_score_is_exactly_26(self) -> None:
        """Ghost score exactly 26 returns light warning (boundary)."""
        signals = GhostSignals(
            days_open=35,
            days_open_score=50,
            repost_count=0,
            repost_score=0,
            vagueness_score=30,
            missing_fields=[],
            missing_fields_score=0,
            requirement_mismatch=False,
            requirement_mismatch_score=0,
            ghost_score=26,  # Boundary (should be Moderate)
        )

        message = generate_ghost_warning(signals)

        assert message is not None
        assert "26" in message

    def test_warning_omits_repost_when_repost_count_is_zero(self) -> None:
        """Message omits repost information when repost_count is 0."""
        signals = GhostSignals(
            days_open=65,
            days_open_score=100,
            repost_count=0,
            repost_score=0,
            vagueness_score=60,
            missing_fields=["salary"],
            missing_fields_score=33,
            requirement_mismatch=False,
            requirement_mismatch_score=0,
            ghost_score=52,  # Elevated
        )

        message = generate_ghost_warning(signals)

        assert message is not None
        assert "repost" not in message.lower()

    def test_warning_uses_once_when_repost_count_is_one(self) -> None:
        """Message uses correct grammar for single repost."""
        signals = GhostSignals(
            days_open=45,
            days_open_score=50,
            repost_count=1,
            repost_score=30,
            vagueness_score=50,
            missing_fields=[],
            missing_fields_score=0,
            requirement_mismatch=False,
            requirement_mismatch_score=0,
            ghost_score=35,  # Moderate
        )

        message = generate_ghost_warning(signals)

        assert message is not None
        # Should say "once" or "1 time", not "twice" or "times"
        assert "once" in message.lower() or "1 time" in message.lower()
