"""PDF generation service — render resumes using ReportLab Platypus.

REQ-002 §6.4: Generates PDF documents from BaseResume or JobVariant data.
Uses ReportLab Platypus (high-level layout API) with standard fonts.

Two rendering paths:
1. BaseResume → uses included_* selection fields + Persona content
2. JobVariant → Draft inherits from BaseResume; Approved uses snapshot_* fields

Public API:
- gather_base_resume_content  — extract structured content from BaseResume
- gather_variant_content      — extract structured content from JobVariant
- render_resume_pdf           — pure render: ResumeContent → PDF bytes
- render_base_resume_pdf      — gather + render for BaseResume
- render_variant_pdf          — gather + render for JobVariant
"""

import io
import uuid
from dataclasses import dataclass
from datetime import date
from xml.sax.saxutils import (
    escape as _xml_escape,  # nosec B406 — output escaping, not XML parsing
)

from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.persona import Persona
from app.models.persona_content import (
    Bullet,
    Certification,
    Education,
    Skill,
    WorkHistory,
)
from app.models.resume import BaseResume, JobVariant

# =============================================================================
# Data Structures
# =============================================================================


@dataclass(frozen=True)
class ResumeContactInfo:
    """Contact information for the resume header."""

    full_name: str
    email: str
    phone: str
    city: str
    state: str
    linkedin_url: str | None
    portfolio_url: str | None


@dataclass(frozen=True)
class ResumeJobEntry:
    """A work history entry for the resume."""

    job_title: str
    company_name: str
    location: str
    start_date: date
    end_date: date | None
    is_current: bool
    bullets: list[str]


@dataclass(frozen=True)
class ResumeEducationEntry:
    """An education entry for the resume."""

    degree: str
    institution: str
    field_of_study: str
    graduation_year: int


@dataclass(frozen=True)
class ResumeCertificationEntry:
    """A certification entry for the resume."""

    certification_name: str
    issuing_organization: str
    date_obtained: date


@dataclass(frozen=True)
class ResumeSkillEntry:
    """A skill entry for the resume."""

    skill_name: str
    skill_type: str
    category: str


@dataclass(frozen=True)
class ResumeContent:
    """All structured content needed to render a resume PDF."""

    contact: ResumeContactInfo
    summary: str
    jobs: list[ResumeJobEntry]
    education: list[ResumeEducationEntry]
    certifications: list[ResumeCertificationEntry]
    skills: list[ResumeSkillEntry]


# =============================================================================
# Styles
# =============================================================================

_MARGIN_SIDE = 0.75 * inch
_MARGIN_TOP = 0.5 * inch
_MARGIN_BOTTOM = 0.5 * inch
_SECTION_SPACING = 6
_ITEM_SPACING = 3

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


def _format_date(d: date) -> str:
    """Format a date as 'Mon YYYY'."""
    return f"{_MONTH_NAMES[d.month]} {d.year}"


def _format_date_range(start: date, end: date | None, is_current: bool) -> str:
    """Format a date range for display."""
    start_str = _format_date(start)
    if is_current:
        return f"{start_str} – Present"
    if end is not None:
        return f"{start_str} – {_format_date(end)}"
    return start_str


