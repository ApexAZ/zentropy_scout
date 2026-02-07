"""Tests for cover letter editing service.

REQ-002b §7.3: User editing workflow for cover letter draft text.
"""

import uuid
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cover_letter import CoverLetter
from app.models.job_posting import JobPosting
from app.models.job_source import JobSource
from app.models.persona import Persona
from app.models.user import User

# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def editing_scenario(db_session: AsyncSession):
    """Create scenario for cover letter editing tests.

    Creates: User → Persona → JobSource → JobPosting → Draft CoverLetter + Approved CoverLetter.
    """
    user = User(id=uuid.uuid4(), email="cl_edit@example.com")
    db_session.add(user)
    await db_session.flush()

    persona = Persona(
        user_id=user.id,
        full_name="Edit Tester",
        email="edit@example.com",
        phone="555-0200",
        home_city="Seattle",
        home_state="Washington",
        home_country="USA",
    )
    db_session.add(persona)
    await db_session.flush()

    source = JobSource(
        source_name="EditBoard",
        source_type="Extension",
        description="Test source for editing",
    )
    db_session.add(source)
    await db_session.flush()

    job_posting = JobPosting(
        persona_id=persona.id,
        source_id=source.id,
        external_id="test-edit-001",
        job_title="Product Manager",
        company_name="EditCo",
        description="Manage products",
        description_hash="edit_hash_001",
        first_seen_date=date(2026, 1, 25),
        status="Discovered",
    )
    db_session.add(job_posting)
    await db_session.flush()

    draft_cl = CoverLetter(
        persona_id=persona.id,
        job_posting_id=job_posting.id,
        draft_text="Original draft text before editing.",
        status="Draft",
        agent_reasoning="Initial reasoning.",
        achievement_stories_used=[],
    )
    db_session.add(draft_cl)
    await db_session.flush()

    approved_cl = CoverLetter(
        persona_id=persona.id,
        job_posting_id=job_posting.id,
        draft_text="Approved draft.",
        final_text="Locked final text.",
        status="Approved",
        agent_reasoning="Approved reasoning.",
        achievement_stories_used=[],
        approved_at=datetime.now(UTC),
    )
    db_session.add(approved_cl)
    await db_session.flush()

    await db_session.commit()

    class Scenario:
        pass

    s = Scenario()
    s.draft_cl_id = draft_cl.id
    s.approved_cl_id = approved_cl.id
    return s


# =============================================================================
# TestUpdateCoverLetterDraft
# =============================================================================


