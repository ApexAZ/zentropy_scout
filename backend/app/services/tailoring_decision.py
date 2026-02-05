"""Tailoring decision service.

REQ-007 §8.4: Tailoring Decision
REQ-010 §4.1: Tailoring Decision Logic

Evaluates whether a BaseResume needs modification for a specific job posting.
Uses pre-extracted keyword/skill sets (not raw text) to keep the function pure,
testable, and decoupled from extraction logic (REQ-010 §6.x).

Signal Types:
    keyword_gap: Job keywords missing from the resume summary. Priority equals
        the gap ratio (fraction of job keywords not present in summary).
    bullet_relevance: Top resume bullets that don't highlight skills required
        by the job. Priority decreases by position (0.5, 0.4, 0.3 for positions
        0, 1, 2 respectively).

Decision Matrix:
    - No signals: action="use_base" (resume aligns well)
    - Total priority < 0.3: action="use_base" (gaps too minor)
    - Total priority >= 0.3: action="create_variant" (tailoring recommended)
"""

import logging
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

KEYWORD_GAP_THRESHOLD: float = 0.3
"""Fraction of job keywords missing from summary to trigger a signal (>30%)."""

MIN_PRIORITY_THRESHOLD: float = 0.3
"""Minimum total priority sum to warrant creating a variant."""

MAX_BULLETS_TO_CHECK: int = 3
"""Maximum number of top bullets to check per job entry."""

_MAX_BULLET_SKILLS: int = 1000
"""Safety bound on bullet_skills list length to prevent resource exhaustion."""

_MAX_KEYWORDS: int = 1000
"""Safety bound on keyword set size to prevent resource exhaustion."""


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class TailoringSignal:
    """A signal indicating potential need for resume tailoring.

    Attributes:
        type: Signal category ("keyword_gap" or "bullet_relevance").
        priority: Numerical priority weight for this signal (0.0-1.0).
        detail: Human-readable description of what triggered this signal.
    """

    type: Literal["keyword_gap", "bullet_relevance"]
    priority: float
    detail: str


@dataclass
class BulletSkillData:
    """Pre-extracted skill data for a single resume bullet.

    Attributes:
        job_entry_id: The work history entry this bullet belongs to.
        position: Zero-based position of the bullet within the entry
            (0 = top bullet, 1 = second, etc.).
        skills: Set of lowercased skill names extracted from the bullet text.
    """

    job_entry_id: str
    position: int
    skills: set[str]


@dataclass
class TailoringDecision:
    """Result of the tailoring evaluation.

    Attributes:
        action: Decision action ("use_base" or "create_variant").
        signals: List of tailoring signals that informed the decision.
        reasoning: Human-readable explanation of the decision.
    """

    action: Literal["use_base", "create_variant"]
    signals: list[TailoringSignal] = field(default_factory=list)
    reasoning: str = ""


# =============================================================================
# Core Logic
# =============================================================================


