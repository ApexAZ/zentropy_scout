"""Tests for global deduplication service.

REQ-015 §6: Global deduplication pipeline.
4-step dedup: (1) source_id + external_id → UPDATE, (2) description_hash → ADD to also_found_on,
(3) company + title + similarity → LINK as repost, (4) no match → CREATE.
After dedup: create persona_jobs link. Race condition: ON CONFLICT recovery.
"""

import hashlib
import uuid
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_posting import JobPosting
from app.models.job_source import JobSource
from app.models.persona import Persona
from app.models.user import User
from app.services.global_dedup_service import deduplicate_and_save

_TODAY = date.today()
_DESC_A = "Build great software at Acme Corp using Python and FastAPI"
_DESC_B = "Analyze data trends and build ML pipelines at DataCo"
_HASH_A = hashlib.sha256(_DESC_A.encode()).hexdigest()
_HASH_B = hashlib.sha256(_DESC_B.encode()).hexdigest()
_EXT_ID_LI = "LI-12345"
_EXT_ID_IND = "IND-99999"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def source_linkedin(db_session: AsyncSession) -> JobSource:
    """Create LinkedIn job source."""
    s = JobSource(
        source_name="LinkedIn", source_type="Extension", description="LinkedIn"
    )
    db_session.add(s)
    await db_session.flush()
    await db_session.refresh(s)
    return s


@pytest.fixture
async def source_indeed(db_session: AsyncSession) -> JobSource:
    """Create Indeed job source."""
    s = JobSource(source_name="Indeed", source_type="Extension", description="Indeed")
    db_session.add(s)
    await db_session.flush()
    await db_session.refresh(s)
    return s


@pytest.fixture
async def user_a(db_session: AsyncSession) -> User:
    """Create User A."""
    u = User(email="dedup_a@test.com")
    db_session.add(u)
    await db_session.flush()
    await db_session.refresh(u)
    return u


@pytest.fixture
async def user_b(db_session: AsyncSession) -> User:
    """Create User B (cross-user tests)."""
    u = User(email="dedup_b@test.com")
    db_session.add(u)
    await db_session.flush()
    await db_session.refresh(u)
    return u


@pytest.fixture
async def persona_a(db_session: AsyncSession, user_a: User) -> Persona:
    """Create Persona for User A."""
    p = Persona(
        user_id=user_a.id,
        full_name="User A",
        email="pa@test.com",
        phone="555-0001",
        home_city="City A",
        home_state="State A",
        home_country="USA",
    )
    db_session.add(p)
    await db_session.flush()
    await db_session.refresh(p)
    return p


@pytest.fixture
async def persona_b(db_session: AsyncSession, user_b: User) -> Persona:
    """Create Persona for User B."""
    p = Persona(
        user_id=user_b.id,
        full_name="User B",
        email="pb@test.com",
        phone="555-0002",
        home_city="City B",
        home_state="State B",
        home_country="USA",
    )
    db_session.add(p)
    await db_session.flush()
    await db_session.refresh(p)
    return p


@pytest.fixture
async def existing_job(
    db_session: AsyncSession, source_linkedin: JobSource
) -> JobPosting:
    """Create an existing job with external_id for step 1 tests."""
    jp = JobPosting(
        source_id=source_linkedin.id,
        external_id=_EXT_ID_LI,
        job_title="Software Engineer",
        company_name="Acme Corp",
        description=_DESC_A,
        description_hash=_HASH_A,
        first_seen_date=_TODAY,
    )
    db_session.add(jp)
    await db_session.flush()
    await db_session.refresh(jp)
    return jp


def _make_job_data(
    source_id: uuid.UUID,
    *,
    external_id: str | None = None,
    job_title: str = "Software Engineer",
    company_name: str = "Acme Corp",
    description: str = _DESC_A,
    description_hash: str = _HASH_A,
    **extra: str | int | None,
) -> dict:
    """Build a job_data dict for deduplicate_and_save()."""
    data: dict = {
        "source_id": source_id,
        "job_title": job_title,
        "company_name": company_name,
        "description": description,
        "description_hash": description_hash,
        "first_seen_date": _TODAY,
    }
    if external_id is not None:
        data["external_id"] = external_id
    data.update(extra)
    return data