def _build_styles() -> dict[str, ParagraphStyle]:
    """Build custom paragraph styles for resume rendering."""
    base = getSampleStyleSheet()

    return {
        "name": ParagraphStyle(
            "ResumeName",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "contact": ParagraphStyle(
            "ResumeContact",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "section_heading": ParagraphStyle(
            "SectionHeading",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            spaceBefore=8,
            spaceAfter=4,
            textColor="black",
        ),
        "job_title": ParagraphStyle(
            "JobTitle",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            spaceAfter=1,
        ),
        "job_meta": ParagraphStyle(
            "JobMeta",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=11,
            spaceAfter=2,
            textColor="#444444",
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            leftIndent=12,
            spaceAfter=1,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            alignment=TA_LEFT,
            spaceAfter=2,
        ),
        "edu_line": ParagraphStyle(
            "EduLine",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            spaceAfter=1,
        ),
        "skills_line": ParagraphStyle(
            "SkillsLine",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            spaceAfter=2,
        ),
    }


# =============================================================================
# Content Gathering — Internal Helpers
# =============================================================================


async def _load_persona(db: AsyncSession, persona_id: uuid.UUID) -> Persona:
    """Load a Persona by ID, raising NotFoundError if missing."""
    persona = await db.get(Persona, persona_id)
    if persona is None:
        raise NotFoundError("Persona", str(persona_id))
    return persona


def _build_contact(persona: Persona) -> ResumeContactInfo:
    """Extract contact info from a Persona."""
    return ResumeContactInfo(
        full_name=persona.full_name,
        email=persona.email,
        phone=persona.phone,
        city=persona.home_city,
        state=persona.home_state,
        linkedin_url=persona.linkedin_url,
        portfolio_url=persona.portfolio_url,
    )


async def _load_jobs_with_bullets(
    db: AsyncSession,
    included_jobs: list[str],
    bullet_selections: dict[str, list[str]],
    bullet_order: dict[str, list[str]],
) -> list[ResumeJobEntry]:
    """Load WorkHistory entries and their selected bullets.

    Args:
        db: Database session.
        included_jobs: List of job ID strings to include.
        bullet_selections: Map of job_id → [bullet_ids] to include.
        bullet_order: Map of job_id → [bullet_ids] in display order.

    Returns:
        List of ResumeJobEntry with bullets in the correct order.
    """
    if not included_jobs:
        return []

    job_ids = [uuid.UUID(jid) for jid in included_jobs]

    # Batch load all selected jobs
    result = await db.execute(select(WorkHistory).where(WorkHistory.id.in_(job_ids)))
    jobs_by_id = {j.id: j for j in result.scalars().all()}

    # Batch load all selected bullets
    all_bullet_id_strs: list[str] = []
    for bid_list in bullet_selections.values():
        all_bullet_id_strs.extend(bid_list)

    bullets_by_id: dict[uuid.UUID, Bullet] = {}
    if all_bullet_id_strs:
        bullet_uuids = [uuid.UUID(bid) for bid in all_bullet_id_strs]
        bullet_result = await db.execute(
            select(Bullet).where(Bullet.id.in_(bullet_uuids))
        )
        bullets_by_id = {b.id: b for b in bullet_result.scalars().all()}

    # Assemble in included_jobs order (preserves display order)
    entries: list[ResumeJobEntry] = []
    for jid_str in included_jobs:
        jid = uuid.UUID(jid_str)
        job = jobs_by_id.get(jid)
        if job is None:
            continue

        # Determine bullet order for this job
        selected_bid_strs = bullet_selections.get(jid_str, [])
        order_bid_strs = bullet_order.get(jid_str)

        if order_bid_strs is not None:
            # Use explicit order, filtering to only selected bullets
            selected_set = set(selected_bid_strs)
            ordered_bid_strs = [b for b in order_bid_strs if b in selected_set]
        else:
            # Fall back to selection order
            ordered_bid_strs = selected_bid_strs

        bullet_texts: list[str] = []
        for bid_str in ordered_bid_strs:
            bullet = bullets_by_id.get(uuid.UUID(bid_str))
            if bullet is not None:
                bullet_texts.append(bullet.text)

        entries.append(
            ResumeJobEntry(
                job_title=job.job_title,
                company_name=job.company_name,
                location=job.location,
                start_date=job.start_date,
                end_date=job.end_date,
                is_current=job.is_current,
                bullets=bullet_texts,
            )
        )

    return entries


async def _load_education(
    db: AsyncSession,
    included_education: list[str],
) -> list[ResumeEducationEntry]:
    """Load Education entries by ID list."""
    if not included_education:
        return []

    edu_ids = [uuid.UUID(eid) for eid in included_education]
    result = await db.execute(select(Education).where(Education.id.in_(edu_ids)))
    edu_by_id = {e.id: e for e in result.scalars().all()}

    # Preserve included_education order
    return [
        ResumeEducationEntry(
            degree=e.degree,
            institution=e.institution,
            field_of_study=e.field_of_study,
            graduation_year=e.graduation_year,
        )
        for eid_str in included_education
        if (e := edu_by_id.get(uuid.UUID(eid_str))) is not None
    ]


async def _load_certifications(
    db: AsyncSession,
    included_certifications: list[str],
) -> list[ResumeCertificationEntry]:
    """Load Certification entries by ID list."""
    if not included_certifications:
        return []

    cert_ids = [uuid.UUID(cid) for cid in included_certifications]
    result = await db.execute(
        select(Certification).where(Certification.id.in_(cert_ids))
    )
    cert_by_id = {c.id: c for c in result.scalars().all()}

    return [
        ResumeCertificationEntry(
            certification_name=c.certification_name,
            issuing_organization=c.issuing_organization,
            date_obtained=c.date_obtained,
        )
        for cid_str in included_certifications
        if (c := cert_by_id.get(uuid.UUID(cid_str))) is not None
    ]


async def _load_skills(
    db: AsyncSession,
    skills_emphasis: list[str],
) -> list[ResumeSkillEntry]:
    """Load Skill entries by ID list."""
    if not skills_emphasis:
        return []

    skill_ids = [uuid.UUID(sid) for sid in skills_emphasis]
    result = await db.execute(select(Skill).where(Skill.id.in_(skill_ids)))
    skill_by_id = {s.id: s for s in result.scalars().all()}

    return [
        ResumeSkillEntry(
            skill_name=s.skill_name,
            skill_type=s.skill_type,
            category=s.category,
        )
        for sid_str in skills_emphasis
        if (s := skill_by_id.get(uuid.UUID(sid_str))) is not None
    ]


async def _gather_content(
    db: AsyncSession,
    persona_id: uuid.UUID,
    summary: str,
    included_jobs: list[str],
    bullet_selections: dict[str, list[str]],
    bullet_order: dict[str, list[str]],
    included_education: list[str],
    included_certifications: list[str],
    skills_emphasis: list[str],
) -> ResumeContent:
    """Gather all resume content from DB into a ResumeContent structure."""
    persona = await _load_persona(db, persona_id)
    contact = _build_contact(persona)

    jobs = await _load_jobs_with_bullets(
        db, included_jobs, bullet_selections, bullet_order
    )
    education = await _load_education(db, included_education)
    certifications = await _load_certifications(db, included_certifications)
    skills = await _load_skills(db, skills_emphasis)

    return ResumeContent(
        contact=contact,
        summary=summary,
        jobs=jobs,
        education=education,
        certifications=certifications,
        skills=skills,
    )


# =============================================================================
# Public API — Content Gathering
# =============================================================================


async def gather_base_resume_content(
    db: AsyncSession,
    base_resume_id: uuid.UUID,
) -> ResumeContent:
    """Gather structured content from a BaseResume and its Persona.

    Args:
        db: Database session.
        base_resume_id: The BaseResume to gather content from.

    Returns:
        ResumeContent with all sections populated from selections.

    Raises:
        NotFoundError: If BaseResume or its Persona does not exist.
    """
    resume = await db.get(BaseResume, base_resume_id)
    if resume is None:
        raise NotFoundError("BaseResume", str(base_resume_id))

    return await _gather_content(
        db=db,
        persona_id=resume.persona_id,
        summary=resume.summary,
        included_jobs=list(resume.included_jobs),
        bullet_selections=dict(resume.job_bullet_selections),
        bullet_order=dict(resume.job_bullet_order),
        included_education=list(resume.included_education),
        included_certifications=list(resume.included_certifications),
        skills_emphasis=list(resume.skills_emphasis),
    )


async def gather_variant_content(
    db: AsyncSession,
    job_variant_id: uuid.UUID,
) -> ResumeContent:
    """Gather structured content from a JobVariant.

    Draft variants inherit selection fields from their BaseResume.
    Approved variants use their own snapshot_* fields.

    Args:
        db: Database session.
        job_variant_id: The JobVariant to gather content from.

    Returns:
        ResumeContent with all sections populated.

    Raises:
        NotFoundError: If JobVariant, its BaseResume, or Persona does not exist.
    """
    variant = await db.get(JobVariant, job_variant_id)
    if variant is None:
        raise NotFoundError("JobVariant", str(job_variant_id))

    base_resume = await db.get(BaseResume, variant.base_resume_id)
    if base_resume is None:
        raise NotFoundError("BaseResume", str(variant.base_resume_id))

    # Approved variants use snapshot fields; drafts inherit from base resume
    if variant.status == "Approved" and variant.snapshot_included_jobs is not None:
        included_jobs = list(variant.snapshot_included_jobs)
        bullet_selections = dict(variant.snapshot_job_bullet_selections or {})
        included_education = list(variant.snapshot_included_education or [])
        included_certifications = list(variant.snapshot_included_certifications or [])
        skills_emphasis = list(variant.snapshot_skills_emphasis or [])
    else:
        included_jobs = list(base_resume.included_jobs)
        bullet_selections = dict(base_resume.job_bullet_selections)
        included_education = list(base_resume.included_education)
        included_certifications = list(base_resume.included_certifications)
        skills_emphasis = list(base_resume.skills_emphasis)

    return await _gather_content(
        db=db,
        persona_id=base_resume.persona_id,
        summary=variant.summary,
        included_jobs=included_jobs,
        bullet_selections=bullet_selections,
        bullet_order=dict(variant.job_bullet_order),
        included_education=included_education,
        included_certifications=included_certifications,
        skills_emphasis=skills_emphasis,
    )


# =============================================================================
# Public API — PDF Rendering
# =============================================================================


def render_resume_pdf(content: ResumeContent) -> bytes:
    """Render a ResumeContent structure into a PDF document.

    Uses ReportLab Platypus with standard Helvetica fonts.
    Returns raw PDF bytes suitable for BYTEA storage.

    Args:
        content: Structured resume content to render.

    Returns:
        PDF file as bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=_MARGIN_SIDE,
        rightMargin=_MARGIN_SIDE,
        topMargin=_MARGIN_TOP,
        bottomMargin=_MARGIN_BOTTOM,
    )

    styles = _build_styles()
    elements: list[object] = []

    # --- Header ---
    # WHY _xml_escape: ReportLab Paragraph interprets XML/HTML markup.
    # All user-controlled strings must be escaped to prevent PDF injection.
    esc = _xml_escape

    elements.append(Paragraph(esc(content.contact.full_name), styles["name"]))

    contact_parts = [esc(content.contact.email), esc(content.contact.phone)]
    if content.contact.city:
        location = esc(content.contact.city)
        if content.contact.state:
            location = f"{location}, {esc(content.contact.state)}"
        contact_parts.append(location)
    if content.contact.linkedin_url:
        contact_parts.append(esc(content.contact.linkedin_url))

    elements.append(Paragraph(" | ".join(contact_parts), styles["contact"]))
    elements.append(
        HRFlowable(
            width="100%", thickness=0.5, color="black", spaceAfter=_SECTION_SPACING
        )
    )

    # --- Professional Summary ---
    if content.summary:
        elements.append(Paragraph("PROFESSIONAL SUMMARY", styles["section_heading"]))
        elements.append(Paragraph(esc(content.summary), styles["body"]))
        elements.append(Spacer(1, _SECTION_SPACING))

    # --- Work Experience ---
    if content.jobs:
        elements.append(Paragraph("WORK EXPERIENCE", styles["section_heading"]))
        for job in content.jobs:
            date_range = _format_date_range(
                job.start_date, job.end_date, job.is_current
            )
            elements.append(
                Paragraph(
                    f"<b>{esc(job.job_title)}</b> — {esc(job.company_name)}",
                    styles["job_title"],
                )
            )
            elements.append(
                Paragraph(
                    f"{esc(job.location)} | {date_range}",
                    styles["job_meta"],
                )
            )
            for bullet_text in job.bullets:
                elements.append(Paragraph(f"• {esc(bullet_text)}", styles["bullet"]))
            elements.append(Spacer(1, _ITEM_SPACING))

    # --- Education ---
    if content.education:
        elements.append(Paragraph("EDUCATION", styles["section_heading"]))
        for edu in content.education:
            elements.append(
                Paragraph(
                    f"<b>{esc(edu.degree)}</b> in {esc(edu.field_of_study)} — "
                    f"{esc(edu.institution)}, {edu.graduation_year}",
                    styles["edu_line"],
                )
            )
        elements.append(Spacer(1, _ITEM_SPACING))

    # --- Certifications ---
    if content.certifications:
        elements.append(Paragraph("CERTIFICATIONS", styles["section_heading"]))
        for cert in content.certifications:
            cert_date = _format_date(cert.date_obtained)
            elements.append(
                Paragraph(
                    f"<b>{esc(cert.certification_name)}</b> — "
                    f"{esc(cert.issuing_organization)} ({cert_date})",
                    styles["edu_line"],
                )
            )
        elements.append(Spacer(1, _ITEM_SPACING))

    # --- Skills ---
    if content.skills:
        elements.append(Paragraph("SKILLS", styles["section_heading"]))
        skill_names = [esc(s.skill_name) for s in content.skills]
        elements.append(Paragraph(", ".join(skill_names), styles["skills_line"]))

    doc.build(elements)
    return buffer.getvalue()


# =============================================================================
# Public API — Combined (Gather + Render)
# =============================================================================


async def render_base_resume_pdf(
    db: AsyncSession,
    base_resume_id: uuid.UUID,
) -> bytes:
    """Gather content from a BaseResume and render as PDF.

    Args:
        db: Database session.
        base_resume_id: The BaseResume to render.

    Returns:
        PDF file as bytes.

    Raises:
        NotFoundError: If BaseResume or its Persona does not exist.
    """
    content = await gather_base_resume_content(db, base_resume_id)
    return render_resume_pdf(content)


async def render_variant_pdf(
    db: AsyncSession,
    job_variant_id: uuid.UUID,
) -> bytes:
    """Gather content from a JobVariant and render as PDF.

    Args:
        db: Database session.
        job_variant_id: The JobVariant to render.

    Returns:
        PDF file as bytes.

    Raises:
        NotFoundError: If JobVariant, BaseResume, or Persona does not exist.
    """
    content = await gather_variant_content(db, job_variant_id)
    return render_resume_pdf(content)
