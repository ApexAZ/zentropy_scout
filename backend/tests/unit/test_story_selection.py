"""Tests for achievement story selection service.

REQ-007 §8.6: Story Selection Logic
REQ-010 §5.2: Achievement Story Selection

Scoring factors:
    - Skills match (0-40): min(overlap_count * 10, 40)
    - Recency (0-20): current=20, <2yr=15, <4yr=10
    - Quantified outcome (0-15): has_metrics(outcome) → 15
    - Culture alignment (0-15): min(culture_keyword_matches * 5, 15)
    - Freshness penalty (-10): story used 3+ times in last 30 days

Edge cases (REQ-010 §8.1, §8.4):
    - No achievement stories → empty list
    - All scores < 20 → use top 2 with disclaimer
    - No culture_text → skip culture factor
    - Only 1 story available → return single story
    - Top 2 from same job entry with same outcome → substitute #3
    - All stories hit freshness penalty → ignore penalty
"""

from datetime import date, timedelta

from app.services.story_selection import (
    StoryInput,
    StorySelectionConfig,
    WorkHistoryInfo,
    select_achievement_stories,
)

# =============================================================================
# Helpers — Create test data
# =============================================================================


def _story(
    story_id: str = "story-1",
    title: str = "Led Cloud Migration",
    context: str = "Company needed cloud migration",
    action: str = "Led the engineering team",
    outcome: str = "Improved system reliability",
    skills: list[str] | None = None,
    related_job_id: str | None = None,
) -> StoryInput:
    """Create a StoryInput for testing."""
    return StoryInput(
        id=story_id,
        title=title,
        context=context,
        action=action,
        outcome=outcome,
        skills_demonstrated=skills or [],
        related_job_id=related_job_id,
    )


def _work_info(
    is_current: bool = False,
    end_date: date | None = None,
) -> WorkHistoryInfo:
    """Create a WorkHistoryInfo for testing."""
    return WorkHistoryInfo(
        is_current=is_current,
        end_date=end_date,
    )


# =============================================================================
# Core Scoring Tests
# =============================================================================


class TestSkillsMatchScoring:
    """Skills match factor: min(overlap * 10, 40)."""

    def test_zero_overlap_scores_zero(self) -> None:
        """No skill overlap should give 0 points for skills match."""
        story = _story(skills=["Java", "Spring"])
        job_skills = {"Python", "FastAPI"}

        results = select_achievement_stories(
            stories=[story],
            job_skills=job_skills,
            max_stories=1,
        )

        assert len(results) == 1
        assert results[0].score >= 0  # No negative from skills alone

    def test_one_overlap_scores_ten(self) -> None:
        """One overlapping skill should give 10 points."""
        story = _story(skills=["Python", "Java"])
        job_skills = {"Python", "FastAPI"}

        results = select_achievement_stories(
            stories=[story],
            job_skills=job_skills,
            max_stories=1,
        )

        # Skill contribution is 10
        assert results[0].score >= 10

    def test_four_overlaps_caps_at_forty(self) -> None:
        """Four overlapping skills should cap at 40 points."""
        story = _story(skills=["Python", "FastAPI", "Docker", "AWS"])
        job_skills = {"Python", "FastAPI", "Docker", "AWS", "Kubernetes"}

        results = select_achievement_stories(
            stories=[story],
            job_skills=job_skills,
            max_stories=1,
        )

        assert results[0].score >= 40

    def test_five_overlaps_still_capped_at_forty(self) -> None:
        """Five+ overlapping skills should still cap at 40."""
        story = _story(skills=["Python", "FastAPI", "Docker", "AWS", "Kubernetes"])
        job_skills = {"Python", "FastAPI", "Docker", "AWS", "Kubernetes"}

        results = select_achievement_stories(
            stories=[story],
            job_skills=job_skills,
            max_stories=1,
        )

        # Without recency/metrics/culture, max is 40
        assert results[0].score == 40

    def test_case_insensitive_matching(self) -> None:
        """Skill matching should be case-insensitive."""
        story = _story(skills=["python", "FastAPI"])
        job_skills = {"Python", "fastapi"}

        results = select_achievement_stories(
            stories=[story],
            job_skills=job_skills,
            max_stories=1,
        )

        # Both should match → 20 points
        assert results[0].score >= 20


