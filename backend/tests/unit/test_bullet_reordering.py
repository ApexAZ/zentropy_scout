"""Tests for bullet reordering logic.

REQ-010 §4.3: Bullet Reordering Logic.

Tests verify that bullets are reordered by relevance to a job posting
using four weighted factors: skill overlap (40%), keyword presence (30%),
quantified outcome bonus (20%), and recency boost (10%).
"""

import pytest

from app.services.bullet_reordering import (
    BulletData,
    calculate_bullet_relevance,
    reorder_bullets_for_job,
)

# =============================================================================
# Helpers
# =============================================================================


def _make_bullet(
    *,
    bullet_id: str = "bullet-1",
    job_entry_id: str = "job-1",
    skills: set[str] | None = None,
    keywords: set[str] | None = None,
    has_metrics: bool = False,
    is_current_job: bool = False,
    is_recent_job: bool = False,
) -> BulletData:
    """Create a BulletData with sensible defaults."""
    return BulletData(
        bullet_id=bullet_id,
        job_entry_id=job_entry_id,
        skills=skills or set(),
        keywords=keywords or set(),
        has_metrics=has_metrics,
        is_current_job=is_current_job,
        is_recent_job=is_recent_job,
    )


# =============================================================================
# Tests: BulletData dataclass
# =============================================================================


class TestBulletData:
    """Tests for the BulletData dataclass structure."""

    def test_creates_with_required_fields(self) -> None:
        """BulletData stores all required fields."""
        bullet = BulletData(
            bullet_id="b-1",
            job_entry_id="j-1",
            skills={"python", "sql"},
            keywords={"backend", "api"},
            has_metrics=True,
            is_current_job=False,
            is_recent_job=True,
        )
        assert bullet.bullet_id == "b-1"
        assert bullet.job_entry_id == "j-1"
        assert bullet.skills == {"python", "sql"}
        assert bullet.keywords == {"backend", "api"}
        assert bullet.has_metrics is True
        assert bullet.is_current_job is False
        assert bullet.is_recent_job is True


# =============================================================================
# Tests: calculate_bullet_relevance — Individual Factors
# =============================================================================


class TestSkillOverlapFactor:
    """Tests for Factor 1: Skill overlap (40% weight)."""

    def test_full_skill_overlap_scores_0_4(self) -> None:
        """All job skills matched gives maximum skill factor (0.4)."""
        bullet = _make_bullet(skills={"python", "sql", "fastapi"})
        score = calculate_bullet_relevance(
            bullet=bullet,
            job_skills={"python", "sql", "fastapi"},
            job_keywords=set(),
        )
        assert score == 0.4

    def test_partial_skill_overlap(self) -> None:
        """Matching 2 of 4 job skills gives 50% of skill weight (0.2)."""
        bullet = _make_bullet(skills={"python", "sql"})
        score = calculate_bullet_relevance(
            bullet=bullet,
            job_skills={"python", "sql", "react", "docker"},
            job_keywords=set(),
        )
        assert score == pytest.approx(0.2)

    def test_no_skill_overlap_scores_zero(self) -> None:
        """No matching skills gives zero for skill factor."""
        bullet = _make_bullet(skills={"java", "spring"})
        score = calculate_bullet_relevance(
            bullet=bullet,
            job_skills={"python", "sql"},
            job_keywords=set(),
        )
        assert score == 0.0

    def test_empty_job_skills_no_skill_score(self) -> None:
        """Empty job skills set produces zero for skill factor (no division by zero)."""
        bullet = _make_bullet(skills={"python"})
        score = calculate_bullet_relevance(
            bullet=bullet,
            job_skills=set(),
            job_keywords=set(),
        )
        assert score == 0.0

    def test_empty_bullet_skills_no_skill_score(self) -> None:
        """Bullet with no skills gets zero for skill factor."""
        bullet = _make_bullet(skills=set())
        score = calculate_bullet_relevance(
            bullet=bullet,
            job_skills={"python", "sql"},
            job_keywords=set(),
        )
        assert score == 0.0

    def test_skill_comparison_is_case_sensitive(self) -> None:
        """Skill matching assumes pre-lowercased inputs (no implicit case folding)."""
        bullet = _make_bullet(skills={"Python"})
        score = calculate_bullet_relevance(
            bullet=bullet,
            job_skills={"python"},
            job_keywords=set(),
        )
        # Uppercase "Python" != lowercase "python" — caller must pre-lowercase
        assert score == 0.0


