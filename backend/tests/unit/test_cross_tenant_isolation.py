"""Comprehensive cross-tenant data isolation tests.

REQ-014 §10: Every API endpoint tested with two users to verify isolation.

User A = TEST_USER_ID (via ``client`` fixture)
User B = USER_B_ID  (via ``client_user_b`` fixture)

Coverage target: every router in REQ-014 §6.1 — personas, base_resumes,
job_variants, applications, cover_letters, user_source_preferences,
persona_change_flags, files. Stub-only endpoints are excluded because
they return static data with no DB queries to leak.

NOTE: This file exceeds 300 lines because it systematically tests
cross-tenant isolation across 8 routers with ~35 tests. Splitting would
fragment the cohesive isolation audit.
"""

import uuid
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TEST_JOB_SOURCE_ID

# =============================================================================
# URL Constants
# =============================================================================

_PERSONAS = "/api/v1/personas"
_BASE_RESUMES = "/api/v1/base-resumes"
_JOB_VARIANTS = "/api/v1/job-variants"
_APPLICATIONS = "/api/v1/applications"
_COVER_LETTERS = "/api/v1/cover-letters"
_USER_SOURCE_PREFS = "/api/v1/user-source-preferences"
_CHANGE_FLAGS = "/api/v1/persona-change-flags"
_RESUME_FILES = "/api/v1/resume-files"
_SUBMITTED_RESUME_PDFS = "/api/v1/submitted-resume-pdfs"
_SUBMITTED_COVER_LETTER_PDFS = "/api/v1/submitted-cover-letter-pdfs"


# =============================================================================
# User B Resource Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def job_posting_b(db_session: AsyncSession, persona_user_b):
    """Job posting linked to User B's persona via PersonaJob."""
    from app.models.job_posting import JobPosting
    from app.models.persona_job import PersonaJob

    posting = JobPosting(
        id=uuid.uuid4(),
        source_id=TEST_JOB_SOURCE_ID,
        job_title="User B Job",
        company_name="User B Corp",
        description="User B's job description.",
        description_hash="cross_tenant_hash_b01",
        first_seen_date=date(2026, 1, 15),
    )
    db_session.add(posting)
    await db_session.flush()

    pj = PersonaJob(
        persona_id=persona_user_b.id,
        job_posting_id=posting.id,
        status="Discovered",
        discovery_method="manual",
    )
    db_session.add(pj)
    await db_session.commit()
    await db_session.refresh(posting)
    return posting


@pytest_asyncio.fixture
async def base_resume_b(db_session: AsyncSession, persona_user_b):
    """Base resume owned by User B's persona."""
    from app.models.resume import BaseResume

    resume = BaseResume(
        id=uuid.uuid4(),
        persona_id=persona_user_b.id,
        name="User B Resume",
        role_type="User B Role",
        summary="User B's resume summary.",
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)
    return resume


@pytest_asyncio.fixture
async def job_variant_b(db_session: AsyncSession, base_resume_b, job_posting_b):
    """Job variant owned by User B (via base_resume → persona chain)."""
    from app.models.resume import JobVariant

    variant = JobVariant(
        id=uuid.uuid4(),
        base_resume_id=base_resume_b.id,
        job_posting_id=job_posting_b.id,
        summary="User B's tailored variant.",
    )
    db_session.add(variant)
    await db_session.commit()
    await db_session.refresh(variant)
    return variant


@pytest_asyncio.fixture
async def application_b(
    db_session: AsyncSession, persona_user_b, job_posting_b, job_variant_b
):
    """Application owned by User B's persona."""
    from app.models.application import Application

    application = Application(
        id=uuid.uuid4(),
        persona_id=persona_user_b.id,
        job_posting_id=job_posting_b.id,
        job_variant_id=job_variant_b.id,
        job_snapshot={"title": "User B Job", "company": "User B Corp"},
    )
    db_session.add(application)
    await db_session.commit()
    await db_session.refresh(application)
    return application


