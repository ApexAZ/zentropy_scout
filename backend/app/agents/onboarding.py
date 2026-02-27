"""Onboarding utility functions.

REQ-019 §5: Post-onboarding utilities retained after graph deletion.

The chat-based onboarding interview has been replaced by a frontend form wizard
(REQ-019 §6). This module retains only the framework-independent utility
functions used for:
- Post-onboarding persona updates (via chat commands)
- Section detection and routing
- Embedding impact mapping for re-scoring
- Data summary formatting
- Prompt templates for work history, achievement stories, and voice profiles
"""

import re
from typing import Any

from app.core.llm_sanitization import sanitize_llm_input

# =============================================================================
# Constants
# =============================================================================

_NO_DATA_COLLECTED_MSG = "No information collected yet."

# Defense-in-depth: bound regex input to prevent ReDoS on unbounded messages
_MAX_REGEX_INPUT_LENGTH = 2000

# Patterns for detecting update requests (§5.1)
UPDATE_REQUEST_PATTERNS = [
    re.compile(r"update\s+(?:my\s+)?(?:profile|info)", re.IGNORECASE),
    re.compile(
        r"(?:add|edit|change)\s+(?:my\s+)?(?:skills?|experience)", re.IGNORECASE
    ),
    re.compile(
        r"(?:add|edit|change)\s+(?:a\s+)?(?:new\s+)?(?:skill|job|story)", re.IGNORECASE
    ),
    re.compile(r"change\s+my\s+(?:salary|location|preferences)", re.IGNORECASE),
]


# =============================================================================
# Prompt Templates (§5.6)
# =============================================================================

# §5.6.2 Work History Expansion Prompt
WORK_HISTORY_EXPANSION_PROMPT = """The user just described a role at {company} as {title}.

Your goal: Surface 2-3 strong accomplishment bullets from this role.

Probing areas:
- Biggest accomplishment in this role
- A challenge they overcame
- Impact — numbers, percentages, scale

Handling vague answers:
- "How many projects?" or "What was the scale?"
- "What was the outcome?"

After gathering details, summarize what will be recorded and ask for confirmation."""

# §5.6.2 Achievement Story Prompt (STAR format)
ACHIEVEMENT_STORY_PROMPT = """Goal: Capture 3-5 achievement stories in STAR format.

Each story needs:
- Context: What was the situation/challenge?
- Action: What specifically did THEY do (not their team)?
- Outcome: What was the measurable result?
- Skills demonstrated: Which skills does this showcase?

Probing questions:
- "What made this challenging?"
- "What would have happened if you hadn't stepped in?"
- "Can you put a number on the impact?"

Already captured stories:
{existing_stories}

Skills already covered:
{covered_skills}

Important: Ask for stories that demonstrate DIFFERENT skills than those already captured."""

# §5.6.2 Voice Profile Derivation Prompt
VOICE_PROFILE_DERIVATION_PROMPT = """Analyze the conversation below to derive the user's professional voice.

Analyze these dimensions:
1. Tone: Formal/casual? Direct/diplomatic? Confident/humble?
2. Sentence style: Short and punchy? Detailed and thorough?
3. Vocabulary: Technical jargon? Plain English? Industry-specific terms?
4. Patterns to avoid: Buzzwords they never use? Phrases they dislike?

Conversation transcript:
{transcript}

Output a Voice Profile summary (3-4 bullet points).

Present as: "Based on our conversation, here's how I'd describe your professional voice..."

Then ask the user to confirm or adjust."""


# =============================================================================
# Prompt Template Functions (§5.6)
# =============================================================================


def get_work_history_prompt(job_entry: dict[str, Any]) -> str:
    """Get the work history expansion prompt for a specific job.

    Args:
        job_entry: Dict with job details (title, company, dates, etc.).

    Returns:
        Work history expansion prompt with job context.
    """
    title = sanitize_llm_input(
        job_entry.get("title", job_entry.get("raw_input", "this role"))
    )
    company = sanitize_llm_input(job_entry.get("company", "their company"))

    return WORK_HISTORY_EXPANSION_PROMPT.format(
        title=title,
        company=company,
    )


