"""Resume generation service — deterministic + LLM-assisted resume generation.

REQ-026 §3.4: Deterministic template fill — gathers persona data via
gather_base_resume_content() and mechanically slots it into template
{placeholder} markers. No LLM involved.

REQ-026 §4.4: LLM-assisted generation — gathers persona data, builds prompt
with template structure + persona + voice profile + generation options, calls
LLM via MeteredLLMProvider, returns (markdown, metadata).
"""

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models.persona_settings import VoiceProfile
from app.models.resume import BaseResume
from app.models.resume_template import ResumeTemplate
from app.prompts.resume_generation import (
    RESUME_GENERATION_SYSTEM_PROMPT,
    build_resume_generation_prompt,
)
from app.providers.errors import ProviderError
from app.providers.llm.base import LLMMessage, LLMProvider, TaskType
from app.services.generation.voice_prompt_block import build_voice_profile_block
from app.services.pdf_generation import (
    ResumeContent,
    ResumeJobEntry,
    gather_base_resume_content,
)

logger = logging.getLogger(__name__)

# Month names for date formatting (shared with pdf_generation.py)
_MONTH_NAMES = [
    "",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]

# Regex to find {placeholder} tokens for single-pass replacement.
_PLACEHOLDER_RE = re.compile(r"\{([a-z_]+)\}")


def _format_date(d: date) -> str:
    """Format a date as 'Mon YYYY'."""
    return f"{_MONTH_NAMES[d.month]} {d.year}"


def _format_date_range(job: ResumeJobEntry) -> str:
    """Format a job's date range for display."""
    start_str = _format_date(job.start_date)
    if job.is_current:
        return f"{start_str} – Present"
    if job.end_date is not None:
        return f"{start_str} – {_format_date(job.end_date)}"
    return start_str


def _render_experience(content: ResumeContent) -> str:
    """Render all job entries as markdown."""
    if not content.jobs:
        return ""
    entries = []
    for job in content.jobs:
        date_range = _format_date_range(job)
        bullets = "\n".join(f"- {b}" for b in job.bullets)
        entry = f"### {job.job_title} — {job.company_name}\n*{date_range}*"
        if bullets:
            entry += f"\n\n{bullets}"
        entries.append(entry)
    return "\n\n".join(entries)


def _render_education(content: ResumeContent) -> str:
    """Render all education entries as markdown."""
    if not content.education:
        return ""
    entries = []
    for edu in content.education:
        entry = f"### {edu.degree} — {edu.institution}\n*{edu.graduation_year}*"
        entries.append(entry)
    return "\n\n".join(entries)


def _render_skills(content: ResumeContent) -> str:
    """Render skills as a comma-separated list."""
    if not content.skills:
        return ""
    return ", ".join(s.skill_name for s in content.skills)


def _render_certifications(content: ResumeContent) -> str:
    """Render certifications as a markdown bullet list."""
    if not content.certifications:
        return ""
    return "\n".join(f"- {c.certification_name}" for c in content.certifications)


def _replace_section_content(markdown: str, section_name: str, rendered: str) -> str:
    """Replace the content of a ## section with rendered data.

    Finds the section by its ``## SectionName`` header and replaces
    everything between the header line and the next ``---`` or ``## ``
    boundary with the rendered content.

    Uses a replacement function (not a replacement string) to avoid
    regex back-reference injection from user-controlled persona data.

    Args:
        markdown: Full template markdown.
        section_name: Section header text — must be one of the hardcoded
            values ("Experience", "Education", "Certifications").
            Never pass user input here.
        rendered: Pre-rendered markdown to insert.

    Returns:
        Updated markdown with section content replaced.
    """
    pattern = re.compile(
        rf"(## {re.escape(section_name)}\n)"  # group 1: header + newline
        rf"\n.*?"  # content to replace (non-greedy)
        rf"(\n---|\n## |\Z)",  # group 2: terminator
        re.DOTALL,
    )

    def _replacer(m: re.Match[str]) -> str:
        if rendered:
            return f"{m.group(1)}\n{rendered}\n{m.group(2)}"
        return f"{m.group(1)}{m.group(2)}"

    return pattern.sub(_replacer, markdown, count=1)