class TestKeywordPresenceFactor:
    """Tests for Factor 2: Keyword presence (30% weight)."""

    def test_full_keyword_overlap_scores_0_3(self) -> None:
        """All job keywords matched gives maximum keyword factor (0.3)."""
        bullet = _make_bullet(keywords={"scalable", "microservices", "cloud"})
        score = calculate_bullet_relevance(
            bullet=bullet,
            job_skills=set(),
            job_keywords={"scalable", "microservices", "cloud"},
        )
        assert score == pytest.approx(0.3)

    def test_partial_keyword_overlap(self) -> None:
        """Matching 1 of 3 keywords gives 33% of keyword weight."""
        bullet = _make_bullet(keywords={"scalable"})
        score = calculate_bullet_relevance(
            bullet=bullet,
            job_skills=set(),
            job_keywords={"scalable", "microservices", "cloud"},
        )
        assert score == pytest.approx(0.1)

    def test_no_keyword_overlap_scores_zero(self) -> None:
        """No matching keywords gives zero for keyword factor."""
        bullet = _make_bullet(keywords={"legacy", "cobol"})
        score = calculate_bullet_relevance(
            bullet=bullet,
            job_skills=set(),
            job_keywords={"scalable", "cloud"},
        )
        assert score == 0.0

    def test_empty_job_keywords_no_keyword_score(self) -> None:
        """Empty job keywords set produces zero (no division by zero)."""
        bullet = _make_bullet(keywords={"scalable"})
        score = calculate_bullet_relevance(
            bullet=bullet,
            job_skills=set(),
            job_keywords=set(),
        )
        assert score == 0.0


class TestMetricsBonusFactor:
    """Tests for Factor 3: Quantified outcome bonus (20% weight)."""

    def test_metrics_present_scores_0_2(self) -> None:
        """Bullet with metrics gets the full bonus (0.2)."""
        bullet = _make_bullet(has_metrics=True)
        score = calculate_bullet_relevance(
            bullet=bullet,
            job_skills=set(),
            job_keywords=set(),
        )
        assert score == 0.2

    def test_no_metrics_scores_zero(self) -> None:
        """Bullet without metrics gets zero for this factor."""
        bullet = _make_bullet(has_metrics=False)
        score = calculate_bullet_relevance(
            bullet=bullet,
            job_skills=set(),
            job_keywords=set(),
        )
        assert score == 0.0


class TestRecencyBoostFactor:
    """Tests for Factor 4: Recency boost (10% weight)."""

    def test_current_job_scores_0_1(self) -> None:
        """Bullet from current job gets full recency boost (0.1)."""
        bullet = _make_bullet(is_current_job=True)
        score = calculate_bullet_relevance(
            bullet=bullet,
            job_skills=set(),
            job_keywords=set(),
        )
        assert score == 0.1

    def test_recent_job_scores_0_05(self) -> None:
        """Bullet from recent job (within 24 months) gets partial boost (0.05)."""
        bullet = _make_bullet(is_recent_job=True)
        score = calculate_bullet_relevance(
            bullet=bullet,
            job_skills=set(),
            job_keywords=set(),
        )
        assert score == 0.05

    def test_current_takes_precedence_over_recent(self) -> None:
        """If both is_current and is_recent are True, current boost applies (0.1)."""
        bullet = _make_bullet(is_current_job=True, is_recent_job=True)
        score = calculate_bullet_relevance(
            bullet=bullet,
            job_skills=set(),
            job_keywords=set(),
        )
        assert score == 0.1

    def test_old_job_no_boost(self) -> None:
        """Bullet from non-current, non-recent job gets no recency boost."""
        bullet = _make_bullet(is_current_job=False, is_recent_job=False)
        score = calculate_bullet_relevance(
            bullet=bullet,
            job_skills=set(),
            job_keywords=set(),
        )
        assert score == 0.0


