"""Achievement story selection service.

REQ-007 §8.6: Story Selection Logic
REQ-010 §5.2: Achievement Story Selection

Selects and ranks achievement stories from the persona for use in cover
letter generation. Each story is scored across five factors:

    Skills match (0-40):      min(overlap_count * 10, 40)
    Recency (0-20):           current=20, <2yr=15, <4yr=10, older=0
    Quantified outcome (0-15): has_metrics(outcome) → 15
    Culture alignment (0-15): min(culture_keyword_matches * 5, 15)
    Freshness penalty (-10):  story used 3+ times in last 30 days

Design rationale (REQ-010 §5.2): "2 stories is optimal — enough to show a
pattern of success without overwhelming. 3 max for senior/executive roles."

WHY PURE FUNCTIONS: This service accepts pre-extracted data (skill sets,
culture keywords, work history map) rather than querying the database directly.
This keeps the function pure, testable, and decoupled from data access. The
graph node is responsible for fetching data and passing it in.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import date

logger = logging.getLogger(__name__)

# =============================================================================
# Constants (REQ-010 §5.2)
# =============================================================================

_DEFAULT_SKILLS_POINTS_PER_SKILL: int = 10
"""Points per overlapping skill."""

_DEFAULT_SKILLS_CAP: int = 40
"""Maximum points from skills match factor."""

_RECENCY_CURRENT: int = 20
"""Recency points for current role."""

_RECENCY_TWO_YEARS: int = 15
"""Recency points for role ended within 2 years."""

_RECENCY_FOUR_YEARS: int = 10
"""Recency points for role ended within 4 years."""

_METRICS_POINTS: int = 15
"""Points for having quantified metrics in outcome."""

_DEFAULT_CULTURE_POINTS_PER_MATCH: int = 5
"""Points per culture keyword match."""

_DEFAULT_CULTURE_CAP: int = 15
"""Maximum points from culture alignment factor."""

_FRESHNESS_PENALTY: int = 10
"""Penalty for stories used 3+ times in last 30 days."""

_FRESHNESS_THRESHOLD: int = 3
"""Number of recent uses before freshness penalty applies."""

_DEFAULT_MAX_STORIES: int = 2
"""Default number of stories to return."""

_MAX_INPUT_STORIES: int = 100
"""Safety bound on input stories to prevent resource exhaustion."""

_MAX_SKILLS: int = 500
"""Safety bound on job skills set size."""

_MAX_CULTURE_KEYWORDS: int = 100
"""Safety bound on culture keywords list size."""

# WHY REGEX: Fast path for metrics detection. Catches percentages, dollar
# amounts, multipliers, and significant numbers. Avoids LLM call for a
# pattern that's reliably detectable with regex (REQ-010 §6.4).
_METRICS_PATTERN = re.compile(
    r"""
    \d+%                  # Percentages: 40%, 100%
    | \$[\d,]+            # Dollar amounts: $2.5M, $100,000
    | \d+x                # Multipliers: 3x, 10x
    | \d{2,}              # Significant numbers (2+ digits): 50ms, 1000 users
    """,
    re.VERBOSE | re.IGNORECASE,
)


# =============================================================================
# Data Models
# =============================================================================


@dataclass(frozen=True)
class StoryInput:
    """Input data for a single achievement story.

    Attributes:
        id: Unique story identifier.
        title: Story title.
        context: STAR context (situation/task).
        action: STAR action taken.
        outcome: STAR result/outcome.
        skills_demonstrated: List of skill names the story demonstrates.
        related_job_id: ID of the work history entry this story relates to.
    """

    id: str
    title: str
    context: str
    action: str
    outcome: str
    skills_demonstrated: list[str] = field(default_factory=list)
    related_job_id: str | None = None


@dataclass(frozen=True)
class WorkHistoryInfo:
    """Minimal work history data needed for recency scoring.

    Attributes:
        is_current: Whether this is the user's current job.
        end_date: When the job ended (None if current).
    """

    is_current: bool = False
    end_date: date | None = None


@dataclass(frozen=True)
class StorySelectionConfig:
    """Configuration overrides for scoring constants.

    Allows customization of scoring weights for testing or future tuning.

    Attributes:
        skills_match_points_per_skill: Points per overlapping skill.
        skills_match_cap: Maximum points from skills match.
        culture_points_per_match: Points per culture keyword match.
        culture_cap: Maximum culture alignment points.
    """

    skills_match_points_per_skill: int = _DEFAULT_SKILLS_POINTS_PER_SKILL
    skills_match_cap: int = _DEFAULT_SKILLS_CAP
    culture_points_per_match: int = _DEFAULT_CULTURE_POINTS_PER_MATCH
    culture_cap: int = _DEFAULT_CULTURE_CAP


@dataclass(frozen=True)
class ScoredStory:
    """A scored and ranked achievement story.

    REQ-010 §5.2: Each ScoredStory includes the story data, numeric score,
    and a human-readable rationale explaining why it was selected.

    Attributes:
        story_id: Original story ID.
        title: Story title.
        context: STAR context.
        action: STAR action.
        outcome: STAR outcome.
        score: Numeric score (sum of all factors).
        rationale: Human-readable selection reason.
    """

    story_id: str
    title: str
    context: str
    action: str
    outcome: str
    score: int
    rationale: str


# =============================================================================
# Scoring Functions
# =============================================================================


def _score_skills_match(
    story_skills: list[str],
    job_skills: set[str],
    config: StorySelectionConfig,
) -> tuple[int, list[str]]:
    """Score skills overlap between story and job.

    Args:
        story_skills: Skills demonstrated in the story.
        job_skills: Skills required by the job.
        config: Scoring configuration.

    Returns:
        Tuple of (score, list of matching skill names).
    """
    story_lower = {s.lower() for s in story_skills}
    job_lower = {s.lower() for s in job_skills}
    overlap = story_lower & job_lower
    score = min(
        len(overlap) * config.skills_match_points_per_skill,
        config.skills_match_cap,
    )
    return score, sorted(overlap)


def _score_recency(
    related_job_id: str | None,
    work_history_map: dict[str, WorkHistoryInfo],
) -> tuple[int, str]:
    """Score story recency based on related work history.

    Args:
        related_job_id: ID of the related work history entry.
        work_history_map: Map of job ID to work history info.

    Returns:
        Tuple of (score, recency description).
    """
    if related_job_id is None:
        return 0, ""

    work_info = work_history_map.get(related_job_id)
    if work_info is None:
        return 0, ""

    if work_info.is_current:
        return _RECENCY_CURRENT, "From current role"

    if work_info.end_date is None:
        return 0, ""

    days_since = (date.today() - work_info.end_date).days
    months_since = days_since / 30.44  # Average days per month

    if months_since < 24:
        return _RECENCY_TWO_YEARS, "From recent role (<2 years)"
    if months_since < 48:
        return _RECENCY_FOUR_YEARS, "From role within 4 years"
    return 0, ""


def has_metrics(text: str) -> bool:
    """Check if text contains quantified metrics.

    REQ-010 §6.4: Regex-based fast path for metrics detection.

    Args:
        text: Text to check for metrics patterns.

    Returns:
        True if metrics pattern found.
    """
    return bool(_METRICS_PATTERN.search(text))


def _score_quantified_outcome(outcome: str) -> tuple[int, str]:
    """Score whether the story outcome has quantified metrics.

    Args:
        outcome: Story outcome text.

    Returns:
        Tuple of (score, description).
    """
    if has_metrics(outcome):
        return _METRICS_POINTS, "Quantified impact"
    return 0, ""


def _score_culture_alignment(
    story: StoryInput,
    culture_keywords: list[str] | None,
    config: StorySelectionConfig,
) -> tuple[int, list[str]]:
    """Score culture keyword alignment.

    Checks culture keywords against story context, action, and outcome.

    Args:
        story: The story to check.
        culture_keywords: Keywords extracted from job posting culture_text.
        config: Scoring configuration.

    Returns:
        Tuple of (score, list of matching keywords).
    """
    if culture_keywords is None:
        return 0, []

    story_text = f"{story.context} {story.action} {story.outcome}".lower()
    matches = [kw for kw in culture_keywords if kw.lower() in story_text]
    score = min(
        len(matches) * config.culture_points_per_match,
        config.culture_cap,
    )
    return score, matches


def _apply_freshness_penalty(
    story_id: str,
    recent_story_usage: dict[str, int],
) -> int:
    """Calculate freshness penalty for a story.

    Args:
        story_id: The story's ID.
        recent_story_usage: Map of story_id to usage count in last 30 days.

    Returns:
        Penalty value (negative or 0).
    """
    usage_count = recent_story_usage.get(story_id, 0)
    if usage_count >= _FRESHNESS_THRESHOLD:
        return -_FRESHNESS_PENALTY
    return 0


def _build_rationale(
    matching_skills: list[str],
    recency_desc: str,
    metrics_desc: str,
    culture_matches: list[str],
) -> str:
    """Build human-readable rationale from scoring components.

    Args:
        matching_skills: Skills that matched the job.
        recency_desc: Recency description string.
        metrics_desc: Metrics description string.
        culture_matches: Culture keywords that matched.

    Returns:
        Semicolon-separated rationale string.
    """
    parts: list[str] = []
    if matching_skills:
        parts.append(f"Demonstrates {', '.join(matching_skills)}")
    if recency_desc:
        parts.append(recency_desc)
    if metrics_desc:
        parts.append(metrics_desc)
    if culture_matches:
        parts.append(f"Culture fit: {', '.join(culture_matches)}")
    return "; ".join(parts) if parts else "Best available story"


def _outcomes_are_similar(outcome_a: str, outcome_b: str) -> bool:
    """Check if two story outcomes are similar enough to warrant diversification.

    Uses simple word overlap heuristic. Two outcomes are "similar" if they
    share more than 50% of their significant words (4+ chars).

    Args:
        outcome_a: First outcome text.
        outcome_b: Second outcome text.

    Returns:
        True if outcomes are similar.
    """
    words_a = {w.lower() for w in outcome_a.split() if len(w) >= 4}
    words_b = {w.lower() for w in outcome_b.split() if len(w) >= 4}

    if not words_a or not words_b:
        return False

    overlap = len(words_a & words_b)
    smaller = min(len(words_a), len(words_b))

    return overlap > smaller * 0.5


# =============================================================================
# Main Selection Function
# =============================================================================


def select_achievement_stories(
    stories: list[StoryInput],
    job_skills: set[str],
    work_history_map: dict[str, WorkHistoryInfo] | None = None,
    culture_keywords: list[str] | None = None,
    recent_story_usage: dict[str, int] | None = None,
    max_stories: int = _DEFAULT_MAX_STORIES,
    config: StorySelectionConfig | None = None,
) -> list[ScoredStory]:
    """Select and rank achievement stories for cover letter generation.

    REQ-007 §8.6: Match stories to job requirements, prefer recent and
    quantified stories, avoid repetition from recent applications.
    REQ-010 §5.2: Detailed scoring algorithm with five factors.

    Args:
        stories: Achievement stories from the persona.
        job_skills: Skill names extracted from the job posting.
        work_history_map: Map of work history ID to recency info.
        culture_keywords: Keywords from job posting culture_text.
        recent_story_usage: Map of story_id to usage count in last 30 days.
        max_stories: Maximum number of stories to return (default 2).
        config: Optional scoring configuration overrides.

    Returns:
        List of ScoredStory objects, ranked by score descending.
        Empty list if no stories are provided.
    """
    if not stories:
        return []

    cfg = config or StorySelectionConfig()
    work_map = work_history_map or {}
    usage_map = recent_story_usage or {}

    # Safety bounds
    max_stories = max(1, min(max_stories, _MAX_INPUT_STORIES))
    bounded_stories = stories[:_MAX_INPUT_STORIES]
    bounded_skills = set(list(job_skills)[:_MAX_SKILLS])
    bounded_culture = (
        culture_keywords[:_MAX_CULTURE_KEYWORDS] if culture_keywords else None
    )

    # Score each story
    scored: list[tuple[StoryInput, int, str]] = []
    all_penalized = True

    for story in bounded_stories:
        skill_score, matching_skills = _score_skills_match(
            story.skills_demonstrated,
            bounded_skills,
            cfg,
        )
        recency_score, recency_desc = _score_recency(
            story.related_job_id,
            work_map,
        )
        metrics_score, metrics_desc = _score_quantified_outcome(story.outcome)
        culture_score, culture_matches = _score_culture_alignment(
            story,
            bounded_culture,
            cfg,
        )
        freshness = _apply_freshness_penalty(story.id, usage_map)

        if freshness == 0:
            all_penalized = False

        base_score = skill_score + recency_score + metrics_score + culture_score
        total_score = base_score + freshness

        rationale = _build_rationale(
            matching_skills,
            recency_desc,
            metrics_desc,
            culture_matches,
        )

        scored.append((story, total_score, rationale))

    # REQ-010 §8.4: If ALL stories hit freshness penalty, ignore it
    if all_penalized and usage_map:
        logger.info("All stories hit freshness penalty; ignoring penalty")
        scored = [
            (story, score + _FRESHNESS_PENALTY, rationale)
            for story, score, rationale in scored
        ]

    # Sort by score descending
    scored.sort(key=lambda x: -x[1])

    # Diversify: avoid top-2 from same job with similar outcomes (REQ-010 §8.4)
    selected = _diversify_selection(scored, max_stories)

    return [
        ScoredStory(
            story_id=story.id,
            title=story.title,
            context=story.context,
            action=story.action,
            outcome=story.outcome,
            score=score,
            rationale=rationale,
        )
        for story, score, rationale in selected
    ]


def _is_duplicate_job_story(
    candidate: StoryInput,
    selected: list[tuple[StoryInput, int, str]],
) -> bool:
    """Check if candidate shares a job with similar outcome to a selected story."""
    if candidate.related_job_id is None:
        return False
    for sel_story, _, _ in selected:
        if (
            candidate.related_job_id == sel_story.related_job_id
            and _outcomes_are_similar(candidate.outcome, sel_story.outcome)
        ):
            return True
    return False


def _fill_remaining_slots(
    selected: list[tuple[StoryInput, int, str]],
    remaining: list[tuple[StoryInput, int, str]],
    max_stories: int,
) -> None:
    """Fill remaining slots with non-duplicate stories if diversification filtered too many."""
    selected_ids = {s[0].id for s in selected}
    for candidate_story, candidate_score, candidate_rationale in remaining:
        if len(selected) >= max_stories:
            break
        if candidate_story.id not in selected_ids:
            selected.append((candidate_story, candidate_score, candidate_rationale))


def _diversify_selection(
    scored: list[tuple[StoryInput, int, str]],
    max_stories: int,
) -> list[tuple[StoryInput, int, str]]:
    """Apply diversification to avoid redundant story selection.

    REQ-010 §8.4: Top 2 stories from same job entry with similar outcomes
    should have one substituted with the next-best alternative.

    Args:
        scored: Stories sorted by score descending.
        max_stories: Maximum stories to return.

    Returns:
        Selected stories after diversification.
    """
    if len(scored) <= 1 or max_stories <= 1:
        return scored[:max_stories]

    selected: list[tuple[StoryInput, int, str]] = [scored[0]]
    remaining = scored[1:]

    for candidate_story, candidate_score, candidate_rationale in remaining:
        if len(selected) >= max_stories:
            break
        if not _is_duplicate_job_story(candidate_story, selected):
            selected.append((candidate_story, candidate_score, candidate_rationale))

    # If diversification filtered too many, fill remaining slots
    if len(selected) < max_stories:
        _fill_remaining_slots(selected, remaining, max_stories)

    return selected[:max_stories]
