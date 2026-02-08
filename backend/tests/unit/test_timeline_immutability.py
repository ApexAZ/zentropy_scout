"""Tests for timeline event immutability.

REQ-004 §9: Timeline events are immutable — once created, cannot be
edited or deleted. PATCH and DELETE endpoints return 405 Method Not Allowed.

REQ-012 Appendix A.2: Backend stubs for timeline event PATCH/DELETE
must return 405 to enforce append-only behavior.
"""

import pytest
from httpx import AsyncClient

_TEST_APP_ID = "123e4567-e89b-12d3-a456-426614174000"
_TEST_EVENT_ID = "223e4567-e89b-12d3-a456-426614174000"


class TestTimelineEventPatchReturns405:
    """PATCH /applications/{id}/timeline/{event_id} returns 405."""

    @pytest.mark.asyncio
    async def test_patch_timeline_event_returns_405(self, client: AsyncClient) -> None:
        """PATCH on a timeline event returns 405 Method Not Allowed."""
        app_id = _TEST_APP_ID
        event_id = _TEST_EVENT_ID
        response = await client.patch(
            f"/api/v1/applications/{app_id}/timeline/{event_id}",
            json={"description": "Updated"},
        )
        assert response.status_code == 405

    @pytest.mark.asyncio
    async def test_patch_timeline_event_returns_error_body(
        self, client: AsyncClient
    ) -> None:
        """PATCH response body contains error code and message."""
        app_id = _TEST_APP_ID
        event_id = _TEST_EVENT_ID
        response = await client.patch(
            f"/api/v1/applications/{app_id}/timeline/{event_id}",
            json={},
        )
        body = response.json()
        assert body["error"]["code"] == "METHOD_NOT_ALLOWED"
        assert "immutable" in body["error"]["message"].lower()


class TestTimelineEventDeleteReturns405:
    """DELETE /applications/{id}/timeline/{event_id} returns 405."""

    @pytest.mark.asyncio
    async def test_delete_timeline_event_returns_405(self, client: AsyncClient) -> None:
        """DELETE on a timeline event returns 405 Method Not Allowed."""
        app_id = _TEST_APP_ID
        event_id = _TEST_EVENT_ID
        response = await client.delete(
            f"/api/v1/applications/{app_id}/timeline/{event_id}",
        )
        assert response.status_code == 405

    @pytest.mark.asyncio
    async def test_delete_timeline_event_returns_error_body(
        self, client: AsyncClient
    ) -> None:
        """DELETE response body contains error code and message."""
        app_id = _TEST_APP_ID
        event_id = _TEST_EVENT_ID
        response = await client.delete(
            f"/api/v1/applications/{app_id}/timeline/{event_id}",
        )
        body = response.json()
        assert body["error"]["code"] == "METHOD_NOT_ALLOWED"
        assert "immutable" in body["error"]["message"].lower()


class TestTimelineReadEndpointsStillWork:
    """Verify GET and POST endpoints remain accessible (sanity check)."""

    @pytest.mark.asyncio
    async def test_get_timeline_list_not_405(self, client: AsyncClient) -> None:
        """GET /applications/{id}/timeline does not return 405."""
        app_id = _TEST_APP_ID
        response = await client.get(f"/api/v1/applications/{app_id}/timeline")
        assert response.status_code != 405

    @pytest.mark.asyncio
    async def test_post_timeline_event_not_405(self, client: AsyncClient) -> None:
        """POST /applications/{id}/timeline does not return 405."""
        app_id = _TEST_APP_ID
        response = await client.post(
            f"/api/v1/applications/{app_id}/timeline",
            json={},
        )
        assert response.status_code != 405

    @pytest.mark.asyncio
    async def test_get_single_timeline_event_not_405(self, client: AsyncClient) -> None:
        """GET /applications/{id}/timeline/{event_id} does not return 405."""
        app_id = _TEST_APP_ID
        event_id = _TEST_EVENT_ID
        response = await client.get(
            f"/api/v1/applications/{app_id}/timeline/{event_id}",
        )
        assert response.status_code != 405