# =============================================================================
# Tests: calculate_bullet_relevance — Combined Scoring
# =============================================================================


class TestCombinedScoring:
    """Tests for combined scoring across all four factors."""

    def test_all_factors_maxed_returns_1_0(self) -> None:
        """Perfect match on all factors returns maximum score of 1.0."""
        bullet = _make_bullet(
            skills={"python", "sql"},
            keywords={"scalable", "cloud"},
            has_metrics=True,
            is_current_job=True,
        )
        score = calculate_bullet_relevance(
            bullet=bullet,
            job_skills={"python", "sql"},
            job_keywords={"scalable", "cloud"},
        )
        assert score == pytest.approx(1.0)

    def test_score_capped_at_1_0(self) -> None:
        """Score cannot exceed 1.0 even if weights would sum higher."""
        from unittest.mock import patch

        # Temporarily inflate skill weight so factors sum > 1.0
        bullet = _make_bullet(
            skills={"python", "sql"},
            has_metrics=True,
            is_current_job=True,
        )
        with patch("app.services.bullet_reordering._SKILL_OVERLAP_WEIGHT", 0.8):
            score = calculate_bullet_relevance(
                bullet=bullet,
                job_skills={"python", "sql"},
                job_keywords=set(),
            )
        # 0.8 (inflated skill) + 0.2 (metrics) + 0.1 (recency) = 1.1 → capped to 1.0
        assert score == pytest.approx(1.0)

    def test_zero_on_all_factors(self) -> None:
        """Bullet matching nothing returns 0.0."""
        bullet = _make_bullet()
        score = calculate_bullet_relevance(
            bullet=bullet,
            job_skills={"python"},
            job_keywords={"cloud"},
        )
        assert score == 0.0

    def test_additive_scoring(self) -> None:
        """Factors combine additively: skill(0.4) + metrics(0.2) = 0.6."""
        bullet = _make_bullet(
            skills={"python", "sql"},
            has_metrics=True,
        )
        score = calculate_bullet_relevance(
            bullet=bullet,
            job_skills={"python", "sql"},
            job_keywords=set(),
        )
        assert score == pytest.approx(0.6)

    def test_partial_factors_combine(self) -> None:
        """Half skill (0.2) + half keyword (0.15) + metrics (0.2) = 0.55."""
        bullet = _make_bullet(
            skills={"python"},
            keywords={"cloud"},
            has_metrics=True,
        )
        score = calculate_bullet_relevance(
            bullet=bullet,
            job_skills={"python", "sql"},
            job_keywords={"cloud", "scalable"},
        )
        assert score == pytest.approx(0.55)


# =============================================================================
# Tests: reorder_bullets_for_job
# =============================================================================


