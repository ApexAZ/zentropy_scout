"""Tests for tailoring decision service.

REQ-007 §8.4: Tailoring Decision
REQ-010 §4.1: Tailoring Decision Logic

The tailoring decision evaluates whether a BaseResume needs modification
for a specific job posting. It examines keyword gaps in the summary and
bullet relevance mismatches, producing a TailoringDecision with action
("use_base" or "create_variant"), signals, and reasoning.
"""

import pytest

from app.services.tailoring_decision import (
    BulletSkillData,
    TailoringDecision,
    TailoringSignal,
    evaluate_tailoring_need,
)

# =============================================================================
# Data Model Tests
# =============================================================================


class TestTailoringSignal:
    """Tests for TailoringSignal dataclass."""

    def test_create_keyword_gap_signal(self) -> None:
        """Should create a keyword gap signal with all fields."""

        signal = TailoringSignal(
            type="keyword_gap",
            priority=0.5,
            detail="Summary missing 3 key terms",
        )

        assert signal.type == "keyword_gap"
        assert signal.priority == 0.5
        assert signal.detail == "Summary missing 3 key terms"

    def test_create_bullet_relevance_signal(self) -> None:
        """Should create a bullet relevance signal with all fields."""

        signal = TailoringSignal(
            type="bullet_relevance",
            priority=0.4,
            detail="Top bullet in job-1 doesn't highlight required skills",
        )

        assert signal.type == "bullet_relevance"
        assert signal.priority == 0.4


class TestBulletSkillData:
    """Tests for BulletSkillData dataclass."""

    def test_create_bullet_skill_data(self) -> None:
        """Should create BulletSkillData with all fields."""

        data = BulletSkillData(
            job_entry_id="job-entry-1",
            position=0,
            skills={"python", "sql"},
        )

        assert data.job_entry_id == "job-entry-1"
        assert data.position == 0
        assert data.skills == {"python", "sql"}


class TestTailoringDecision:
    """Tests for TailoringDecision dataclass."""

    def test_create_use_base_decision(self) -> None:
        """Should create a use_base decision with reasoning."""

        decision = TailoringDecision(
            action="use_base",
            signals=[],
            reasoning="BaseResume aligns well with job requirements.",
        )

        assert decision.action == "use_base"
        assert decision.signals == []
        assert "aligns well" in decision.reasoning

    def test_create_variant_decision_with_signals(self) -> None:
        """Should create a create_variant decision with signals."""

        signal = TailoringSignal(
            type="keyword_gap",
            priority=0.5,
            detail="Missing keywords",
        )
        decision = TailoringDecision(
            action="create_variant",
            signals=[signal],
            reasoning="Tailoring recommended",
        )

        assert decision.action == "create_variant"
        assert len(decision.signals) == 1


# =============================================================================
# No Signals → use_base
# =============================================================================


class TestNoSignals:
    """Tests for when no tailoring signals are detected."""

    def test_no_signals_returns_use_base(self) -> None:
        """When resume keywords match job and bullets are relevant, use base."""

        result = evaluate_tailoring_need(
            job_keywords={"python", "sql", "fastapi"},
            summary_keywords={"python", "sql", "fastapi", "docker"},
            bullet_skills=[],
            fit_score=85.0,
        )

        assert result.action == "use_base"
        assert result.signals == []

    def test_no_signals_includes_reasoning(self) -> None:
        """use_base result should include reasoning text."""

        result = evaluate_tailoring_need(
            job_keywords={"python"},
            summary_keywords={"python"},
            bullet_skills=[],
            fit_score=85.0,
        )

        assert result.reasoning
        assert len(result.reasoning) > 0


# =============================================================================
# Keyword Gap Signal Tests
# =============================================================================