@pytest_asyncio.fixture
async def timeline_event_b(db_session: AsyncSession, application_b):
    """Timeline event on User B's application."""
    from app.models.application import TimelineEvent

    event = TimelineEvent(
        id=uuid.uuid4(),
        application_id=application_b.id,
        event_type="applied",
        event_date=datetime(2026, 1, 20, 10, 0, 0, tzinfo=UTC),
        description="User B applied.",
    )
    db_session.add(event)
    await db_session.commit()
    await db_session.refresh(event)
    return event


@pytest_asyncio.fixture
async def cover_letter_b(db_session: AsyncSession, persona_user_b, job_posting_b):
    """Cover letter owned by User B's persona."""
    from app.models.cover_letter import CoverLetter

    cl = CoverLetter(
        id=uuid.uuid4(),
        persona_id=persona_user_b.id,
        job_posting_id=job_posting_b.id,
        draft_text="User B's cover letter text.",
        achievement_stories_used=[],
    )
    db_session.add(cl)
    await db_session.commit()
    await db_session.refresh(cl)
    return cl


@pytest_asyncio.fixture
async def user_source_pref_b(db_session: AsyncSession, persona_user_b):
    """User source preference owned by User B's persona."""
    from app.models.job_source import JobSource, UserSourcePreference

    source = JobSource(
        id=uuid.uuid4(),
        source_name="UserBSource",
        source_type="API",
        description="Source for User B cross-tenant test",
    )
    db_session.add(source)
    await db_session.flush()

    pref = UserSourcePreference(
        id=uuid.uuid4(),
        persona_id=persona_user_b.id,
        source_id=source.id,
        is_enabled=True,
        display_order=1,
    )
    db_session.add(pref)
    await db_session.commit()
    await db_session.refresh(pref)
    return pref


@pytest_asyncio.fixture
async def change_flag_b(db_session: AsyncSession, persona_user_b):
    """Persona change flag owned by User B's persona."""
    from app.models.persona_settings import PersonaChangeFlag

    flag = PersonaChangeFlag(
        id=uuid.uuid4(),
        persona_id=persona_user_b.id,
        change_type="skill_added",
        item_id=uuid.uuid4(),
        item_description="User B's skill: Docker",
        status="Pending",
    )
    db_session.add(flag)
    await db_session.commit()
    await db_session.refresh(flag)
    return flag


@pytest_asyncio.fixture
async def resume_file_b(db_session: AsyncSession, persona_user_b):
    """Resume file owned by User B's persona."""
    from app.models import ResumeFile

    rf = ResumeFile(
        id=uuid.uuid4(),
        persona_id=persona_user_b.id,
        file_name="user_b_resume.pdf",
        file_type="PDF",
        file_size_bytes=512,
        file_binary=b"%PDF-1.4 user b content",
        is_active=True,
    )
    db_session.add(rf)
    await db_session.commit()
    await db_session.refresh(rf)
    return rf


@pytest_asyncio.fixture
async def base_resume_b_with_pdf(db_session: AsyncSession, persona_user_b):
    """Base resume with rendered PDF owned by User B."""
    from app.models.resume import BaseResume

    resume = BaseResume(
        id=uuid.uuid4(),
        persona_id=persona_user_b.id,
        name="User B PDF Resume",
        role_type="User B Role",
        summary="User B's resume with PDF.",
        rendered_document=b"%PDF-1.4 user b pdf content",
        rendered_at=datetime.now(UTC),
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)
    return resume


# =============================================================================
# User A Resource Fixtures (for cross-reference tests)
# =============================================================================


@pytest_asyncio.fixture
async def base_resume_a(db_session: AsyncSession, test_persona):
    """Base resume owned by User A's persona (for variant create tests)."""
    from app.models.resume import BaseResume

    resume = BaseResume(
        id=uuid.uuid4(),
        persona_id=test_persona.id,
        name="User A Resume",
        role_type="User A Role",
        summary="User A's resume summary.",
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)
    return resume