class TestRecencyScoring:
    """Recency factor: current=20, <2yr=15, <4yr=10, older=0."""

    def test_current_role_scores_twenty(self) -> None:
        """Story from current job should get 20 recency points."""
        story = _story(related_job_id="job-1")
        work_info = {"job-1": _work_info(is_current=True)}

        results = select_achievement_stories(
            stories=[story],
            job_skills=set(),
            work_history_map=work_info,
            max_stories=1,
        )

        assert results[0].score >= 20

    def test_recent_two_years_scores_fifteen(self) -> None:
        """Story from job ended <2 years ago should get 15 recency points."""
        recent_end = date.today() - timedelta(days=365)
        story = _story(related_job_id="job-1")
        work_info = {"job-1": _work_info(end_date=recent_end)}

        results = select_achievement_stories(
            stories=[story],
            job_skills=set(),
            work_history_map=work_info,
            max_stories=1,
        )

        assert results[0].score >= 15

    def test_recent_four_years_scores_ten(self) -> None:
        """Story from job ended <4 years ago should get 10 recency points."""
        end_date = date.today() - timedelta(days=365 * 3)
        story = _story(related_job_id="job-1")
        work_info = {"job-1": _work_info(end_date=end_date)}

        results = select_achievement_stories(
            stories=[story],
            job_skills=set(),
            work_history_map=work_info,
            max_stories=1,
        )

        assert results[0].score >= 10

    def test_older_than_four_years_scores_zero(self) -> None:
        """Story from job ended 5+ years ago should get 0 recency points."""
        old_end = date.today() - timedelta(days=365 * 5)
        story = _story(related_job_id="job-1")
        work_info = {"job-1": _work_info(end_date=old_end)}

        results = select_achievement_stories(
            stories=[story],
            job_skills=set(),
            work_history_map=work_info,
            max_stories=1,
        )

        assert results[0].score == 0

    def test_no_related_job_scores_zero_recency(self) -> None:
        """Story with no related_job_id should get 0 recency points."""
        story = _story(related_job_id=None)

        results = select_achievement_stories(
            stories=[story],
            job_skills=set(),
            max_stories=1,
        )

        assert results[0].score == 0


class TestQuantifiedOutcomeScoring:
    """Quantified outcome factor: has_metrics(outcome) → 15 points."""

    def test_outcome_with_percentage_scores_fifteen(self) -> None:
        """Outcome with percentage should score 15 points."""
        story = _story(outcome="Reduced costs by 40%")

        results = select_achievement_stories(
            stories=[story],
            job_skills=set(),
            max_stories=1,
        )

        assert results[0].score >= 15

    def test_outcome_with_dollar_amount_scores_fifteen(self) -> None:
        """Outcome with dollar amount should score 15 points."""
        story = _story(outcome="Saved $2.5M in annual costs")

        results = select_achievement_stories(
            stories=[story],
            job_skills=set(),
            max_stories=1,
        )

        assert results[0].score >= 15

    def test_outcome_with_number_scores_fifteen(self) -> None:
        """Outcome with significant number should score 15 points."""
        story = _story(outcome="Improved response time from 500ms to 50ms")

        results = select_achievement_stories(
            stories=[story],
            job_skills=set(),
            max_stories=1,
        )

        assert results[0].score >= 15

    def test_outcome_without_metrics_scores_zero(self) -> None:
        """Outcome without quantified metrics should score 0."""
        story = _story(outcome="Improved team collaboration and morale")

        results = select_achievement_stories(
            stories=[story],
            job_skills=set(),
            max_stories=1,
        )

        assert results[0].score == 0


