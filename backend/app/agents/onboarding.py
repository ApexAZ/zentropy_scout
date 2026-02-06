"""Onboarding Agent implementation.

REQ-007 §5: Onboarding Agent

The Onboarding Agent guides new users through persona creation via a structured
interview. It:
- Triggers for new users or incomplete onboarding
- Walks through interview steps (resume upload → basic info → work history → ...)
- Handles HITL checkpoints at each step
- Supports skipping optional sections
- Can be re-invoked for partial profile updates

Architecture:
    [Trigger] → check_resume_upload → gather_basic_info → gather_work_history →
        → gather_education → gather_skills → gather_certifications →
        → gather_stories → gather_non_negotiables → gather_growth_targets →
        → derive_voice_profile → review_persona → setup_base_resume →
        → complete_onboarding → [END]

    Each step pauses for HITL via wait_for_input node.

Interview Steps (§5.2):
    - resume_upload: Optional resume upload, extract data
    - basic_info: Name, email, phone, location, URLs
    - work_history: Confirm/expand extracted jobs
    - education: Optional education entries
    - skills: Rate proficiency, add missing
    - certifications: Optional certifications
    - achievement_stories: 3-5 STAR format stories
    - non_negotiables: Remote, salary, filters
    - growth_targets: Target roles, skills to learn
    - voice_profile: Derive writing style from conversation
    - review: User reviews gathered data
    - base_resume_setup: Create initial BaseResume
"""

import re

from langgraph.graph import END, StateGraph

from app.agents.state import CheckpointReason, OnboardingState

# =============================================================================
# Constants (§5.2)
# =============================================================================

_NO_DATA_COLLECTED_MSG = "No information collected yet."

# WHY: Ordered list defines the interview flow state machine. Each step must
# complete (or be skipped) before proceeding to the next.
ONBOARDING_STEPS = [
    "resume_upload",
    "basic_info",
    "work_history",
    "education",
    "skills",
    "certifications",
    "achievement_stories",
    "non_negotiables",
    "growth_targets",
    "voice_profile",
    "review",
    "base_resume_setup",
]

# WHY: These sections can be skipped by the user. Education and certifications
# are optional because not all users have formal education or certs. Resume upload
# is optional because users can provide all info via interview.
OPTIONAL_SECTIONS = {
    "resume_upload",
    "education",
    "certifications",
}

# WHY: Required fields for each step. Used to determine when a step is complete.
REQUIRED_FIELDS: dict[str, list[str]] = {
    "basic_info": ["full_name", "email", "phone", "location"],
    "work_history": ["entries"],  # At least 1 job entry
    "skills": ["entries"],  # At least 1 skill entry
    "achievement_stories": ["entries"],  # At least 1 story entry
    "non_negotiables": ["remote_preference"],  # At minimum
    "growth_targets": ["target_roles"],  # At minimum
    "voice_profile": ["tone"],  # At minimum
}

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

# WHY: These prompts establish the "Scout" interviewer persona. The consistent
# persona prevents drift into generic chatbot behavior and maintains the
# interview flow. Template variables allow dynamic context injection.

SYSTEM_PROMPT_TEMPLATE = """You are Scout, a friendly career coach conducting an onboarding interview.

## Your Personality
- Warm but efficient — respect the user's time
- Curious and encouraging — draw out details with follow-up questions
- Professional but not stiff — conversational, not corporate
- Celebrate wins without being sycophantic

## Your Responsibilities
- Guide the user through building their professional profile
- Ask probing questions to surface quantifiable achievements
- Help them articulate skills they might undersell
- Capture their authentic voice for future cover letters

## Interview Style Rules
- Ask one question at a time — never overwhelm with multiple questions
- Acknowledge their answer before moving on
- Use their name occasionally if known
- If they give a vague answer, probe for specifics ("Can you quantify that?")
- If they seem stuck, offer examples or reframe the question

## What You Are NOT
- Not a therapist — stay focused on career topics
- Not a resume writer — you're gathering data, not writing yet
- Not pushy — always allow skipping optional sections

## Current Context
Step: {current_step}
Progress so far:
{gathered_data_summary}"""

# §5.6.2 Work History Expansion Prompt
# WHY: After a user describes a role, this prompt helps surface 2-3 strong
# bullet points by probing for accomplishments, challenges, and impact.
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
# WHY: Stories in STAR format (Situation, Task, Action, Result) are essential
# for cover letter generation and showcasing diverse skills.
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
# WHY: Analyzing the conversation transcript helps derive the user's authentic
# writing voice for personalized cover letter generation.
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

# §5.6.3 Transition Prompts
# WHY: Natural transitions between sections maintain conversational flow
# and help users understand what's coming next without feeling interrogated.
TRANSITION_PROMPTS: dict[tuple[str, str], str] = {
    ("work_history", "education"): (
        "Great, I've got a solid picture of your work history.\n\n"
        "Next, let's cover your education — degrees, certifications, or any "
        "relevant training. This is optional if it's not relevant to your field."
    ),
    ("education", "skills"): (
        "Thanks for sharing your educational background.\n\n"
        "Now let's talk about your skills — both the technical ones and the "
        "softer interpersonal skills that are often just as important."
    ),
    ("skills", "certifications"): (
        "You've got a solid skill set.\n\n"
        "Do you have any professional certifications to add? These can help "
        "you stand out for certain roles."
    ),
    ("certifications", "achievement_stories"): (
        "Good to know about your certifications.\n\n"
        "Now for one of the most important parts — your achievement stories. "
        "These are the specific examples that bring your resume to life."
    ),
    ("achievement_stories", "non_negotiables"): (
        "Those are excellent stories — I can already see how they'll strengthen "
        "your applications.\n\n"
        "Now let's define your non-negotiables — the things that would make you "
        "immediately pass on a job, no matter how interesting it sounds."
    ),
    ("non_negotiables", "growth_targets"): (
        "I've noted your must-haves and dealbreakers.\n\n"
        "Let's talk about where you're headed — what roles are you aspiring "
        "to grow into, and what skills do you want to develop?"
    ),
    ("growth_targets", "voice_profile"): (
        "Great perspective on your career goals.\n\n"
        "Finally, let me capture your writing voice so any cover letters I help "
        "draft will sound authentically like you."
    ),
    ("voice_profile", "review"): (
        "Perfect, I've got a sense of your voice.\n\n"
        "Let's review everything we've gathered before creating your profile."
    ),
    ("review", "base_resume_setup"): (
        "Everything looks good!\n\n"
        "Last step — let's set up your base resume so we're ready to tailor it "
        "for specific job applications."
    ),
}


# =============================================================================
# Prompt Template Functions (§5.6)
# =============================================================================


def _format_basic_info(gathered_data: dict[str, object]) -> str | None:
    """Format basic info section for summary."""
    basic = gathered_data.get("basic_info", {})
    if isinstance(basic, dict) and basic.get("full_name"):
        return f"Name: {basic.get('full_name')}"
    return None


def _format_work_history(gathered_data: dict[str, object]) -> str | None:
    """Format work history section for summary."""
    work = gathered_data.get("work_history", {})
    if isinstance(work, dict):
        entries = work.get("entries", [])
        if entries:
            return f"Work history: {len(entries)} job(s) recorded"
    return None


def _format_skills(gathered_data: dict[str, object]) -> str | None:
    """Format skills section for summary."""
    skills = gathered_data.get("skills", {})
    if not isinstance(skills, dict):
        return None
    entries = skills.get("entries", [])
    if not entries:
        return None
    skill_names = [e.get("skill_name", "") for e in entries if e.get("skill_name")]
    if not skill_names:
        return None
    result = f"Skills: {', '.join(skill_names[:5])}"
    if len(skill_names) > 5:
        result += f" (+{len(skill_names) - 5} more)"
    return result