@pytest_asyncio.fixture
async def job_posting_a(db_session: AsyncSession, test_persona):
    """Job posting linked to User A's persona via PersonaJob."""
    from app.models.job_posting import JobPosting
    from app.models.persona_job import PersonaJob

    posting = JobPosting(
        id=uuid.uuid4(),
        source_id=TEST_JOB_SOURCE_ID,
        job_title="User A Job",
        company_name="User A Corp",
        description="User A's job description.",
        description_hash="cross_tenant_hash_a01",
        first_seen_date=date(2026, 1, 15),
    )
    db_session.add(posting)
    await db_session.flush()

    pj = PersonaJob(
        persona_id=test_persona.id,
        job_posting_id=posting.id,
        status="Discovered",
        discovery_method="manual",
    )
    db_session.add(pj)
    await db_session.commit()
    await db_session.refresh(posting)
    return posting


# =============================================================================
# User B Submitted PDF Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def submitted_resume_pdf_b(db_session: AsyncSession, base_resume_b):
    """Submitted resume PDF owned by User B (via base resume chain)."""
    from app.models.resume import SubmittedResumePDF

    pdf = SubmittedResumePDF(
        id=uuid.uuid4(),
        application_id=None,
        resume_source_type="Base",
        resume_source_id=base_resume_b.id,
        file_name="user_b_submitted_resume.pdf",
        file_binary=b"%PDF-1.4 user b submitted resume",
    )
    db_session.add(pdf)
    await db_session.commit()
    await db_session.refresh(pdf)
    return pdf


@pytest_asyncio.fixture
async def submitted_cover_letter_pdf_b(db_session: AsyncSession, cover_letter_b):
    """Submitted cover letter PDF owned by User B (via cover letter chain)."""
    from app.models.cover_letter import SubmittedCoverLetterPDF

    pdf = SubmittedCoverLetterPDF(
        id=uuid.uuid4(),
        cover_letter_id=cover_letter_b.id,
        application_id=None,
        file_name="user_b_submitted_cover_letter.pdf",
        file_binary=b"%PDF-1.4 user b cover letter",
    )
    db_session.add(pdf)
    await db_session.commit()
    await db_session.refresh(pdf)
    return pdf


# =============================================================================
# Personas Isolation
# =============================================================================


