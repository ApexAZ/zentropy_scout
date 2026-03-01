"""Tests for PDF generation service (REQ-002 §6.4).

TDD tests for ReportLab-based resume PDF rendering:
- Content gathering from BaseResume/JobVariant selections
- Platypus-based PDF rendering
- Full pipeline integration (gather + render)
"""

import uuid
from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.persona import Persona
from app.models.persona_content import (
    Bullet,
    Certification,
    Education,
    Skill,
    WorkHistory,
)
from app.models.resume import BaseResume, JobVariant
from app.models.user import User
from app.services.pdf_generation import (
    ResumeContent,
    gather_base_resume_content,
    gather_variant_content,
    render_base_resume_pdf,
    render_resume_pdf,
    render_variant_pdf,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def pdf_persona(db_session: AsyncSession) -> SimpleNamespace:
    """Create a persona with full content for PDF rendering tests.

    Returns namespace with persona, jobs, bullets, education, certs, skills.
    """
    user = User(email="pdftest@example.com")
    db_session.add(user)
    await db_session.flush()

    persona = Persona(
        user_id=user.id,
        email="jane.smith@example.com",
        full_name="Jane Smith",
        phone="555-0100",
        home_city="Austin",
        home_state="TX",
        home_country="US",
        linkedin_url="https://linkedin.com/in/janesmith",
        onboarding_complete=True,
    )
    db_session.add(persona)
    await db_session.flush()

    # Two work history entries
    job1 = WorkHistory(
        persona_id=persona.id,
        job_title="Senior Software Engineer",
        company_name="TechCorp Inc",
        start_date=date(2020, 1, 1),
        end_date=None,
        is_current=True,
        location="Austin, TX",
        work_model="Remote",
        display_order=0,
    )
    job2 = WorkHistory(
        persona_id=persona.id,
        job_title="Software Engineer",
        company_name="StartupCo",
        start_date=date(2018, 6, 1),
        end_date=date(2019, 12, 31),
        is_current=False,
        location="San Francisco, CA",
        work_model="Hybrid",
        display_order=1,
    )
    # A third job NOT included in any resume (to test filtering)
    job3 = WorkHistory(
        persona_id=persona.id,
        job_title="Intern",
        company_name="BigCo",
        start_date=date(2017, 5, 1),
        end_date=date(2017, 8, 31),
        is_current=False,
        location="New York, NY",
        work_model="Onsite",
        display_order=2,
    )
    db_session.add_all([job1, job2, job3])
    await db_session.flush()

    # Bullets for job1
    b1 = Bullet(
        work_history_id=job1.id,
        text="Led team of 5 engineers on microservice migration",
        display_order=0,
    )
    b2 = Bullet(
        work_history_id=job1.id,
        text="Reduced API latency by 40% through caching strategy",
        display_order=1,
    )
    # A third bullet NOT included (to test filtering)
    b3_excluded = Bullet(
        work_history_id=job1.id,
        text="Wrote internal documentation",
        display_order=2,
    )
    # Bullet for job2
    b4 = Bullet(
        work_history_id=job2.id,
        text="Built event-driven architecture serving 1M daily events",
        display_order=0,
    )
    db_session.add_all([b1, b2, b3_excluded, b4])
    await db_session.flush()

    # Education
    edu1 = Education(
        persona_id=persona.id,
        degree="B.S.",
        institution="MIT",
        field_of_study="Computer Science",
        graduation_year=2018,
        display_order=0,
    )
    edu2 = Education(
        persona_id=persona.id,
        degree="M.S.",
        institution="Stanford University",
        field_of_study="Machine Learning",
        graduation_year=2020,
        display_order=1,
    )
    db_session.add_all([edu1, edu2])
    await db_session.flush()

    # Certifications
    cert1 = Certification(
        persona_id=persona.id,
        certification_name="AWS Solutions Architect",
        issuing_organization="Amazon Web Services",
        date_obtained=date(2021, 3, 15),
        display_order=0,
    )
    db_session.add(cert1)
    await db_session.flush()

    # Skills
    skill1 = Skill(
        persona_id=persona.id,
        skill_name="Python",
        skill_type="Hard",
        category="Programming",
        proficiency="Expert",
        years_used=5,
        last_used="Current",
    )
    skill2 = Skill(
        persona_id=persona.id,
        skill_name="Leadership",
        skill_type="Soft",
        category="Management",
        proficiency="Proficient",
        years_used=3,
        last_used="Current",
    )
    skill3 = Skill(
        persona_id=persona.id,
        skill_name="SQL",
        skill_type="Hard",
        category="Database",
        proficiency="Proficient",
        years_used=4,
        last_used="Current",
    )
    db_session.add_all([skill1, skill2, skill3])
    await db_session.flush()
    await db_session.commit()

    return SimpleNamespace(
        persona=persona,
        job1=job1,
        job2=job2,
        job3=job3,
        b1=b1,
        b2=b2,
        b3_excluded=b3_excluded,
        b4=b4,
        edu1=edu1,
        edu2=edu2,
        cert1=cert1,
        skill1=skill1,
        skill2=skill2,
        skill3=skill3,
    )


@pytest_asyncio.fixture
async def base_resume(
    db_session: AsyncSession,
    pdf_persona: SimpleNamespace,
) -> BaseResume:
    """Create a base resume with selections referencing pdf_persona data."""
    p = pdf_persona
    resume = BaseResume(
        persona_id=p.persona.id,
        name="Engineering Resume",
        role_type="Senior Engineer",
        summary="Experienced engineer with 5+ years building scalable systems.",
        included_jobs=[str(p.job1.id), str(p.job2.id)],
        job_bullet_selections={
            str(p.job1.id): [str(p.b1.id), str(p.b2.id)],
            str(p.job2.id): [str(p.b4.id)],
        },
        # Custom order: reversed for job1, no order for job2
        job_bullet_order={
            str(p.job1.id): [str(p.b2.id), str(p.b1.id)],
        },
        included_education=[str(p.edu1.id)],
        included_certifications=[str(p.cert1.id)],
        skills_emphasis=[str(p.skill1.id), str(p.skill2.id)],
        status="Active",
    )
    db_session.add(resume)
    await db_session.flush()
    await db_session.commit()
    return resume


@pytest_asyncio.fixture
async def job_variant_draft(
    db_session: AsyncSession,
    base_resume: BaseResume,
) -> JobVariant:
    """Create a draft job variant (inherits from base resume)."""
    from app.models.job_posting import JobPosting
    from app.models.job_source import JobSource

    source = JobSource(
        source_name="TestSource",
        source_type="Extension",
        description="Test",
    )
    db_session.add(source)
    await db_session.flush()

    job_posting = JobPosting(
        source_id=source.id,
        job_title="Staff Engineer at BigTech",
        company_name="BigTech Corp",
        description="We need a staff engineer.",
        requirements="5+ years Python",
        first_seen_date=date(2026, 1, 15),
        description_hash="draft_hash_001",
    )
    db_session.add(job_posting)
    await db_session.flush()

    variant = JobVariant(
        base_resume_id=base_resume.id,
        job_posting_id=job_posting.id,
        summary="Tailored summary for BigTech staff engineer role.",
        job_bullet_order={},
        status="Draft",
    )
    db_session.add(variant)
    await db_session.flush()
    await db_session.commit()
    return variant


@pytest_asyncio.fixture
async def job_variant_approved(
    db_session: AsyncSession,
    pdf_persona: SimpleNamespace,
    base_resume: BaseResume,
) -> JobVariant:
    """Create an approved job variant with snapshot fields populated."""
    from datetime import UTC, datetime

    from app.models.job_posting import JobPosting
    from app.models.job_source import JobSource

    p = pdf_persona
    source = JobSource(
        source_name="ApprovedSource",
        source_type="Extension",
        description="Test",
    )
    db_session.add(source)
    await db_session.flush()

    job_posting = JobPosting(
        source_id=source.id,
        job_title="Principal Engineer at MegaCorp",
        company_name="MegaCorp",
        description="We need a principal engineer.",
        requirements="10+ years experience",
        first_seen_date=date(2026, 1, 20),
        description_hash="approved_hash_001",
    )
    db_session.add(job_posting)
    await db_session.flush()

    variant = JobVariant(
        base_resume_id=base_resume.id,
        job_posting_id=job_posting.id,
        summary="Tailored summary for MegaCorp principal engineer role.",
        job_bullet_order={
            str(p.job1.id): [str(p.b1.id), str(p.b2.id)],
        },
        status="Approved",
        approved_at=datetime.now(UTC),
        # Snapshot fields — frozen copy of base resume selections
        snapshot_included_jobs=[str(p.job1.id), str(p.job2.id)],
        snapshot_job_bullet_selections={
            str(p.job1.id): [str(p.b1.id), str(p.b2.id)],
            str(p.job2.id): [str(p.b4.id)],
        },
        snapshot_included_education=[str(p.edu1.id)],
        snapshot_included_certifications=[str(p.cert1.id)],
        snapshot_skills_emphasis=[str(p.skill1.id), str(p.skill2.id)],
    )
    db_session.add(variant)
    await db_session.flush()
    await db_session.commit()
    return variant


# =============================================================================
# TestGatherBaseResumeContent
# =============================================================================


class TestGatherBaseResumeContent:
    """Tests for gathering resume content from BaseResume selections."""

    @pytest.mark.asyncio
    async def test_gathers_persona_contact_info(
        self,
        db_session: AsyncSession,
        base_resume: BaseResume,
    ) -> None:
        """Contact info extracted from persona."""
        content = await gather_base_resume_content(db_session, base_resume.id)

        assert content.contact.full_name == "Jane Smith"
        assert content.contact.email == "jane.smith@example.com"
        assert content.contact.phone == "555-0100"
        assert content.contact.city == "Austin"
        assert content.contact.state == "TX"

    @pytest.mark.asyncio
    async def test_includes_resume_summary(
        self,
        db_session: AsyncSession,
        base_resume: BaseResume,
    ) -> None:
        """Summary comes from the BaseResume."""
        content = await gather_base_resume_content(db_session, base_resume.id)

        assert (
            content.summary
            == "Experienced engineer with 5+ years building scalable systems."
        )

    @pytest.mark.asyncio
    async def test_filters_jobs_by_included_jobs(
        self,
        db_session: AsyncSession,
        base_resume: BaseResume,
    ) -> None:
        """Only jobs listed in included_jobs are included."""
        content = await gather_base_resume_content(db_session, base_resume.id)

        job_titles = [j.job_title for j in content.jobs]
        assert "Senior Software Engineer" in job_titles
        assert "Software Engineer" in job_titles
        assert "Intern" not in job_titles  # job3 excluded

    @pytest.mark.asyncio
    async def test_selects_bullets_per_job_bullet_selections(
        self,
        db_session: AsyncSession,
        base_resume: BaseResume,
    ) -> None:
        """Only bullets listed in job_bullet_selections are included."""
        content = await gather_base_resume_content(db_session, base_resume.id)

        job1 = next(
            j for j in content.jobs if j.job_title == "Senior Software Engineer"
        )
        assert "Led team of 5 engineers on microservice migration" in job1.bullets
        assert "Reduced API latency by 40% through caching strategy" in job1.bullets
        assert "Wrote internal documentation" not in job1.bullets  # b3_excluded

    @pytest.mark.asyncio
    async def test_orders_bullets_per_job_bullet_order(
        self,
        db_session: AsyncSession,
        base_resume: BaseResume,
    ) -> None:
        """Bullets ordered per job_bullet_order when present."""
        content = await gather_base_resume_content(db_session, base_resume.id)

        job1 = next(
            j for j in content.jobs if j.job_title == "Senior Software Engineer"
        )
        # Order was [b2, b1] — latency bullet first, then team bullet
        assert "Reduced API latency" in job1.bullets[0]
        assert "Led team" in job1.bullets[1]

    @pytest.mark.asyncio
    async def test_falls_back_to_selection_order(
        self,
        db_session: AsyncSession,
        base_resume: BaseResume,
    ) -> None:
        """When no explicit order, uses job_bullet_selections order."""
        content = await gather_base_resume_content(db_session, base_resume.id)

        # job2 has no explicit order in job_bullet_order
        job2 = next(j for j in content.jobs if j.job_title == "Software Engineer")
        assert len(job2.bullets) == 1
        assert "event-driven architecture" in job2.bullets[0]

    @pytest.mark.asyncio
    async def test_filters_education(
        self,
        db_session: AsyncSession,
        base_resume: BaseResume,
    ) -> None:
        """Only education listed in included_education is included."""
        content = await gather_base_resume_content(db_session, base_resume.id)

        assert len(content.education) == 1
        assert content.education[0].institution == "MIT"
        # edu2 (Stanford) not included

    @pytest.mark.asyncio
    async def test_filters_certifications(
        self,
        db_session: AsyncSession,
        base_resume: BaseResume,
    ) -> None:
        """Only certifications listed in included_certifications are included."""
        content = await gather_base_resume_content(db_session, base_resume.id)

        assert len(content.certifications) == 1
        assert content.certifications[0].certification_name == "AWS Solutions Architect"

    @pytest.mark.asyncio
    async def test_filters_skills(
        self,
        db_session: AsyncSession,
        base_resume: BaseResume,
    ) -> None:
        """Only skills listed in skills_emphasis are included."""
        content = await gather_base_resume_content(db_session, base_resume.id)

        skill_names = [s.skill_name for s in content.skills]
        assert "Python" in skill_names
        assert "Leadership" in skill_names
        assert "SQL" not in skill_names  # skill3 not in emphasis

    @pytest.mark.asyncio
    async def test_not_found_error(self, db_session: AsyncSession) -> None:
        """Raises NotFoundError for nonexistent base resume."""
        from app.core.errors import NotFoundError

        with pytest.raises(NotFoundError):
            await gather_base_resume_content(db_session, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_handles_empty_selections(
        self,
        db_session: AsyncSession,
        pdf_persona: SimpleNamespace,
    ) -> None:
        """Empty selections produce empty content lists."""
        resume = BaseResume(
            persona_id=pdf_persona.persona.id,
            name="Empty Resume",
            role_type="General",
            summary="A minimal resume.",
            included_jobs=[],
            job_bullet_selections={},
            job_bullet_order={},
            included_education=[],
            included_certifications=[],
            skills_emphasis=[],
            status="Active",
        )
        db_session.add(resume)
        await db_session.flush()
        await db_session.commit()

        content = await gather_base_resume_content(db_session, resume.id)

        assert content.jobs == []
        assert content.education == []
        assert content.certifications == []
        assert content.skills == []


# =============================================================================
# TestGatherVariantContent
# =============================================================================


class TestGatherVariantContent:
    """Tests for gathering resume content from JobVariant."""

    @pytest.mark.asyncio
    async def test_draft_uses_base_resume_selections(
        self,
        db_session: AsyncSession,
        job_variant_draft: JobVariant,
    ) -> None:
        """Draft variant inherits included_* from base resume."""
        content = await gather_variant_content(db_session, job_variant_draft.id)

        job_titles = [j.job_title for j in content.jobs]
        assert "Senior Software Engineer" in job_titles
        assert "Software Engineer" in job_titles

    @pytest.mark.asyncio
    async def test_approved_uses_snapshot_fields(
        self,
        db_session: AsyncSession,
        job_variant_approved: JobVariant,
    ) -> None:
        """Approved variant uses snapshot_* fields."""
        content = await gather_variant_content(db_session, job_variant_approved.id)

        job_titles = [j.job_title for j in content.jobs]
        assert "Senior Software Engineer" in job_titles
        assert "Software Engineer" in job_titles
        assert len(content.education) == 1
        assert len(content.certifications) == 1

    @pytest.mark.asyncio
    async def test_uses_variant_summary(
        self,
        db_session: AsyncSession,
        job_variant_draft: JobVariant,
    ) -> None:
        """Variant summary overrides base resume summary."""
        content = await gather_variant_content(db_session, job_variant_draft.id)

        assert content.summary == "Tailored summary for BigTech staff engineer role."

    @pytest.mark.asyncio
    async def test_uses_variant_bullet_order(
        self,
        db_session: AsyncSession,
        pdf_persona: SimpleNamespace,  # noqa: ARG002
        job_variant_approved: JobVariant,
    ) -> None:
        """Approved variant uses its own job_bullet_order."""
        content = await gather_variant_content(db_session, job_variant_approved.id)

        # Approved variant has order [b1, b2] (not reversed like base resume)
        job1 = next(
            j for j in content.jobs if j.job_title == "Senior Software Engineer"
        )
        assert "Led team" in job1.bullets[0]
        assert "Reduced API latency" in job1.bullets[1]

    @pytest.mark.asyncio
    async def test_not_found_error(self, db_session: AsyncSession) -> None:
        """Raises NotFoundError for nonexistent variant."""
        from app.core.errors import NotFoundError

        with pytest.raises(NotFoundError):
            await gather_variant_content(db_session, uuid.uuid4())


# =============================================================================
# TestRenderResumePdf
# =============================================================================


class TestRenderResumePdf:
    """Tests for the pure PDF rendering function (no DB)."""

    @staticmethod
    def _make_content(**kwargs: Any) -> ResumeContent:
        """Build a ResumeContent with defaults for any unspecified fields."""
        from app.services.pdf_generation import (
            ResumeCertificationEntry,
            ResumeContactInfo,
            ResumeEducationEntry,
            ResumeJobEntry,
            ResumeSkillEntry,
        )

        defaults: dict[str, Any] = {
            "contact": ResumeContactInfo(
                full_name="Jane Smith",
                email="jane@example.com",
                phone="555-0100",
                city="Austin",
                state="TX",
                linkedin_url=None,
                portfolio_url=None,
            ),
            "summary": "Experienced software engineer.",
            "jobs": [
                ResumeJobEntry(
                    job_title="Senior Engineer",
                    company_name="TechCorp",
                    location="Austin, TX",
                    start_date=date(2020, 1, 1),
                    end_date=None,
                    is_current=True,
                    bullets=["Led team of 5", "Reduced latency by 40%"],
                ),
            ],
            "education": [
                ResumeEducationEntry(
                    degree="B.S.",
                    institution="MIT",
                    field_of_study="Computer Science",
                    graduation_year=2018,
                ),
            ],
            "certifications": [
                ResumeCertificationEntry(
                    certification_name="AWS SA",
                    issuing_organization="Amazon",
                    date_obtained=date(2021, 3, 15),
                ),
            ],
            "skills": [
                ResumeSkillEntry(
                    skill_name="Python", skill_type="Hard", category="Programming"
                ),
                ResumeSkillEntry(
                    skill_name="Leadership", skill_type="Soft", category="Management"
                ),
            ],
        }
        defaults.update(kwargs)
        return ResumeContent(**defaults)

    def test_returns_pdf_bytes(self) -> None:
        """Output starts with PDF magic bytes."""
        content = self._make_content()
        pdf_bytes = render_resume_pdf(content)

        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:5] == b"%PDF-"

    def test_produces_non_trivial_output(self) -> None:
        """Full content produces a meaningful-sized PDF."""
        content = self._make_content()
        pdf_bytes = render_resume_pdf(content)

        # A resume with actual content should be at least 1KB
        assert len(pdf_bytes) > 1000

    def test_handles_empty_jobs(self) -> None:
        """No crash when jobs list is empty."""
        content = self._make_content(jobs=[])
        pdf_bytes = render_resume_pdf(content)

        assert pdf_bytes[:5] == b"%PDF-"

    def test_handles_no_education(self) -> None:
        """No crash when education list is empty."""
        content = self._make_content(education=[])
        pdf_bytes = render_resume_pdf(content)

        assert pdf_bytes[:5] == b"%PDF-"

    def test_handles_no_certifications(self) -> None:
        """No crash when certifications list is empty."""
        content = self._make_content(certifications=[])
        pdf_bytes = render_resume_pdf(content)

        assert pdf_bytes[:5] == b"%PDF-"

    def test_handles_no_skills(self) -> None:
        """No crash when skills list is empty."""
        content = self._make_content(skills=[])
        pdf_bytes = render_resume_pdf(content)

        assert pdf_bytes[:5] == b"%PDF-"

    def test_minimal_content(self) -> None:
        """Works with only contact info and summary."""
        content = self._make_content(
            jobs=[], education=[], certifications=[], skills=[]
        )
        pdf_bytes = render_resume_pdf(content)

        assert pdf_bytes[:5] == b"%PDF-"
        assert len(pdf_bytes) > 500

    def test_xml_special_characters_do_not_crash(self) -> None:
        """User content with XML chars renders without error."""
        from app.services.pdf_generation import (
            ResumeContactInfo,
            ResumeJobEntry,
        )

        content = self._make_content(
            contact=ResumeContactInfo(
                full_name="Jane <script>alert</script> Smith",
                email="jane&co@example.com",
                phone="555-0100",
                city="Austin",
                state="TX",
                linkedin_url=None,
                portfolio_url=None,
            ),
            summary='Summary with <b>bold</b> and "quotes" & ampersands.',
            jobs=[
                ResumeJobEntry(
                    job_title="Engineer <font size=72>BIG</font>",
                    company_name="Corp & Co",
                    location="City <br/> State",
                    start_date=date(2020, 1, 1),
                    end_date=None,
                    is_current=True,
                    bullets=["Bullet with <a href='evil'>link</a>"],
                ),
            ],
        )
        pdf_bytes = render_resume_pdf(content)

        assert pdf_bytes[:5] == b"%PDF-"
        assert len(pdf_bytes) > 500


# =============================================================================
# TestRenderBaseResumePdf
# =============================================================================


class TestRenderBaseResumePdf:
    """Integration tests: gather + render for BaseResume."""

    @pytest.mark.asyncio
    async def test_full_pipeline_returns_pdf(
        self,
        db_session: AsyncSession,
        base_resume: BaseResume,
    ) -> None:
        """Full pipeline gathers content and renders PDF."""
        pdf_bytes = await render_base_resume_pdf(db_session, base_resume.id)

        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:5] == b"%PDF-"
        assert len(pdf_bytes) > 1000

    @pytest.mark.asyncio
    async def test_not_found_error(self, db_session: AsyncSession) -> None:
        """Raises NotFoundError for nonexistent base resume."""
        from app.core.errors import NotFoundError

        with pytest.raises(NotFoundError):
            await render_base_resume_pdf(db_session, uuid.uuid4())


# =============================================================================
# TestRenderVariantPdf
# =============================================================================


class TestRenderVariantPdf:
    """Integration tests: gather + render for JobVariant."""

    @pytest.mark.asyncio
    async def test_full_pipeline_draft(
        self,
        db_session: AsyncSession,
        job_variant_draft: JobVariant,
    ) -> None:
        """Full pipeline works for draft variant."""
        pdf_bytes = await render_variant_pdf(db_session, job_variant_draft.id)

        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:5] == b"%PDF-"
        assert len(pdf_bytes) > 1000

    @pytest.mark.asyncio
    async def test_full_pipeline_approved(
        self,
        db_session: AsyncSession,
        job_variant_approved: JobVariant,
    ) -> None:
        """Full pipeline works for approved variant with snapshots."""
        pdf_bytes = await render_variant_pdf(db_session, job_variant_approved.id)

        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:5] == b"%PDF-"
        assert len(pdf_bytes) > 1000

    @pytest.mark.asyncio
    async def test_not_found_error(self, db_session: AsyncSession) -> None:
        """Raises NotFoundError for nonexistent variant."""
        from app.core.errors import NotFoundError

        with pytest.raises(NotFoundError):
            await render_variant_pdf(db_session, uuid.uuid4())