def _format_stories(gathered_data: dict[str, object]) -> str | None:
    """Format achievement stories section for summary."""
    stories = gathered_data.get("achievement_stories", {})
    if isinstance(stories, dict):
        entries = stories.get("entries", [])
        if entries:
            return f"Achievement stories: {len(entries)} captured"
    return None


def _format_skipped_sections(gathered_data: dict[str, object]) -> str | None:
    """Format skipped sections for summary."""
    skipped = []
    for section in ["education", "certifications", "resume_upload"]:
        sec_data = gathered_data.get(section, {})
        if isinstance(sec_data, dict) and sec_data.get("skipped"):
            skipped.append(section.replace("_", " "))
    if skipped:
        return f"Skipped: {', '.join(skipped)}"
    return None


def format_gathered_data_summary(gathered_data: dict[str, object]) -> str:
    """Format gathered data into a human-readable summary.

    REQ-007 §5.6.1: System Prompt Template Variables

    Converts the gathered_data dict into a summary string suitable for
    injection into the system prompt. Provides context about what has
    been collected so far.

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
    summary_parts = [f(gathered_data) for f in formatters]
    summary_parts = [p for p in summary_parts if p is not None]

    return "\n".join(summary_parts) if summary_parts else _NO_DATA_COLLECTED_MSG


def get_system_prompt(current_step: str, gathered_data_summary: str) -> str:
    """Get the system prompt with template variables filled in.

    REQ-007 §5.6.1: System Prompt (Interviewer Persona)

    Fills in the current step and gathered data summary into the
    system prompt template.

    Args:
        current_step: Current step in the onboarding flow.
        gathered_data_summary: Pre-formatted summary of gathered data.

    Returns:
        Complete system prompt with variables filled in.
    """
    return SYSTEM_PROMPT_TEMPLATE.format(
        current_step=current_step,
        gathered_data_summary=gathered_data_summary or _NO_DATA_COLLECTED_MSG,
    )


def get_work_history_prompt(job_entry: dict[str, object]) -> str:
    """Get the work history expansion prompt for a specific job.

    REQ-007 §5.6.2: Step-Specific Prompts

    Fills in job details to guide probing for accomplishments.

    Args:
        job_entry: Dict with job details (title, company, dates, etc.).

    Returns:
        Work history expansion prompt with job context.
    """
    title = job_entry.get("title", job_entry.get("raw_input", "this role"))
    company = job_entry.get("company", "their company")

    return WORK_HISTORY_EXPANSION_PROMPT.format(
        title=title,
        company=company,
    )


def get_achievement_story_prompt(
    existing_stories: list[str],
    covered_skills: list[str],
) -> str:
    """Get the achievement story prompt with context about what's captured.

    REQ-007 §5.6.2: Achievement Story Gathering

    Fills in existing stories and covered skills to guide the user
    toward sharing stories that demonstrate different competencies.

    Args:
        existing_stories: List of story summaries already captured.
        covered_skills: List of skills already demonstrated by stories.

    Returns:
        Achievement story prompt with context about diversity needs.
    """
    stories_str = (
        "\n".join(f"- {s}" for s in existing_stories)
        if existing_stories
        else "None yet"
    )
    skills_str = ", ".join(covered_skills) if covered_skills else "None yet"

    return ACHIEVEMENT_STORY_PROMPT.format(
        existing_stories=stories_str,
        covered_skills=skills_str,
    )


def get_voice_profile_prompt(transcript: str) -> str:
    """Get the voice profile derivation prompt with conversation transcript.

    REQ-007 §5.6.2: Voice Profile Derivation

    Fills in the conversation transcript for voice analysis.

    Args:
        transcript: The conversation transcript to analyze.

    Returns:
        Voice profile prompt with transcript included.
    """
    return VOICE_PROFILE_DERIVATION_PROMPT.format(
        transcript=transcript or "(No transcript available)",
    )


def get_transition_prompt(from_step: str, to_step: str) -> str:
    """Get the transition prompt between two steps.

    REQ-007 §5.6.3: Transition Prompts

    Returns a natural conversational transition between interview sections.
    Falls back to a generic transition if no specific prompt is defined.

    Args:
        from_step: The step being completed.
        to_step: The step being started.

    Returns:
        Transition prompt text.
    """
    # Try exact match first
    if (from_step, to_step) in TRANSITION_PROMPTS:
        return TRANSITION_PROMPTS[(from_step, to_step)]

    # Generic fallback
    step_display = to_step.replace("_", " ")
    return f"Let's move on to {step_display}."


# =============================================================================
# Post-Onboarding Update Constants (§5.5)
# =============================================================================

# WHY: These sections affect job matching when updated. After updating these,
# the system must regenerate embeddings and/or re-score jobs (REQ-007 §5.5).
SECTIONS_REQUIRING_RESCORE = {
    "skills",  # Affects fit score via hard_skills embedding
    "non_negotiables",  # Affects job filtering (salary, remote, etc.)
    "growth_targets",  # Affects stretch score calculation
    "work_history",  # Affects experience level matching
}

# WHY: Maps sections to affected embedding types for regeneration (REQ-007 §5.5).
# When a section is updated, these embeddings need refresh before re-scoring.
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

# WHY: Patterns for detecting which section user wants to update (§5.5).
# Order matters - more specific patterns should come first.
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
    # Work history - must indicate adding/updating, not just asking about jobs
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
            r"(?:finish|complet|graduat).*(?:degree|school|education)", re.IGNORECASE
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

    REQ-007 §5.1: Trigger Conditions

    Triggers when:
    - New user (no persona exists)
    - User has persona but onboarding_complete is False (incomplete)

    Does NOT trigger when:
    - User has persona with onboarding_complete = True

    Args:
        persona_exists: Whether user has a persona record.
        onboarding_complete: Whether onboarding is marked complete.

    Returns:
        True if onboarding should start/resume.
    """
    # No persona → definitely need onboarding
    if not persona_exists:
        return True

    # Has persona but incomplete → resume
    return not onboarding_complete


def is_update_request(message: str) -> bool:
    """Check if a message is a profile update request.

    REQ-007 §5.1: Trigger Conditions

    Users can trigger partial re-interview by saying things like:
    - "Update my profile"
    - "Add a new skill"
    - "Change my salary requirement"

    Args:
        message: User's message text.

    Returns:
        True if message indicates an update request.
    """
    return any(pattern.search(message) for pattern in UPDATE_REQUEST_PATTERNS)


# =============================================================================
# Post-Onboarding Updates (§5.5)
# =============================================================================


def detect_update_section(message: str) -> str | None:
    """Detect which persona section the user wants to update.

    REQ-007 §5.5: Post-Onboarding Updates

    Analyzes the user's message to determine which section of their persona
    they want to update. Used to route to the appropriate interview step.

    Examples:
        - "I got a new certification" → "certifications"
        - "I learned Kubernetes" → "skills"
        - "Change my salary requirement" → "non_negotiables"

    Args:
        message: User's message text.

    Returns:
        Section name if detected, None otherwise.
    """
    for pattern, section in SECTION_DETECTION_PATTERNS:
        if pattern.search(message):
            return section
    return None


def create_update_state(
    section: str,
    user_id: str,
    persona_id: str,
) -> OnboardingState:
    """Create state for a single-section post-onboarding update.

    REQ-007 §5.5: Post-Onboarding Updates

    Creates an OnboardingState configured for partial update mode.
    Unlike full onboarding, this runs only the specified section's
    interview step and then completes.

    Args:
        section: Section name to update (e.g., "skills", "certifications").
        user_id: User's ID for tenant isolation.
        persona_id: Persona ID being updated.

    Returns:
        OnboardingState configured for partial update.
    """
    state: OnboardingState = {
        "user_id": user_id,
        "persona_id": persona_id,
        "messages": [],
        "current_message": None,
        "tool_calls": [],
        "tool_results": [],
        "next_action": None,
        "requires_human_input": False,
        "checkpoint_reason": None,
        "current_step": section,
        "gathered_data": {},
        "skipped_sections": [],
        "pending_question": None,
        "user_response": None,
        "is_partial_update": True,
    }
    return state


