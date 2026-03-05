"""Resume generation service — deterministic template fill.

REQ-026 §3.4: Gathers persona data via gather_base_resume_content()
and mechanically slots it into template {placeholder} markers.
No LLM involved — pure string substitution from persona fields.
"""

import re
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resume import BaseResume
from app.models.resume_template import ResumeTemplate
from app.services.pdf_generation import (
    ResumeContent,
    ResumeJobEntry,
    gather_base_resume_content,
)

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