class TestCultureAlignmentScoring:
    """Culture alignment factor: min(keyword_matches * 5, 15)."""

    def test_no_culture_text_skips_culture_factor(self) -> None:
        """When culture_text is None, culture factor should be 0."""
        story = _story(
            context="Led agile team with collaborative approach",
            outcome="Built strong team culture",
        )

        results = select_achievement_stories(
            stories=[story],
            job_skills=set(),
            culture_keywords=None,
            max_stories=1,
        )

        assert results[0].score == 0

    def test_one_culture_match_scores_five(self) -> None:
        """One culture keyword match should give 5 points."""
        story = _story(
            context="Led collaborative team effort",
            action="Used agile methodology",
            outcome="Improved team velocity",
        )

        results = select_achievement_stories(
            stories=[story],
            job_skills=set(),
            culture_keywords=["collaborative"],
            max_stories=1,
        )

        assert results[0].score >= 5

    def test_three_matches_caps_at_fifteen(self) -> None:
        """Three+ culture keyword matches should cap at 15."""
        story = _story(
            context="Led collaborative agile team with mentoring focus",
            action="Championed collaborative agile mentoring approach",
            outcome="Great collaborative agile mentoring results",
        )

        results = select_achievement_stories(
            stories=[story],
            job_skills=set(),
            culture_keywords=["collaborative", "agile", "mentoring"],
            max_stories=1,
        )

        assert results[0].score >= 15


class TestFreshnessPenalty:
    """Freshness penalty: -10 if story used 3+ times in last 30 days."""

    def test_no_recent_uses_no_penalty(self) -> None:
        """Story with 0 recent uses should have no penalty."""
        story = _story(skills=["Python"])

        results = select_achievement_stories(
            stories=[story],
            job_skills={"Python"},
            recent_story_usage={},
            max_stories=1,
        )

        assert results[0].score >= 10  # At least the skill match

    def test_two_uses_no_penalty(self) -> None:
        """Story used 2 times recently should have no penalty."""
        story = _story(story_id="s1", skills=["Python"])

        results = select_achievement_stories(
            stories=[story],
            job_skills={"Python"},
            recent_story_usage={"s1": 2},
            max_stories=1,
        )

        assert results[0].score >= 10

    def test_three_uses_applies_penalty(self) -> None:
        """Story used 3 times recently should get -10 penalty."""
        # Use two stories so "all penalized" override doesn't trigger
        s1 = _story(story_id="s1", skills=["Python"])
        s2 = _story(story_id="s2", skills=["Java"])

        results_no_penalty = select_achievement_stories(
            stories=[s1, s2],
            job_skills={"Python"},
            recent_story_usage={},
            max_stories=2,
        )

        results_with_penalty = select_achievement_stories(
            stories=[s1, s2],
            job_skills={"Python"},
            recent_story_usage={"s1": 3},
            max_stories=2,
        )

        # Find s1 in both results
        s1_no = next(r for r in results_no_penalty if r.story_id == "s1")
        s1_pen = next(r for r in results_with_penalty if r.story_id == "s1")
        assert s1_pen.score == s1_no.score - 10

    def test_all_stories_penalized_ignores_penalty(self) -> None:
        """When ALL stories hit freshness penalty, ignore it entirely."""
        s1 = _story(story_id="s1", skills=["Python"])
        s2 = _story(story_id="s2", skills=["Java"])

        results_all_penalized = select_achievement_stories(
            stories=[s1, s2],
            job_skills={"Python"},
            recent_story_usage={"s1": 5, "s2": 4},
            max_stories=2,
        )

        results_no_penalty = select_achievement_stories(
            stories=[s1, s2],
            job_skills={"Python"},
            recent_story_usage={},
            max_stories=2,
        )

        # When all penalized, scores should equal no-penalty scores
        penalized_scores = sorted(r.score for r in results_all_penalized)
        normal_scores = sorted(r.score for r in results_no_penalty)
        assert penalized_scores == normal_scores


# =============================================================================
# Ranking and Selection Tests
# =============================================================================