def is_post_onboarding_update(state: OnboardingState) -> bool:
    """Check if the current state represents a post-onboarding partial update.

    REQ-007 §5.5: Post-Onboarding Updates

    Distinguishes between full onboarding flow and partial updates.
    This affects completion behavior - partial updates don't proceed
    through all steps.

    Args:
        state: Current onboarding state.

    Returns:
        True if this is a partial update (not full onboarding).
    """
    return state.get("is_partial_update", False)


def get_affected_embeddings(section: str) -> list[str]:
    """Get embedding types affected by updating a section.

    REQ-007 §5.5: Post-Onboarding Updates

    When a persona section is updated, certain embeddings may need
    regeneration before job re-scoring. This function identifies
    which embedding types are affected.

    Args:
        section: Section name that was updated.

    Returns:
        List of affected embedding type names. Empty list if no
        embeddings are affected (e.g., non_negotiables affects
        filtering, not embeddings).
    """
    return SECTION_AFFECTED_EMBEDDINGS.get(section, [])


def get_update_completion_message(section: str) -> str:
    """Generate completion message after a post-onboarding update.

    REQ-007 §5.5: Post-Onboarding Updates

    Generates an appropriate message informing the user about what
    happens next. For sections that affect job matching (skills,
    non_negotiables, growth_targets), mentions re-analyzing jobs.

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


# =============================================================================
# Interview Flow (§5.2)
# =============================================================================


def get_next_step(current_step: str) -> str | None:
    """Get the next step in the onboarding flow.

    Args:
        current_step: Current step name.

    Returns:
        Next step name, or None if at the end.
    """
    try:
        current_index = ONBOARDING_STEPS.index(current_step)
        if current_index < len(ONBOARDING_STEPS) - 1:
            return ONBOARDING_STEPS[current_index + 1]
        return None
    except ValueError:
        return None


def is_step_optional(step: str) -> bool:
    """Check if a step can be skipped.

    Args:
        step: Step name.

    Returns:
        True if the step is optional.
    """
    return step in OPTIONAL_SECTIONS


# =============================================================================
# Step Behaviors (§5.3)
# =============================================================================


def gather_basic_info(state: OnboardingState) -> OnboardingState:
    """Gather basic contact information.

    REQ-007 §5.3.2: Basic Info Step

    Gathers: full_name, email, phone, location, linkedin_url, portfolio_url

    Args:
        state: Current onboarding state.

    Returns:
        Updated state with gathered data or HITL flags set.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    gathered = dict(state.get("gathered_data", {}))
    basic_info = gathered.get("basic_info", {})

    # Check if we have a response to process
    user_response = state.get("user_response")
    pending_question = state.get("pending_question")

    if user_response and pending_question:
        # Determine which field this response is for
        if "name" in pending_question.lower():
            basic_info["full_name"] = user_response
            # Ask for email next
            new_state["pending_question"] = (
                "What's the best email for job applications?"
            )
            new_state["user_response"] = None
        elif "email" in pending_question.lower():
            basic_info["email"] = user_response
            new_state["pending_question"] = "And your phone number?"
            new_state["user_response"] = None
        elif "phone" in pending_question.lower():
            basic_info["phone"] = user_response
            new_state["pending_question"] = (
                "Where are you located? (City, State/Country)"
            )
            new_state["user_response"] = None
        elif (
            "location" in pending_question.lower()
            or "located" in pending_question.lower()
        ):
            basic_info["location"] = user_response
            # Optional fields - we can ask or skip
            new_state["pending_question"] = None
            new_state["user_response"] = None

        gathered["basic_info"] = basic_info
        new_state["gathered_data"] = gathered

        # If we have all required fields, we're done
        required = REQUIRED_FIELDS.get("basic_info", [])
        if all(basic_info.get(field) for field in required):
            new_state["requires_human_input"] = False
            return new_state

    # No response yet or still need more info - ask first question
    if not basic_info.get("full_name"):
        new_state["pending_question"] = (
            "What's your full name as you'd like it on applications?"
        )
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["gathered_data"] = gathered
        return new_state

    # If we get here but still need input, set HITL
    if new_state.get("pending_question"):
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value

    return new_state


def check_step_complete(state: OnboardingState) -> str:
    """Check if the current step is complete.

    REQ-007 §5.2: Determines routing after each step:
    - "needs_input": Step requires more user input
    - "skip_requested": User wants to skip (optional sections only)
    - "complete": Step has all required data

    Args:
        state: Current onboarding state.

    Returns:
        Routing decision string.
    """
    current_step = state.get("current_step", "")
    user_response = state.get("user_response", "")

    # Check for skip request on optional sections
    if (
        user_response
        and user_response.lower().strip() == "skip"
        and is_step_optional(current_step)
    ):
        return "skip_requested"

    # Check if HITL is needed (still waiting for input)
    if state.get("requires_human_input"):
        return "needs_input"

    # Check if we have all required data for this step
    gathered = state.get("gathered_data", {})
    step_data = gathered.get(current_step, {})
    required = REQUIRED_FIELDS.get(current_step, [])

    if required:
        if all(step_data.get(field) for field in required):
            return "complete"
        return "needs_input"

    # Steps without specific requirements are complete if they ran
    return "complete"


def wait_for_input(state: OnboardingState) -> OnboardingState:
    """HITL checkpoint node - pauses for user input.

    REQ-007 §5.4: Checkpoint Handling

    This node is reached when a step needs user input. It ensures
    HITL flags are set so the graph checkpoints and waits.

    Args:
        state: Current onboarding state.

    Returns:
        State with HITL flags set.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["requires_human_input"] = True
    new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value

    # Add the pending question to messages for display
    pending = state.get("pending_question")
    if pending:
        messages = list(state.get("messages", []))
        # Only add if not already the last message
        if not messages or messages[-1].get("content") != pending:
            messages.append(
                {
                    "role": "assistant",
                    "content": pending,
                }
            )
            new_state["messages"] = messages

    return new_state


def handle_skip(state: OnboardingState) -> OnboardingState:
    """Handle skip request for optional sections.

    REQ-007 §5.4: Checkpoint Handling

    Adds the current step to skipped_sections list.

    Args:
        state: Current onboarding state.

    Returns:
        State with step added to skipped_sections.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    current_step = state.get("current_step", "")
    skipped = list(state.get("skipped_sections", []))

    if current_step not in skipped:
        skipped.append(current_step)

    new_state["skipped_sections"] = skipped
    new_state["user_response"] = None
    new_state["pending_question"] = None

    return new_state


# =============================================================================
# Placeholder Step Nodes (§5.3)
# =============================================================================

# WHY: These are placeholder implementations. Full implementations will use
# LLM calls for conversational gathering (§5.6 Prompt Templates) and API calls
# to persist data (AgentAPIClient). For MVP, we test the graph structure first.