class TestKeywordGapSignal:
    """Tests for keyword gap detection (Signal 1 per REQ-010 §4.1)."""

    def test_keyword_gap_above_threshold_creates_signal(self) -> None:
        """Keyword gap >30% should create a keyword_gap signal."""

        # 3 out of 4 missing = 75% gap
        result = evaluate_tailoring_need(
            job_keywords={"python", "sql", "fastapi", "docker"},
            summary_keywords={"python"},
            bullet_skills=[],
            fit_score=80.0,
        )

        keyword_signals = [s for s in result.signals if s.type == "keyword_gap"]
        assert len(keyword_signals) == 1
        assert keyword_signals[0].priority == pytest.approx(0.75)

    def test_keyword_gap_at_threshold_no_signal(self) -> None:
        """Keyword gap exactly at 30% should NOT create a signal (not >30%)."""

        # 3 out of 10 missing = exactly 30%
        job_kw = {f"skill_{i}" for i in range(10)}
        summary_kw = {f"skill_{i}" for i in range(7)}

        result = evaluate_tailoring_need(
            job_keywords=job_kw,
            summary_keywords=summary_kw,
            bullet_skills=[],
            fit_score=80.0,
        )

        keyword_signals = [s for s in result.signals if s.type == "keyword_gap"]
        assert len(keyword_signals) == 0

    def test_keyword_gap_below_threshold_no_signal(self) -> None:
        """Keyword gap <=30% should NOT create a signal."""

        # 1 out of 4 missing = 25% gap
        result = evaluate_tailoring_need(
            job_keywords={"python", "sql", "fastapi", "docker"},
            summary_keywords={"python", "sql", "fastapi"},
            bullet_skills=[],
            fit_score=80.0,
        )

        keyword_signals = [s for s in result.signals if s.type == "keyword_gap"]
        assert len(keyword_signals) == 0

    def test_keyword_gap_signal_detail_includes_missing_terms(self) -> None:
        """Keyword gap signal detail should mention missing terms."""

        result = evaluate_tailoring_need(
            job_keywords={"python", "sql", "fastapi", "docker"},
            summary_keywords={"python"},
            bullet_skills=[],
            fit_score=80.0,
        )

        keyword_signals = [s for s in result.signals if s.type == "keyword_gap"]
        assert len(keyword_signals) == 1
        assert "missing" in keyword_signals[0].detail.lower()

    def test_keyword_gap_priority_equals_gap_ratio(self) -> None:
        """Keyword gap signal priority should equal the gap ratio."""

        # 2 out of 4 missing = 50% gap
        result = evaluate_tailoring_need(
            job_keywords={"python", "sql", "fastapi", "docker"},
            summary_keywords={"python", "sql"},
            bullet_skills=[],
            fit_score=80.0,
        )

        keyword_signals = [s for s in result.signals if s.type == "keyword_gap"]
        assert len(keyword_signals) == 1
        assert keyword_signals[0].priority == pytest.approx(0.5)


# =============================================================================
# Empty Input Edge Cases
# =============================================================================


class TestEmptyInputs:
    """Tests for edge cases with empty inputs."""

    def test_empty_job_keywords_returns_use_base(self) -> None:
        """Empty job keywords should return use_base (no division by zero)."""

        result = evaluate_tailoring_need(
            job_keywords=set(),
            summary_keywords={"python", "sql"},
            bullet_skills=[],
            fit_score=80.0,
        )

        assert result.action == "use_base"

    def test_empty_summary_keywords_with_job_keywords(self) -> None:
        """Empty summary with job keywords = 100% gap → signal."""

        result = evaluate_tailoring_need(
            job_keywords={"python", "sql"},
            summary_keywords=set(),
            bullet_skills=[],
            fit_score=80.0,
        )

        keyword_signals = [s for s in result.signals if s.type == "keyword_gap"]
        assert len(keyword_signals) == 1
        assert keyword_signals[0].priority == pytest.approx(1.0)

    def test_empty_job_skills_no_bullet_signals(self) -> None:
        """Empty job skills should produce no bullet relevance signals."""

        # Bullet has skills, but job has none → no signal
        bullet_skills = [
            BulletSkillData(
                job_entry_id="job-entry-1",
                position=0,
                skills={"python"},
            ),
        ]

        result = evaluate_tailoring_need(
            job_keywords=set(),
            summary_keywords=set(),
            bullet_skills=bullet_skills,
            fit_score=80.0,
        )

        bullet_signals = [s for s in result.signals if s.type == "bullet_relevance"]
        assert len(bullet_signals) == 0

    def test_both_empty_keywords_returns_use_base(self) -> None:
        """Both empty keyword sets should return use_base."""

        result = evaluate_tailoring_need(
            job_keywords=set(),
            summary_keywords=set(),
            bullet_skills=[],
            fit_score=80.0,
        )

        assert result.action == "use_base"


# =============================================================================
# Bullet Relevance Signal Tests
# =============================================================================


