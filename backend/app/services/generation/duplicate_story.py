"""Duplicate story selection edge case detection.

REQ-010 §8.4: Duplicate Story Selection.

Detects four degenerate story selection scenarios and returns a structured
result with adjusted word count targets and user-facing warnings:

1. Only 1 story available → shorter cover letter (200-250 words)
2. Top 2 stories from same job → substitute if outcomes similar
3. User excluded all high-scoring stories → use best available + disclaimer
4. All stories used recently → ignore freshness penalty
"""

from dataclasses import dataclass

_NORMAL_MIN_WORDS: int = 250
"""Standard minimum word count for cover letters (REQ-010 §5.1)."""

_NORMAL_MAX_WORDS: int = 350
"""Standard maximum word count for cover letters (REQ-010 §5.1)."""

_SHORT_MIN_WORDS: int = 200
"""Reduced minimum when only one story is available (REQ-010 §8.4)."""

_SHORT_MAX_WORDS: int = 250
"""Reduced maximum when only one story is available (REQ-010 §8.4)."""


@dataclass(frozen=True)
class DuplicateStoryResult:
    """Result of checking for story selection edge cases.

    REQ-010 §8.4: Captures all degenerate story selection scenarios in a
    single immutable result. The graph node uses these flags to adjust
    word count targets and surface warnings to the user.

    Attributes:
        use_short_format: True when only one story is available.
        substitution_made: True when a same-job story was replaced.
        using_excluded_fallback: True when all high-scoring stories excluded.
        freshness_overridden: True when freshness penalty was ignored.
        adjusted_min_words: Minimum word count target for the cover letter.
        adjusted_max_words: Maximum word count target for the cover letter.
        warnings: User-facing warning messages for each active scenario.
    """

    use_short_format: bool
    substitution_made: bool
    using_excluded_fallback: bool
    freshness_overridden: bool
    adjusted_min_words: int
    adjusted_max_words: int
    warnings: tuple[str, ...]


def check_duplicate_story_selection(
    *,
    available_count: int,
    substitution_made: bool,
    all_high_scoring_excluded: bool,
    freshness_overridden: bool,
) -> DuplicateStoryResult:
    """Detect story selection edge cases and compute adjustments.

    REQ-010 §8.4: Evaluates four degenerate scenarios post-selection and
    returns a structured result with adjusted word counts and warnings.
    The graph node calls this after ``select_achievement_stories`` to
    determine if any edge case handling is needed.

    Args:
        available_count: Total achievement stories available before selection.
        substitution_made: Whether a same-job story was substituted for variety.
        all_high_scoring_excluded: Whether user feedback excluded all top stories.
        freshness_overridden: Whether freshness penalty was ignored for all stories.

    Returns:
        DuplicateStoryResult with flags, adjusted word counts, and warnings.
    """
    warnings: list[str] = []

    # Scenario 1: Only 1 story available → shorter cover letter
    use_short_format = available_count == 1
    if use_short_format:
        adjusted_min = _SHORT_MIN_WORDS
        adjusted_max = _SHORT_MAX_WORDS
        warnings.append(
            "Only one achievement story available. "
            "Generating a shorter cover letter (200-250 words)."
        )
    else:
        adjusted_min = _NORMAL_MIN_WORDS
        adjusted_max = _NORMAL_MAX_WORDS

    # Scenario 2: Same-job substitution
    if substitution_made:
        warnings.append(
            "Top stories were from the same role with similar outcomes. "
            "An alternative story was substituted for variety."
        )

    # Scenario 3: All high-scoring stories excluded by user
    using_excluded_fallback = all_high_scoring_excluded
    if using_excluded_fallback:
        warnings.append(
            "All high-scoring stories were excluded per your feedback. "
            "Using the best available alternatives."
        )

    # Scenario 4: Freshness penalty overridden
    if freshness_overridden:
        warnings.append(
            "All stories have been used recently. Reusing stories for best results."
        )

    return DuplicateStoryResult(
        use_short_format=use_short_format,
        substitution_made=substitution_made,
        using_excluded_fallback=using_excluded_fallback,
        freshness_overridden=freshness_overridden,
        adjusted_min_words=adjusted_min,
        adjusted_max_words=adjusted_max,
        warnings=tuple(warnings),
    )