def check_resume_upload(state: OnboardingState) -> OnboardingState:
    """Check for resume upload step.

    REQ-007 §5.3.1: Resume Upload Step

    Asks if user has an existing resume. Options:
    - Upload resume → Extract data, populate persona
    - Skip → Proceed to manual entry via interview

    Args:
        state: Current onboarding state.

    Returns:
        Updated state with HITL flags or gathered data.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["current_step"] = "resume_upload"
    gathered = dict(state.get("gathered_data", {}))

    user_response = state.get("user_response")
    pending_question = state.get("pending_question")

    # Handle user response
    if user_response and pending_question:
        response_lower = user_response.lower().strip()

        # User wants to skip
        # WHY: "no" is treated as skip because the question is "Do you have a resume?"
        # A "no" answer means they don't have one, same outcome as explicitly skipping.
        if response_lower == "skip" or response_lower == "no":
            gathered["resume_upload"] = {"skipped": True}
            new_state["gathered_data"] = gathered
            new_state["requires_human_input"] = False
            new_state["pending_question"] = None
            new_state["user_response"] = None
            return new_state

        # User wants to upload
        if response_lower == "yes" or "upload" in response_lower:
            new_state["pending_question"] = (
                "Please upload your resume file (PDF or DOCX format)."
            )
            new_state["requires_human_input"] = True
            new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
            new_state["user_response"] = None
            new_state["gathered_data"] = gathered
            return new_state

    # Check if resume data already gathered (from file upload)
    resume_data = gathered.get("resume_upload", {})
    if resume_data.get("skipped") or resume_data.get("extracted_jobs"):
        new_state["requires_human_input"] = False
        new_state["gathered_data"] = gathered
        return new_state

    # First time - ask if user has resume
    new_state["pending_question"] = (
        "Do you have an existing resume to upload? (PDF or DOCX) "
        "Type 'yes' to upload, or 'skip' to enter your info manually."
    )
    new_state["requires_human_input"] = True
    new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
    new_state["gathered_data"] = gathered

    return new_state


def _handle_work_history_response(
    user_response: str,
    question_lower: str,
    work_history: dict[str, object],
    new_state: OnboardingState,
    gathered: dict[str, object],
) -> OnboardingState:
    """Handle user response during work history gathering."""
    # User is done adding jobs - check this FIRST before other keyword parsing
    if "done" in user_response.lower():
        new_state["requires_human_input"] = False
        new_state["pending_question"] = None
        new_state["user_response"] = None
        gathered["work_history"] = work_history
        new_state["gathered_data"] = gathered
        return new_state

    # Confirming extracted job
    if (
        "confirm" in question_lower or "correct" in question_lower
    ) and work_history.get("current_entry"):
        work_history["current_entry"]["confirmed"] = True
        new_state["pending_question"] = (
            "Tell me more about your accomplishments in this role. "
            "What was your biggest achievement?"
        )
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["work_history"] = work_history
        new_state["gathered_data"] = gathered
        return new_state

    # Job title/role response
    # WHY: We parse question text to determine state. Future improvement could
    # use an explicit current_field state flag for more robust transitions.
    if "job" in question_lower or "role" in question_lower or "title" in question_lower:
        work_history["current_entry"] = {
            "raw_input": user_response,
            "bullets": [],
        }
        new_state["pending_question"] = (
            "What company was this at, and what were the dates?"
        )
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["work_history"] = work_history
        new_state["gathered_data"] = gathered
        return new_state

    # Company/dates response
    if "company" in question_lower or "dates" in question_lower:
        if work_history.get("current_entry"):
            work_history["current_entry"]["company_dates"] = user_response
        new_state["pending_question"] = (
            "Tell me about your key accomplishments in this role. "
            "What results did you achieve?"
        )
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["work_history"] = work_history
        new_state["gathered_data"] = gathered
        return new_state

    # Accomplishments response
    if (
        "accomplish" in question_lower or "achieve" in question_lower
    ) and work_history.get("current_entry"):
        current = work_history["current_entry"]
        if "bullets" not in current:
            current["bullets"] = []
        current["bullets"].append(user_response)

        entries = list(work_history.get("entries", []))
        entries.append(current)
        work_history["entries"] = entries
        work_history["current_entry"] = None

        new_state["pending_question"] = (
            "Do you have another job to add? "
            "Say 'done' if you've listed all your relevant experience."
        )
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["work_history"] = work_history
        new_state["gathered_data"] = gathered
        return new_state

    gathered["work_history"] = work_history
    new_state["gathered_data"] = gathered
    return new_state


def gather_work_history(state: OnboardingState) -> OnboardingState:
    """Gather work history step.

    REQ-007 §5.3.3: Work History Step

    Gathers job entries with:
    - Title, company, dates
    - Accomplishment bullets (expanded via probing questions)

    If resume was uploaded, presents extracted jobs for confirmation.
    Otherwise, asks for each job manually.

    Args:
        state: Current onboarding state.

    Returns:
        Updated state with job entries or HITL flags.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["current_step"] = "work_history"
    gathered = dict(state.get("gathered_data", {}))
    work_history = dict(gathered.get("work_history", {}))

    user_response = state.get("user_response")
    pending_question = state.get("pending_question")

    # Initialize entries list if not present
    if "entries" not in work_history:
        work_history["entries"] = []

    # Check if we have extracted jobs from resume
    resume_data = gathered.get("resume_upload", {})
    extracted_jobs = resume_data.get("extracted_jobs", [])

    # Handle user response
    if user_response and pending_question:
        return _handle_work_history_response(
            user_response,
            pending_question.lower(),
            work_history,
            new_state,
            gathered,
        )

    # Check if work history is already complete
    entries = work_history.get("entries", [])
    if entries and all(e.get("bullets") for e in entries):
        new_state["requires_human_input"] = False
        gathered["work_history"] = work_history
        new_state["gathered_data"] = gathered
        return new_state

    # If we have extracted jobs, present first one for confirmation
    if extracted_jobs and not work_history.get("current_entry"):
        job = extracted_jobs[0]
        work_history["current_entry"] = job
        new_state["pending_question"] = (
            f"I found this job from your resume: {job.get('title', 'Unknown')} "
            f"at {job.get('company', 'Unknown')} "
            f"({job.get('start_date', '?')} - {job.get('end_date', '?')}). "
            "Is this correct? (yes/no)"
        )
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        gathered["work_history"] = work_history
        new_state["gathered_data"] = gathered
        return new_state

    # No resume data - ask for most recent job
    new_state["pending_question"] = (
        "Let's start with your most recent job. What was your job title?"
    )
    new_state["requires_human_input"] = True
    new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
    gathered["work_history"] = work_history
    new_state["gathered_data"] = gathered

    return new_state


def _handle_education_response(
    user_response: str,
    question_lower: str,
    education: dict[str, object],
    new_state: OnboardingState,
    gathered: dict[str, object],
) -> OnboardingState:
    """Handle user response during education gathering."""
    response_lower = user_response.lower().strip()

    # User is done adding entries - check this FIRST before other keyword parsing
    if response_lower == "done":
        new_state["requires_human_input"] = False
        new_state["pending_question"] = None
        new_state["user_response"] = None
        gathered["education"] = education
        new_state["gathered_data"] = gathered
        return new_state

    # User wants to skip or has no education
    # WHY: "no" is treated as skip because the question is "Do you have education?"
    # A "no" answer means they don't have any, same outcome as explicitly skipping.
    if response_lower == "skip" or response_lower == "no":
        education["skipped"] = True
        gathered["education"] = education
        new_state["gathered_data"] = gathered
        new_state["requires_human_input"] = False
        new_state["pending_question"] = None
        new_state["user_response"] = None
        return new_state

    # Graduation year response (last field before completion)
    if ("year" in question_lower or "graduat" in question_lower) and education.get(
        "current_entry"
    ):
        education["current_entry"]["graduation_year"] = user_response

        entries = list(education.get("entries", []))
        entries.append(education["current_entry"])
        education["entries"] = entries
        education["current_entry"] = None

        new_state["pending_question"] = (
            "Do you have another degree to add? "
            "Say 'done' if you've listed all your education."
        )
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["education"] = education
        new_state["gathered_data"] = gathered
        return new_state

    # Institution response
    if "institution" in question_lower or "school" in question_lower:
        if education.get("current_entry"):
            education["current_entry"]["institution"] = user_response
        new_state["pending_question"] = "What year did you graduate?"
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["education"] = education
        new_state["gathered_data"] = gathered
        return new_state

    # Degree/field response (first answer in the chain)
    if "degree" in question_lower or "education" in question_lower:
        education["current_entry"] = {
            "degree": user_response,
        }
        new_state["pending_question"] = "What institution did you attend?"
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["education"] = education
        new_state["gathered_data"] = gathered
        return new_state

    gathered["education"] = education
    new_state["gathered_data"] = gathered
    return new_state


