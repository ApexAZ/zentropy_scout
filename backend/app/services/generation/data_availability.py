"""Data availability checks for content generation.

REQ-010 §8.1: Insufficient Data edge cases.

Detects five degraded-data scenarios before or during generation and
returns a structured result with flags and user-facing warnings:

1. No achievement stories → skip cover letter
2. Voice profile incomplete → use defaults + warning
3. No matching stories (all scores < threshold) → use top 2 + disclaimer
4. Job posting minimal (< 2 skills) → generic approach + flag
5. No culture_text → skip culture alignment section
"""

from dataclasses import dataclass

_MIN_EXTRACTED_SKILLS: int = 2
"""Minimum extracted skills for a non-minimal job posting."""

_MIN_STORY_MATCH_SCORE: int = 20
"""Minimum story score to be considered a meaningful match."""

_VOICE_PROFILE_REQUIRED_FIELDS: frozenset[str] = frozenset(
    {"tone", "sentence_style", "vocabulary_level"}
)
"""Voice profile fields that must be non-empty for full-quality generation."""


@dataclass(frozen=True)
class DataAvailabilityResult:
    """Result of checking data availability for content generation.

    REQ-010 §8.1: Captures all insufficient data scenarios in a single
    immutable result. Each flag corresponds to a specific scenario from
    the spec.

    Attributes:
        can_generate_cover_letter: False when no achievement stories exist.
        voice_profile_incomplete: True when required voice fields are missing.
        has_low_match_stories: True when all story scores are below threshold.
        is_minimal_job_posting: True when fewer than 2 skills were extracted.
        skip_culture_alignment: True when no culture_text is available.
        warnings: User-facing warning messages for each detected scenario.
    """

    can_generate_cover_letter: bool
    voice_profile_incomplete: bool
    has_low_match_stories: bool
    is_minimal_job_posting: bool
    skip_culture_alignment: bool
    warnings: tuple[str, ...]


def check_data_availability(
    *,
    achievement_story_count: int,
    missing_voice_fields: tuple[str, ...],
    extracted_skills_count: int,
    has_culture_text: bool,
    top_story_scores: tuple[float, ...] | None = None,
) -> DataAvailabilityResult:
    """Check data availability for ghostwriter content generation.

    REQ-010 §8.1: Evaluates five insufficient data scenarios and returns
    a structured result with flags and user-facing warnings.

    Args:
        achievement_story_count: Number of achievement stories in persona.
        missing_voice_fields: Voice profile field names that are empty.
        extracted_skills_count: Number of skills extracted from job posting.
        has_culture_text: Whether the job posting has culture_text.
        top_story_scores: Scores of selected stories (None if not yet scored).

    Returns:
        DataAvailabilityResult with flags and warnings for each scenario.
    """
    warnings: list[str] = []

    # Scenario 1: No achievement stories → skip cover letter
    can_generate_cover_letter = achievement_story_count > 0
    if not can_generate_cover_letter:
        warnings.append(
            "No achievement stories found in your profile. "
            "Cover letter generation will be skipped. "
            "Add stories in your persona to enable cover letters."
        )

    # Scenario 2: Voice profile incomplete → defaults + warning
    voice_profile_incomplete = len(missing_voice_fields) > 0
    if voice_profile_incomplete:
        field_list = ", ".join(missing_voice_fields)
        warnings.append(
            f"Voice profile is incomplete (missing: {field_list}). "
            "Sensible defaults will be used, but the output may not "
            "match your authentic writing style."
        )

    # Scenario 3: No matching stories → use top 2 + disclaimer
    has_low_match_stories = False
    if top_story_scores is not None and len(top_story_scores) > 0:
        has_low_match_stories = all(
            s < _MIN_STORY_MATCH_SCORE for s in top_story_scores
        )
        if has_low_match_stories:
            warnings.append(
                "None of your achievement stories closely match this job's "
                "requirements. The best available stories will be used, "
                "but relevance may be limited."
            )

    # Scenario 4: Job posting minimal → generic approach + flag
    is_minimal_job_posting = extracted_skills_count < _MIN_EXTRACTED_SKILLS
    if is_minimal_job_posting:
        warnings.append(
            "Limited information was extracted from this job posting. "
            "A generic approach will be used. Please review the output "
            "carefully for relevance."
        )

    # Scenario 5: No culture_text → skip culture alignment
    skip_culture_alignment = not has_culture_text
    if skip_culture_alignment:
        warnings.append(
            "No culture signals were found in this job posting. "
            "The culture alignment section will be skipped."
        )

    return DataAvailabilityResult(
        can_generate_cover_letter=can_generate_cover_letter,
        voice_profile_incomplete=voice_profile_incomplete,
        has_low_match_stories=has_low_match_stories,
        is_minimal_job_posting=is_minimal_job_posting,
        skip_culture_alignment=skip_culture_alignment,
        warnings=tuple(warnings),
    )