# ---------------------------------------------------------------------------
# Step 1: source_id + external_id match → UPDATE existing
# ---------------------------------------------------------------------------


class TestStep1SourceMatch:
    """Step 1: Same source + external_id updates the existing job."""

    async def test_updates_existing_on_source_match(
        self,
        db_session: AsyncSession,
        existing_job: JobPosting,
        source_linkedin: JobSource,
        persona_a: Persona,
        user_a: User,
    ) -> None:
        """Same source_id + external_id returns update_existing action."""
        job_data = _make_job_data(
            source_linkedin.id,
            external_id=_EXT_ID_LI,
            job_title="Senior Software Engineer",  # updated title
        )
        outcome = await deduplicate_and_save(
            db_session,
            job_data=job_data,
            persona_id=persona_a.id,
            user_id=user_a.id,
        )
        assert outcome.action == "update_existing"
        assert outcome.job_posting.id == existing_job.id
        assert outcome.confidence == "High"
        assert outcome.matched_job_id == existing_job.id

    async def test_updates_source_fields(
        self,
        db_session: AsyncSession,
        existing_job: JobPosting,  # noqa: ARG002
        source_linkedin: JobSource,
        persona_a: Persona,
        user_a: User,
    ) -> None:
        """Source-provided fields are updated on the existing job."""
        job_data = _make_job_data(
            source_linkedin.id,
            external_id=_EXT_ID_LI,
            job_title="Senior Software Engineer",
            location="Remote",
        )
        outcome = await deduplicate_and_save(
            db_session,
            job_data=job_data,
            persona_id=persona_a.id,
            user_id=user_a.id,
        )
        await db_session.refresh(outcome.job_posting)
        assert outcome.job_posting.job_title == "Senior Software Engineer"
        assert outcome.job_posting.location == "Remote"

    async def test_sets_last_verified_at(
        self,
        db_session: AsyncSession,
        existing_job: JobPosting,
        source_linkedin: JobSource,
        persona_a: Persona,
        user_a: User,
    ) -> None:
        """last_verified_at is set on source match update."""
        assert existing_job.last_verified_at is None
        job_data = _make_job_data(source_linkedin.id, external_id=_EXT_ID_LI)
        outcome = await deduplicate_and_save(
            db_session,
            job_data=job_data,
            persona_id=persona_a.id,
            user_id=user_a.id,
        )
        await db_session.refresh(outcome.job_posting)
        assert outcome.job_posting.last_verified_at is not None

    async def test_creates_persona_jobs_link(
        self,
        db_session: AsyncSession,
        existing_job: JobPosting,  # noqa: ARG002
        source_linkedin: JobSource,
        persona_a: Persona,
        user_a: User,
    ) -> None:
        """persona_jobs link is created after step 1."""
        job_data = _make_job_data(source_linkedin.id, external_id=_EXT_ID_LI)
        outcome = await deduplicate_and_save(
            db_session,
            job_data=job_data,
            persona_id=persona_a.id,
            user_id=user_a.id,
        )
        assert outcome.persona_job is not None
        assert outcome.persona_job.persona_id == persona_a.id
        assert outcome.persona_job.discovery_method == "scouter"


# ---------------------------------------------------------------------------
# Step 2: description_hash match → ADD to also_found_on
# ---------------------------------------------------------------------------


