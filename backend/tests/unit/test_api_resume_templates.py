"""Tests for Resume Templates CRUD API endpoints.

REQ-025 §6.4, §8: Tests cover list, get, create, update, delete
with access control, system template protection, and markdown validation.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resume_template import ResumeTemplate
from tests.conftest import TEST_USER_ID

_BASE_URL = "/api/v1/resume-templates"
_VALID_MARKDOWN = "# My Template\n\n## Experience\n\n- {bullet_1}"
_MISSING_UUID = str(uuid.UUID("99999999-9999-9999-9999-999999999999"))


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def system_template(db_session: AsyncSession) -> ResumeTemplate:
    """Create a system template."""
    template = ResumeTemplate(
        name="System Default",
        description="A built-in template",
        markdown_content="# {full_name}\n\n## Summary\n\n{summary}",
        is_system=True,
        user_id=None,
        display_order=0,
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)
    return template


@pytest_asyncio.fixture
async def user_template(db_session: AsyncSession) -> ResumeTemplate:
    """Create a user-owned template for TEST_USER_ID."""
    template = ResumeTemplate(
        name="My Custom Template",
        description="User's own template",
        markdown_content=_VALID_MARKDOWN,
        is_system=False,
        user_id=TEST_USER_ID,
        display_order=5,
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)
    return template


@pytest_asyncio.fixture
async def other_user_template(db_session: AsyncSession, user_b) -> ResumeTemplate:
    """Create a template owned by user_b (not the test user)."""
    template = ResumeTemplate(
        name="Other User Template",
        description="Not yours",
        markdown_content="# Other\n\nContent",
        is_system=False,
        user_id=user_b.id,
        display_order=3,
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)
    return template


# =============================================================================
# List Templates
# =============================================================================


class TestListResumeTemplates:
    """GET /api/v1/resume-templates — list with access control."""

    @pytest.mark.asyncio
    async def test_list_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.get(_BASE_URL)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_returns_system_templates(
        self, client: AsyncClient, system_template: ResumeTemplate
    ) -> None:
        """System templates are visible to any authenticated user."""
        response = await client.get(_BASE_URL)
        assert response.status_code == 200
        body = response.json()
        ids = [t["id"] for t in body["data"]]
        assert str(system_template.id) in ids

    @pytest.mark.asyncio
    async def test_list_returns_own_templates(
        self, client: AsyncClient, user_template: ResumeTemplate
    ) -> None:
        """User's own templates are included."""
        response = await client.get(_BASE_URL)
        assert response.status_code == 200
        body = response.json()
        ids = [t["id"] for t in body["data"]]
        assert str(user_template.id) in ids

    @pytest.mark.asyncio
    async def test_list_excludes_other_users_templates(
        self,
        client: AsyncClient,
        other_user_template: ResumeTemplate,
    ) -> None:
        """Templates owned by another user are not visible."""
        response = await client.get(_BASE_URL)
        assert response.status_code == 200
        body = response.json()
        ids = [t["id"] for t in body["data"]]
        assert str(other_user_template.id) not in ids

    @pytest.mark.asyncio
    async def test_list_ordered_by_display_order(
        self,
        client: AsyncClient,
        system_template: ResumeTemplate,
        user_template: ResumeTemplate,
    ) -> None:
        """Results are sorted by display_order ascending."""
        response = await client.get(_BASE_URL)
        body = response.json()
        ids = [t["id"] for t in body["data"]]
        assert ids.index(str(system_template.id)) < ids.index(str(user_template.id))

    @pytest.mark.asyncio
    async def test_list_empty_when_no_templates(self, client: AsyncClient) -> None:
        """Returns empty list when no templates exist."""
        response = await client.get(_BASE_URL)
        assert response.status_code == 200
        body = response.json()
        assert body["data"] == []


# =============================================================================
# Get Template
# =============================================================================


