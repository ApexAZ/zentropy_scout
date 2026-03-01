"""Tests for authentication dependencies.

REQ-013 §7.1, REQ-006 §6.1: Tests cover JWT validation (hosted mode),
local-first fallback (auth disabled), token revocation, and error cases.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException

from app.api.deps import get_current_user, get_current_user_id
from tests.conftest import TEST_AUTH_SECRET

_TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_TEST_AUDIENCE = "zentropy-scout"
_TEST_ISSUER = "zentropy-scout"


def _make_jwt(
    *,
    sub: str = str(_TEST_USER_ID),
    aud: str = _TEST_AUDIENCE,
    iss: str = _TEST_ISSUER,
    exp: datetime | None = None,
    iat: datetime | None = None,
    secret: str = TEST_AUTH_SECRET,
    extra_claims: dict | None = None,
    exclude_claims: set[str] | None = None,
) -> str:
    """Build a signed JWT for testing.

    Args:
        sub: Subject claim (user ID).
        aud: Audience claim.
        iss: Issuer claim.
        exp: Expiration time. Defaults to 1 hour from now.
        iat: Issued-at time. Defaults to now.
        secret: Signing secret.
        extra_claims: Additional claims to include.
        exclude_claims: Claim names to omit from the payload.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(UTC)
    payload: dict = {
        "sub": sub,
        "aud": aud,
        "iss": iss,
        "exp": exp or (now + timedelta(hours=1)),
        "iat": iat or now,
    }
    if extra_claims:
        payload.update(extra_claims)
    if exclude_claims:
        for claim in exclude_claims:
            payload.pop(claim, None)
    return jwt.encode(payload, secret, algorithm="HS256")


def _mock_request(cookie_value: str | None = None) -> MagicMock:
    """Create a mock Request with optional JWT cookie.

    Args:
        cookie_value: JWT string to place in the cookie, or None for no cookie.

    Returns:
        Mock Request object.
    """
    mock = MagicMock()
    if cookie_value is not None:
        mock.cookies = {"zentropy.session-token": cookie_value}
    else:
        mock.cookies = {}
    return mock


def _mock_settings(
    *,
    auth_enabled: bool = True,
    default_user_id: uuid.UUID | None = None,
    auth_secret: str = TEST_AUTH_SECRET,
    auth_issuer: str = _TEST_ISSUER,
    auth_cookie_name: str = "zentropy.session-token",
) -> MagicMock:
    """Create a mock Settings object for auth tests.

    Args:
        auth_enabled: Whether JWT auth is active.
        default_user_id: Fallback user ID for local-first mode.
        auth_secret: JWT signing secret.
        auth_issuer: Expected issuer claim.
        auth_cookie_name: Cookie name to read JWT from.

    Returns:
        Mock settings object.
    """
    mock = MagicMock()
    mock.auth_enabled = auth_enabled
    mock.default_user_id = default_user_id
    mock.auth_secret = MagicMock()
    mock.auth_secret.get_secret_value.return_value = auth_secret
    mock.auth_issuer = auth_issuer
    mock.auth_cookie_name = auth_cookie_name
    return mock


def _mock_db(token_invalidated_before: datetime | None = None) -> AsyncMock:
    """Create a mock AsyncSession for revocation check.

    Args:
        token_invalidated_before: Value to return from the revocation query.
            None means no revocation timestamp (token is valid).

    Returns:
        Mock AsyncSession.
    """
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = token_invalidated_before
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result
    return mock_db


# =============================================================================
# Auth Disabled (Local-First Mode)
# =============================================================================


class TestAuthDisabled:
    """Tests for auth_enabled=False (local-first mode)."""

    async def test_returns_default_user_id(self):
        """Should return DEFAULT_USER_ID when auth is disabled."""
        settings = _mock_settings(auth_enabled=False, default_user_id=_TEST_USER_ID)
        request = _mock_request()
        db = _mock_db()

        with patch("app.api.deps.settings", settings):
            result = await get_current_user_id(request, db)
        assert result == _TEST_USER_ID

    async def test_raises_401_when_no_default_user_id(self):
        """Should raise 401 when auth disabled and no DEFAULT_USER_ID."""
        settings = _mock_settings(auth_enabled=False, default_user_id=None)
        request = _mock_request()
        db = _mock_db()

        with patch("app.api.deps.settings", settings):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request, db)
            assert exc_info.value.status_code == 401

    async def test_skips_jwt_validation_when_disabled(self):
        """Should NOT attempt JWT decode when auth is disabled."""
        settings = _mock_settings(auth_enabled=False, default_user_id=_TEST_USER_ID)
        # Request has a JWT cookie, but it should be ignored
        token = _make_jwt()
        request = _mock_request(cookie_value=token)
        db = _mock_db()

        with (
            patch("app.api.deps.settings", settings),
            patch("app.api.deps.jwt") as mock_jwt,
        ):
            await get_current_user_id(request, db)
            mock_jwt.decode.assert_not_called()