def gather_education(state: OnboardingState) -> OnboardingState:
    """Gather education step.

    REQ-007 §5.3 / REQ-001 §3.3: Education Step

    Gathers education entries with:
    - Degree, field of study
    - Institution, graduation year
    - Optional: GPA, honors

    This is an optional section - users can skip if they have no formal education.

    Args:
        state: Current onboarding state.

    Returns:
        Updated state with education entries or HITL flags.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["current_step"] = "education"
    gathered = dict(state.get("gathered_data", {}))
    education = dict(gathered.get("education", {}))

    user_response = state.get("user_response")
    pending_question = state.get("pending_question")

    # Initialize entries list if not present
    if "entries" not in education:
        education["entries"] = []

    # Handle user response
    if user_response and pending_question:
        return _handle_education_response(
            user_response,
            pending_question.lower(),
            education,
            new_state,
            gathered,
        )

    # Check if education data already gathered
    if education.get("skipped") or education.get("entries"):
        new_state["requires_human_input"] = False
        gathered["education"] = education
        new_state["gathered_data"] = gathered
        return new_state

    # First time - ask if user has education
    new_state["pending_question"] = (
        "Do you have any formal education you'd like to include? (degrees, etc.) "
        "Type 'yes' to add education, or 'skip' if not applicable."
    )
    new_state["requires_human_input"] = True
    new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
    gathered["education"] = education
    new_state["gathered_data"] = gathered

    return new_state


def _handle_skills_response(
    user_response: str,
    question_lower: str,
    skills: dict[str, object],
    new_state: OnboardingState,
    gathered: dict[str, object],
) -> OnboardingState:
    """Handle user response during skills gathering."""
    response_lower = user_response.lower().strip()

    # User is done adding skills - check this FIRST before other keyword parsing
    if response_lower == "done":
        new_state["requires_human_input"] = False
        new_state["pending_question"] = None
        new_state["user_response"] = None
        gathered["skills"] = skills
        new_state["gathered_data"] = gathered
        return new_state

    # Skill type response (last field before completion)
    if (
        "type" in question_lower or "hard" in question_lower or "soft" in question_lower
    ) and skills.get("current_entry"):
        skills["current_entry"]["skill_type"] = user_response

        entries = list(skills.get("entries", []))
        entries.append(skills["current_entry"])
        skills["entries"] = entries
        skills["current_entry"] = None

        new_state["pending_question"] = (
            "Do you have another skill to add? "
            "Say 'done' if you've listed all your key skills."
        )
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["skills"] = skills
        new_state["gathered_data"] = gathered
        return new_state

    # Proficiency response
    if "proficiency" in question_lower or "rate" in question_lower:
        if skills.get("current_entry"):
            skills["current_entry"]["proficiency"] = user_response
        skill_name = skills.get("current_entry", {}).get("skill_name", "this skill")
        new_state["pending_question"] = (
            f"Is {skill_name} a hard (technical) or soft (interpersonal) skill?"
        )
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["skills"] = skills
        new_state["gathered_data"] = gathered
        return new_state

    # Skill name response (first answer in the chain)
    if "skill" in question_lower and (
        "what" in question_lower or "key" in question_lower
    ):
        skills["current_entry"] = {
            "skill_name": user_response,
        }
        new_state["pending_question"] = (
            f"How would you rate your {user_response} proficiency? "
            "(Learning / Familiar / Proficient / Expert)"
        )
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["skills"] = skills
        new_state["gathered_data"] = gathered
        return new_state

    gathered["skills"] = skills
    new_state["gathered_data"] = gathered
    return new_state


def gather_skills(state: OnboardingState) -> OnboardingState:
    """Gather skills step.

    REQ-007 §5.3.4: Skills Step

    Gathers skills with:
    - Skill name
    - Proficiency level (Learning / Familiar / Proficient / Expert)
    - Skill type (Hard/technical or Soft/interpersonal)

    If resume was uploaded, presents extracted skills for proficiency rating.
    Otherwise, asks user to list skills manually.

    Args:
        state: Current onboarding state.

    Returns:
        Updated state with skills entries or HITL flags.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["current_step"] = "skills"
    gathered = dict(state.get("gathered_data", {}))
    skills = dict(gathered.get("skills", {}))

    user_response = state.get("user_response")
    pending_question = state.get("pending_question")

    # Initialize entries list if not present
    if "entries" not in skills:
        skills["entries"] = []

    # Check for extracted skills from resume
    resume_data = gathered.get("resume_upload", {})
    extracted_skills = resume_data.get("extracted_skills", [])

    # Handle user response
    if user_response and pending_question:
        return _handle_skills_response(
            user_response,
            pending_question.lower(),
            skills,
            new_state,
            gathered,
        )

    # Check if skills data already gathered
    if skills.get("entries"):
        new_state["requires_human_input"] = False
        gathered["skills"] = skills
        new_state["gathered_data"] = gathered
        return new_state

    # If we have extracted skills from resume, present them for rating
    if extracted_skills:
        first_skill = extracted_skills[0]
        skills["current_entry"] = {"skill_name": first_skill}
        skills["remaining_extracted"] = extracted_skills[1:]
        new_state["pending_question"] = (
            f"I found '{first_skill}' in your resume. "
            "How would you rate your proficiency? (Learning / Familiar / Proficient / Expert)"
        )
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        gathered["skills"] = skills
        new_state["gathered_data"] = gathered
        return new_state

    # First time - ask for skills
    new_state["pending_question"] = (
        "What is one of your key skills? (technical or interpersonal)"
    )
    new_state["requires_human_input"] = True
    new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
    gathered["skills"] = skills
    new_state["gathered_data"] = gathered

    return new_state


def _handle_certifications_response(
    user_response: str,
    question_lower: str,
    certifications: dict[str, object],
    new_state: OnboardingState,
    gathered: dict[str, object],
) -> OnboardingState:
    """Handle user response during certifications gathering."""
    response_lower = user_response.lower().strip()

    # User is done adding entries - check this FIRST before other keyword parsing
    if response_lower == "done":
        new_state["requires_human_input"] = False
        new_state["pending_question"] = None
        new_state["user_response"] = None
        gathered["certifications"] = certifications
        new_state["gathered_data"] = gathered
        return new_state

    # User wants to skip or has no certifications
    # WHY: "no" is treated as skip because the question is "Do you have certs?"
    # A "no" answer means they don't have any, same outcome as explicitly skipping.
    if response_lower == "skip" or response_lower == "no":
        certifications["skipped"] = True
        gathered["certifications"] = certifications
        new_state["gathered_data"] = gathered
        new_state["requires_human_input"] = False
        new_state["pending_question"] = None
        new_state["user_response"] = None
        return new_state

    # Date obtained response (last field before completion)
    if ("date" in question_lower or "when" in question_lower) and certifications.get(
        "current_entry"
    ):
        certifications["current_entry"]["date_obtained"] = user_response

        entries = list(certifications.get("entries", []))
        entries.append(certifications["current_entry"])
        certifications["entries"] = entries
        certifications["current_entry"] = None

        new_state["pending_question"] = (
            "Do you have another certification to add? "
            "Say 'done' if you've listed all your certifications."
        )
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["certifications"] = certifications
        new_state["gathered_data"] = gathered
        return new_state

    # Issuing organization response
    if "issu" in question_lower or "organization" in question_lower:
        if certifications.get("current_entry"):
            certifications["current_entry"]["issuing_organization"] = user_response
        new_state["pending_question"] = "When did you obtain this certification?"
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["certifications"] = certifications
        new_state["gathered_data"] = gathered
        return new_state

    # Certification name response (first answer in the chain)
    if "certification" in question_lower or "cert" in question_lower:
        certifications["current_entry"] = {
            "certification_name": user_response,
        }
        new_state["pending_question"] = "What organization issued this certification?"
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["certifications"] = certifications
        new_state["gathered_data"] = gathered
        return new_state

    gathered["certifications"] = certifications
    new_state["gathered_data"] = gathered
    return new_state


