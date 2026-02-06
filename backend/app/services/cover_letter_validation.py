"""Cover letter validation.

REQ-010 §5.4: Cover Letter Validation.

Validates generated cover letters against five rules:

1. Word count bounds (250-350) — uses §5.1 constants.
2. Blacklisted phrases from voice profile — catches voice adherence violations.
3. Company name in opening paragraph — ensures specificity.
4. Metric accuracy — flags metrics not from selected stories.
5. Skills fabrication check — warns if draft mentions too many unlisted skills.

Errors (severity="error") block presentation to user; warnings are shown
but do not block. The ``passed`` field is True only when there are no errors.

Pattern follows modification_limits.py: pure functions with pre-extracted data.
The caller (Ghostwriter agent) pre-extracts metrics, skills, and voice profile
data before calling validate_cover_letter().
"""

import logging
import re
from dataclasses import dataclass
from typing import Literal

from app.services.cover_letter_structure import (
    MAX_COVER_LETTER_WORDS,
    MIN_COVER_LETTER_WORDS,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

_MAX_DRAFT_LENGTH: int = 50_000
"""Maximum character length for draft text."""

_MAX_THINGS_TO_AVOID: int = 100
"""Maximum number of blacklisted phrases."""

_MAX_STORY_METRICS: int = 200
"""Maximum number of story metrics."""

_MAX_SKILLS: int = 500
"""Maximum number of skills (story or draft)."""

_MAX_COMPANY_NAME_LENGTH: int = 500
"""Maximum character length for company name."""

_SUSPICIOUS_SKILLS_THRESHOLD: int = 3
"""Number of unknown skills before triggering fabrication warning."""

# Split into separate simple patterns to keep regex complexity low (S5843)
_PERCENTAGE_PATTERN = re.compile(r"\d+(?:\.\d+)?%")
_DOLLAR_PATTERN = re.compile(r"\$[\d,.]+[MBK]?", re.IGNORECASE)
_MULTIPLIER_PATTERN = re.compile(r"\d+(?:\.\d+)?x", re.IGNORECASE)


# =============================================================================
# Data Structures
# =============================================================================


@dataclass(frozen=True)
class ValidationIssue:
    """A single validation issue found in a cover letter draft.

    Attributes:
        severity: "error" (blocks presentation) or "warning" (shown only).
        rule: Machine-readable rule identifier.
        message: Human-readable description of the issue.
    """

    severity: Literal["error", "warning"]
    rule: str
    message: str


@dataclass(frozen=True)
class CoverLetterValidation:
    """Result of validating a cover letter draft.

    Attributes:
        passed: True if no errors (warnings allowed).
        issues: Tuple of validation issues found.
        word_count: Word count of the draft.
    """

    passed: bool
    issues: tuple[ValidationIssue, ...]
    word_count: int


# =============================================================================
# Metric Extraction
# =============================================================================


def extract_draft_metrics(text: str) -> set[str]:
    """Extract metric-like patterns from text using regex.

    Captures percentages (40%, 2.5%), dollar amounts ($2.5M, $100,000),
    and multipliers (3x, 10x). Used for comparing draft metrics against
    story metrics in Rule 4.

    Args:
        text: Text to extract metrics from.

    Returns:
        Set of extracted metric strings (lowercased).
    """
    matches: set[str] = set()
    for pattern in (_PERCENTAGE_PATTERN, _DOLLAR_PATTERN, _MULTIPLIER_PATTERN):
        matches.update(m.lower() for m in pattern.findall(text))
    return matches


# =============================================================================
# Rule Functions
# =============================================================================


def _check_word_count(word_count: int) -> list[ValidationIssue]:
    """Rule 1: Word count must be within 250-350 range.

    Args:
        word_count: Number of words in the draft.

    Returns:
        List with one issue if out of range, empty otherwise.
    """
    issues: list[ValidationIssue] = []
    if word_count < MIN_COVER_LETTER_WORDS:
        issues.append(
            ValidationIssue(
                severity="error",
                rule="length_min",
                message=(
                    f"Too short: {word_count} words (minimum {MIN_COVER_LETTER_WORDS})"
                ),
            )
        )
    elif word_count > MAX_COVER_LETTER_WORDS:
        issues.append(
            ValidationIssue(
                severity="warning",
                rule="length_max",
                message=(
                    f"Long: {word_count} words "
                    f"(target {MIN_COVER_LETTER_WORDS}-{MAX_COVER_LETTER_WORDS})"
                ),
            )
        )
    return issues


def _check_blacklist(
    draft_lower: str,
    things_to_avoid: list[str],
) -> list[ValidationIssue]:
    """Rule 2: Draft must not contain blacklisted phrases.

    Args:
        draft_lower: Lowercased draft text (pre-lowered by caller).
        things_to_avoid: Phrases from voice profile blacklist.

    Returns:
        List of error issues, one per matching phrase.
    """
    issues: list[ValidationIssue] = []
    for phrase in things_to_avoid:
        if phrase.lower() in draft_lower:
            issues.append(
                ValidationIssue(
                    severity="error",
                    rule="blacklist_violation",
                    message=f"Contains avoided phrase: '{phrase}'",
                )
            )
    return issues


def _check_company_specificity(
    draft_text: str,
    company_name: str,
) -> list[ValidationIssue]:
    """Rule 3: Company name should appear in the opening paragraph.

    The first paragraph is determined by splitting on ``\\n\\n``. If no
    paragraph break exists, the first 500 characters are used as the
    opening.

    Args:
        draft_text: The draft cover letter text.
        company_name: Target company name from job posting.

    Returns:
        List with one warning if company name is missing, empty otherwise.
    """
    if not company_name.strip():
        return []

    first_paragraph = (
        draft_text.split("\n\n")[0] if "\n\n" in draft_text else draft_text[:500]
    )

    if company_name.lower() not in first_paragraph.lower():
        return [
            ValidationIssue(
                severity="warning",
                rule="company_specificity",
                message="Company name not in opening paragraph",
            )
        ]
    return []


def _check_metric_accuracy(
    draft_text: str,
    story_metrics: set[str],
) -> list[ValidationIssue]:
    """Rule 4: Metrics in draft must come from selected stories.

    Extracts metric patterns from the draft and compares against the
    pre-extracted story metrics. Any draft metric not found in the story
    metrics set is flagged as potentially fabricated or misattributed.

    Args:
        draft_text: The draft cover letter text.
        story_metrics: Metrics pre-extracted from selected story outcomes.

    Returns:
        List of error issues, one per unmatched metric.
    """
    draft_metrics = extract_draft_metrics(draft_text)
    if not draft_metrics:
        return []

    story_metrics_lower = {m.lower() for m in story_metrics}
    issues: list[ValidationIssue] = []

    for metric in sorted(draft_metrics):
        if metric not in story_metrics_lower:
            issues.append(
                ValidationIssue(
                    severity="error",
                    rule="metric_accuracy",
                    message=f"Metric '{metric}' may be misattributed",
                )
            )
    return issues


def _check_skills_fabrication(
    draft_skills: set[str] | None,
    story_skills: set[str],
) -> list[ValidationIssue]:
    """Rule 5: Draft should not mention too many skills not in stories.

    Compares pre-extracted draft skills against the union of skills from
    selected stories. More than 3 unknown skills triggers a warning.

    Args:
        draft_skills: Skills pre-extracted from draft text, or None to skip.
        story_skills: Union of skills from selected stories.

    Returns:
        List with one warning if threshold exceeded, empty otherwise.
    """
    if draft_skills is None:
        return []

    draft_lower = {s.lower() for s in draft_skills}
    story_lower = {s.lower() for s in story_skills}
    suspicious = draft_lower - story_lower

    if len(suspicious) > _SUSPICIOUS_SKILLS_THRESHOLD:
        return [
            ValidationIssue(
                severity="warning",
                rule="potential_fabrication",
                message=(
                    f"Draft mentions skills not in selected stories: "
                    f"{sorted(suspicious)[:3]}"
                ),
            )
        ]
    return []


# =============================================================================
# Main Validation Function
# =============================================================================


def validate_cover_letter(
    *,
    draft_text: str,
    things_to_avoid: list[str],
    company_name: str,
    story_metrics: set[str],
    story_skills: set[str],
    draft_skills: set[str] | None = None,
) -> CoverLetterValidation:
    """Validate a generated cover letter against five rules.

    REQ-010 §5.4: Automated validation catches common generation errors.
    Errors block presentation to user; warnings are shown but don't block.

    Args:
        draft_text: The LLM-generated cover letter text.
        things_to_avoid: Phrases from voice profile blacklist.
        company_name: Target company name from job posting.
        story_metrics: Metrics pre-extracted from selected story outcomes
            (e.g., {"40%", "$2M", "3x"}).
        story_skills: Union of lowercased skills from selected stories.
        draft_skills: Skills pre-extracted from draft text (by LLM).
            None to skip fabrication check.

    Returns:
        CoverLetterValidation with passed status, issues, and word count.

    Raises:
        ValueError: If input sizes exceed safety bounds.
    """
    # Safety bounds
    if len(draft_text) > _MAX_DRAFT_LENGTH:
        raise ValueError(
            f"draft_text has {len(draft_text)} characters, "
            f"exceeds maximum of {_MAX_DRAFT_LENGTH}"
        )
    if len(company_name) > _MAX_COMPANY_NAME_LENGTH:
        raise ValueError(
            f"company_name has {len(company_name)} characters, "
            f"exceeds maximum of {_MAX_COMPANY_NAME_LENGTH}"
        )
    if len(things_to_avoid) > _MAX_THINGS_TO_AVOID:
        raise ValueError(
            f"things_to_avoid has {len(things_to_avoid)} items, "
            f"exceeds maximum of {_MAX_THINGS_TO_AVOID}"
        )
    if len(story_metrics) > _MAX_STORY_METRICS:
        raise ValueError(
            f"story_metrics has {len(story_metrics)} items, "
            f"exceeds maximum of {_MAX_STORY_METRICS}"
        )
    if len(story_skills) > _MAX_SKILLS:
        raise ValueError(
            f"story_skills has {len(story_skills)} items, "
            f"exceeds maximum of {_MAX_SKILLS}"
        )
    if draft_skills is not None and len(draft_skills) > _MAX_SKILLS:
        raise ValueError(
            f"draft_skills has {len(draft_skills)} items, "
            f"exceeds maximum of {_MAX_SKILLS}"
        )

    word_count = len(draft_text.split())
    draft_lower = draft_text.lower()

    issues: list[ValidationIssue] = []
    issues.extend(_check_word_count(word_count))
    issues.extend(_check_blacklist(draft_lower, things_to_avoid))
    issues.extend(_check_company_specificity(draft_text, company_name))
    issues.extend(_check_metric_accuracy(draft_text, story_metrics))
    issues.extend(_check_skills_fabrication(draft_skills, story_skills))

    passed = not any(issue.severity == "error" for issue in issues)

    logger.debug(
        "Cover letter validation: %d issue(s), passed=%s",
        len(issues),
        passed,
    )

    return CoverLetterValidation(
        passed=passed,
        issues=tuple(issues),
        word_count=word_count,
    )