def get_achievement_story_prompt(
    existing_stories: list[str],
    covered_skills: list[str],
) -> str:
    """Get the achievement story prompt with context about what's captured.

    Args:
        existing_stories: List of story summaries already captured.
        covered_skills: List of skills already demonstrated by stories.

    Returns:
        Achievement story prompt with context about diversity needs.
    """
    stories_str = (
        "\n".join(f"- {sanitize_llm_input(s)}" for s in existing_stories)
        if existing_stories
        else "None yet"
    )
    skills_str = (
        ", ".join(sanitize_llm_input(s) for s in covered_skills)
        if covered_skills
        else "None yet"
    )

    return ACHIEVEMENT_STORY_PROMPT.format(
        existing_stories=stories_str,
        covered_skills=skills_str,
    )


def get_voice_profile_prompt(transcript: str) -> str:
    """Get the voice profile derivation prompt with conversation transcript.

    Args:
        transcript: The conversation transcript to analyze.

    Returns:
        Voice profile prompt with transcript included.
    """
    safe_transcript = (
        sanitize_llm_input(transcript) if transcript else "(No transcript available)"
    )
    return VOICE_PROFILE_DERIVATION_PROMPT.format(
        transcript=safe_transcript,
    )


# =============================================================================
# Data Summary Formatting
# =============================================================================


def _format_basic_info(gathered_data: dict[str, Any]) -> str | None:
    """Format basic info section for summary."""
    basic = gathered_data.get("basic_info", {})
    if isinstance(basic, dict) and basic.get("full_name"):
        return f"Name: {sanitize_llm_input(basic['full_name'])}"
    return None


def _format_work_history(gathered_data: dict[str, Any]) -> str | None:
    """Format work history section for summary."""
    work = gathered_data.get("work_history", {})
    if isinstance(work, dict):
        entries = work.get("entries", [])
        if entries:
            return f"Work history: {len(entries)} job(s) recorded"
    return None


def _format_skills(gathered_data: dict[str, Any]) -> str | None:
    """Format skills section for summary."""
    skills = gathered_data.get("skills", {})
    if not isinstance(skills, dict):
        return None
    entries = skills.get("entries", [])
    if not entries:
        return None
    skill_names = [
        sanitize_llm_input(e["skill_name"]) for e in entries if e.get("skill_name")
    ]
    if not skill_names:
        return None
    result = f"Skills: {', '.join(skill_names[:5])}"
    if len(skill_names) > 5:
        result += f" (+{len(skill_names) - 5} more)"
    return result


def _format_stories(gathered_data: dict[str, Any]) -> str | None:
    """Format achievement stories section for summary."""
    stories = gathered_data.get("achievement_stories", {})
    if isinstance(stories, dict):
        entries = stories.get("entries", [])
        if entries:
            return f"Achievement stories: {len(entries)} captured"
    return None


def _format_skipped_sections(gathered_data: dict[str, Any]) -> str | None:
    """Format skipped sections for summary."""
    skipped = []
    for section in ["education", "certifications", "resume_upload"]:
        sec_data = gathered_data.get(section, {})
        if isinstance(sec_data, dict) and sec_data.get("skipped"):
            skipped.append(section.replace("_", " "))
    if skipped:
        return f"Skipped: {', '.join(skipped)}"
    return None