def gather_certifications(state: OnboardingState) -> OnboardingState:
    """Gather certifications step.

    REQ-007 §5.3 / REQ-001 §3.5: Certifications Step

    Gathers certification entries with:
    - Certification name
    - Issuing organization
    - Date obtained
    - Optional: expiration date, credential ID, verification URL

    This is an optional section - users can skip if they have no certifications.

    Args:
        state: Current onboarding state.

    Returns:
        Updated state with certification entries or HITL flags.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["current_step"] = "certifications"
    gathered = dict(state.get("gathered_data", {}))
    certifications = dict(gathered.get("certifications", {}))

    user_response = state.get("user_response")
    pending_question = state.get("pending_question")

    # Initialize entries list if not present
    if "entries" not in certifications:
        certifications["entries"] = []

    # Handle user response
    if user_response and pending_question:
        return _handle_certifications_response(
            user_response,
            pending_question.lower(),
            certifications,
            new_state,
            gathered,
        )

    # Check if certifications data already gathered
    if certifications.get("skipped") or certifications.get("entries"):
        new_state["requires_human_input"] = False
        gathered["certifications"] = certifications
        new_state["gathered_data"] = gathered
        return new_state

    # First time - ask if user has certifications
    new_state["pending_question"] = (
        "Do you have any professional certifications? "
        "Type 'yes' to add certifications, or 'skip' if not applicable."
    )
    new_state["requires_human_input"] = True
    new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
    gathered["certifications"] = certifications
    new_state["gathered_data"] = gathered

    return new_state


def _handle_stories_response(
    user_response: str,
    question_lower: str,
    stories: dict[str, object],
    new_state: OnboardingState,
    gathered: dict[str, object],
) -> OnboardingState:
    """Handle user response during achievement stories gathering."""
    response_lower = user_response.lower().strip()

    # User is done adding stories - check this FIRST
    if response_lower == "done":
        new_state["requires_human_input"] = False
        new_state["pending_question"] = None
        new_state["user_response"] = None
        gathered["achievement_stories"] = stories
        new_state["gathered_data"] = gathered
        return new_state

    # Skills demonstrated response (last field - completes the story)
    if ("skill" in question_lower and "demonstrat" in question_lower) and stories.get(
        "current_entry"
    ):
        stories["current_entry"]["skills_demonstrated"] = user_response

        entries = list(stories.get("entries", []))
        entries.append(stories["current_entry"])
        stories["entries"] = entries
        stories["current_entry"] = None

        story_count = len(entries)
        if story_count < 3:
            new_state["pending_question"] = (
                f"Great story! You have {story_count} so far. "
                "Do you have another achievement story to share? (goal is 3-5 stories)"
            )
        else:
            new_state["pending_question"] = (
                f"Excellent! You have {story_count} stories. "
                "Do you have another achievement story, or say 'done' to continue."
            )
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["achievement_stories"] = stories
        new_state["gathered_data"] = gathered
        return new_state

    # Outcome/result response
    if (
        "result" in question_lower
        or "outcome" in question_lower
        or "impact" in question_lower
    ) and stories.get("current_entry"):
        stories["current_entry"]["outcome"] = user_response
        new_state["pending_question"] = "Which skills did this demonstrate?"
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["achievement_stories"] = stories
        new_state["gathered_data"] = gathered
        return new_state

    # Action response
    if (
        "action" in question_lower
        or "you do" in question_lower
        or "specifically" in question_lower
    ) and stories.get("current_entry"):
        stories["current_entry"]["action"] = user_response
        new_state["pending_question"] = (
            "What was the result or impact? Can you put a number on it?"
        )
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["achievement_stories"] = stories
        new_state["gathered_data"] = gathered
        return new_state

    # Context/situation response
    if (
        "context" in question_lower
        or "situation" in question_lower
        or "challeng" in question_lower
    ) and stories.get("current_entry"):
        stories["current_entry"]["context"] = user_response
        new_state["pending_question"] = (
            "What specifically did YOU do? (not your team, just your actions)"
        )
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["achievement_stories"] = stories
        new_state["gathered_data"] = gathered
        return new_state

    # Initial story response (first answer in the chain)
    if (
        "achiev" in question_lower
        or "accomplish" in question_lower
        or "tell" in question_lower
    ):
        stories["current_entry"] = {
            "initial_story": user_response,
        }
        new_state["pending_question"] = (
            "What was the context or challenge you were facing?"
        )
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["achievement_stories"] = stories
        new_state["gathered_data"] = gathered
        return new_state

    gathered["achievement_stories"] = stories
    new_state["gathered_data"] = gathered
    return new_state


def gather_stories(state: OnboardingState) -> OnboardingState:
    """Gather achievement stories step.

    REQ-007 §5.3.5: Achievement Stories Step

    Gathers 3-5 structured stories in STAR format:
    - Context: What was the situation/challenge?
    - Action: What specifically did THEY do (not their team)?
    - Outcome: What was the measurable result?
    - Skills demonstrated: Which skills does this showcase?

    Uses probing questions to extract rich details for cover letter generation.

    Args:
        state: Current onboarding state.

    Returns:
        Updated state with story entries or HITL flags.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["current_step"] = "achievement_stories"
    gathered = dict(state.get("gathered_data", {}))
    stories = dict(gathered.get("achievement_stories", {}))

    user_response = state.get("user_response")
    pending_question = state.get("pending_question")

    # Initialize entries list if not present
    if "entries" not in stories:
        stories["entries"] = []

    # Handle user response
    if user_response and pending_question:
        return _handle_stories_response(
            user_response,
            pending_question.lower(),
            stories,
            new_state,
            gathered,
        )

    # Check if stories data already gathered
    if stories.get("entries"):
        new_state["requires_human_input"] = False
        gathered["achievement_stories"] = stories
        new_state["gathered_data"] = gathered
        return new_state

    # First time - prompt for an achievement story
    new_state["pending_question"] = (
        "Tell me about a time you achieved something significant at work. "
        "What's an accomplishment you're proud of?"
    )
    new_state["requires_human_input"] = True
    new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
    gathered["achievement_stories"] = stories
    new_state["gathered_data"] = gathered

    return new_state


def _handle_non_negotiables_response(
    user_response: str,
    question_lower: str,
    non_neg: dict[str, object],
    new_state: OnboardingState,
    gathered: dict[str, object],
) -> OnboardingState:
    """Handle user response during non-negotiables gathering."""
    # Custom filters response (last field - completes the step)
    if "dealbreaker" in question_lower or "other" in question_lower:
        non_neg["custom_filters"] = user_response
        gathered["non_negotiables"] = non_neg
        new_state["gathered_data"] = gathered
        new_state["requires_human_input"] = False
        new_state["pending_question"] = None
        new_state["user_response"] = None
        return new_state

    # Industry exclusions response
    if "industr" in question_lower or "avoid" in question_lower:
        non_neg["industry_exclusions"] = user_response
        new_state["pending_question"] = "Any other dealbreakers I should know about?"
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["non_negotiables"] = non_neg
        new_state["gathered_data"] = gathered
        return new_state

    # Visa sponsorship response
    if "visa" in question_lower or "sponsor" in question_lower:
        non_neg["visa_sponsorship"] = user_response
        new_state["pending_question"] = "Any industries you want to avoid?"
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["non_negotiables"] = non_neg
        new_state["gathered_data"] = gathered
        return new_state

    # Salary response
    if "salary" in question_lower or "minimum" in question_lower:
        non_neg["minimum_base_salary"] = user_response
        new_state["pending_question"] = "Do you require visa sponsorship?"
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["non_negotiables"] = non_neg
        new_state["gathered_data"] = gathered
        return new_state

    # Commutable cities response
    if "cit" in question_lower or "commut" in question_lower:
        non_neg["commutable_cities"] = user_response
        new_state["pending_question"] = "What's your minimum acceptable base salary?"
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["non_negotiables"] = non_neg
        new_state["gathered_data"] = gathered
        return new_state

    # Remote preference response (first in chain)
    if (
        "remote" in question_lower
        or "hybrid" in question_lower
        or "onsite" in question_lower
    ):
        non_neg["remote_preference"] = user_response
        response_lower = user_response.lower()

        # WHY: If remote-only, skip cities question since commute location
        # doesn't matter. Otherwise ask for commutable cities.
        if "remote" in response_lower and "only" in response_lower:
            new_state["pending_question"] = (
                "What's your minimum acceptable base salary?"
            )
        else:
            new_state["pending_question"] = "Which cities can you commute to?"

        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["non_negotiables"] = non_neg
        new_state["gathered_data"] = gathered
        return new_state

    gathered["non_negotiables"] = non_neg
    new_state["gathered_data"] = gathered
    return new_state