class TestReorderBulletsForJob:
    """Tests for reorder_bullets_for_job() function."""

    def test_returns_dict_mapping_job_ids_to_bullet_ids(self) -> None:
        """Output maps job_entry_id to ordered list of bullet_ids."""
        bullets_by_job = {
            "job-1": [
                _make_bullet(bullet_id="b-1", job_entry_id="job-1"),
                _make_bullet(bullet_id="b-2", job_entry_id="job-1"),
            ],
        }
        result = reorder_bullets_for_job(
            bullets_by_job=bullets_by_job,
            job_skills=set(),
            job_keywords=set(),
        )
        assert isinstance(result, dict)
        assert "job-1" in result
        assert result["job-1"] == ["b-1", "b-2"]

    def test_higher_relevance_bullet_sorted_first(self) -> None:
        """Bullet with higher relevance score appears before lower."""
        bullets_by_job = {
            "job-1": [
                _make_bullet(bullet_id="low", job_entry_id="job-1"),
                _make_bullet(
                    bullet_id="high",
                    job_entry_id="job-1",
                    skills={"python", "sql"},
                    has_metrics=True,
                ),
            ],
        }
        result = reorder_bullets_for_job(
            bullets_by_job=bullets_by_job,
            job_skills={"python", "sql"},
            job_keywords=set(),
        )
        assert result["job-1"] == ["high", "low"]

    def test_preserves_relative_order_for_ties(self) -> None:
        """Bullets with equal relevance scores keep their original order."""
        bullets_by_job = {
            "job-1": [
                _make_bullet(bullet_id="first", job_entry_id="job-1"),
                _make_bullet(bullet_id="second", job_entry_id="job-1"),
                _make_bullet(bullet_id="third", job_entry_id="job-1"),
            ],
        }
        result = reorder_bullets_for_job(
            bullets_by_job=bullets_by_job,
            job_skills=set(),
            job_keywords=set(),
        )
        # All have score 0.0, so original order preserved
        assert result["job-1"] == ["first", "second", "third"]

    def test_multiple_job_entries_reordered_independently(self) -> None:
        """Each job entry's bullets are reordered independently."""
        bullets_by_job = {
            "job-1": [
                _make_bullet(bullet_id="j1-low", job_entry_id="job-1"),
                _make_bullet(
                    bullet_id="j1-high",
                    job_entry_id="job-1",
                    skills={"python"},
                ),
            ],
            "job-2": [
                _make_bullet(bullet_id="j2-low", job_entry_id="job-2"),
                _make_bullet(
                    bullet_id="j2-high",
                    job_entry_id="job-2",
                    has_metrics=True,
                ),
            ],
        }
        result = reorder_bullets_for_job(
            bullets_by_job=bullets_by_job,
            job_skills={"python"},
            job_keywords=set(),
        )
        assert result["job-1"] == ["j1-high", "j1-low"]
        assert result["job-2"] == ["j2-high", "j2-low"]

    def test_empty_job_entries_returns_empty_dict(self) -> None:
        """Empty input produces empty output."""
        result = reorder_bullets_for_job(
            bullets_by_job={},
            job_skills={"python"},
            job_keywords=set(),
        )
        assert result == {}

    def test_single_bullet_per_job_returns_unchanged(self) -> None:
        """Job entry with only one bullet returns it unchanged."""
        bullets_by_job = {
            "job-1": [
                _make_bullet(bullet_id="only", job_entry_id="job-1"),
            ],
        }
        result = reorder_bullets_for_job(
            bullets_by_job=bullets_by_job,
            job_skills={"python"},
            job_keywords=set(),
        )
        assert result["job-1"] == ["only"]

    def test_three_bullets_full_ranking(self) -> None:
        """Three bullets ranked: high-relevance first, medium second, low third."""
        bullets_by_job = {
            "job-1": [
                _make_bullet(
                    bullet_id="medium",
                    job_entry_id="job-1",
                    has_metrics=True,
                ),
                _make_bullet(
                    bullet_id="high",
                    job_entry_id="job-1",
                    skills={"python", "sql"},
                    has_metrics=True,
                    is_current_job=True,
                ),
                _make_bullet(bullet_id="low", job_entry_id="job-1"),
            ],
        }
        result = reorder_bullets_for_job(
            bullets_by_job=bullets_by_job,
            job_skills={"python", "sql"},
            job_keywords=set(),
        )
        assert result["job-1"] == ["high", "medium", "low"]