class TestStep2HashMatch:
    """Step 2: Same description_hash adds to also_found_on."""

    async def test_adds_to_also_found_on(
        self,
        db_session: AsyncSession,
        existing_job: JobPosting,
        source_indeed: JobSource,
        persona_a: Persona,
        user_a: User,
    ) -> None:
        """Same hash, different source adds to also_found_on."""
        job_data = _make_job_data(
            source_indeed.id,
            external_id=_EXT_ID_IND,
            source_url="https://indeed.com/j/99999",
        )
        outcome = await deduplicate_and_save(
            db_session,
            job_data=job_data,
            persona_id=persona_a.id,
            user_id=user_a.id,
        )
        assert outcome.action == "add_to_also_found_on"
        assert outcome.job_posting.id == existing_job.id
        assert outcome.confidence == "High"

        # Verify also_found_on updated
        await db_session.refresh(outcome.job_posting)
        sources = outcome.job_posting.also_found_on.get("sources", [])
        assert len(sources) == 1
        assert sources[0]["source_id"] == str(source_indeed.id)

    async def test_deduplicates_source_in_also_found_on(
        self,
        db_session: AsyncSession,
        existing_job: JobPosting,  # noqa: ARG002
        source_indeed: JobSource,
        persona_a: Persona,
        user_a: User,
    ) -> None:
        """Same source_id is not added twice to also_found_on."""
        job_data = _make_job_data(source_indeed.id, external_id=_EXT_ID_IND)

        # First call
        await deduplicate_and_save(
            db_session,
            job_data=job_data,
            persona_id=persona_a.id,
            user_id=user_a.id,
        )
        # Second call with same source
        outcome = await deduplicate_and_save(
            db_session,
            job_data=job_data,
            persona_id=persona_a.id,
            user_id=user_a.id,
        )
        await db_session.refresh(outcome.job_posting)
        sources = outcome.job_posting.also_found_on.get("sources", [])
        assert len(sources) == 1  # not 2

    async def test_creates_persona_jobs_link(
        self,
        db_session: AsyncSession,
        existing_job: JobPosting,  # noqa: ARG002
        source_indeed: JobSource,
        persona_a: Persona,
        user_a: User,
    ) -> None:
        """persona_jobs link is created after step 2."""
        job_data = _make_job_data(source_indeed.id)
        outcome = await deduplicate_and_save(
            db_session,
            job_data=job_data,
            persona_id=persona_a.id,
            user_id=user_a.id,
        )
        assert outcome.persona_job.persona_id == persona_a.id


# ---------------------------------------------------------------------------
# Step 3: company + title + description similarity → LINK as repost
# ---------------------------------------------------------------------------


class TestStep3SimilarityMatch:
    """Step 3: Similar job creates a linked repost."""

    async def test_creates_repost_on_high_similarity(
        self,
        db_session: AsyncSession,
        existing_job: JobPosting,
        source_indeed: JobSource,
        persona_a: Persona,
        user_a: User,
    ) -> None:
        """Same company + similar title + >85% similarity creates repost."""
        # One-word change: "FastAPI" → "Django" gives ~90% similarity
        similar_desc = _DESC_A.replace("FastAPI", "Django")
        similar_hash = hashlib.sha256(similar_desc.encode()).hexdigest()

        job_data = _make_job_data(
            source_indeed.id,
            external_id="IND-NEW",
            job_title="Software Engineer",
            description=similar_desc,
            description_hash=similar_hash,
        )
        outcome = await deduplicate_and_save(
            db_session,
            job_data=job_data,
            persona_id=persona_a.id,
            user_id=user_a.id,
        )
        assert outcome.action == "create_linked_repost"
        assert outcome.confidence == "High"
        assert outcome.matched_job_id == existing_job.id
        # New job was created (not the existing one)
        assert outcome.job_posting.id != existing_job.id
        assert outcome.job_posting.previous_posting_ids is not None
        assert str(existing_job.id) in [
            str(pid) for pid in outcome.job_posting.previous_posting_ids
        ]

    async def test_requires_same_company(
        self,
        db_session: AsyncSession,
        existing_job: JobPosting,  # noqa: ARG002
        source_indeed: JobSource,
        persona_a: Persona,
        user_a: User,
    ) -> None:
        """Different company does not trigger repost detection."""
        similar_desc = _DESC_A + " with minor changes"
        similar_hash = hashlib.sha256(similar_desc.encode()).hexdigest()

        job_data = _make_job_data(
            source_indeed.id,
            job_title="Software Engineer",
            company_name="Different Corp",  # different company
            description=similar_desc,
            description_hash=similar_hash,
        )
        outcome = await deduplicate_and_save(
            db_session,
            job_data=job_data,
            persona_id=persona_a.id,
            user_id=user_a.id,
        )
        assert outcome.action == "create_new"

    async def test_creates_persona_jobs_link_for_repost(
        self,
        db_session: AsyncSession,
        existing_job: JobPosting,  # noqa: ARG002
        source_indeed: JobSource,
        persona_a: Persona,
        user_a: User,
    ) -> None:
        """persona_jobs link is created for the new repost job."""
        similar_desc = _DESC_A + " plus minor additions"
        similar_hash = hashlib.sha256(similar_desc.encode()).hexdigest()

        job_data = _make_job_data(
            source_indeed.id,
            description=similar_desc,
            description_hash=similar_hash,
        )
        outcome = await deduplicate_and_save(
            db_session,
            job_data=job_data,
            persona_id=persona_a.id,
            user_id=user_a.id,
        )
        assert outcome.persona_job.job_posting_id == outcome.job_posting.id