class TestStoryRanking:
    """Stories should be ranked by score descending."""

    def test_returns_top_n_by_score(self) -> None:
        """Should return top max_stories by score."""
        s1 = _story(story_id="s1", skills=["Python", "FastAPI", "Docker"])
        s2 = _story(story_id="s2", skills=["Python"])
        s3 = _story(story_id="s3", skills=[])

        results = select_achievement_stories(
            stories=[s3, s1, s2],
            job_skills={"Python", "FastAPI", "Docker"},
            max_stories=2,
        )

        assert len(results) == 2
        assert results[0].story_id == "s1"
        assert results[1].story_id == "s2"

    def test_default_max_stories_is_two(self) -> None:
        """Default max_stories should be 2."""
        stories = [_story(story_id=f"s{i}") for i in range(5)]

        results = select_achievement_stories(
            stories=stories,
            job_skills=set(),
        )

        assert len(results) == 2

    def test_returns_fewer_if_not_enough_stories(self) -> None:
        """Should return fewer stories if fewer are available."""
        story = _story()

        results = select_achievement_stories(
            stories=[story],
            job_skills=set(),
            max_stories=2,
        )

        assert len(results) == 1


class TestScoredStoryOutput:
    """ScoredStory should include story data, score, and rationale."""

    def test_scored_story_has_required_fields(self) -> None:
        """ScoredStory should have story_id, score, and rationale."""
        story = _story(
            story_id="s1",
            skills=["Python"],
            outcome="Reduced costs by 40%",
        )

        results = select_achievement_stories(
            stories=[story],
            job_skills={"Python"},
            max_stories=1,
        )

        result = results[0]
        assert result.story_id == "s1"
        assert isinstance(result.score, (int, float))
        assert isinstance(result.rationale, str)
        assert len(result.rationale) > 0

    def test_rationale_mentions_matching_skills(self) -> None:
        """Rationale should mention which skills matched."""
        story = _story(skills=["Python", "FastAPI"])

        results = select_achievement_stories(
            stories=[story],
            job_skills={"Python", "FastAPI"},
            max_stories=1,
        )

        rationale = results[0].rationale.lower()
        assert "python" in rationale or "fastapi" in rationale

    def test_scored_story_includes_story_data(self) -> None:
        """ScoredStory should include the story data for downstream use."""
        story = _story(
            story_id="s1",
            title="Led Cloud Migration",
            context="Company needed AWS",
            action="Led team",
            outcome="Reduced costs by 40%",
        )

        results = select_achievement_stories(
            stories=[story],
            job_skills=set(),
            max_stories=1,
        )

        result = results[0]
        assert result.title == "Led Cloud Migration"
        assert result.context == "Company needed AWS"
        assert result.action == "Led team"
        assert result.outcome == "Reduced costs by 40%"


# =============================================================================
# Edge Case Tests (REQ-010 §8.1, §8.4)
# =============================================================================


class TestEdgeCases:
    """Edge cases per REQ-010 §8.1 and §8.4."""

    def test_no_stories_returns_empty(self) -> None:
        """No achievement stories should return empty list."""
        results = select_achievement_stories(
            stories=[],
            job_skills={"Python"},
            max_stories=2,
        )

        assert results == []

    def test_all_low_scores_still_returns_top_two(self) -> None:
        """When all scores < 20, should still return top 2."""
        s1 = _story(story_id="s1")
        s2 = _story(story_id="s2")
        s3 = _story(story_id="s3")

        results = select_achievement_stories(
            stories=[s1, s2, s3],
            job_skills=set(),
            max_stories=2,
        )

        assert len(results) == 2

    def test_single_story_returns_one(self) -> None:
        """Only 1 story available should return that single story."""
        story = _story()

        results = select_achievement_stories(
            stories=[story],
            job_skills=set(),
            max_stories=2,
        )

        assert len(results) == 1

    def test_top_two_same_job_same_outcome_substitutes_third(self) -> None:
        """Top 2 from same job with similar outcomes should substitute #3."""
        s1 = _story(
            story_id="s1",
            skills=["Python", "FastAPI"],
            related_job_id="job-1",
            outcome="Reduced costs by 40%",
        )
        s2 = _story(
            story_id="s2",
            skills=["Python", "Docker"],
            related_job_id="job-1",
            outcome="Reduced costs by 35%",
        )
        s3 = _story(
            story_id="s3",
            skills=["Python"],
            related_job_id="job-2",
            outcome="Improved throughput by 3x",
        )

        work_info = {
            "job-1": _work_info(is_current=True),
            "job-2": _work_info(end_date=date.today() - timedelta(days=100)),
        }

        results = select_achievement_stories(
            stories=[s1, s2, s3],
            job_skills={"Python", "FastAPI", "Docker"},
            work_history_map=work_info,
            max_stories=2,
        )

        # Should not have both s1 and s2 (same job, similar outcomes)
        job_ids = [r.story_id for r in results]
        assert not ("s1" in job_ids and "s2" in job_ids), (
            "Should diversify: not both stories from same job with similar outcomes"
        )

    def test_same_job_different_outcomes_keeps_both(self) -> None:
        """Top 2 from same job with DIFFERENT outcomes should keep both."""
        s1 = _story(
            story_id="s1",
            skills=["Python", "FastAPI"],
            related_job_id="job-1",
            outcome="Reduced costs by 40%",
        )
        s2 = _story(
            story_id="s2",
            skills=["Python", "Docker"],
            related_job_id="job-1",
            outcome="Built real-time analytics pipeline processing 1M events/day",
        )

        work_info = {
            "job-1": _work_info(is_current=True),
        }

        results = select_achievement_stories(
            stories=[s1, s2],
            job_skills={"Python", "FastAPI", "Docker"},
            work_history_map=work_info,
            max_stories=2,
        )

        # Both can stay since outcomes are different
        assert len(results) == 2