# =============================================================================
# JWT Validation (Hosted Mode)
# =============================================================================


class TestJwtValidation:
    """Tests for auth_enabled=True JWT cookie validation."""

    async def test_valid_jwt_returns_user_id(self):
        """Valid JWT in cookie should return the user UUID from sub claim."""
        token = _make_jwt()
        settings = _mock_settings()
        request = _mock_request(cookie_value=token)
        db = _mock_db()

        with patch("app.api.deps.settings", settings):
            result = await get_current_user_id(request, db)
        assert result == _TEST_USER_ID

    async def test_missing_cookie_raises_401(self):
        """Missing auth cookie should raise 401."""
        settings = _mock_settings()
        request = _mock_request(cookie_value=None)
        db = _mock_db()

        with patch("app.api.deps.settings", settings):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request, db)
            assert exc_info.value.status_code == 401

    async def test_expired_jwt_raises_401(self):
        """Expired JWT should raise 401."""
        expired = datetime.now(UTC) - timedelta(hours=1)
        token = _make_jwt(exp=expired)
        settings = _mock_settings()
        request = _mock_request(cookie_value=token)
        db = _mock_db()

        with patch("app.api.deps.settings", settings):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request, db)
            assert exc_info.value.status_code == 401

    async def test_invalid_signature_raises_401(self):
        """JWT signed with wrong secret should raise 401."""
        token = _make_jwt(secret="wrong-secret-that-is-also-long-enough")  # nosec B106
        settings = _mock_settings()
        request = _mock_request(cookie_value=token)
        db = _mock_db()

        with patch("app.api.deps.settings", settings):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request, db)
            assert exc_info.value.status_code == 401

    async def test_wrong_audience_raises_401(self):
        """JWT with wrong audience claim should raise 401."""
        token = _make_jwt(aud="wrong-audience")
        settings = _mock_settings()
        request = _mock_request(cookie_value=token)
        db = _mock_db()

        with patch("app.api.deps.settings", settings):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request, db)
            assert exc_info.value.status_code == 401

    async def test_wrong_issuer_raises_401(self):
        """JWT with wrong issuer claim should raise 401."""
        token = _make_jwt(iss="wrong-issuer")
        settings = _mock_settings()
        request = _mock_request(cookie_value=token)
        db = _mock_db()

        with patch("app.api.deps.settings", settings):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request, db)
            assert exc_info.value.status_code == 401

    async def test_missing_sub_claim_raises_401(self):
        """JWT without sub claim should raise 401."""
        token = _make_jwt(exclude_claims={"sub"})
        settings = _mock_settings()
        request = _mock_request(cookie_value=token)
        db = _mock_db()

        with patch("app.api.deps.settings", settings):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request, db)
            assert exc_info.value.status_code == 401

    async def test_invalid_sub_uuid_raises_401(self):
        """JWT with non-UUID sub claim should raise 401."""
        token = _make_jwt(sub="not-a-valid-uuid")
        settings = _mock_settings()
        request = _mock_request(cookie_value=token)
        db = _mock_db()

        with patch("app.api.deps.settings", settings):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request, db)
            assert exc_info.value.status_code == 401

    async def test_malformed_token_raises_401(self):
        """Garbage string as JWT should raise 401."""
        settings = _mock_settings()
        request = _mock_request(cookie_value="not.a.jwt")
        db = _mock_db()

        with patch("app.api.deps.settings", settings):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request, db)
            assert exc_info.value.status_code == 401

    async def test_empty_token_raises_401(self):
        """Empty string as JWT should raise 401."""
        settings = _mock_settings()
        request = _mock_request(cookie_value="")
        db = _mock_db()

        with patch("app.api.deps.settings", settings):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request, db)
            assert exc_info.value.status_code == 401

    async def test_error_detail_is_generic(self):
        """401 errors should use generic detail to prevent info leakage."""
        settings = _mock_settings()
        request = _mock_request(cookie_value=None)
        db = _mock_db()

        with patch("app.api.deps.settings", settings):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request, db)
            detail = exc_info.value.detail
            assert detail["code"] == "UNAUTHORIZED"

    async def test_missing_iat_raises_401(self):
        """JWT without iat claim should be rejected.

        Security: Missing iat would bypass token_invalidated_before revocation.
        """
        token = _make_jwt(exclude_claims={"iat"})
        settings = _mock_settings()
        request = _mock_request(cookie_value=token)
        db = _mock_db()

        with patch("app.api.deps.settings", settings):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request, db)
            assert exc_info.value.status_code == 401

    async def test_none_algorithm_raises_401(self):
        """JWT with 'none' algorithm must be rejected (algorithm confusion).

        Defense-in-depth: PyJWT rejects alg=none when algorithms=["HS256"],
        but this test ensures the protection holds.
        """
        import base64
        import json

        payload = {
            "sub": str(_TEST_USER_ID),
            "aud": _TEST_AUDIENCE,
            "iss": _TEST_ISSUER,
            "exp": (datetime.now(UTC) + timedelta(hours=1)).timestamp(),
            "iat": datetime.now(UTC).timestamp(),
        }
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "none", "typ": "JWT"}).encode()
        ).rstrip(b"=")
        body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
        token = f"{header.decode()}.{body.decode()}."

        settings = _mock_settings()
        request = _mock_request(cookie_value=token)
        db = _mock_db()

        with patch("app.api.deps.settings", settings):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request, db)
            assert exc_info.value.status_code == 401


