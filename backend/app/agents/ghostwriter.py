"""Ghostwriter Agent utility functions.

REQ-007 §8: Ghostwriter Agent

The Ghostwriter Agent generates tailored resumes and cover letters for job
postings. It:
- Triggers on auto-draft threshold, manual request, or regeneration
- Checks for existing JobVariants (race condition prevention)
- Selects the best BaseResume for the role
- Evaluates tailoring need and creates JobVariant if needed
- Selects relevant Achievement Stories
- Generates cover letters with Voice Profile
- Presents work to user for review

Architecture:
    [Trigger] → check_existing_variant → select_base_resume →
        → evaluate_tailoring_need → create_job_variant (if needed) →
        → select_achievement_stories → generate_cover_letter →
        → check_job_still_active → present_for_review → [END]

Trigger Conditions (§8.1):
    - Auto-draft: fit_score >= persona.auto_draft_threshold
    - Manual request: User says "Draft materials for this job"
    - Regeneration: User says "Try a different approach"
"""

import re
from enum import Enum

# =============================================================================
# Trigger Types (§8.1)
# =============================================================================


class TriggerType(str, Enum):
    """How the Ghostwriter was triggered.

    REQ-007 §8.1: Three distinct triggers invoke the Ghostwriter.
    """

    AUTO_DRAFT = "auto_draft"
    """Job fit_score >= persona.auto_draft_threshold."""

    MANUAL_REQUEST = "manual_request"
    """User explicitly asks to draft materials for a job."""

    REGENERATION = "regeneration"
    """User asks to try a different approach on existing draft."""


# =============================================================================
# Constants (§8.1)
# =============================================================================

# WHY: These patterns detect user intent to manually trigger content generation.
# They match common variations of "draft/write/generate/create/prepare"
# followed by content type words (resume, cover letter, materials).
# Patterns are case-insensitive.
DRAFT_REQUEST_PATTERNS = [
    # Draft materials
    re.compile(
        r"draft\s+(?:a\s+)?(?:resume|cover\s+letter|materials)",
        re.IGNORECASE,
    ),
    # Write materials
    re.compile(
        r"write\s+(?:a\s+)?(?:resume|cover\s+letter|materials)",
        re.IGNORECASE,
    ),
    # Generate materials
    re.compile(
        r"generate\s+(?:a\s+)?(?:resume|cover\s+letter|materials)",
        re.IGNORECASE,
    ),
    # Create materials
    re.compile(
        r"create\s+(?:a\s+)?(?:resume|cover\s+letter|materials)",
        re.IGNORECASE,
    ),
    # Prepare materials
    re.compile(
        r"prepare\s+(?:a\s+)?(?:resume|cover\s+letter|materials)",
        re.IGNORECASE,
    ),
]

# WHY: These patterns detect user intent to regenerate existing content.
# They match phrases indicating dissatisfaction or desire for a new version.
REGENERATION_PATTERNS = [
    # Try again / different approach
    re.compile(r"try\s+(?:a\s+)?(?:different|again|something\s+else)", re.IGNORECASE),
    # Regenerate
    re.compile(r"regenerate", re.IGNORECASE),
    # Redo
    re.compile(r"redo\s+(?:this|the)", re.IGNORECASE),
    # Start over
    re.compile(r"start\s+over", re.IGNORECASE),
    # Another version
    re.compile(r"(?:give|get)\s+(?:me\s+)?another\s+version", re.IGNORECASE),
    # Make it different
    re.compile(r"make\s+it\s+different", re.IGNORECASE),
]


# =============================================================================
# Trigger Condition Functions (§8.1)
# =============================================================================


def should_auto_draft(
    fit_score: float | None,
    threshold: int | None,
) -> bool:
    """Check if auto-draft should trigger for a scored job.

    REQ-007 §8.1: Auto-draft triggers when fit_score >= persona.auto_draft_threshold.

    Args:
        fit_score: The job's fit score (0-100). None if not scored.
        threshold: The persona's auto-draft threshold. None if disabled.

    Returns:
        True if auto-draft should trigger.
    """
    if fit_score is None or threshold is None:
        return False

    return fit_score >= threshold


def is_draft_request(message: str) -> bool:
    """Check if user message is a manual draft request.

    REQ-007 §8.1: Manual request triggers when user explicitly asks to
    draft materials (e.g., "Draft materials for this job").

    Args:
        message: User's message text.

    Returns:
        True if message matches a draft request pattern.
    """
    if not message:
        return False

    return any(pattern.search(message) for pattern in DRAFT_REQUEST_PATTERNS)


def is_regeneration_request(message: str) -> bool:
    """Check if user message is a regeneration request.

    REQ-007 §8.1: Regeneration triggers when user asks to try a different
    approach (e.g., "Try a different approach", "Regenerate").

    Args:
        message: User's message text.

    Returns:
        True if message matches a regeneration pattern.
    """
    if not message:
        return False

    return any(pattern.search(message) for pattern in REGENERATION_PATTERNS)