def _replace_placeholders(markdown: str, replacements: dict[str, str]) -> str:
    """Replace all {placeholder} tokens in a single pass.

    Single-pass replacement prevents cascading substitution where
    a persona value containing a placeholder token (e.g.
    full_name="{skills_list}") would be double-substituted.

    Args:
        markdown: Template markdown with {placeholder} tokens.
        replacements: Mapping of placeholder name to replacement value.

    Returns:
        Markdown with all known placeholders replaced. Unknown
        placeholders are left as-is.
    """

    def _lookup(m: re.Match[str]) -> str:
        key = m.group(1)
        return replacements.get(key, m.group(0))

    return _PLACEHOLDER_RE.sub(_lookup, markdown)


async def template_fill(
    resume: BaseResume,
    template: ResumeTemplate,
    session: AsyncSession,
) -> str:
    """Fill a template with persona data from a base resume.

    REQ-026 §3.4: Deterministic template fill (free path).
    Gathers selected persona data and mechanically slots it into
    the template's {placeholder} markers.

    Args:
        resume: BaseResume ORM instance (needs .id for data gathering).
        template: ResumeTemplate with markdown_content containing placeholders.
        session: Database session for gathering persona data.

    Returns:
        Completed markdown string with all placeholders replaced.
    """
    content = await gather_base_resume_content(session, resume.id)
    markdown = template.markdown_content

    # 1. Single-pass replacement of all simple placeholders.
    # Prevents cascading substitution from persona values that
    # contain placeholder tokens.
    location = f"{content.contact.city}, {content.contact.state}"
    markdown = _replace_placeholders(
        markdown,
        {
            "full_name": content.contact.full_name,
            "email": content.contact.email,
            "phone": content.contact.phone,
            "location": location,
            "linkedin_url": content.contact.linkedin_url or "",
            "summary": content.summary or "",
            "skills_list": _render_skills(content),
        },
    )

    # 2. Replace repeating section content.
    # Uses replacement functions (not strings) to prevent
    # regex back-reference injection from user data.
    markdown = _replace_section_content(
        markdown, "Experience", _render_experience(content)
    )
    markdown = _replace_section_content(
        markdown, "Education", _render_education(content)
    )
    markdown = _replace_section_content(
        markdown, "Certifications", _render_certifications(content)
    )

    return markdown


# =============================================================================
# LLM-Assisted Generation (REQ-026 §4.4)
# =============================================================================