# ---------------------------------------------------------------------------
# Step 4: No match → CREATE new
# ---------------------------------------------------------------------------


class TestStep4CreateNew:
    """Step 4: No dedup match creates a new job."""

    async def test_creates_new_on_no_match(
        self,
        db_session: AsyncSession,
        source_linkedin: JobSource,
        persona_a: Persona,
        user_a: User,
    ) -> None:
        """Completely new job creates in shared pool."""
        job_data = _make_job_data(
            source_linkedin.id,
            external_id="LI-NEW",
            job_title="Data Scientist",
            company_name="DataCo",
            description=_DESC_B,
            description_hash=_HASH_B,
        )
        outcome = await deduplicate_and_save(
            db_session,
            job_data=job_data,
            persona_id=persona_a.id,
            user_id=user_a.id,
        )
        assert outcome.action == "create_new"
        assert outcome.confidence is None
        assert outcome.matched_job_id is None
        assert outcome.job_posting.job_title == "Data Scientist"

    async def test_creates_persona_jobs_link(
        self,
        db_session: AsyncSession,
        source_linkedin: JobSource,
        persona_a: Persona,
        user_a: User,
    ) -> None:
        """persona_jobs link is created for new job."""
        job_data = _make_job_data(
            source_linkedin.id,
            job_title="Data Scientist",
            company_name="DataCo",
            description=_DESC_B,
            description_hash=_HASH_B,
        )
        outcome = await deduplicate_and_save(
            db_session,
            job_data=job_data,
            persona_id=persona_a.id,
            user_id=user_a.id,
        )
        assert outcome.persona_job.persona_id == persona_a.id
        assert outcome.persona_job.job_posting_id == outcome.job_posting.id
        assert outcome.persona_job.discovery_method == "scouter"


# ---------------------------------------------------------------------------
# Cross-user linking
# ---------------------------------------------------------------------------


class TestCrossUserDedup:
    """Cross-user deduplication: same shared job, different users."""

    async def test_second_user_links_to_existing_job(
        self,
        db_session: AsyncSession,
        existing_job: JobPosting,  # noqa: ARG002
        source_indeed: JobSource,
        persona_a: Persona,
        user_a: User,
        persona_b: Persona,
        user_b: User,
    ) -> None:
        """User B discovering same job links to User A's shared job."""
        # User A discovers via hash match
        job_data_a = _make_job_data(source_indeed.id)
        outcome_a = await deduplicate_and_save(
            db_session,
            job_data=job_data_a,
            persona_id=persona_a.id,
            user_id=user_a.id,
        )

        # User B discovers same job
        outcome_b = await deduplicate_and_save(
            db_session,
            job_data=job_data_a,
            persona_id=persona_b.id,
            user_id=user_b.id,
        )

        # Both link to the same shared job
        assert outcome_a.job_posting.id == outcome_b.job_posting.id
        # But different persona_jobs links
        assert outcome_a.persona_job.id != outcome_b.persona_job.id
        assert outcome_a.persona_job.persona_id == persona_a.id
        assert outcome_b.persona_job.persona_id == persona_b.id


# ---------------------------------------------------------------------------
# Existing link handling
# ---------------------------------------------------------------------------


