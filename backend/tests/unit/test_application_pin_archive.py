"""Tests for Application is_pinned and archived_at columns.

REQ-012 Appendix A.1: Applications support pinning and archiving.
- is_pinned: Boolean, default False, excludes from auto-archive.
- archived_at: DateTime, nullable, via SoftDeleteMixin.

Tests verify:
- New applications have is_pinned=False by default
- is_pinned can be set to True
- SoftDeleteMixin provides archived_at and is_archived property
- Pinned applications survive auto-archive queries
"""

import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.job_posting import JobPosting
from app.models.resume import BaseResume, JobVariant
from tests.conftest import TEST_PERSONA_ID

_JOB_SOURCE_ID = uuid.UUID("20000000-0000-0000-0000-000000000002")
_JOB_POSTING_ID = uuid.UUID("20000000-0000-0000-0000-000000000003")
_BASE_RESUME_ID = uuid.UUID("20000000-0000-0000-0000-000000000004")
_JOB_VARIANT_ID = uuid.UUID("20000000-0000-0000-0000-000000000005")

_JOB_SNAPSHOT = {"title": "Engineer", "company_name": "TestCorp"}


@pytest_asyncio.fixture
async def pin_archive_scenario(
    db_session: AsyncSession,
    test_user,  # noqa: ARG001
    test_persona,  # noqa: ARG001
) -> SimpleNamespace:
    """Create entity chain for Application tests.

    Reuses test_user and test_persona from conftest. Adds
    BaseResume -> JobSource -> JobPosting -> JobVariant.
    """
    from app.models.job_source import JobSource

    base_resume = BaseResume(
        id=_BASE_RESUME_ID,
        persona_id=TEST_PERSONA_ID,
        name="Test Resume",
        role_type="Engineer",
        summary="Summary",
        is_primary=True,
        included_jobs=[],
        included_education=[],
        included_certifications=[],
        skills_emphasis=[],
        job_bullet_selections={},
        job_bullet_order={},
    )
    db_session.add(base_resume)
    await db_session.flush()

    source = JobSource(
        id=_JOB_SOURCE_ID,
        source_name="Extension",
        source_type="Extension",
        description="Test source",
    )
    db_session.add(source)
    await db_session.flush()

    job_posting = JobPosting(
        id=_JOB_POSTING_ID,
        source_id=_JOB_SOURCE_ID,
        job_title="Engineer",
        company_name="TestCorp",
        description="Description",
        first_seen_date=date(2026, 1, 1),
        description_hash="hash123",
    )
    db_session.add(job_posting)
    await db_session.flush()

    job_variant = JobVariant(
        id=_JOB_VARIANT_ID,
        base_resume_id=_BASE_RESUME_ID,
        job_posting_id=_JOB_POSTING_ID,
        summary="Variant summary",
        status="Approved",
        approved_at=datetime.now(UTC),
        snapshot_included_jobs=[],
        snapshot_included_education=[],
        snapshot_included_certifications=[],
        snapshot_skills_emphasis=[],
        snapshot_job_bullet_selections={},
    )
    db_session.add(job_variant)
    await db_session.commit()

    return SimpleNamespace(
        persona_id=TEST_PERSONA_ID,
        job_posting_id=_JOB_POSTING_ID,
        job_variant_id=_JOB_VARIANT_ID,
    )


def _make_application(
    scenario: SimpleNamespace,
    *,
    is_pinned: bool = False,
) -> Application:
    """Create an Application instance for testing."""
    return Application(
        persona_id=scenario.persona_id,
        job_posting_id=scenario.job_posting_id,
        job_variant_id=scenario.job_variant_id,
        job_snapshot=_JOB_SNAPSHOT,
        status="Applied",
        is_pinned=is_pinned,
    )


class TestApplicationIsPinned:
    """is_pinned column behavior on Application."""

    @pytest.mark.asyncio
    async def test_default_is_pinned_false(
        self,
        db_session: AsyncSession,
        pin_archive_scenario: SimpleNamespace,
    ) -> None:
        """New applications have is_pinned=False by default."""
        app = Application(
            persona_id=pin_archive_scenario.persona_id,
            job_posting_id=pin_archive_scenario.job_posting_id,
            job_variant_id=pin_archive_scenario.job_variant_id,
            job_snapshot=_JOB_SNAPSHOT,
            status="Applied",
        )
        db_session.add(app)
        await db_session.commit()
        await db_session.refresh(app)

        assert app.is_pinned is False

    @pytest.mark.asyncio
    async def test_set_is_pinned_true(
        self,
        db_session: AsyncSession,
        pin_archive_scenario: SimpleNamespace,
    ) -> None:
        """is_pinned can be set to True."""
        app = _make_application(pin_archive_scenario, is_pinned=True)
        db_session.add(app)
        await db_session.commit()
        await db_session.refresh(app)

        assert app.is_pinned is True

    @pytest.mark.asyncio
    async def test_toggle_pin(
        self,
        db_session: AsyncSession,
        pin_archive_scenario: SimpleNamespace,
    ) -> None:
        """is_pinned can be toggled from False to True and back."""
        app = _make_application(pin_archive_scenario)
        db_session.add(app)
        await db_session.commit()

        assert app.is_pinned is False

        app.is_pinned = True
        await db_session.commit()
        await db_session.refresh(app)
        assert app.is_pinned is True

        app.is_pinned = False
        await db_session.commit()
        await db_session.refresh(app)
        assert app.is_pinned is False