# =============================================================================
# Tests: Edge Cases & Safety Bounds
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and safety bounds."""

    def test_bullet_with_extra_skills_not_in_job(self) -> None:
        """Extra bullet skills beyond job skills don't inflate the score."""
        bullet = _make_bullet(skills={"python", "sql", "go", "rust", "c++"})
        score = calculate_bullet_relevance(
            bullet=bullet,
            job_skills={"python", "sql"},
            job_keywords=set(),
        )
        # 2 matches out of 2 job skills = 100% overlap → 0.4
        assert score == 0.4

    def test_bullet_with_extra_keywords_not_in_job(self) -> None:
        """Extra bullet keywords beyond job keywords don't inflate the score."""
        bullet = _make_bullet(keywords={"cloud", "scalable", "devops", "agile", "lean"})
        score = calculate_bullet_relevance(
            bullet=bullet,
            job_skills=set(),
            job_keywords={"cloud", "scalable"},
        )
        assert score == pytest.approx(0.3)

    def test_large_number_of_bullets_processed(self) -> None:
        """Function handles many bullets without error."""
        bullets = [
            _make_bullet(bullet_id=f"b-{i}", job_entry_id="job-1") for i in range(100)
        ]
        bullets_by_job = {"job-1": bullets}
        result = reorder_bullets_for_job(
            bullets_by_job=bullets_by_job,
            job_skills={"python"},
            job_keywords=set(),
        )
        assert len(result["job-1"]) == 100

    def test_empty_bullet_list_for_job_entry(self) -> None:
        """Job entry with empty bullet list produces empty list in output."""
        result = reorder_bullets_for_job(
            bullets_by_job={"job-1": []},
            job_skills={"python"},
            job_keywords=set(),
        )
        assert result["job-1"] == []


# =============================================================================
# Tests: Safety Bounds
# =============================================================================


class TestSafetyBounds:
    """Tests for input size validation."""

    def test_raises_when_job_entries_exceed_maximum(self) -> None:
        """ValueError raised when bullets_by_job has too many entries."""
        oversized = {
            f"job-{i}": [_make_bullet(bullet_id=f"b-{i}", job_entry_id=f"job-{i}")]
            for i in range(51)
        }
        with pytest.raises(ValueError, match="exceeds maximum of 50"):
            reorder_bullets_for_job(
                bullets_by_job=oversized,
                job_skills=set(),
                job_keywords=set(),
            )

    def test_raises_when_bullets_per_job_exceed_maximum(self) -> None:
        """ValueError raised when a single job entry has too many bullets."""
        oversized_bullets = [
            _make_bullet(bullet_id=f"b-{i}", job_entry_id="job-1") for i in range(101)
        ]
        with pytest.raises(ValueError, match="exceeds maximum of 100"):
            reorder_bullets_for_job(
                bullets_by_job={"job-1": oversized_bullets},
                job_skills=set(),
                job_keywords=set(),
            )

    def test_raises_when_job_skills_exceed_maximum(self) -> None:
        """ValueError raised when job_skills set is too large."""
        oversized_skills = {f"skill-{i}" for i in range(1001)}
        with pytest.raises(ValueError, match="exceeds maximum of 1000"):
            reorder_bullets_for_job(
                bullets_by_job={},
                job_skills=oversized_skills,
                job_keywords=set(),
            )

    def test_raises_when_job_keywords_exceed_maximum(self) -> None:
        """ValueError raised when job_keywords set is too large."""
        oversized_keywords = {f"kw-{i}" for i in range(1001)}
        with pytest.raises(ValueError, match="exceeds maximum of 1000"):
            reorder_bullets_for_job(
                bullets_by_job={},
                job_skills=set(),
                job_keywords=oversized_keywords,
            )

    def test_at_maximum_job_entries_succeeds(self) -> None:
        """Exactly 50 job entries is allowed (boundary test)."""
        at_limit = {
            f"job-{i}": [_make_bullet(bullet_id=f"b-{i}", job_entry_id=f"job-{i}")]
            for i in range(50)
        }
        result = reorder_bullets_for_job(
            bullets_by_job=at_limit,
            job_skills=set(),
            job_keywords=set(),
        )
        assert len(result) == 50

    def test_at_maximum_bullets_per_job_succeeds(self) -> None:
        """Exactly 100 bullets per job is allowed (boundary test)."""
        at_limit = [
            _make_bullet(bullet_id=f"b-{i}", job_entry_id="job-1") for i in range(100)
        ]
        result = reorder_bullets_for_job(
            bullets_by_job={"job-1": at_limit},
            job_skills=set(),
            job_keywords=set(),
        )
        assert len(result["job-1"]) == 100