def format_gathered_data_summary(gathered_data: dict[str, Any]) -> str:
    """Format gathered data into a human-readable summary.

    Converts the gathered_data dict into a summary string suitable for
    display or prompt context. User-provided strings are sanitized.

    Args:
        gathered_data: Dict of section data collected during onboarding.

    Returns:
        Human-readable summary of gathered data.
    """
    if not gathered_data:
        return _NO_DATA_COLLECTED_MSG

    formatters = [
        _format_basic_info,
        _format_work_history,
        _format_skills,
        _format_stories,
        _format_skipped_sections,
    ]
    raw_parts = [f(gathered_data) for f in formatters]
    summary_parts: list[str] = [p for p in raw_parts if p is not None]

    return "\n".join(summary_parts) if summary_parts else _NO_DATA_COLLECTED_MSG


# =============================================================================
# Post-Onboarding Update Constants (§5.5)
# =============================================================================

SECTIONS_REQUIRING_RESCORE = {
    "skills",  # Affects fit score via hard_skills embedding
    "non_negotiables",  # Affects job filtering (salary, remote, etc.)
    "growth_targets",  # Affects stretch score calculation
    "work_history",  # Affects experience level matching
}

SECTION_AFFECTED_EMBEDDINGS: dict[str, list[str]] = {
    "skills": ["hard_skills"],
    "work_history": ["experience"],
    "growth_targets": ["target_roles"],
    "achievement_stories": ["stories"],
    "non_negotiables": [],  # Affects filtering, not embeddings
    "certifications": [],  # No direct embedding impact
    "education": [],  # No direct embedding impact
    "voice_profile": [],  # Affects generation, not matching
    "basic_info": [],  # No embedding impact
}

SECTION_DETECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Certifications
    (re.compile(r"certific", re.IGNORECASE), "certifications"),
    (
        re.compile(r"(?:got|earned|passed)\s+(?:a\s+)?(?:new\s+)?cert", re.IGNORECASE),
        "certifications",
    ),
    # Skills
    (re.compile(r"(?:learned|know)\s+\w+", re.IGNORECASE), "skills"),
    (re.compile(r"(?:update|add|change)\s+(?:my\s+)?skill", re.IGNORECASE), "skills"),
    (re.compile(r"new\s+skill", re.IGNORECASE), "skills"),
    # Non-negotiables (salary, remote, preferences)
    (re.compile(r"salary", re.IGNORECASE), "non_negotiables"),
    (re.compile(r"remote", re.IGNORECASE), "non_negotiables"),
    (
        re.compile(r"(?:prefer|requirement|expectation)", re.IGNORECASE),
        "non_negotiables",
    ),
    (re.compile(r"non.?negotiable", re.IGNORECASE), "non_negotiables"),
    # Work history
    (
        re.compile(r"(?:add|update|change)\s+(?:my\s+)?(?:job|work)", re.IGNORECASE),
        "work_history",
    ),
    (re.compile(r"work\s+(?:history|experience)", re.IGNORECASE), "work_history"),
    (
        re.compile(
            r"new\s+job\s+(?:to\s+)?(?:my\s+)?(?:history|profile)", re.IGNORECASE
        ),
        "work_history",
    ),
    (
        re.compile(
            r"(?:started|left|got)\s+(?:a\s+)?(?:new\s+)?(?:job|position|role)",
            re.IGNORECASE,
        ),
        "work_history",
    ),
    # Education
    (
        re.compile(
            r"(?:finish|complet|graduat).{0,100}(?:degree|school|education)",
            re.IGNORECASE,
        ),
        "education",
    ),
    (re.compile(r"education", re.IGNORECASE), "education"),
    (re.compile(r"degree", re.IGNORECASE), "education"),
    # Achievement stories
    (
        re.compile(r"(?:new\s+)?(?:achievement|accomplishment|story)", re.IGNORECASE),
        "achievement_stories",
    ),
    # Growth targets
    (
        re.compile(r"(?:career|growth)\s+(?:goal|target)", re.IGNORECASE),
        "growth_targets",
    ),
    (re.compile(r"target\s+role", re.IGNORECASE), "growth_targets"),
]


# =============================================================================
# Trigger Conditions (§5.1)
# =============================================================================