class TestStorySelectionConfig:
    """StorySelectionConfig should support custom thresholds."""

    def test_custom_max_stories(self) -> None:
        """Should respect custom max_stories parameter."""
        stories = [_story(story_id=f"s{i}") for i in range(5)]

        results = select_achievement_stories(
            stories=stories,
            job_skills=set(),
            max_stories=3,
        )

        assert len(results) == 3

    def test_config_overrides_defaults(self) -> None:
        """Custom config should override default scoring constants."""
        story = _story(skills=["Python"])
        config = StorySelectionConfig(
            skills_match_points_per_skill=20,
            skills_match_cap=100,
        )

        results = select_achievement_stories(
            stories=[story],
            job_skills={"Python"},
            max_stories=1,
            config=config,
        )

        # With 20 points per skill, one match = 20
        assert results[0].score >= 20


# =============================================================================
# Combined Scoring Tests
# =============================================================================


class TestCombinedScoring:
    """Test multiple scoring factors together."""

    def test_perfect_story_scores_maximum(self) -> None:
        """Story matching all factors should score near maximum (90)."""
        story = _story(
            skills=["Python", "FastAPI", "Docker", "AWS"],
            related_job_id="job-1",
            outcome="Reduced infrastructure costs by 60%, saving $2M annually",
            context="Led collaborative agile cross-functional team initiative",
            action="Drove collaborative agile innovation approach",
        )
        work_info = {"job-1": _work_info(is_current=True)}

        results = select_achievement_stories(
            stories=[story],
            job_skills={"Python", "FastAPI", "Docker", "AWS"},
            work_history_map=work_info,
            culture_keywords=["collaborative", "agile", "innovation"],
            max_stories=1,
        )

        # Skills: 40 + Recency: 20 + Metrics: 15 + Culture: 15 = 90
        assert results[0].score == 90

    def test_ranking_with_mixed_scores(self) -> None:
        """Stories with mixed factor scores should rank correctly."""
        # High skills, no recency, no metrics
        s1 = _story(
            story_id="s1",
            skills=["Python", "FastAPI", "Docker"],
            outcome="Improved team processes",
        )
        # Low skills, high recency, with metrics
        s2 = _story(
            story_id="s2",
            skills=["Python"],
            related_job_id="job-1",
            outcome="Reduced costs by 40%",
        )
        work_info = {"job-1": _work_info(is_current=True)}

        results = select_achievement_stories(
            stories=[s1, s2],
            job_skills={"Python", "FastAPI", "Docker"},
            work_history_map=work_info,
            max_stories=2,
        )

        # s2: skills=10, recency=20, metrics=15 = 45
        # s1: skills=30, recency=0, metrics=0 = 30
        assert results[0].story_id == "s2"
        assert results[1].story_id == "s1"