class TestBulletRelevanceSignal:
    """Tests for bullet relevance detection (Signal 2 per REQ-010 §4.1)."""

    def test_top_bullet_missing_job_skills_creates_signal(self) -> None:
        """Top bullet without job skills should create bullet_relevance signal."""

        bullet_skills = [
            BulletSkillData(
                job_entry_id="job-entry-1",
                position=0,
                skills={"excel", "powerpoint"},  # Not matching job skills
            ),
        ]

        result = evaluate_tailoring_need(
            job_keywords={"python"},
            summary_keywords={"python"},
            bullet_skills=bullet_skills,
            job_skills={"python", "sql"},
            fit_score=80.0,
        )

        bullet_signals = [s for s in result.signals if s.type == "bullet_relevance"]
        assert len(bullet_signals) == 1

    def test_top_bullet_with_job_skills_no_signal(self) -> None:
        """Top bullet with job skills should NOT create a signal."""

        bullet_skills = [
            BulletSkillData(
                job_entry_id="job-entry-1",
                position=0,
                skills={"python", "sql"},  # Matches job skills
            ),
        ]

        result = evaluate_tailoring_need(
            job_keywords={"python"},
            summary_keywords={"python"},
            bullet_skills=bullet_skills,
            job_skills={"python", "sql"},
            fit_score=80.0,
        )

        bullet_signals = [s for s in result.signals if s.type == "bullet_relevance"]
        assert len(bullet_signals) == 0

    def test_bullet_position_affects_priority(self) -> None:
        """Bullet priority should decrease by 0.1 per position (0.5, 0.4, 0.3)."""

        bullet_skills = [
            BulletSkillData(
                job_entry_id="job-entry-1",
                position=0,
                skills={"excel"},
            ),
            BulletSkillData(
                job_entry_id="job-entry-1",
                position=1,
                skills={"word"},
            ),
            BulletSkillData(
                job_entry_id="job-entry-1",
                position=2,
                skills={"outlook"},
            ),
        ]

        result = evaluate_tailoring_need(
            job_keywords={"python"},
            summary_keywords={"python"},
            bullet_skills=bullet_skills,
            job_skills={"python", "sql"},
            fit_score=80.0,
        )

        bullet_signals = [s for s in result.signals if s.type == "bullet_relevance"]
        assert len(bullet_signals) == 3
        priorities = sorted([s.priority for s in bullet_signals], reverse=True)
        assert priorities == pytest.approx([0.5, 0.4, 0.3])

    def test_only_top_three_bullets_per_job_checked(self) -> None:
        """Should only check top 3 bullets per job entry."""

        bullet_skills = [
            BulletSkillData(
                job_entry_id="job-entry-1",
                position=i,
                skills={"excel"},
            )
            for i in range(5)  # 5 bullets, but only top 3 should be checked
        ]

        result = evaluate_tailoring_need(
            job_keywords={"python"},
            summary_keywords={"python"},
            bullet_skills=bullet_skills,
            job_skills={"python", "sql"},
            fit_score=80.0,
        )

        bullet_signals = [s for s in result.signals if s.type == "bullet_relevance"]
        assert len(bullet_signals) == 3

    def test_bullet_signal_detail_includes_job_entry_id(self) -> None:
        """Bullet signal detail should reference the job entry."""

        bullet_skills = [
            BulletSkillData(
                job_entry_id="acme-corp-swe",
                position=0,
                skills={"excel"},
            ),
        ]

        result = evaluate_tailoring_need(
            job_keywords={"python"},
            summary_keywords={"python"},
            bullet_skills=bullet_skills,
            job_skills={"python", "sql"},
            fit_score=80.0,
        )

        bullet_signals = [s for s in result.signals if s.type == "bullet_relevance"]
        assert len(bullet_signals) == 1
        assert "acme-corp-swe" in bullet_signals[0].detail

    def test_empty_bullet_skills_with_job_skills_creates_signal(self) -> None:
        """Bullet with no skills at all should create a signal when job has skills."""

        bullet_skills = [
            BulletSkillData(
                job_entry_id="job-entry-1",
                position=0,
                skills=set(),  # No skills extracted from bullet
            ),
        ]

        result = evaluate_tailoring_need(
            job_keywords={"python"},
            summary_keywords={"python"},
            bullet_skills=bullet_skills,
            job_skills={"python", "sql"},
            fit_score=80.0,
        )

        bullet_signals = [s for s in result.signals if s.type == "bullet_relevance"]
        assert len(bullet_signals) == 1


# =============================================================================
# Priority Threshold Tests
# =============================================================================


