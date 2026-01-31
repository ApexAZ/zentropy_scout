"""Tests for extra="forbid" on request schemas.

Security: Ensures unexpected fields are rejected to prevent
mass assignment and data injection attacks.
"""

import pytest
from pydantic import ValidationError


class TestIngestSchemas:
    """Tests for ingest request schema validation."""

    def test_ingest_request_rejects_extra_fields(self):
        """IngestJobPostingRequest should reject extra fields."""
        from app.schemas.ingest import IngestJobPostingRequest

        with pytest.raises(ValidationError) as exc_info:
            IngestJobPostingRequest(
                raw_text="Job posting text",
                source_url="https://example.com/job/123",
                source_name="LinkedIn",
                malicious_field="should not be allowed",
            )

        errors = exc_info.value.errors()
        assert any("malicious_field" in str(e) for e in errors)

    def test_ingest_confirm_request_rejects_extra_fields(self):
        """IngestConfirmRequest should reject extra fields."""
        from app.schemas.ingest import IngestConfirmRequest

        with pytest.raises(ValidationError) as exc_info:
            IngestConfirmRequest(
                confirmation_token="abc123",
                extra_field="not allowed",
            )

        errors = exc_info.value.errors()
        assert any("extra_field" in str(e) for e in errors)


class TestChatSchemas:
    """Tests for chat request schema validation."""

    def test_chat_message_request_rejects_extra_fields(self):
        """ChatMessageRequest should reject extra fields."""
        from app.schemas.chat import ChatMessageRequest

        with pytest.raises(ValidationError) as exc_info:
            ChatMessageRequest(
                content="Hello",
                hidden_instruction="should not work",
            )

        errors = exc_info.value.errors()
        assert any("hidden_instruction" in str(e) for e in errors)


class TestBulkSchemas:
    """Tests for bulk operation request schema validation."""

    def test_bulk_dismiss_rejects_extra_fields(self):
        """BulkDismissRequest should reject extra fields."""
        from uuid import uuid4

        from app.schemas.bulk import BulkDismissRequest

        with pytest.raises(ValidationError) as exc_info:
            BulkDismissRequest(
                ids=[uuid4()],
                force_delete=True,  # Not a valid field
            )

        errors = exc_info.value.errors()
        assert any("force_delete" in str(e) for e in errors)

    def test_bulk_favorite_rejects_extra_fields(self):
        """BulkFavoriteRequest should reject extra fields."""
        from uuid import uuid4

        from app.schemas.bulk import BulkFavoriteRequest

        with pytest.raises(ValidationError) as exc_info:
            BulkFavoriteRequest(
                ids=[uuid4()],
                is_favorite=True,
                notify_user=True,  # Not a valid field
            )

        errors = exc_info.value.errors()
        assert any("notify_user" in str(e) for e in errors)

    def test_bulk_archive_rejects_extra_fields(self):
        """BulkArchiveRequest should reject extra fields."""
        from uuid import uuid4

        from app.schemas.bulk import BulkArchiveRequest

        with pytest.raises(ValidationError) as exc_info:
            BulkArchiveRequest(
                ids=[uuid4()],
                delete_permanently=True,  # Not a valid field
            )

        errors = exc_info.value.errors()
        assert any("delete_permanently" in str(e) for e in errors)
