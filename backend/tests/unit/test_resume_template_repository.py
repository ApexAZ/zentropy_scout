"""Tests for ResumeTemplateRepository.

REQ-025 §4.3, §6.4: Tests cover CRUD operations, access control
(system vs user templates), and list_available scoping.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resume_template import ResumeTemplate
from app.repositories.resume_template_repository import ResumeTemplateRepository

_MISSING_UUID = uuid.UUID("99999999-9999-9999-9999-999999999999")
_TEMPLATE_MARKDOWN = "# {full_name}\n\n## Experience\n\n{experience}"


async def _seed_system_template(db: AsyncSession) -> ResumeTemplate:
    """Create a system template for tests."""
    template = ResumeTemplate(
        name="System Template",
        description="A system-owned template",
        markdown_content=_TEMPLATE_MARKDOWN,
        is_system=True,
        user_id=None,
        display_order=1,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)
    return template


async def _seed_user_template(
    db: AsyncSession, user_id: uuid.UUID, *, name: str = "My Template"
) -> ResumeTemplate:
    """Create a user-owned template for tests."""
    template = ResumeTemplate(
        name=name,
        description="A user-owned template",
        markdown_content=_TEMPLATE_MARKDOWN,
        is_system=False,
        user_id=user_id,
        display_order=10,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)
    return template


class TestListAvailable:
    """Test ResumeTemplateRepository.list_available()."""

    async def test_returns_system_templates(self, db_session: AsyncSession, test_user):
        """System templates are visible to any user."""
        sys_tmpl = await _seed_system_template(db_session)
        templates = await ResumeTemplateRepository.list_available(
            db_session, test_user.id
        )
        assert any(t.id == sys_tmpl.id for t in templates)

    async def test_returns_users_own_templates(
        self, db_session: AsyncSession, test_user
    ):
        """User's own templates are included."""
        user_tmpl = await _seed_user_template(db_session, test_user.id)
        templates = await ResumeTemplateRepository.list_available(
            db_session, test_user.id
        )
        assert any(t.id == user_tmpl.id for t in templates)

    async def test_excludes_other_users_templates(
        self, db_session: AsyncSession, test_user, user_b
    ):
        """Templates owned by another user are not visible."""
        other_tmpl = await _seed_user_template(db_session, user_b.id, name="Other")
        templates = await ResumeTemplateRepository.list_available(
            db_session, test_user.id
        )
        assert not any(t.id == other_tmpl.id for t in templates)

    async def test_ordered_by_display_order(self, db_session: AsyncSession, test_user):
        """Results are sorted by display_order ascending."""
        sys_tmpl = await _seed_system_template(db_session)  # display_order=1
        user_tmpl = await _seed_user_template(
            db_session, test_user.id
        )  # display_order=10
        templates = await ResumeTemplateRepository.list_available(
            db_session, test_user.id
        )
        ids = [t.id for t in templates]
        assert ids.index(sys_tmpl.id) < ids.index(user_tmpl.id)

    async def test_returns_empty_when_no_templates(
        self, db_session: AsyncSession, test_user
    ):
        """Returns empty list when no templates exist."""
        templates = await ResumeTemplateRepository.list_available(
            db_session, test_user.id
        )
        assert templates == []


class TestGetById:
    """Test ResumeTemplateRepository.get_by_id()."""

    async def test_returns_system_template(self, db_session: AsyncSession, test_user):
        """Any user can fetch a system template by ID."""
        sys_tmpl = await _seed_system_template(db_session)
        result = await ResumeTemplateRepository.get_by_id(
            db_session, sys_tmpl.id, test_user.id
        )
        assert result is not None
        assert result.id == sys_tmpl.id
        assert result.name == "System Template"

    async def test_returns_own_template(self, db_session: AsyncSession, test_user):
        """User can fetch their own template."""
        user_tmpl = await _seed_user_template(db_session, test_user.id)
        result = await ResumeTemplateRepository.get_by_id(
            db_session, user_tmpl.id, test_user.id
        )
        assert result is not None
        assert result.id == user_tmpl.id

    async def test_returns_none_for_other_users_template(
        self, db_session: AsyncSession, test_user, user_b
    ):
        """Cannot fetch another user's template."""
        other_tmpl = await _seed_user_template(db_session, user_b.id, name="Other")
        result = await ResumeTemplateRepository.get_by_id(
            db_session, other_tmpl.id, test_user.id
        )
        assert result is None

    async def test_returns_none_for_missing_id(
        self, db_session: AsyncSession, test_user
    ):
        """Non-existent ID returns None."""
        result = await ResumeTemplateRepository.get_by_id(
            db_session, _MISSING_UUID, test_user.id
        )
        assert result is None