class TestUpdateCoverLetterDraft:
    """Tests for update_cover_letter_draft."""

    @pytest.mark.asyncio
    async def test_updates_draft_text(self, db_session, editing_scenario):
        """Draft text is replaced with new content."""
        from app.services.cover_letter_editing import update_cover_letter_draft

        await update_cover_letter_draft(
            db=db_session,
            cover_letter_id=editing_scenario.draft_cl_id,
            new_draft_text="Revised draft with more technical focus.",
        )

        cl = await db_session.get(CoverLetter, editing_scenario.draft_cl_id)
        assert cl is not None
        assert cl.draft_text == "Revised draft with more technical focus."

    @pytest.mark.asyncio
    async def test_preserves_draft_status(self, db_session, editing_scenario):
        """Status remains Draft after editing."""
        from app.services.cover_letter_editing import update_cover_letter_draft

        await update_cover_letter_draft(
            db=db_session,
            cover_letter_id=editing_scenario.draft_cl_id,
            new_draft_text="Updated content.",
        )

        cl = await db_session.get(CoverLetter, editing_scenario.draft_cl_id)
        assert cl is not None
        assert cl.status == "Draft"

    @pytest.mark.asyncio
    async def test_refreshes_updated_at(self, db_session, editing_scenario):
        """updated_at timestamp is refreshed after edit."""
        from app.services.cover_letter_editing import update_cover_letter_draft

        cl_before = await db_session.get(CoverLetter, editing_scenario.draft_cl_id)
        original_updated_at = cl_before.updated_at

        await update_cover_letter_draft(
            db=db_session,
            cover_letter_id=editing_scenario.draft_cl_id,
            new_draft_text="New text triggers timestamp update.",
        )

        await db_session.refresh(cl_before)
        assert cl_before.updated_at > original_updated_at

    @pytest.mark.asyncio
    async def test_returns_result_with_cover_letter_id(
        self, db_session, editing_scenario
    ):
        """Result contains the cover letter ID."""
        from app.services.cover_letter_editing import update_cover_letter_draft

        result = await update_cover_letter_draft(
            db=db_session,
            cover_letter_id=editing_scenario.draft_cl_id,
            new_draft_text="Some new text.",
        )

        assert result.cover_letter_id == editing_scenario.draft_cl_id
        assert result.status == "Draft"

    @pytest.mark.asyncio
    async def test_rejects_approved_cover_letter(self, db_session, editing_scenario):
        """Cannot edit a cover letter that is already Approved."""
        from app.core.errors import InvalidStateError
        from app.services.cover_letter_editing import update_cover_letter_draft

        with pytest.raises(InvalidStateError, match="Approved"):
            await update_cover_letter_draft(
                db=db_session,
                cover_letter_id=editing_scenario.approved_cl_id,
                new_draft_text="Trying to edit locked letter.",
            )

    @pytest.mark.asyncio
    async def test_rejects_nonexistent_cover_letter(self, db_session):
        """NotFoundError when cover letter does not exist."""
        from app.core.errors import NotFoundError
        from app.services.cover_letter_editing import update_cover_letter_draft

        with pytest.raises(NotFoundError):
            await update_cover_letter_draft(
                db=db_session,
                cover_letter_id=uuid.uuid4(),
                new_draft_text="Text for nonexistent letter.",
            )

    @pytest.mark.asyncio
    async def test_rejects_empty_draft_text(self, db_session, editing_scenario):
        """Empty draft text is rejected."""
        from app.core.errors import ValidationError
        from app.services.cover_letter_editing import update_cover_letter_draft

        with pytest.raises(ValidationError, match="empty"):
            await update_cover_letter_draft(
                db=db_session,
                cover_letter_id=editing_scenario.draft_cl_id,
                new_draft_text="",
            )

    @pytest.mark.asyncio
    async def test_rejects_whitespace_only_draft_text(
        self, db_session, editing_scenario
    ):
        """Whitespace-only draft text is rejected."""
        from app.core.errors import ValidationError
        from app.services.cover_letter_editing import update_cover_letter_draft

        with pytest.raises(ValidationError, match="empty"):
            await update_cover_letter_draft(
                db=db_session,
                cover_letter_id=editing_scenario.draft_cl_id,
                new_draft_text="   \n\t  ",
            )

    @pytest.mark.asyncio
    async def test_rejects_archived_cover_letter(self, db_session, editing_scenario):
        """Cannot edit a cover letter with Archived status."""
        from app.core.errors import InvalidStateError
        from app.services.cover_letter_editing import update_cover_letter_draft

        # Change the draft to Archived status
        cl = await db_session.get(CoverLetter, editing_scenario.draft_cl_id)
        cl.status = "Archived"
        await db_session.commit()

        with pytest.raises(InvalidStateError, match="Archived"):
            await update_cover_letter_draft(
                db=db_session,
                cover_letter_id=editing_scenario.draft_cl_id,
                new_draft_text="Trying to edit archived letter.",
            )

    @pytest.mark.asyncio
    async def test_rejects_soft_deleted_cover_letter(
        self, db_session, editing_scenario
    ):
        """Cannot edit a soft-deleted cover letter."""
        from app.core.errors import NotFoundError
        from app.services.cover_letter_editing import update_cover_letter_draft

        cl = await db_session.get(CoverLetter, editing_scenario.draft_cl_id)
        cl.archived_at = datetime.now(UTC)
        await db_session.commit()

        with pytest.raises(NotFoundError):
            await update_cover_letter_draft(
                db=db_session,
                cover_letter_id=editing_scenario.draft_cl_id,
                new_draft_text="Trying to edit deleted letter.",
            )

    @pytest.mark.asyncio
    async def test_rejects_oversized_draft_text(self, db_session, editing_scenario):
        """Draft text exceeding max length is rejected."""
        from app.core.errors import ValidationError
        from app.services.cover_letter_editing import (
            _MAX_DRAFT_TEXT_LENGTH,
            update_cover_letter_draft,
        )

        oversized = "x" * (_MAX_DRAFT_TEXT_LENGTH + 1)

        with pytest.raises(ValidationError, match="maximum"):
            await update_cover_letter_draft(
                db=db_session,
                cover_letter_id=editing_scenario.draft_cl_id,
                new_draft_text=oversized,
            )