class TestGetResumeTemplate:
    """GET /api/v1/resume-templates/{id} — get single template."""

    @pytest.mark.asyncio
    async def test_get_system_template(
        self, client: AsyncClient, system_template: ResumeTemplate
    ) -> None:
        """Any user can fetch a system template."""
        response = await client.get(f"{_BASE_URL}/{system_template.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["id"] == str(system_template.id)
        assert body["data"]["name"] == "System Default"
        assert body["data"]["is_system"] is True

    @pytest.mark.asyncio
    async def test_get_own_template(
        self, client: AsyncClient, user_template: ResumeTemplate
    ) -> None:
        """User can fetch their own template."""
        response = await client.get(f"{_BASE_URL}/{user_template.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["id"] == str(user_template.id)

    @pytest.mark.asyncio
    async def test_get_other_users_template_returns_404(
        self, client: AsyncClient, other_user_template: ResumeTemplate
    ) -> None:
        """Cannot fetch another user's template — returns 404."""
        response = await client.get(f"{_BASE_URL}/{other_user_template.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_missing_id_returns_404(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        response = await client.get(f"{_BASE_URL}/{_MISSING_UUID}")
        assert response.status_code == 404


# =============================================================================
# Create Template
# =============================================================================


class TestCreateResumeTemplate:
    """POST /api/v1/resume-templates — create user template."""

    @pytest.mark.asyncio
    async def test_create_with_all_fields(self, client: AsyncClient) -> None:
        """Creates a user template with all fields."""
        payload = {
            "name": "New Template",
            "markdown_content": _VALID_MARKDOWN,
            "description": "A test template",
            "display_order": 3,
        }
        response = await client.post(_BASE_URL, json=payload)
        assert response.status_code == 201
        body = response.json()
        assert body["data"]["name"] == "New Template"
        assert body["data"]["markdown_content"] == _VALID_MARKDOWN
        assert body["data"]["description"] == "A test template"
        assert body["data"]["display_order"] == 3
        assert body["data"]["is_system"] is False
        assert body["data"]["user_id"] == str(TEST_USER_ID)
        assert body["data"]["id"] is not None

    @pytest.mark.asyncio
    async def test_create_with_minimal_fields(self, client: AsyncClient) -> None:
        """Creates with just name and markdown_content — defaults apply."""
        payload = {
            "name": "Minimal",
            "markdown_content": "# Resume\n\nContent",
        }
        response = await client.post(_BASE_URL, json=payload)
        assert response.status_code == 201
        body = response.json()
        assert body["data"]["description"] is None
        assert body["data"]["display_order"] == 0

    @pytest.mark.asyncio
    async def test_create_rejects_markdown_without_heading(
        self, client: AsyncClient
    ) -> None:
        """Markdown without headings is rejected."""
        payload = {
            "name": "No Heading",
            "markdown_content": "Just plain text without any heading.",
        }
        response = await client.post(_BASE_URL, json=payload)
        assert response.status_code == 400
        body = response.json()
        assert "heading" in body["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_create_rejects_empty_markdown(self, client: AsyncClient) -> None:
        """Empty markdown is rejected by Pydantic validation."""
        payload = {
            "name": "Empty",
            "markdown_content": "",
        }
        response = await client.post(_BASE_URL, json=payload)
        # App converts Pydantic 422 → 400 via validation_error_handler
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_rejects_extra_fields(self, client: AsyncClient) -> None:
        """Extra fields are rejected."""
        payload = {
            "name": "Test",
            "markdown_content": "# Resume",
            "is_system": True,
        }
        response = await client.post(_BASE_URL, json=payload)
        # App converts Pydantic 422 → 400 via validation_error_handler
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        payload = {
            "name": "Test",
            "markdown_content": "# Resume",
        }
        response = await unauthenticated_client.post(_BASE_URL, json=payload)
        assert response.status_code == 401


# =============================================================================
# Update Template
# =============================================================================


class TestUpdateResumeTemplate:
    """PATCH /api/v1/resume-templates/{id} — update user template."""

    @pytest.mark.asyncio
    async def test_update_own_template(
        self, client: AsyncClient, user_template: ResumeTemplate
    ) -> None:
        """User can update their own template."""
        payload = {"name": "Updated Name", "description": "Updated desc"}
        response = await client.patch(f"{_BASE_URL}/{user_template.id}", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["name"] == "Updated Name"
        assert body["data"]["description"] == "Updated desc"
        # Unchanged fields preserved
        assert body["data"]["markdown_content"] == _VALID_MARKDOWN

    @pytest.mark.asyncio
    async def test_update_markdown_content(
        self, client: AsyncClient, user_template: ResumeTemplate
    ) -> None:
        """Can update markdown content with valid markdown."""
        new_markdown = "# Updated\n\n## New Section\n\nNew content"
        payload = {"markdown_content": new_markdown}
        response = await client.patch(f"{_BASE_URL}/{user_template.id}", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["markdown_content"] == new_markdown

    @pytest.mark.asyncio
    async def test_update_rejects_markdown_without_heading(
        self, client: AsyncClient, user_template: ResumeTemplate
    ) -> None:
        """Markdown without headings is rejected on update too."""
        payload = {"markdown_content": "No heading here."}
        response = await client.patch(f"{_BASE_URL}/{user_template.id}", json=payload)
        assert response.status_code == 400
        body = response.json()
        assert "heading" in body["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_update_system_template_returns_422(
        self, client: AsyncClient, system_template: ResumeTemplate
    ) -> None:
        """System templates cannot be modified."""
        payload = {"name": "Hacked Name"}
        response = await client.patch(f"{_BASE_URL}/{system_template.id}", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_other_users_template_returns_404(
        self, client: AsyncClient, other_user_template: ResumeTemplate
    ) -> None:
        """Cannot update another user's template."""
        payload = {"name": "Stolen"}
        response = await client.patch(
            f"{_BASE_URL}/{other_user_template.id}", json=payload
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_missing_id_returns_404(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        payload = {"name": "Ghost"}
        response = await client.patch(f"{_BASE_URL}/{_MISSING_UUID}", json=payload)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_partial_update_preserves_unchanged_fields(
        self, client: AsyncClient, user_template: ResumeTemplate
    ) -> None:
        """Only provided fields are updated; others remain unchanged."""
        payload = {"name": "New Name Only"}
        response = await client.patch(f"{_BASE_URL}/{user_template.id}", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["name"] == "New Name Only"
        assert body["data"]["description"] == "User's own template"
        assert body["data"]["markdown_content"] == _VALID_MARKDOWN


# =============================================================================
# Delete Template
# =============================================================================


class TestDeleteResumeTemplate:
    """DELETE /api/v1/resume-templates/{id} — delete user template."""

    @pytest.mark.asyncio
    async def test_delete_own_template(
        self, client: AsyncClient, user_template: ResumeTemplate
    ) -> None:
        """User can delete their own template."""
        response = await client.delete(f"{_BASE_URL}/{user_template.id}")
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_system_template_returns_422(
        self, client: AsyncClient, system_template: ResumeTemplate
    ) -> None:
        """System templates cannot be deleted."""
        response = await client.delete(f"{_BASE_URL}/{system_template.id}")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_delete_other_users_template_returns_404(
        self, client: AsyncClient, other_user_template: ResumeTemplate
    ) -> None:
        """Cannot delete another user's template."""
        response = await client.delete(f"{_BASE_URL}/{other_user_template.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_missing_id_returns_404(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        response = await client.delete(f"{_BASE_URL}/{_MISSING_UUID}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.delete(f"{_BASE_URL}/{_MISSING_UUID}")
        assert response.status_code == 401