def gather_non_negotiables(state: OnboardingState) -> OnboardingState:
    """Gather non-negotiables step.

    REQ-007 §5.3.6: Non-Negotiables Step

    Gathers job preference filters:
    - remote_preference: Remote / Hybrid / Onsite
    - commutable_cities: Only if not remote-only
    - minimum_base_salary: Minimum acceptable base salary
    - visa_sponsorship: Whether visa sponsorship is required
    - industry_exclusions: Industries to avoid
    - custom_filters: Any other dealbreakers

    Args:
        state: Current onboarding state.

    Returns:
        Updated state with non-negotiables data or HITL flags.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["current_step"] = "non_negotiables"
    gathered = dict(state.get("gathered_data", {}))
    non_neg = dict(gathered.get("non_negotiables", {}))

    user_response = state.get("user_response")
    pending_question = state.get("pending_question")

    # Handle user response
    if user_response and pending_question:
        return _handle_non_negotiables_response(
            user_response,
            pending_question.lower(),
            non_neg,
            new_state,
            gathered,
        )

    # Check if non-negotiables data already gathered (all fields complete)
    if non_neg.get("custom_filters"):
        new_state["requires_human_input"] = False
        gathered["non_negotiables"] = non_neg
        new_state["gathered_data"] = gathered
        return new_state

    # First time - ask about remote preference
    new_state["pending_question"] = (
        "Are you looking for remote, hybrid, or onsite roles?"
    )
    new_state["requires_human_input"] = True
    new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
    gathered["non_negotiables"] = non_neg
    new_state["gathered_data"] = gathered

    return new_state


def gather_growth_targets(state: OnboardingState) -> OnboardingState:
    """Gather growth targets step.

    REQ-007 §5.3.7 / §7.5: Growth Targets Step

    Gathers career growth aspirations:
    - target_roles: Roles the user aspires to grow into
    - target_skills: Skills the user wants to develop

    These are used by the Strategist for Stretch Score calculation (§7.5):
    - Target role alignment: Similarity between job.job_title and persona.target_roles
    - Target skills exposure: Count of persona.target_skills present in job.requirements

    Args:
        state: Current onboarding state.

    Returns:
        Updated state with growth targets data or HITL flags.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["current_step"] = "growth_targets"
    gathered = dict(state.get("gathered_data", {}))
    growth = dict(gathered.get("growth_targets", {}))

    user_response = state.get("user_response")
    pending_question = state.get("pending_question")

    # Handle user response
    if user_response and pending_question:
        question_lower = pending_question.lower()

        # Target skills response (last field - completes the step)
        if (
            "skill" in question_lower
            or "learn" in question_lower
            or "develop" in question_lower
        ):
            growth["target_skills"] = user_response
            gathered["growth_targets"] = growth
            new_state["gathered_data"] = gathered
            new_state["requires_human_input"] = False
            new_state["pending_question"] = None
            new_state["user_response"] = None
            return new_state

        # Target roles response (first in chain)
        if (
            "role" in question_lower
            or "aspir" in question_lower
            or "grow" in question_lower
        ):
            growth["target_roles"] = user_response
            new_state["pending_question"] = "What skills would you like to develop?"
            new_state["requires_human_input"] = True
            new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
            new_state["user_response"] = None
            gathered["growth_targets"] = growth
            new_state["gathered_data"] = gathered
            return new_state

    # Check if growth targets data already gathered
    if growth.get("target_skills"):
        new_state["requires_human_input"] = False
        gathered["growth_targets"] = growth
        new_state["gathered_data"] = gathered
        return new_state

    # First time - ask about target roles
    new_state["pending_question"] = (
        "What roles are you aspiring to grow into? (or 'same role' if staying put)"
    )
    new_state["requires_human_input"] = True
    new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
    gathered["growth_targets"] = growth
    new_state["gathered_data"] = gathered

    return new_state


def _handle_voice_profile_response(
    user_response: str,
    question_lower: str,
    voice: dict[str, object],
    new_state: OnboardingState,
    gathered: dict[str, object],
) -> OnboardingState:
    """Handle user response during voice profile gathering."""
    response_lower = user_response.lower().strip()

    # Things to avoid response (last field - completes the step)
    if (
        "avoid" in question_lower
        or "buzzword" in question_lower
        or "never" in question_lower
    ):
        voice["things_to_avoid"] = user_response
        gathered["voice_profile"] = voice
        new_state["gathered_data"] = gathered
        new_state["requires_human_input"] = False
        new_state["pending_question"] = None
        new_state["user_response"] = None
        return new_state

    # Vocabulary level response
    if (
        "vocabulary" in question_lower
        or "technical" in question_lower
        or "jargon" in question_lower
    ):
        voice["vocabulary_level"] = user_response
        new_state["pending_question"] = (
            "Are there any words or phrases you never use? (buzzwords to avoid)"
        )
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["voice_profile"] = voice
        new_state["gathered_data"] = gathered
        return new_state

    # Sentence style response
    if "sentence" in question_lower or "style" in question_lower:
        voice["sentence_style"] = user_response
        new_state["pending_question"] = (
            "Do you prefer technical jargon or plain English?"
        )
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["voice_profile"] = voice
        new_state["gathered_data"] = gathered
        return new_state

    # Tone response
    if "tone" in question_lower:
        voice["tone"] = user_response
        new_state["pending_question"] = (
            "How would you describe your sentence style? (short and punchy, or detailed?)"
        )
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["voice_profile"] = voice
        new_state["gathered_data"] = gathered
        return new_state

    # Writing sample response or skip
    if "writing" in question_lower or "sample" in question_lower:
        if response_lower != "skip":
            voice["writing_sample_text"] = user_response
        new_state["pending_question"] = (
            "How would you describe your tone? (e.g., direct, warm, formal)"
        )
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["user_response"] = None
        gathered["voice_profile"] = voice
        new_state["gathered_data"] = gathered
        return new_state

    gathered["voice_profile"] = voice
    new_state["gathered_data"] = gathered
    return new_state


def derive_voice_profile(state: OnboardingState) -> OnboardingState:
    """Derive voice profile step.

    REQ-007 §5.3.7: Voice Profile Step

    Gathers voice profile traits for content generation:
    - writing_sample_text: Optional sample for analysis (§5.6.2)
    - tone: Direct/confident, warm/friendly, formal, etc.
    - sentence_style: Short and punchy, detailed and thorough, etc.
    - vocabulary_level: Technical jargon, plain English, etc.
    - things_to_avoid: Buzzwords/phrases user never uses

    These traits are used by Ghostwriter (REQ-007 §8.5) to generate
    cover letters that match the user's authentic writing voice.

    Args:
        state: Current onboarding state.

    Returns:
        Updated state with voice profile data or HITL flags.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["current_step"] = "voice_profile"
    gathered = dict(state.get("gathered_data", {}))
    voice = dict(gathered.get("voice_profile", {}))

    user_response = state.get("user_response")
    pending_question = state.get("pending_question")

    # Handle user response
    if user_response and pending_question:
        return _handle_voice_profile_response(
            user_response,
            pending_question.lower(),
            voice,
            new_state,
            gathered,
        )

    # Check if voice profile data already gathered (all required fields)
    if voice.get("things_to_avoid"):
        new_state["requires_human_input"] = False
        gathered["voice_profile"] = voice
        new_state["gathered_data"] = gathered
        return new_state

    # First time - ask about writing sample (optional)
    new_state["pending_question"] = (
        "Do you have a writing sample to share? (email, doc, etc.) "
        "This helps me capture your voice. Type 'skip' to continue without one."
    )
    new_state["requires_human_input"] = True
    new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
    gathered["voice_profile"] = voice
    new_state["gathered_data"] = gathered

    return new_state


def review_persona(state: OnboardingState) -> OnboardingState:
    """Review gathered persona step.

    Placeholder: Full implementation will present summary.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["current_step"] = "review"
    return new_state


