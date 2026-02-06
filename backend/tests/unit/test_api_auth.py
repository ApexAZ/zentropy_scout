"""Tests for authentication dependencies.

REQ-006 §6.1: Local-first auth with DEFAULT_USER_ID.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.deps import get_current_user, get_current_user_id


class TestGetCurrentUserId:
    """Tests for get_current_user_id dependency."""

    def test_returns_default_user_id_when_set(self):
        """Should return DEFAULT_USER_ID from settings when configured."""
        test_id = uuid.uuid4()
        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.default_user_id = test_id
            result = get_current_user_id()
            assert result == test_id

    def test_raises_401_when_no_default_user(self):
        """Should raise HTTPException 401 when no user configured."""
        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.default_user_id = None
            with pytest.raises(HTTPException) as exc_info:
                get_current_user_id()
            assert exc_info.value.status_code == 401

    def test_error_detail_has_unauthorized_code(self):
        """401 error should include UNAUTHORIZED code in detail."""
        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.default_user_id = None
            with pytest.raises(HTTPException) as exc_info:
                get_current_user_id()
            assert exc_info.value.detail["code"] == "UNAUTHORIZED"


class TestGetCurrentUser:
    """Tests for get_current_user dependency.

    Note: db.execute is async but result.scalar_one_or_none is sync.
    """

    @pytest.mark.asyncio
    async def test_returns_user_when_found(self):
        """Should return User object when user exists in database."""
        test_id = uuid.uuid4()
        mock_user = MagicMock()
        mock_user.id = test_id

        # db.execute is async, returns a result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await get_current_user(user_id=test_id, db=mock_db)
        assert result == mock_user

    @pytest.mark.asyncio
    async def test_raises_401_when_user_not_found(self):
        """Should raise 401 when user_id not found in database."""
        test_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(user_id=test_id, db=mock_db)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_user_not_found_has_unauthorized_code(self):
        """User not found error should have UNAUTHORIZED code."""
        test_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(user_id=test_id, db=mock_db)
        assert exc_info.value.detail["code"] == "UNAUTHORIZED"