def evaluate_tailoring_need(
    *,
    job_keywords: set[str],
    summary_keywords: set[str],
    bullet_skills: list[BulletSkillData],
    fit_score: float,
    job_skills: set[str] | None = None,
) -> TailoringDecision:
    """Evaluate whether a base resume needs tailoring for a job posting.

    REQ-010 §4.1: Pure function that compares pre-extracted keyword and skill
    sets to determine if creating a JobVariant is worthwhile.

    Args:
        job_keywords: Keywords extracted from the job posting description.
        summary_keywords: Keywords extracted from the base resume summary.
        bullet_skills: Pre-extracted skill data for resume bullets. Only the
            top MAX_BULLETS_TO_CHECK per job entry are evaluated.
        fit_score: Job fit score (0-100). Accepted for future use but does
            not currently influence the decision.
        job_skills: Lowercased skill names extracted from the job posting.
            If None, bullet relevance signals are skipped.

    Returns:
        TailoringDecision with action, signals, and reasoning.

    Raises:
        ValueError: If input sizes exceed safety bounds.
    """
    if len(bullet_skills) > _MAX_BULLET_SKILLS:
        raise ValueError(
            f"bullet_skills length {len(bullet_skills)} exceeds "
            f"maximum {_MAX_BULLET_SKILLS}"
        )
    if len(job_keywords) > _MAX_KEYWORDS:
        raise ValueError(
            f"job_keywords size {len(job_keywords)} exceeds maximum {_MAX_KEYWORDS}"
        )
    if len(summary_keywords) > _MAX_KEYWORDS:
        raise ValueError(
            f"summary_keywords size {len(summary_keywords)} exceeds "
            f"maximum {_MAX_KEYWORDS}"
        )

    signals: list[TailoringSignal] = []

    # Signal 1: Keyword gaps in summary
    _check_keyword_gap(job_keywords, summary_keywords, signals)

    # Signal 2: Bullet relevance mismatch
    effective_job_skills = job_skills if job_skills is not None else set()
    _check_bullet_relevance(bullet_skills, effective_job_skills, signals)

    # Decision matrix
    if not signals:
        logger.debug("No tailoring signals detected (fit_score=%.1f)", fit_score)
        return TailoringDecision(
            action="use_base",
            signals=[],
            reasoning=(
                "BaseResume aligns well with job requirements. No tailoring needed."
            ),
        )

    total_priority = sum(s.priority for s in signals)

    if total_priority < MIN_PRIORITY_THRESHOLD:
        logger.debug(
            "Tailoring signals below threshold (total=%.2f, threshold=%.2f)",
            total_priority,
            MIN_PRIORITY_THRESHOLD,
        )
        return TailoringDecision(
            action="use_base",
            signals=signals,
            reasoning=(
                "Minor gaps detected but not significant enough to warrant tailoring."
            ),
        )

    detail_summary = "; ".join(s.detail for s in signals[:3])
    logger.info(
        "Tailoring recommended (total_priority=%.2f): %s",
        total_priority,
        detail_summary,
    )
    return TailoringDecision(
        action="create_variant",
        signals=signals,
        reasoning=f"Tailoring recommended: {detail_summary}",
    )


# =============================================================================
# Signal Detection Helpers
# =============================================================================


def _check_keyword_gap(
    job_keywords: set[str],
    summary_keywords: set[str],
    signals: list[TailoringSignal],
) -> None:
    """Check for keyword gaps between job posting and resume summary.

    Args:
        job_keywords: Keywords from the job posting.
        summary_keywords: Keywords from the resume summary.
        signals: Signal list to append to (mutated in place).
    """
    if not job_keywords:
        return

    missing_keywords = job_keywords - summary_keywords
    keyword_gap = len(missing_keywords) / len(job_keywords)

    if keyword_gap > KEYWORD_GAP_THRESHOLD:
        missing_sample = sorted(missing_keywords)[:5]
        signals.append(
            TailoringSignal(
                type="keyword_gap",
                priority=keyword_gap,
                detail=(
                    f"Summary missing {len(missing_keywords)} key terms: "
                    f"{missing_sample}"
                ),
            )
        )


def _check_bullet_relevance(
    bullet_skills: list[BulletSkillData],
    job_skills: set[str],
    signals: list[TailoringSignal],
) -> None:
    """Check for bullet relevance mismatches.

    Bullets with position < MAX_BULLETS_TO_CHECK are evaluated.
    Priority decreases by position: 0.5 for position 0, 0.4 for position 1,
    0.3 for position 2.

    Args:
        bullet_skills: Pre-extracted skill data for resume bullets.
        job_skills: Skills required by the job posting.
        signals: Signal list to append to (mutated in place).
    """
    if not job_skills:
        return

    for bullet in bullet_skills:
        if bullet.position >= MAX_BULLETS_TO_CHECK:
            continue

        if not (bullet.skills & job_skills):
            priority = 0.5 - (bullet.position * 0.1)
            signals.append(
                TailoringSignal(
                    type="bullet_relevance",
                    priority=priority,
                    detail=(
                        f"Top bullet in {bullet.job_entry_id} doesn't "
                        f"highlight required skills"
                    ),
                )
            )