class TestApplicationArchivedAt:
    """archived_at column behavior on Application via SoftDeleteMixin."""

    @pytest.mark.asyncio
    async def test_default_archived_at_none(
        self,
        db_session: AsyncSession,
        pin_archive_scenario: SimpleNamespace,
    ) -> None:
        """New applications have archived_at=None."""
        app = _make_application(pin_archive_scenario)
        db_session.add(app)
        await db_session.commit()
        await db_session.refresh(app)

        assert app.archived_at is None

    @pytest.mark.asyncio
    async def test_is_archived_property_false_by_default(
        self,
        db_session: AsyncSession,
        pin_archive_scenario: SimpleNamespace,
    ) -> None:
        """is_archived property returns False for new applications."""
        app = _make_application(pin_archive_scenario)
        db_session.add(app)
        await db_session.commit()

        assert app.is_archived is False

    @pytest.mark.asyncio
    async def test_archive_sets_timestamp(
        self,
        db_session: AsyncSession,
        pin_archive_scenario: SimpleNamespace,
    ) -> None:
        """Setting archived_at to a timestamp archives the application."""
        app = _make_application(pin_archive_scenario)
        db_session.add(app)
        await db_session.commit()

        now = datetime.now(UTC)
        app.archived_at = now
        await db_session.commit()
        await db_session.refresh(app)

        assert app.archived_at is not None
        assert app.is_archived is True

    @pytest.mark.asyncio
    async def test_restore_clears_timestamp(
        self,
        db_session: AsyncSession,
        pin_archive_scenario: SimpleNamespace,
    ) -> None:
        """Setting archived_at back to None restores the application."""
        app = _make_application(pin_archive_scenario)
        db_session.add(app)
        await db_session.commit()

        app.archived_at = datetime.now(UTC)
        await db_session.commit()
        assert app.is_archived is True

        app.archived_at = None
        await db_session.commit()
        await db_session.refresh(app)
        assert app.is_archived is False

    @pytest.mark.asyncio
    async def test_filter_excludes_archived(
        self,
        db_session: AsyncSession,
        pin_archive_scenario: SimpleNamespace,
    ) -> None:
        """Query filtering by archived_at IS NULL excludes archived records."""
        app = _make_application(pin_archive_scenario)
        app.archived_at = datetime.now(UTC)
        db_session.add(app)
        await db_session.commit()

        stmt = select(Application).where(Application.archived_at.is_(None))
        result = await db_session.execute(stmt)
        active_apps = result.scalars().all()

        assert len(active_apps) == 0


class TestPinnedArchiveInteraction:
    """Interaction between is_pinned and archived_at."""

    @pytest.mark.asyncio
    async def test_pinned_apps_queryable_separately(
        self,
        db_session: AsyncSession,
        pin_archive_scenario: SimpleNamespace,
    ) -> None:
        """Pinned active apps can be queried with is_pinned=True filter."""
        app = _make_application(pin_archive_scenario, is_pinned=True)
        db_session.add(app)
        await db_session.commit()

        stmt = select(Application).where(
            Application.is_pinned.is_(True),
            Application.archived_at.is_(None),
        )
        result = await db_session.execute(stmt)
        pinned = result.scalars().all()

        assert len(pinned) == 1
        assert pinned[0].is_pinned is True

    @pytest.mark.asyncio
    async def test_pinned_and_archived_both_set(
        self,
        db_session: AsyncSession,
        pin_archive_scenario: SimpleNamespace,
    ) -> None:
        """An application can be both pinned and archived simultaneously."""
        app = _make_application(pin_archive_scenario, is_pinned=True)
        app.archived_at = datetime.now(UTC)
        db_session.add(app)
        await db_session.commit()
        await db_session.refresh(app)

        assert app.is_pinned is True
        assert app.is_archived is True