def setup_base_resume(state: OnboardingState) -> OnboardingState:
    """Setup base resume step.

    REQ-007 §5.3.8: Base Resume Setup Step

    Creates one or more BaseResume entries based on target role types:
    - role_type: The type of role this resume targets (e.g., "Senior Software Engineer")
    - is_primary: First resume is marked as primary

    The agent will later use gathered_data from work_history, skills, etc.
    to populate included_jobs, skills_emphasis, and other fields.

    Args:
        state: Current onboarding state.

    Returns:
        Updated state with base resume entries or HITL flags.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["current_step"] = "base_resume_setup"
    gathered = dict(state.get("gathered_data", {}))
    base_resume = dict(gathered.get("base_resume_setup", {}))

    user_response = state.get("user_response")
    pending_question = state.get("pending_question")

    # Initialize entries list if not present
    if "entries" not in base_resume:
        base_resume["entries"] = []

    # Handle user response
    if user_response and pending_question:
        response_lower = user_response.lower().strip()
        question_lower = pending_question.lower()

        # User is done or says no to additional roles
        if response_lower == "done" or response_lower == "no":
            new_state["requires_human_input"] = False
            new_state["pending_question"] = None
            new_state["user_response"] = None
            gathered["base_resume_setup"] = base_resume
            new_state["gathered_data"] = gathered
            return new_state

        # Additional role response
        if (
            "other" in question_lower
            or "another" in question_lower
            or "additional" in question_lower
        ):
            # Create additional resume entry (not primary)
            entries = list(base_resume.get("entries", []))
            entries.append(
                {
                    "role_type": user_response,
                    "is_primary": False,
                }
            )
            base_resume["entries"] = entries

            # Ask if there are more roles
            new_state["pending_question"] = (
                "Any other role types you're considering? (or 'done')"
            )
            new_state["requires_human_input"] = True
            new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
            new_state["user_response"] = None
            gathered["base_resume_setup"] = base_resume
            new_state["gathered_data"] = gathered
            return new_state

        # Primary role response (first in chain)
        if (
            "role" in question_lower
            or "target" in question_lower
            or "position" in question_lower
            or "primarily" in question_lower
        ):
            # Create primary resume entry
            entries = list(base_resume.get("entries", []))
            entries.append(
                {
                    "role_type": user_response,
                    "is_primary": True,
                }
            )
            base_resume["entries"] = entries

            # Ask about additional roles
            new_state["pending_question"] = (
                "Any other role types you're considering? (or 'done')"
            )
            new_state["requires_human_input"] = True
            new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
            new_state["user_response"] = None
            gathered["base_resume_setup"] = base_resume
            new_state["gathered_data"] = gathered
            return new_state

    # Check if base resume data already gathered (at least one entry)
    if base_resume.get("entries"):
        new_state["requires_human_input"] = False
        gathered["base_resume_setup"] = base_resume
        new_state["gathered_data"] = gathered
        return new_state

    # First time - ask about primary role type
    new_state["pending_question"] = (
        "What type of role are you primarily targeting? (e.g., Software Engineer, Data Scientist)"
    )
    new_state["requires_human_input"] = True
    new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
    gathered["base_resume_setup"] = base_resume
    new_state["gathered_data"] = gathered

    return new_state


def complete_onboarding(state: OnboardingState) -> OnboardingState:
    """Complete onboarding step.

    Marks onboarding as complete and clears HITL flags.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["requires_human_input"] = False
    new_state["checkpoint_reason"] = None
    new_state["pending_question"] = None

    # Add completion message
    messages = list(state.get("messages", []))
    messages.append(
        {
            "role": "assistant",
            "content": "Great! Your profile is all set up. You can now start discovering job opportunities!",
        }
    )
    new_state["messages"] = messages

    return new_state


# =============================================================================
# Graph Construction (§15.2)
# =============================================================================


def create_onboarding_graph() -> StateGraph:
    """Create the Onboarding Agent LangGraph graph.

    REQ-007 §15.2: Graph Spec - Onboarding Agent

    Graph structure follows the interview flow with HITL checkpoints.
    Each step can pause for user input via wait_for_input node.

    Returns:
        Configured StateGraph (not compiled).
    """
    graph = StateGraph(OnboardingState)

    # Add step nodes
    graph.add_node("check_resume_upload", check_resume_upload)
    graph.add_node("gather_basic_info", gather_basic_info)
    graph.add_node("gather_work_history", gather_work_history)
    graph.add_node("gather_education", gather_education)
    graph.add_node("gather_skills", gather_skills)
    graph.add_node("gather_certifications", gather_certifications)
    graph.add_node("gather_stories", gather_stories)
    graph.add_node("gather_non_negotiables", gather_non_negotiables)
    graph.add_node("gather_growth_targets", gather_growth_targets)
    graph.add_node("derive_voice_profile", derive_voice_profile)
    graph.add_node("review_persona", review_persona)
    graph.add_node("setup_base_resume", setup_base_resume)
    graph.add_node("complete_onboarding", complete_onboarding)

    # HITL checkpoint node
    graph.add_node("wait_for_input", wait_for_input)

    # Skip handler
    graph.add_node("handle_skip", handle_skip)

    # Set entry point
    graph.set_entry_point("check_resume_upload")

    # Define step transitions
    # WHY: Each step has conditional edges to handle:
    # - needs_input → wait_for_input → back to step
    # - skip_requested → handle_skip → next step
    # - complete → next step

    step_pairs = [
        ("check_resume_upload", "gather_basic_info"),
        ("gather_basic_info", "gather_work_history"),
        ("gather_work_history", "gather_education"),
        ("gather_education", "gather_skills"),
        ("gather_skills", "gather_certifications"),
        ("gather_certifications", "gather_stories"),
        ("gather_stories", "gather_non_negotiables"),
        ("gather_non_negotiables", "gather_growth_targets"),
        ("gather_growth_targets", "derive_voice_profile"),
        ("derive_voice_profile", "review_persona"),
        ("review_persona", "setup_base_resume"),
        ("setup_base_resume", "complete_onboarding"),
    ]

    # Add conditional edges for each step
    for from_step, to_step in step_pairs:
        graph.add_conditional_edges(
            from_step,
            check_step_complete,
            {
                "needs_input": "wait_for_input",
                "skip_requested": "handle_skip",
                "complete": to_step,
            },
        )
        # wait_for_input returns to the step it came from
        # WHY: After user provides input, we re-run the step to process it
        graph.add_edge("wait_for_input", from_step)
        # handle_skip proceeds to next step
        graph.add_edge("handle_skip", to_step)

    # Final step goes to END
    graph.add_edge("complete_onboarding", END)

    return graph


# Compiled graph singleton
_onboarding_graph: StateGraph | None = None


def get_onboarding_graph() -> StateGraph:
    """Get the compiled onboarding graph.

    Returns a singleton compiled graph instance for use in the API.

    Returns:
        Compiled StateGraph ready for invocation.
    """
    global _onboarding_graph
    if _onboarding_graph is None:
        _onboarding_graph = create_onboarding_graph().compile()
    return _onboarding_graph