class TestExistingLink:
    """When persona_jobs link already exists, return it without creating duplicate."""

    async def test_returns_existing_link(
        self,
        db_session: AsyncSession,
        existing_job: JobPosting,  # noqa: ARG002
        source_linkedin: JobSource,
        persona_a: Persona,
        user_a: User,
    ) -> None:
        """Second call returns existing persona_jobs link."""
        job_data = _make_job_data(source_linkedin.id, external_id=_EXT_ID_LI)
        # First call creates link
        outcome1 = await deduplicate_and_save(
            db_session,
            job_data=job_data,
            persona_id=persona_a.id,
            user_id=user_a.id,
        )
        # Second call returns same link
        outcome2 = await deduplicate_and_save(
            db_session,
            job_data=job_data,
            persona_id=persona_a.id,
            user_id=user_a.id,
        )
        assert outcome1.persona_job.id == outcome2.persona_job.id


# ---------------------------------------------------------------------------
# Race condition: INSERT conflict recovery
# ---------------------------------------------------------------------------


class TestRaceConditionRecovery:
    """Race condition: concurrent INSERT triggers IntegrityError recovery."""

    async def test_recovers_on_job_insert_conflict(
        self,
        db_session: AsyncSession,
        source_linkedin: JobSource,
        persona_a: Persona,
        user_a: User,
    ) -> None:
        """IntegrityError on INSERT recovers by looking up existing record.

        Simulates the race condition where step 1 lookup returns None
        (other process hasn't committed yet), but our INSERT fails because
        the other process committed in between.
        """
        # Pre-create the conflicting job (simulates "other process")
        conflict_job = JobPosting(
            source_id=source_linkedin.id,
            external_id="LI-RACE",
            job_title="Software Engineer",
            company_name="Acme Corp",
            description=_DESC_A,
            description_hash=_HASH_A,
            first_seen_date=_TODAY,
        )
        db_session.add(conflict_job)
        await db_session.flush()
        await db_session.refresh(conflict_job)

        # Our dedup call with same source + external_id
        # Since the job exists, step 1 should find it (no race condition here).
        # To truly test the race, we'd need concurrent transactions.
        # This test verifies the normal step 1 path works correctly.
        job_data = _make_job_data(
            source_linkedin.id,
            external_id="LI-RACE",
        )
        outcome = await deduplicate_and_save(
            db_session,
            job_data=job_data,
            persona_id=persona_a.id,
            user_id=user_a.id,
        )
        assert outcome.job_posting.id == conflict_job.id
        assert outcome.persona_job is not None

    async def test_create_conflict_recovery_via_mock(
        self,
        db_session: AsyncSession,
        source_linkedin: JobSource,
        existing_job: JobPosting,
        persona_a: Persona,  # noqa: ARG002
        user_a: User,  # noqa: ARG002
    ) -> None:
        """Mock-based race condition: create raises IntegrityError, recovery finds existing.

        Patches JobPostingRepository.create to raise IntegrityError on the
        first call (simulating a concurrent insert), then verifies the
        recovery path looks up the existing job by source + external_id.
        """
        from app.services.global_dedup_service import _create_with_conflict_recovery

        job_data = _make_job_data(
            source_linkedin.id,
            external_id=_EXT_ID_LI,
            description=_DESC_B,
            description_hash=_HASH_B,
        )

        mock_create = AsyncMock(side_effect=IntegrityError("UNIQUE", {}, Exception()))
        with patch(
            "app.services.global_dedup_service.JobPostingRepository.create",
            mock_create,
        ):
            result = await _create_with_conflict_recovery(db_session, job_data)

        assert result.id == existing_job.id
        mock_create.assert_called_once()


# ---------------------------------------------------------------------------
# Custom discovery method
# ---------------------------------------------------------------------------


class TestDiscoveryMethod:
    """Discovery method is passed through to persona_jobs link."""

    async def test_custom_discovery_method(
        self,
        db_session: AsyncSession,
        source_linkedin: JobSource,
        persona_a: Persona,
        user_a: User,
    ) -> None:
        """Manual discovery method is set on persona_jobs link."""
        job_data = _make_job_data(
            source_linkedin.id,
            job_title="Data Scientist",
            company_name="DataCo",
            description=_DESC_B,
            description_hash=_HASH_B,
        )
        outcome = await deduplicate_and_save(
            db_session,
            job_data=job_data,
            persona_id=persona_a.id,
            user_id=user_a.id,
            discovery_method="manual",
        )
        assert outcome.persona_job.discovery_method == "manual"
