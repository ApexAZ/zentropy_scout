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
    ResumeTemplateListResponse,
    ResumeTemplateResponse,
    UpdateResumeTemplateRequest,
)

_NOW = datetime.now(UTC)
_TEMPLATE_ID = uuid.uuid4()
_USER_ID = uuid.uuid4()


class TestResumeTemplateResponse:
    """Test ResumeTemplateResponse serialization."""

    def test_serializes_all_fields(self):
        """Response includes all template fields."""
        response = ResumeTemplateResponse(
            id=_TEMPLATE_ID,
            name="Clean & Minimal",
            description="A clean layout",
            markdown_content="# Resume",
            is_system=True,
            user_id=None,
            display_order=1,
            created_at=_NOW,
            updated_at=_NOW,
        )
        assert response.id == _TEMPLATE_ID
        assert response.name == "Clean & Minimal"
        assert response.description == "A clean layout"
        assert response.markdown_content == "# Resume"
        assert response.is_system is True
        assert response.user_id is None
        assert response.display_order == 1

    def test_serializes_user_template(self):
        """Response handles user-owned template with user_id."""
        response = ResumeTemplateResponse(
            id=_TEMPLATE_ID,
            name="My Template",
            description=None,
            markdown_content="# Resume",
            is_system=False,
            user_id=_USER_ID,
            display_order=5,
            created_at=_NOW,
            updated_at=_NOW,
        )
        assert response.is_system is False
        assert response.user_id == _USER_ID

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

    def test_valid_request(self):
        """Valid creation request passes validation."""
        request = CreateResumeTemplateRequest(
            name="My Template",
            markdown_content="# Resume\n\n## Experience",
            description="A custom template",
            display_order=5,
        )
        assert request.name == "My Template"
        assert request.markdown_content == "# Resume\n\n## Experience"
        assert request.description == "A custom template"
        assert request.display_order == 5

    def test_minimal_request(self):
        """Only name and markdown_content are required."""
        request = CreateResumeTemplateRequest(
            name="Minimal",
            markdown_content="# Resume",
        )
        assert request.description is None
        assert request.display_order == 0

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

    def test_all_fields_optional(self):
        """Empty update request is valid (no fields provided)."""
        request = UpdateResumeTemplateRequest()
        assert request.name is None
        assert request.description is None
        assert request.markdown_content is None
        assert request.display_order is None

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


class TestResumeTemplateListResponse:
    """Test ResumeTemplateListResponse."""

    def test_wraps_template_list(self):
        """List response contains templates array."""
        template = ResumeTemplateResponse(
            id=_TEMPLATE_ID,
            name="Test",
            description=None,
            markdown_content="# Test",
            is_system=True,
            user_id=None,
            display_order=0,
            created_at=_NOW,
            updated_at=_NOW,
        )
        response = ResumeTemplateListResponse(templates=[template])
        assert len(response.templates) == 1
        assert response.templates[0].name == "Test"

    def test_empty_list(self):
        """Empty templates list is valid."""
        response = ResumeTemplateListResponse(templates=[])
        assert response.templates == []