def should_start_onboarding(
    *,
    persona_exists: bool,
    onboarding_complete: bool,
) -> bool:
    """Check if onboarding should auto-start.

    Triggers when:
    - New user (no persona exists)
    - User has persona but onboarding_complete is False (incomplete)

    Args:
        persona_exists: Whether user has a persona record.
        onboarding_complete: Whether onboarding is marked complete.

    Returns:
        True if onboarding should start/resume.
    """
    if not persona_exists:
        return True
    return not onboarding_complete


def is_update_request(message: str) -> bool:
    """Check if a message is a profile update request.

    Users can trigger partial re-interview by saying things like:
    - "Update my profile"
    - "Add a new skill"
    - "Change my salary requirement"

    Messages are truncated to _MAX_REGEX_INPUT_LENGTH characters before
    matching (ReDoS defense-in-depth).

    Args:
        message: User's message text.

    Returns:
        True if message indicates an update request.
    """
    message = message[:_MAX_REGEX_INPUT_LENGTH]
    return any(pattern.search(message) for pattern in UPDATE_REQUEST_PATTERNS)


# =============================================================================
# Post-Onboarding Updates (§5.5)
# =============================================================================


def detect_update_section(message: str) -> str | None:
    """Detect which persona section the user wants to update.

    Analyzes the user's message to determine which section of their persona
    they want to update. Messages are truncated to _MAX_REGEX_INPUT_LENGTH
    characters before matching (ReDoS defense-in-depth).

    Examples:
        - "I got a new certification" -> "certifications"
        - "I learned Kubernetes" -> "skills"
        - "Change my salary requirement" -> "non_negotiables"

    Args:
        message: User's message text.

    Returns:
        Section name if detected, None otherwise.
    """
    message = message[:_MAX_REGEX_INPUT_LENGTH]
    for pattern, section in SECTION_DETECTION_PATTERNS:
        if pattern.search(message):
            return section
    return None


def create_update_state(
    section: str,
    user_id: str,
    persona_id: str,
) -> dict[str, Any]:
    """Create state for a single-section post-onboarding update.

    Creates a state dict configured for partial update mode.

    Args:
        section: Section name to update (e.g., "skills", "certifications").
        user_id: User's ID for tenant isolation.
        persona_id: Persona ID being updated.

    Returns:
        State dict configured for partial update.
    """
    return {
        "user_id": user_id,
        "persona_id": persona_id,
        "current_step": section,
        "gathered_data": {},
        "is_partial_update": True,
    }


def is_post_onboarding_update(state: dict[str, Any]) -> bool:
    """Check if the current state represents a post-onboarding partial update.

    Args:
        state: Current state dict.

    Returns:
        True if this is a partial update (not full onboarding).
    """
    return bool(state.get("is_partial_update", False))


def get_affected_embeddings(section: str) -> list[str]:
    """Get embedding types affected by updating a section.

    When a persona section is updated, certain embeddings may need
    regeneration before job re-scoring.

    Args:
        section: Section name that was updated.

    Returns:
        List of affected embedding type names.
    """
    return SECTION_AFFECTED_EMBEDDINGS.get(section, [])


def get_update_completion_message(section: str) -> str:
    """Generate completion message after a post-onboarding update.

    For sections that affect job matching, mentions re-analyzing jobs.

    Args:
        section: Section name that was updated.

    Returns:
        User-facing completion message.
    """
    section_names = {
        "skills": "skills",
        "certifications": "certifications",
        "education": "education",
        "work_history": "work history",
        "achievement_stories": "achievement stories",
        "non_negotiables": "preferences",
        "growth_targets": "career goals",
        "voice_profile": "voice profile",
        "basic_info": "contact information",
    }

    section_display = section_names.get(section, section)

    if section in SECTIONS_REQUIRING_RESCORE:
        return (
            f"Updated your {section_display}. "
            "I'm re-analyzing your job matches — you might see new "
            "opportunities based on these changes!"
        )

    return f"Updated your {section_display}."
