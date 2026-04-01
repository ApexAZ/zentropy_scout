"""Resume generation prompt templates.

REQ-026 §4.4: Prompt composed from template structure, persona data,
target role, page limit, emphasis preference, section selections, and
voice profile.

REQ-026 §4.5: Generation constraints — truthfulness, no fabrication,
voice consistency, template adherence, page limit respect.

Pattern: module-level constants + builder function with sanitize_llm_input().

Coordinates with:
  - core/llm_sanitization.py (sanitize_llm_input)

Called by: services/generation/resume_generation_service.py
  (build_resume_generation_prompt, RESUME_GENERATION_SYSTEM_PROMPT).
"""

from app.core.llm_sanitization import sanitize_llm_input

# =============================================================================
# Constants
# =============================================================================

_MAX_SUMMARY_LENGTH = 2000
"""Maximum characters for persona summary in the prompt."""

_MAX_JOBS_TEXT_LENGTH = 8000
"""Maximum characters for rendered job entries in the prompt."""

_MAX_EDUCATION_TEXT_LENGTH = 3000
"""Maximum characters for rendered education entries in the prompt."""

_MAX_SKILLS_TEXT_LENGTH = 1000
"""Maximum characters for rendered skills list in the prompt."""

_MAX_CERTIFICATIONS_TEXT_LENGTH = 2000
"""Maximum characters for rendered certifications in the prompt."""

_MAX_TEMPLATE_LENGTH = 5000
"""Maximum characters for the template markdown skeleton."""

_MAX_FIELD_LENGTH = 500
"""Maximum characters for short text fields (name, emphasis)."""

_MAX_SECTIONS_COUNT = 10
"""Maximum number of section identifiers in the include list."""

_MAX_SECTION_NAME_LENGTH = 50
"""Maximum characters per section identifier."""

# Page limit → target word count mapping (REQ-026 §4.3)
_PAGE_WORD_COUNTS: dict[int, int] = {
    1: 350,
    2: 700,
    3: 1050,
}

# =============================================================================
# System Prompt
# =============================================================================

RESUME_GENERATION_SYSTEM_PROMPT = """\
You are a professional resume writer generating a resume in markdown format.

CRITICAL CONSTRAINTS:
1. TRUTHFULNESS: Only use facts from the persona data provided. \
Do not fabricate metrics, skills, experiences, or accomplishments.
2. NO INVENTION: Never invent job titles, companies, dates, or achievements \
that are not in the persona data.
3. VOICE CONSISTENCY: Match the user's voice profile exactly \
(see <voice_profile> section).
4. TEMPLATE ADHERENCE: Follow the template structure provided. \
Output the same section headings in the same order.
5. PAGE LIMIT: Respect the target word count (within ±10%).

OUTPUT FORMAT:
- Return raw markdown only — no code fences, no explanations, no preamble.
- Start with a top-level heading (# Full Name).
- Use the section structure from the template.
- Bullet points for experience achievements.
- Comma-separated list for skills."""


# =============================================================================
# User Prompt Template
# =============================================================================

_RESUME_GENERATION_USER_TEMPLATE = """\
{voice_profile_block}

<template_structure>
{template_markdown}
</template_structure>

<persona_data>
Name: {persona_name}

Summary:
{persona_summary}

Work Experience:
{persona_jobs_text}

Education:
{persona_education_text}

Skills:
{persona_skills_text}

Certifications:
{persona_certifications_text}
</persona_data>

<generation_instructions>
Page limit: {page_limit_instruction}
Emphasis: {emphasis}
Sections to include: {sections_list}

Generate the resume now. Follow the template structure exactly. \
Only include the sections listed above.\
</generation_instructions>"""


# =============================================================================
# Builder Function
# =============================================================================


def build_resume_generation_prompt(
    *,
    template_markdown: str,
    persona_summary: str,
    persona_name: str,
    persona_jobs_text: str,
    persona_education_text: str,
    persona_skills_text: str,
    persona_certifications_text: str,
    page_limit: int,
    emphasis: str,
    include_sections: list[str],
    voice_profile_block: str,
) -> str:
    """Build the resume generation user prompt.

    REQ-026 §4.4: Composes persona data, template structure, generation
    options, and voice profile into a single user prompt for LLM completion.

    All user-controlled string parameters are sanitized via
    sanitize_llm_input() to mitigate prompt injection. The voice_profile_block
    is embedded as-is because it is already sanitized by
    build_voice_profile_block().

    Args:
        template_markdown: Template markdown skeleton with section headings.
        persona_summary: User's professional summary text.
        persona_name: Full name of the persona.
        persona_jobs_text: Pre-rendered work experience markdown.
        persona_education_text: Pre-rendered education markdown.
        persona_skills_text: Pre-rendered skills text.
        persona_certifications_text: Pre-rendered certifications markdown.
        page_limit: Target page count (1-3).
        emphasis: Emphasis preference (technical/leadership/balanced/industry-specific).
        include_sections: List of section identifiers to include.
        voice_profile_block: Pre-built <voice_profile> XML block (already sanitized).

    Returns:
        Formatted user prompt string for LLM completion.
    """
    target_words = _PAGE_WORD_COUNTS.get(page_limit, _PAGE_WORD_COUNTS[1])
    page_limit_instruction = (
        f"Keep the resume to approximately {target_words} words, "
        f"fitting on {page_limit} page{'s' if page_limit > 1 else ''}"
    )

    safe_sections = [
        sanitize_llm_input(s[:_MAX_SECTION_NAME_LENGTH])
        for s in include_sections[:_MAX_SECTIONS_COUNT]
    ]
    sections_list = ", ".join(safe_sections) if safe_sections else "all"

    return _RESUME_GENERATION_USER_TEMPLATE.format(
        voice_profile_block=voice_profile_block,
        template_markdown=sanitize_llm_input(template_markdown[:_MAX_TEMPLATE_LENGTH]),
        persona_name=sanitize_llm_input(persona_name[:_MAX_FIELD_LENGTH]),
        persona_summary=sanitize_llm_input(persona_summary[:_MAX_SUMMARY_LENGTH]),
        persona_jobs_text=sanitize_llm_input(persona_jobs_text[:_MAX_JOBS_TEXT_LENGTH]),
        persona_education_text=sanitize_llm_input(
            persona_education_text[:_MAX_EDUCATION_TEXT_LENGTH]
        ),
        persona_skills_text=sanitize_llm_input(
            persona_skills_text[:_MAX_SKILLS_TEXT_LENGTH]
        ),
        persona_certifications_text=sanitize_llm_input(
            persona_certifications_text[:_MAX_CERTIFICATIONS_TEXT_LENGTH]
        ),
        page_limit_instruction=page_limit_instruction,
        emphasis=sanitize_llm_input(emphasis[:_MAX_FIELD_LENGTH]),
        sections_list=sections_list,
    )