class ResumeGenerationError(APIError):
    """Raised when LLM resume generation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(
            code="RESUME_GENERATION_ERROR",
            message=message,
            status_code=500,
        )


@dataclass(frozen=True)
class _VoiceProfileSnapshot:
    """Lightweight snapshot of voice profile fields for prompt building."""

    tone: str
    sentence_style: str
    vocabulary_level: str
    personality_markers: str | None
    sample_phrases: tuple[str, ...] | None
    things_to_avoid: tuple[str, ...] | None
    writing_sample_text: str | None


async def _get_voice_profile(
    session: AsyncSession, persona_id: uuid.UUID
) -> _VoiceProfileSnapshot | None:
    """Fetch the voice profile for a persona.

    Args:
        session: Database session.
        persona_id: UUID of the persona.

    Returns:
        VoiceProfileSnapshot if found, None otherwise.
    """
    result = await session.execute(
        select(VoiceProfile).where(VoiceProfile.persona_id == persona_id)
    )
    vp = result.scalar_one_or_none()
    if vp is None:
        return None
    return _VoiceProfileSnapshot(
        tone=vp.tone,
        sentence_style=vp.sentence_style,
        vocabulary_level=vp.vocabulary_level,
        personality_markers=vp.personality_markers,
        sample_phrases=tuple(vp.sample_phrases) if vp.sample_phrases else None,
        things_to_avoid=tuple(vp.things_to_avoid) if vp.things_to_avoid else None,
        writing_sample_text=vp.writing_sample_text,
    )


async def llm_generate(
    *,
    resume: BaseResume,
    template: ResumeTemplate,
    session: AsyncSession,
    provider: LLMProvider,
    page_limit: int = 1,
    emphasis: str = "balanced",
    include_sections: list[str] | None = None,
) -> tuple[str, dict]:
    """Generate a resume using an LLM provider.

    REQ-026 §4.4: Gathers persona data, builds prompt with template
    structure + persona + voice profile + generation options, calls LLM
    via MeteredLLMProvider, returns (markdown, metadata).

    Args:
        resume: BaseResume ORM instance.
        template: ResumeTemplate with markdown_content.
        session: Database session.
        provider: LLM provider (typically MeteredLLMProvider).
        page_limit: Target page count (1-3). Defaults to 1.
        emphasis: Emphasis preference. Defaults to "balanced".
        include_sections: Section identifiers to include. Defaults to all.

    Returns:
        Tuple of (markdown_content, metadata_dict).

    Raises:
        ResumeGenerationError: If the LLM fails or returns empty.
    """
    if include_sections is None:
        include_sections = [
            "summary",
            "experience",
            "education",
            "skills",
            "certifications",
        ]

    # 1. Gather persona data
    content = await gather_base_resume_content(session, resume.id)

    # 2. Build voice profile block
    voice = await _get_voice_profile(session, resume.persona_id)
    if voice is not None:
        voice_block = build_voice_profile_block(
            persona_name=content.contact.full_name,
            tone=voice.tone,
            sentence_style=voice.sentence_style,
            vocabulary_level=voice.vocabulary_level,
            personality_markers=voice.personality_markers,
            sample_phrases=list(voice.sample_phrases) if voice.sample_phrases else None,
            things_to_avoid=list(voice.things_to_avoid)
            if voice.things_to_avoid
            else None,
            writing_sample_text=voice.writing_sample_text,
        )
    else:
        voice_block = ""

    # 3. Pre-render persona sections for the prompt
    persona_jobs_text = _render_experience(content)
    persona_education_text = _render_education(content)
    persona_skills_text = _render_skills(content)
    persona_certifications_text = _render_certifications(content)

    # 4. Build the prompt
    user_prompt = build_resume_generation_prompt(
        template_markdown=template.markdown_content,
        persona_summary=content.summary or "",
        persona_name=content.contact.full_name,
        persona_jobs_text=persona_jobs_text,
        persona_education_text=persona_education_text,
        persona_skills_text=persona_skills_text,
        persona_certifications_text=persona_certifications_text,
        page_limit=page_limit,
        emphasis=emphasis,
        include_sections=include_sections,
        voice_profile_block=voice_block,
    )

    # 5. Call the LLM
    messages = [
        LLMMessage(role="system", content=RESUME_GENERATION_SYSTEM_PROMPT),
        LLMMessage(  # nosemgrep: zentropy.llm-unsanitized-input  # sanitized inside build_resume_generation_prompt()
            role="user", content=user_prompt
        ),
    ]

    try:
        response = await provider.complete(
            messages=messages,
            task=TaskType.RESUME_TAILORING,
        )
    except ProviderError as e:
        logger.error("Resume generation failed: %s", e)
        raise ResumeGenerationError(
            "Resume generation failed. Please try again."
        ) from e

    raw_content = response.content
    if not raw_content:
        raise ResumeGenerationError(
            "LLM returned empty response for resume generation."
        )

    # 6. Build metadata
    metadata = {
        "model": response.model,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "word_count": len(raw_content.split()),
    }

    return raw_content, metadata
