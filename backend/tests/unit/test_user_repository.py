"""Tests for UserRepository.

REQ-013 §7.5, REQ-005 §4.0: Tests cover CRUD operations,
email uniqueness, and not-found cases.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_repository import UserRepository

_MISSING_UUID = uuid.UUID("99999999-9999-9999-9999-999999999999")
_TEST_EMAIL = "test@example.com"
_NEW_IMAGE_URL = "https://example.com/new.jpg"


class TestGetById:
    """Test UserRepository.get_by_id()."""

    async def test_returns_user_when_found(self, db_session: AsyncSession, test_user):
        """Existing user is returned by ID."""
        user = await UserRepository.get_by_id(db_session, test_user.id)
        assert user is not None
        assert user.id == test_user.id
        assert user.email == test_user.email

    async def test_returns_none_when_not_found(self, db_session: AsyncSession):
        """Non-existent ID returns None."""
        user = await UserRepository.get_by_id(db_session, _MISSING_UUID)
        assert user is None


class TestGetByEmail:
    """Test UserRepository.get_by_email()."""

    async def test_returns_user_when_found(self, db_session: AsyncSession, test_user):
        """Existing user is returned by email."""
        user = await UserRepository.get_by_email(db_session, _TEST_EMAIL)
        assert user is not None
        assert user.email == test_user.email
        assert user.id == test_user.id

    async def test_returns_none_when_not_found(self, db_session: AsyncSession):
        """Non-existent email returns None."""
        user = await UserRepository.get_by_email(db_session, "nonexistent@example.com")
        assert user is None

    async def test_email_lookup_is_case_insensitive(
        self, db_session: AsyncSession, test_user
    ):
        """Email lookup ignores case."""
        user = await UserRepository.get_by_email(db_session, "TEST@EXAMPLE.COM")
        assert user is not None
        assert user.id == test_user.id


class TestCreate:
    """Test UserRepository.create()."""

    async def test_creates_user_with_email_only(self, db_session: AsyncSession):
        """Minimal creation with just an email."""
        user = await UserRepository.create(db_session, email="new@example.com")
        assert user.id is not None
        assert user.email == "new@example.com"
        assert user.name is None
        assert user.password_hash is None
        assert user.email_verified is None
        assert user.image is None

    async def test_creates_user_with_all_fields(self, db_session: AsyncSession):
        """Creation with all optional fields populated."""
        now = datetime.now(UTC)
        user = await UserRepository.create(
            db_session,
            email="full@example.com",
            name="Test User",
            password_hash="$2b$12$fakehashfortest",
            email_verified=now,
            image="https://example.com/photo.jpg",
        )
        assert user.email == "full@example.com"
        assert user.name == "Test User"
        assert user.password_hash == "$2b$12$fakehashfortest"
        assert user.email_verified == now
        assert user.image == "https://example.com/photo.jpg"

    async def test_rejects_duplicate_email(
        self,
        db_session: AsyncSession,
        test_user,  # noqa: ARG002
    ):
        """Duplicate email raises IntegrityError."""
        with pytest.raises(IntegrityError):
            await UserRepository.create(db_session, email=_TEST_EMAIL)

    async def test_rejects_duplicate_email_case_insensitive(
        self,
        db_session: AsyncSession,
        test_user,  # noqa: ARG002
    ):
        """Duplicate email with different case also raises IntegrityError."""
        with pytest.raises(IntegrityError):
            await UserRepository.create(db_session, email="TEST@EXAMPLE.COM")

    async def test_generated_uuid_is_unique(self, db_session: AsyncSession):
        """Two users get distinct UUIDs."""
        user1 = await UserRepository.create(db_session, email="a@example.com")
        user2 = await UserRepository.create(db_session, email="b@example.com")
        assert user1.id != user2.id

    async def test_email_stored_lowercase(self, db_session: AsyncSession):
        """Email is normalized to lowercase on creation."""
        user = await UserRepository.create(db_session, email="MiXeD@Example.COM")
        assert user.email == "mixed@example.com"

    async def test_created_at_is_set(self, db_session: AsyncSession):
        """created_at timestamp is populated by the database."""
        user = await UserRepository.create(db_session, email="ts@example.com")
        assert user.created_at is not None

    async def test_updated_at_is_set(self, db_session: AsyncSession):
        """updated_at timestamp is populated by the database."""
        user = await UserRepository.create(db_session, email="ts2@example.com")
        assert user.updated_at is not None


class TestUpdate:
    """Test UserRepository.update()."""

    async def test_updates_name(self, db_session: AsyncSession, test_user):
        """Name field can be updated."""
        user = await UserRepository.update(db_session, test_user.id, name="New Name")
        assert user is not None
        assert user.name == "New Name"

    async def test_updates_password_hash(self, db_session: AsyncSession, test_user):
        """Password hash can be updated."""
        user = await UserRepository.update(
            db_session, test_user.id, password_hash="$2b$12$newhash"
        )
        assert user is not None
        assert user.password_hash == "$2b$12$newhash"

    async def test_updates_token_invalidated_before(
        self, db_session: AsyncSession, test_user
    ):
        """token_invalidated_before can be set for session revocation."""
        now = datetime.now(UTC)
        user = await UserRepository.update(
            db_session, test_user.id, token_invalidated_before=now
        )
        assert user is not None
        assert user.token_invalidated_before == now

    async def test_updates_email_verified(self, db_session: AsyncSession, test_user):
        """email_verified can be set."""
        now = datetime.now(UTC)
        user = await UserRepository.update(db_session, test_user.id, email_verified=now)
        assert user is not None
        assert user.email_verified == now

    async def test_updates_image(self, db_session: AsyncSession, test_user):
        """Image URL can be updated."""
        user = await UserRepository.update(
            db_session, test_user.id, image=_NEW_IMAGE_URL
        )
        assert user is not None
        assert user.image == _NEW_IMAGE_URL

    async def test_returns_none_for_nonexistent_user(self, db_session: AsyncSession):
        """Update on non-existent ID returns None."""
        user = await UserRepository.update(db_session, _MISSING_UUID, name="Ghost")
        assert user is None

    async def test_updates_multiple_fields(self, db_session: AsyncSession, test_user):
        """Multiple fields can be updated in one call."""
        user = await UserRepository.update(
            db_session,
            test_user.id,
            name="Updated Name",
            image=_NEW_IMAGE_URL,
        )
        assert user is not None
        assert user.name == "Updated Name"
        assert user.image == _NEW_IMAGE_URL

    async def test_preserves_unmodified_fields(
        self, db_session: AsyncSession, test_user
    ):
        """Fields not passed to update remain unchanged."""
        await UserRepository.update(db_session, test_user.id, name="Changed")
        user = await UserRepository.get_by_id(db_session, test_user.id)
        assert user is not None
        assert user.name == "Changed"
        assert user.email == test_user.email

    async def test_no_op_update_returns_user(self, db_session: AsyncSession, test_user):
        """Update with no fields returns user unchanged."""
        user = await UserRepository.update(db_session, test_user.id)
        assert user is not None
        assert user.id == test_user.id

    async def test_rejects_unknown_fields(self, db_session: AsyncSession, test_user):
        """Unknown field names raise ValueError."""
        with pytest.raises(ValueError, match="not_a_real_field"):
            await UserRepository.update(
                db_session,
                test_user.id,
                not_a_real_field="bad",
            )

    async def test_rejects_id_update(self, db_session: AsyncSession, test_user):
        """id field cannot be updated (primary key is immutable)."""
        with pytest.raises(ValueError, match="id"):
            await UserRepository.update(db_session, test_user.id, id=uuid.uuid4())

    async def test_rejects_email_update(self, db_session: AsyncSession, test_user):
        """email field cannot be updated via generic update."""
        with pytest.raises(ValueError, match="email"):
            await UserRepository.update(
                db_session, test_user.id, email="attacker@evil.com"
            )