class TestCreate:
    """Test ResumeTemplateRepository.create()."""

    async def test_creates_user_template(self, db_session: AsyncSession, test_user):
        """Creates a user-owned template with all fields."""
        template = await ResumeTemplateRepository.create(
            db_session,
            user_id=test_user.id,
            name="Custom Template",
            description="My custom template",
            markdown_content=_TEMPLATE_MARKDOWN,
            display_order=5,
        )
        assert template.id is not None
        assert template.name == "Custom Template"
        assert template.description == "My custom template"
        assert template.markdown_content == _TEMPLATE_MARKDOWN
        assert template.is_system is False
        assert template.user_id == test_user.id
        assert template.display_order == 5
        assert template.created_at is not None
        assert template.updated_at is not None

    async def test_creates_with_defaults(self, db_session: AsyncSession, test_user):
        """Creates with minimal fields — defaults apply."""
        template = await ResumeTemplateRepository.create(
            db_session,
            user_id=test_user.id,
            name="Minimal",
            markdown_content="# Resume",
        )
        assert template.description is None
        assert template.display_order == 0
        assert template.is_system is False


class TestUpdate:
    """Test ResumeTemplateRepository.update()."""

    async def test_updates_own_template(self, db_session: AsyncSession, test_user):
        """User can update their own template."""
        user_tmpl = await _seed_user_template(db_session, test_user.id)
        result = await ResumeTemplateRepository.update(
            db_session,
            user_tmpl.id,
            test_user.id,
            name="Updated Name",
            description="Updated desc",
        )
        assert result is not None
        assert result.name == "Updated Name"
        assert result.description == "Updated desc"
        assert result.markdown_content == _TEMPLATE_MARKDOWN  # unchanged

    async def test_rejects_system_template_update(
        self, db_session: AsyncSession, test_user
    ):
        """System templates cannot be updated."""
        sys_tmpl = await _seed_system_template(db_session)
        with pytest.raises(ValueError, match="system"):
            await ResumeTemplateRepository.update(
                db_session, sys_tmpl.id, test_user.id, name="Hacked"
            )

    async def test_returns_none_for_other_users_template(
        self, db_session: AsyncSession, test_user, user_b
    ):
        """Cannot update another user's template."""
        other_tmpl = await _seed_user_template(db_session, user_b.id, name="Other")
        result = await ResumeTemplateRepository.update(
            db_session, other_tmpl.id, test_user.id, name="Stolen"
        )
        assert result is None

    async def test_returns_none_for_missing_id(
        self, db_session: AsyncSession, test_user
    ):
        """Non-existent ID returns None."""
        result = await ResumeTemplateRepository.update(
            db_session, _MISSING_UUID, test_user.id, name="Ghost"
        )
        assert result is None

    async def test_partial_update_preserves_fields(
        self, db_session: AsyncSession, test_user
    ):
        """Only provided fields are updated; others remain unchanged."""
        user_tmpl = await _seed_user_template(db_session, test_user.id)
        original_content = user_tmpl.markdown_content
        result = await ResumeTemplateRepository.update(
            db_session, user_tmpl.id, test_user.id, name="New Name"
        )
        assert result is not None
        assert result.name == "New Name"
        assert result.markdown_content == original_content
        assert result.description == "A user-owned template"


class TestDelete:
    """Test ResumeTemplateRepository.delete()."""

    async def test_deletes_own_template(self, db_session: AsyncSession, test_user):
        """User can delete their own template."""
        user_tmpl = await _seed_user_template(db_session, test_user.id)
        deleted = await ResumeTemplateRepository.delete(
            db_session, user_tmpl.id, test_user.id
        )
        assert deleted is True

        # Verify it's gone
        result = await ResumeTemplateRepository.get_by_id(
            db_session, user_tmpl.id, test_user.id
        )
        assert result is None

    async def test_rejects_system_template_delete(
        self, db_session: AsyncSession, test_user
    ):
        """System templates cannot be deleted."""
        sys_tmpl = await _seed_system_template(db_session)
        with pytest.raises(ValueError, match="system"):
            await ResumeTemplateRepository.delete(db_session, sys_tmpl.id, test_user.id)

    async def test_returns_false_for_other_users_template(
        self, db_session: AsyncSession, test_user, user_b
    ):
        """Cannot delete another user's template."""
        other_tmpl = await _seed_user_template(db_session, user_b.id, name="Other")
        deleted = await ResumeTemplateRepository.delete(
            db_session, other_tmpl.id, test_user.id
        )
        assert deleted is False

    async def test_returns_false_for_missing_id(
        self, db_session: AsyncSession, test_user
    ):
        """Non-existent ID returns False."""
        deleted = await ResumeTemplateRepository.delete(
            db_session, _MISSING_UUID, test_user.id
        )
        assert deleted is False