class TestPriorityThreshold:
    """Tests for total priority threshold (decision matrix per REQ-010 §4.1)."""

    def test_total_priority_at_threshold_returns_create_variant(self) -> None:
        """Total priority exactly 0.3 should return create_variant (not <0.3)."""

        # Position 2 bullet → priority 0.3
        bullet_skills = [
            BulletSkillData(
                job_entry_id="job-entry-1",
                position=2,
                skills={"excel"},
            ),
        ]

        result = evaluate_tailoring_need(
            job_keywords={"python"},
            summary_keywords={"python"},
            bullet_skills=bullet_skills,
            job_skills={"python", "sql"},
            fit_score=80.0,
        )

        assert result.action == "create_variant"

    def test_total_priority_above_threshold_returns_create_variant(self) -> None:
        """Total priority >=0.3 should return create_variant."""

        # Position 0 bullet → priority 0.5
        bullet_skills = [
            BulletSkillData(
                job_entry_id="job-entry-1",
                position=0,
                skills={"excel"},
            ),
        ]

        result = evaluate_tailoring_need(
            job_keywords={"python"},
            summary_keywords={"python"},
            bullet_skills=bullet_skills,
            job_skills={"python", "sql"},
            fit_score=80.0,
        )

        assert result.action == "create_variant"
        assert len(result.signals) >= 1


# =============================================================================
# Multiple Signal Accumulation Tests
# =============================================================================


class TestMultipleSignals:
    """Tests for multiple signal accumulation."""

    def test_keyword_gap_and_bullet_signals_accumulate(self) -> None:
        """Both keyword gap and bullet relevance signals should accumulate."""

        bullet_skills = [
            BulletSkillData(
                job_entry_id="job-entry-1",
                position=0,
                skills={"excel"},
            ),
        ]

        # 3/4 keywords missing = 75% gap → keyword signal
        # Bullet has no overlap with job skills → bullet signal
        result = evaluate_tailoring_need(
            job_keywords={"python", "sql", "fastapi", "docker"},
            summary_keywords={"python"},
            bullet_skills=bullet_skills,
            job_skills={"python", "sql"},
            fit_score=80.0,
        )

        signal_types = {s.type for s in result.signals}
        assert "keyword_gap" in signal_types
        assert "bullet_relevance" in signal_types
        assert result.action == "create_variant"

    def test_multiple_bullet_signals_from_different_entries(self) -> None:
        """Bullet signals from different job entries should all be included."""

        bullet_skills = [
            BulletSkillData(
                job_entry_id="job-entry-1",
                position=0,
                skills={"excel"},
            ),
            BulletSkillData(
                job_entry_id="job-entry-2",
                position=0,
                skills={"word"},
            ),
        ]

        result = evaluate_tailoring_need(
            job_keywords={"python"},
            summary_keywords={"python"},
            bullet_skills=bullet_skills,
            job_skills={"python", "sql"},
            fit_score=80.0,
        )

        bullet_signals = [s for s in result.signals if s.type == "bullet_relevance"]
        assert len(bullet_signals) == 2


# =============================================================================
# Reasoning Text Tests
# =============================================================================


class TestReasoningText:
    """Tests for reasoning text in TailoringDecision."""

    def test_use_base_reasoning_mentions_alignment(self) -> None:
        """use_base reasoning should explain good alignment."""

        result = evaluate_tailoring_need(
            job_keywords={"python"},
            summary_keywords={"python"},
            bullet_skills=[],
            fit_score=80.0,
        )

        assert result.action == "use_base"
        assert result.reasoning
        assert len(result.reasoning) > 10

    def test_create_variant_reasoning_includes_signal_details(self) -> None:
        """create_variant reasoning should reference signal details."""

        result = evaluate_tailoring_need(
            job_keywords={"python", "sql", "fastapi", "docker"},
            summary_keywords={"python"},
            bullet_skills=[],
            fit_score=80.0,
        )

        assert result.action == "create_variant"
        assert result.reasoning
        assert len(result.reasoning) > 10


# =============================================================================
# fit_score Parameter Tests
# =============================================================================


class TestFitScoreParameter:
    """Tests for fit_score parameter (future-proofing)."""

    def test_fit_score_accepted_without_error(self) -> None:
        """fit_score should be accepted as a parameter without error."""

        result = evaluate_tailoring_need(
            job_keywords={"python"},
            summary_keywords={"python"},
            bullet_skills=[],
            fit_score=95.0,
        )

        assert result.action == "use_base"

    def test_fit_score_does_not_affect_current_decision(self) -> None:
        """fit_score should not change the decision (future-proofing parameter)."""

        result_high = evaluate_tailoring_need(
            job_keywords={"python"},
            summary_keywords={"python"},
            bullet_skills=[],
            fit_score=99.0,
        )

        result_low = evaluate_tailoring_need(
            job_keywords={"python"},
            summary_keywords={"python"},
            bullet_skills=[],
            fit_score=10.0,
        )

        assert result_high.action == result_low.action