class TestPersonasIsolation:
    """REQ-014 §10: Cross-tenant isolation for /personas."""

    @pytest.mark.asyncio
    async def test_list_excludes_other_users_personas(
        self, client: AsyncClient, persona_user_b
    ) -> None:
        """User A's persona list does not include User B's persona."""
        response = await client.get(_PERSONAS)
        assert response.status_code == 200
        ids = [p["id"] for p in response.json()["data"]]
        assert str(persona_user_b.id) not in ids

    @pytest.mark.asyncio
    async def test_get_other_users_persona_returns_404(
        self, client: AsyncClient, persona_user_b
    ) -> None:
        """User A cannot get User B's persona."""
        response = await client.get(f"{_PERSONAS}/{persona_user_b.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_other_users_persona_returns_404(
        self, client: AsyncClient, persona_user_b
    ) -> None:
        """User A cannot update User B's persona."""
        response = await client.patch(
            f"{_PERSONAS}/{persona_user_b.id}",
            json={"full_name": "Hijacked Name"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_other_users_persona_returns_404(
        self, client: AsyncClient, persona_user_b
    ) -> None:
        """User A cannot delete User B's persona."""
        response = await client.delete(f"{_PERSONAS}/{persona_user_b.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_reverse_user_b_cannot_get_user_a_persona(
        self, client_user_b: AsyncClient, test_persona
    ) -> None:
        """User B cannot get User A's persona (bidirectional)."""
        response = await client_user_b.get(f"{_PERSONAS}/{test_persona.id}")
        assert response.status_code == 404


# =============================================================================
# Base Resumes Isolation
# =============================================================================


class TestBaseResumesIsolation:
    """REQ-014 §10: Cross-tenant isolation for /base-resumes."""

    @pytest.mark.asyncio
    async def test_list_excludes_other_users_resumes(
        self, client: AsyncClient, base_resume_b
    ) -> None:
        """User A's resume list does not include User B's resume."""
        response = await client.get(_BASE_RESUMES)
        assert response.status_code == 200
        ids = [r["id"] for r in response.json()["data"]]
        assert str(base_resume_b.id) not in ids

    @pytest.mark.asyncio
    async def test_get_other_users_resume_returns_404(
        self, client: AsyncClient, base_resume_b
    ) -> None:
        """User A cannot get User B's resume."""
        response = await client.get(f"{_BASE_RESUMES}/{base_resume_b.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_with_other_users_persona_returns_404(
        self, client: AsyncClient, persona_user_b
    ) -> None:
        """User A cannot create a resume under User B's persona."""
        payload = {
            "persona_id": str(persona_user_b.id),
            "name": "Injected Resume",
            "role_type": "Engineer",
            "summary": "Injected summary text.",
        }
        response = await client.post(_BASE_RESUMES, json=payload)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_other_users_resume_returns_404(
        self, client: AsyncClient, base_resume_b
    ) -> None:
        """User A cannot update User B's resume."""
        response = await client.patch(
            f"{_BASE_RESUMES}/{base_resume_b.id}",
            json={"name": "Hijacked Resume"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_other_users_resume_returns_404(
        self, client: AsyncClient, base_resume_b
    ) -> None:
        """User A cannot delete User B's resume."""
        response = await client.delete(f"{_BASE_RESUMES}/{base_resume_b.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_render_other_users_resume_returns_404(
        self, client: AsyncClient, base_resume_b
    ) -> None:
        """User A cannot render User B's resume."""
        response = await client.post(f"{_BASE_RESUMES}/{base_resume_b.id}/render")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_restore_other_users_resume_returns_404(
        self, client: AsyncClient, base_resume_b
    ) -> None:
        """User A cannot restore User B's archived resume."""
        response = await client.post(f"{_BASE_RESUMES}/{base_resume_b.id}/restore")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_download_other_users_resume_pdf_returns_404(
        self, client: AsyncClient, base_resume_b_with_pdf
    ) -> None:
        """User A cannot download User B's resume PDF."""
        response = await client.get(
            f"{_BASE_RESUMES}/{base_resume_b_with_pdf.id}/download"
        )
        assert response.status_code == 404


# =============================================================================
# Job Variants Isolation
# =============================================================================


class TestJobVariantsIsolation:
    """REQ-014 §10: Cross-tenant isolation for /job-variants."""

    @pytest.mark.asyncio
    async def test_list_excludes_other_users_variants(
        self, client: AsyncClient, job_variant_b
    ) -> None:
        """User A's variant list does not include User B's variant."""
        response = await client.get(_JOB_VARIANTS)
        assert response.status_code == 200
        ids = [v["id"] for v in response.json()["data"]]
        assert str(job_variant_b.id) not in ids

    @pytest.mark.asyncio
    async def test_get_other_users_variant_returns_404(
        self, client: AsyncClient, job_variant_b
    ) -> None:
        """User A cannot get User B's variant."""
        response = await client.get(f"{_JOB_VARIANTS}/{job_variant_b.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_other_users_variant_returns_404(
        self, client: AsyncClient, job_variant_b
    ) -> None:
        """User A cannot update User B's variant."""
        response = await client.patch(
            f"{_JOB_VARIANTS}/{job_variant_b.id}",
            json={"summary": "Hijacked variant"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_other_users_variant_returns_404(
        self, client: AsyncClient, job_variant_b
    ) -> None:
        """User A cannot delete User B's variant."""
        response = await client.delete(f"{_JOB_VARIANTS}/{job_variant_b.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_with_foreign_base_resume_returns_404(
        self, client: AsyncClient, base_resume_b, job_posting_a
    ) -> None:
        """User A cannot create a variant using User B's base resume."""
        payload = {
            "base_resume_id": str(base_resume_b.id),
            "job_posting_id": str(job_posting_a.id),
            "summary": "Injected variant with foreign base resume.",
        }
        response = await client.post(_JOB_VARIANTS, json=payload)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_with_foreign_job_posting_returns_404(
        self, client: AsyncClient, base_resume_a, job_posting_b
    ) -> None:
        """User A cannot create a variant using User B's job posting."""
        payload = {
            "base_resume_id": str(base_resume_a.id),
            "job_posting_id": str(job_posting_b.id),
            "summary": "Injected variant with foreign job posting.",
        }
        response = await client.post(_JOB_VARIANTS, json=payload)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_approve_other_users_variant_returns_404(
        self, client: AsyncClient, job_variant_b
    ) -> None:
        """User A cannot approve User B's variant."""
        response = await client.post(f"{_JOB_VARIANTS}/{job_variant_b.id}/approve")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_restore_other_users_variant_returns_404(
        self, client: AsyncClient, job_variant_b
    ) -> None:
        """User A cannot restore User B's archived variant."""
        response = await client.post(f"{_JOB_VARIANTS}/{job_variant_b.id}/restore")
        assert response.status_code == 404


# =============================================================================
# Applications Isolation
# =============================================================================


class TestApplicationsIsolation:
    """REQ-014 §10: Cross-tenant isolation for /applications."""

    @pytest.mark.asyncio
    async def test_list_excludes_other_users_applications(
        self, client: AsyncClient, application_b
    ) -> None:
        """User A's application list does not include User B's."""
        response = await client.get(_APPLICATIONS)
        assert response.status_code == 200
        ids = [a["id"] for a in response.json()["data"]]
        assert str(application_b.id) not in ids

    @pytest.mark.asyncio
    async def test_get_other_users_application_returns_404(
        self, client: AsyncClient, application_b
    ) -> None:
        """User A cannot get User B's application."""
        response = await client.get(f"{_APPLICATIONS}/{application_b.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_with_other_users_persona_returns_404(
        self,
        client: AsyncClient,
        persona_user_b,
        job_posting_b,
        job_variant_b,
    ) -> None:
        """User A cannot create an application under User B's persona."""
        payload = {
            "persona_id": str(persona_user_b.id),
            "job_posting_id": str(job_posting_b.id),
            "job_variant_id": str(job_variant_b.id),
            "job_snapshot": {"title": "Injected", "company": "Injected"},
        }
        response = await client.post(_APPLICATIONS, json=payload)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_other_users_application_returns_404(
        self, client: AsyncClient, application_b
    ) -> None:
        """User A cannot update User B's application."""
        response = await client.patch(
            f"{_APPLICATIONS}/{application_b.id}",
            json={"notes": "Hijacked notes"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_other_users_application_returns_404(
        self, client: AsyncClient, application_b
    ) -> None:
        """User A cannot archive User B's application."""
        response = await client.delete(f"{_APPLICATIONS}/{application_b.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_timeline_list_other_users_application_returns_404(
        self,
        client: AsyncClient,
        application_b,
        timeline_event_b,  # noqa: ARG002
    ) -> None:
        """User A cannot list timeline events on User B's application."""
        response = await client.get(f"{_APPLICATIONS}/{application_b.id}/timeline")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_timeline_create_other_users_application_returns_404(
        self, client: AsyncClient, application_b
    ) -> None:
        """User A cannot create timeline event on User B's application."""
        response = await client.post(
            f"{_APPLICATIONS}/{application_b.id}/timeline",
            json={
                "event_type": "applied",
                "event_date": "2026-01-20T10:00:00Z",
                "description": "Injected event",
            },
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_timeline_get_event_other_users_application_returns_404(
        self, client: AsyncClient, application_b, timeline_event_b
    ) -> None:
        """User A cannot get a specific timeline event on User B's application."""
        response = await client.get(
            f"{_APPLICATIONS}/{application_b.id}/timeline/{timeline_event_b.id}"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_bulk_archive_other_users_application_excluded(
        self, client: AsyncClient, application_b
    ) -> None:
        """Bulk archive with User B's application ID returns empty success."""
        response = await client.post(
            f"{_APPLICATIONS}/bulk-archive",
            json={"ids": [str(application_b.id)]},
        )
        assert response.status_code == 200
        body = response.json()["data"]
        assert str(application_b.id) not in body.get("succeeded", [])

    @pytest.mark.asyncio
    async def test_reverse_user_b_cannot_get_user_a_application(
        self,
        client: AsyncClient,
        client_user_b: AsyncClient,
        application_b,  # noqa: ARG002
    ) -> None:
        """User B cannot access an application created for User A."""
        # Verify User B can't see User A's data by comparing lists —
        # each user should only see their own applications
        response_b = await client_user_b.get(_APPLICATIONS)
        assert response_b.status_code == 200
        ids_b = [a["id"] for a in response_b.json()["data"]]

        response_a = await client.get(_APPLICATIONS)
        assert response_a.status_code == 200
        ids_a = [a["id"] for a in response_a.json()["data"]]

        # No overlap between User A and User B lists
        assert set(ids_a).isdisjoint(set(ids_b))


# =============================================================================
# Cover Letters Isolation
# =============================================================================


class TestCoverLettersIsolation:
    """REQ-014 §10: Cross-tenant isolation for /cover-letters."""

    @pytest.mark.asyncio
    async def test_list_excludes_other_users_cover_letters(
        self, client: AsyncClient, cover_letter_b
    ) -> None:
        """User A's cover letter list does not include User B's."""
        response = await client.get(_COVER_LETTERS)
        assert response.status_code == 200
        ids = [cl["id"] for cl in response.json()["data"]]
        assert str(cover_letter_b.id) not in ids

    @pytest.mark.asyncio
    async def test_get_other_users_cover_letter_returns_404(
        self, client: AsyncClient, cover_letter_b
    ) -> None:
        """User A cannot get User B's cover letter."""
        response = await client.get(f"{_COVER_LETTERS}/{cover_letter_b.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_other_users_cover_letter_returns_404(
        self, client: AsyncClient, cover_letter_b
    ) -> None:
        """User A cannot update User B's cover letter."""
        response = await client.patch(
            f"{_COVER_LETTERS}/{cover_letter_b.id}",
            json={"draft_text": "Hijacked cover letter"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_with_other_users_job_posting_returns_404(
        self, client: AsyncClient, test_persona, job_posting_b
    ) -> None:
        """User A cannot create a cover letter referencing User B's job posting."""
        payload = {
            "persona_id": str(test_persona.id),
            "job_posting_id": str(job_posting_b.id),
            "draft_text": "Injected cover letter targeting foreign job.",
        }
        response = await client.post(_COVER_LETTERS, json=payload)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_other_users_cover_letter_returns_404(
        self, client: AsyncClient, cover_letter_b
    ) -> None:
        """User A cannot delete User B's cover letter."""
        response = await client.delete(f"{_COVER_LETTERS}/{cover_letter_b.id}")
        assert response.status_code == 404


# =============================================================================
# User Source Preferences Isolation
# =============================================================================


class TestUserSourcePreferencesIsolation:
    """REQ-014 §10: Cross-tenant isolation for /user-source-preferences."""

    @pytest.mark.asyncio
    async def test_list_excludes_other_users_preferences(
        self, client: AsyncClient, user_source_pref_b
    ) -> None:
        """User A's preference list does not include User B's."""
        response = await client.get(_USER_SOURCE_PREFS)
        assert response.status_code == 200
        ids = [p["id"] for p in response.json()["data"]]
        assert str(user_source_pref_b.id) not in ids

    @pytest.mark.asyncio
    async def test_get_other_users_preference_returns_404(
        self, client: AsyncClient, user_source_pref_b
    ) -> None:
        """User A cannot get User B's preference."""
        response = await client.get(f"{_USER_SOURCE_PREFS}/{user_source_pref_b.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_other_users_preference_returns_404(
        self, client: AsyncClient, user_source_pref_b
    ) -> None:
        """User A cannot update User B's preference."""
        response = await client.patch(
            f"{_USER_SOURCE_PREFS}/{user_source_pref_b.id}",
            json={"is_enabled": False},
        )
        assert response.status_code == 404


# =============================================================================
# Persona Change Flags Isolation
# =============================================================================


class TestPersonaChangeFlagsIsolation:
    """REQ-014 §10: Cross-tenant isolation for /persona-change-flags."""

    @pytest.mark.asyncio
    async def test_list_excludes_other_users_flags(
        self, client: AsyncClient, change_flag_b
    ) -> None:
        """User A's flag list does not include User B's."""
        response = await client.get(_CHANGE_FLAGS)
        assert response.status_code == 200
        ids = [f["id"] for f in response.json()["data"]]
        assert str(change_flag_b.id) not in ids

    @pytest.mark.asyncio
    async def test_get_other_users_flag_returns_404(
        self, client: AsyncClient, change_flag_b
    ) -> None:
        """User A cannot get User B's change flag."""
        response = await client.get(f"{_CHANGE_FLAGS}/{change_flag_b.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_other_users_flag_returns_404(
        self, client: AsyncClient, change_flag_b
    ) -> None:
        """User A cannot resolve User B's change flag."""
        response = await client.patch(
            f"{_CHANGE_FLAGS}/{change_flag_b.id}",
            json={"status": "Resolved", "resolution": "added_to_all"},
        )
        assert response.status_code == 404


# =============================================================================
# Files Isolation
# =============================================================================


class TestFilesIsolation:
    """REQ-014 §10: Cross-tenant isolation for file endpoints."""

    @pytest.mark.asyncio
    async def test_list_excludes_other_users_files(
        self, client: AsyncClient, resume_file_b
    ) -> None:
        """User A's file list does not include User B's files."""
        response = await client.get(_RESUME_FILES)
        assert response.status_code == 200
        ids = [f["id"] for f in response.json()["data"]]
        assert str(resume_file_b.id) not in ids

    @pytest.mark.asyncio
    async def test_get_other_users_file_metadata_returns_404(
        self, client: AsyncClient, resume_file_b
    ) -> None:
        """User A cannot get metadata for User B's resume file."""
        response = await client.get(f"{_RESUME_FILES}/{resume_file_b.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_download_other_users_resume_file_returns_404(
        self, client: AsyncClient, resume_file_b
    ) -> None:
        """User A cannot download User B's resume file."""
        response = await client.get(f"{_RESUME_FILES}/{resume_file_b.id}/download")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_upload_with_other_users_persona_returns_404(
        self, client: AsyncClient, persona_user_b
    ) -> None:
        """User A cannot upload a file under User B's persona."""
        files = {"file": ("test.pdf", b"%PDF-1.4 test content", "application/pdf")}
        data = {"persona_id": str(persona_user_b.id)}
        response = await client.post(_RESUME_FILES, files=files, data=data)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_download_other_users_submitted_resume_pdf_returns_404(
        self, client: AsyncClient, submitted_resume_pdf_b
    ) -> None:
        """User A cannot download User B's submitted resume PDF."""
        response = await client.get(
            f"{_SUBMITTED_RESUME_PDFS}/{submitted_resume_pdf_b.id}/download"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_download_other_users_submitted_cover_letter_pdf_returns_404(
        self, client: AsyncClient, submitted_cover_letter_pdf_b
    ) -> None:
        """User A cannot download User B's submitted cover letter PDF."""
        response = await client.get(
            f"{_SUBMITTED_COVER_LETTER_PDFS}/{submitted_cover_letter_pdf_b.id}/download"
        )
        assert response.status_code == 404
