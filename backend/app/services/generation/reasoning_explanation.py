"""Agent reasoning explanation service.

REQ-007 §8.7: Reasoning Explanation
REQ-010 §9: Agent Reasoning Output

Produces a user-facing markdown explanation of the Ghostwriter's generation
choices. Combines resume tailoring signals and cover letter story selection
into a single, transparent summary.

WHY PURE FUNCTION: This service accepts pre-extracted data (tailoring action,
signal details, story titles/rationales) rather than querying the database.
This keeps the function pure, testable, and decoupled from data access. The
graph node is responsible for extracting data from state and passing it in.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

_MAX_SIGNAL_DETAILS: int = 3
"""Maximum number of tailoring signal details to show (REQ-010 §9.1)."""

_MAX_STORIES: int = 10
"""Safety bound on stories rendered in reasoning output."""

_MAX_TEXT_LENGTH: int = 500
"""Safety bound on individual text field length to prevent oversized output."""


# =============================================================================
# Helpers
# =============================================================================


def _sanitize_text(text: str) -> str:
    """Sanitize user-provided text for safe markdown embedding.

    Strips HTML angle brackets and newlines to prevent markdown structure
    injection and potential XSS when rendered by frontend markdown parsers.

    Args:
        text: Raw text from user or scraped data.

    Returns:
        Sanitized text safe for markdown embedding.
    """
    sanitized = text.replace("<", "").replace(">", "")
    sanitized = sanitized.replace("\n", " ").replace("\r", " ")
    return sanitized[:_MAX_TEXT_LENGTH]


# =============================================================================
# Data Models
# =============================================================================


@dataclass(frozen=True)
class ReasoningStory:
    """Story info needed for reasoning output.

    Attributes:
        title: Story title for display.
        rationale: Human-readable selection rationale from scoring.
    """

    title: str
    rationale: str


# =============================================================================
# Main Function
# =============================================================================


def format_agent_reasoning(
    job_title: str,
    company_name: str,
    tailoring_action: str,
    tailoring_signal_details: list[str],
    stories: list[ReasoningStory],
) -> str:
    """Generate user-facing explanation of generation choices.

    REQ-010 §9.1: Builds markdown explanation with resume tailoring signals
    and cover letter story rationale.

    WHY: Transparency helps users provide better feedback and builds trust
    that the system isn't making things up.

    Args:
        job_title: Target job title for the header.
        company_name: Target company name for the header.
        tailoring_action: Tailoring decision ("use_base" or "create_variant").
        tailoring_signal_details: Human-readable signal descriptions (max 3 shown).
        stories: Selected stories with titles and rationales (max 10 shown).

    Returns:
        Markdown-formatted reasoning explanation string.
    """
    lines: list[str] = []

    # Sanitize user-controlled values for safe markdown embedding
    safe_title = _sanitize_text(job_title)
    safe_company = _sanitize_text(company_name)

    # Header
    lines.append(
        f"I've prepared materials for **{safe_title}** at **{safe_company}**:\n"
    )

    # Resume tailoring explanation
    if tailoring_action == "create_variant":
        lines.append("**Resume Adjustments:**")
        for detail in tailoring_signal_details[:_MAX_SIGNAL_DETAILS]:
            if detail:
                lines.append(f"- {_sanitize_text(detail)}")
        lines.append("")
    else:
        lines.append(
            "**Resume:** Your base resume aligns well \u2014 no changes needed.\n"
        )

    # Cover letter stories explanation
    bounded_stories = stories[:_MAX_STORIES]
    if bounded_stories:
        lines.append("**Cover Letter Stories:**")
        for story in bounded_stories:
            safe_story_title = _sanitize_text(story.title)
            safe_rationale = _sanitize_text(story.rationale)
            lines.append(f"- *{safe_story_title}* \u2014 {safe_rationale}")

    # Review prompt
    lines.append("\nReady for your review!")

    return "\n".join(lines)