# =============================================================================
# Token Revocation
# =============================================================================


class TestTokenRevocation:
    """Tests for token_invalidated_before revocation check."""

    async def test_revoked_token_raises_401(self):
        """JWT issued before token_invalidated_before should be rejected."""
        issued_at = datetime.now(UTC) - timedelta(hours=2)
        invalidated_at = datetime.now(UTC) - timedelta(hours=1)
        token = _make_jwt(iat=issued_at)
        settings = _mock_settings()
        request = _mock_request(cookie_value=token)
        db = _mock_db(token_invalidated_before=invalidated_at)

        with patch("app.api.deps.settings", settings):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request, db)
            assert exc_info.value.status_code == 401

    async def test_valid_token_after_revocation_succeeds(self):
        """JWT issued after token_invalidated_before should be accepted."""
        invalidated_at = datetime.now(UTC) - timedelta(hours=2)
        issued_at = datetime.now(UTC) - timedelta(hours=1)
        token = _make_jwt(iat=issued_at)
        settings = _mock_settings()
        request = _mock_request(cookie_value=token)
        db = _mock_db(token_invalidated_before=invalidated_at)

        with patch("app.api.deps.settings", settings):
            result = await get_current_user_id(request, db)
        assert result == _TEST_USER_ID

    async def test_no_revocation_timestamp_succeeds(self):
        """NULL token_invalidated_before should accept all valid JWTs."""
        token = _make_jwt()
        settings = _mock_settings()
        request = _mock_request(cookie_value=token)
        db = _mock_db(token_invalidated_before=None)

        with patch("app.api.deps.settings", settings):
            result = await get_current_user_id(request, db)
        assert result == _TEST_USER_ID

    async def test_token_issued_at_revocation_time_is_accepted(self):
        """JWT issued at exactly token_invalidated_before should be accepted.

        Design decision: strict less-than means 'issued before' not 'at or before'.
        Note: microsecond=0 ensures JWT iat (integer seconds) matches
        datetime.timestamp() exactly, avoiding precision mismatch.
        """
        now = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=1)
        token = _make_jwt(iat=now)
        settings = _mock_settings()
        request = _mock_request(cookie_value=token)
        db = _mock_db(token_invalidated_before=now)

        with patch("app.api.deps.settings", settings):
            result = await get_current_user_id(request, db)
        assert result == _TEST_USER_ID

    async def test_revocation_queries_correct_user(self):
        """Revocation check should query the user from the JWT sub claim."""
        token = _make_jwt()
        settings = _mock_settings()
        request = _mock_request(cookie_value=token)
        db = _mock_db()

        with patch("app.api.deps.settings", settings):
            await get_current_user_id(request, db)

        # Verify the DB was queried (revocation check happened)
        db.execute.assert_called_once()


# =============================================================================
# get_current_user (User Object Lookup)
# =============================================================================


class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    async def test_returns_user_when_found(self):
        """Should return User object when user exists in database."""
        test_id = uuid.uuid4()
        mock_user = MagicMock()
        mock_user.id = test_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await get_current_user(user_id=test_id, db=mock_db)
        assert result == mock_user

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
