"""Tests for resume template Pydantic schemas.

REQ-025 §4.3, §6.4: Validates serialization and request validation
for resume template API models.
"""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.resume_template import (
    CreateResumeTemplateRequest,
    ResumeTemplateResponse,
    UpdateResumeTemplateRequest,
)

_NOW = datetime.now(UTC)
_TEMPLATE_ID = uuid.uuid4()


class TestResumeTemplateResponse:
    """Test ResumeTemplateResponse serialization."""

    def test_from_attributes(self):
        """Can be created from ORM model attributes."""

        class FakeORM:
            id = _TEMPLATE_ID
            name = "Test"
            description = None
            markdown_content = "# Test"
            is_system = True
            user_id = None
            display_order = 0
            created_at = _NOW
            updated_at = _NOW

        response = ResumeTemplateResponse.model_validate(FakeORM())
        assert response.id == _TEMPLATE_ID
        assert response.name == "Test"


class TestCreateResumeTemplateRequest:
    """Test CreateResumeTemplateRequest validation."""

    def test_rejects_empty_name(self):
        """Name must be non-empty."""
        with pytest.raises(ValidationError):
            CreateResumeTemplateRequest(
                name="",
                markdown_content="# Resume",
            )

    def test_rejects_long_name(self):
        """Name exceeding 100 chars is rejected."""
        with pytest.raises(ValidationError):
            CreateResumeTemplateRequest(
                name="x" * 101,
                markdown_content="# Resume",
            )

    def test_rejects_empty_markdown(self):
        """Markdown content must be non-empty."""
        with pytest.raises(ValidationError):
            CreateResumeTemplateRequest(
                name="Test",
                markdown_content="",
            )

    def test_rejects_extra_fields(self):
        """Extra fields are forbidden."""
        with pytest.raises(ValidationError):
            CreateResumeTemplateRequest(
                name="Test",
                markdown_content="# Resume",
                is_system=True,  # type: ignore[call-arg]
            )


class TestUpdateResumeTemplateRequest:
    """Test UpdateResumeTemplateRequest validation."""

    def test_partial_update(self):
        """Can update just one field."""
        request = UpdateResumeTemplateRequest(name="New Name")
        data = request.model_dump(exclude_unset=True)
        assert data == {"name": "New Name"}

    def test_rejects_empty_name(self):
        """Name if provided must be non-empty."""
        with pytest.raises(ValidationError):
            UpdateResumeTemplateRequest(name="")

    def test_rejects_extra_fields(self):
        """Extra fields are forbidden."""
        with pytest.raises(ValidationError):
            UpdateResumeTemplateRequest(
                is_system=True,  # type: ignore[call-arg]
            )
