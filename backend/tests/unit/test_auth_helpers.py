"""Tests for auth helper functions.

REQ-013 §7.5, §10.8: JWT creation, cookie management, password validation,
and HIBP breach checking.
"""

import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import bcrypt
import jwt
import pytest

from app.core.auth import (
    DUMMY_HASH,
    check_password_breached,
    create_jwt,
    set_auth_cookie,
    validate_password_strength,
)
from app.core.errors import ValidationError

# Test-only secret for JWT tests
_TEST_SECRET = "test-secret-key-that-is-at-least-32-characters-long"  # nosec B105  # gitleaks:allow


class TestCreateJwt:
    """Tests for create_jwt() helper."""

    def test_returns_decodable_jwt(self):
        """JWT can be decoded with the same secret."""
        token = create_jwt(
            user_id="00000000-0000-0000-0000-000000000001",
            secret=_TEST_SECRET,
        )
        payload = jwt.decode(
            token,
            _TEST_SECRET,
            algorithms=["HS256"],
            audience="zentropy-scout",
            issuer="zentropy-scout",
        )
        assert payload["sub"] == "00000000-0000-0000-0000-000000000001"

    def test_contains_required_claims(self):
        """JWT has sub, aud, iss, exp, iat claims."""
        token = create_jwt(
            user_id="00000000-0000-0000-0000-000000000001",
            secret=_TEST_SECRET,
        )
        payload = jwt.decode(
            token,
            _TEST_SECRET,
            algorithms=["HS256"],
            audience="zentropy-scout",
            issuer="zentropy-scout",
        )
        for claim in ("sub", "aud", "iss", "exp", "iat"):
            assert claim in payload, f"Missing claim: {claim}"
        assert payload["aud"] == "zentropy-scout"
        assert payload["iss"] == "zentropy-scout"

    def test_custom_expiration(self):
        """Expiration can be customized via expires_delta."""
        token = create_jwt(
            user_id="00000000-0000-0000-0000-000000000001",
            secret=_TEST_SECRET,
            expires_delta=timedelta(minutes=5),
        )
        payload = jwt.decode(
            token,
            _TEST_SECRET,
            algorithms=["HS256"],
            audience="zentropy-scout",
            issuer="zentropy-scout",
        )
        now = datetime.now(UTC).timestamp()
        seconds_until_exp = payload["exp"] - now
        assert 280 < seconds_until_exp < 310

    def test_default_expiration_is_one_hour(self):
        """Default expiration is 1 hour."""
        token = create_jwt(
            user_id="00000000-0000-0000-0000-000000000001",
            secret=_TEST_SECRET,
        )
        payload = jwt.decode(
            token,
            _TEST_SECRET,
            algorithms=["HS256"],
            audience="zentropy-scout",
            issuer="zentropy-scout",
        )
        now = datetime.now(UTC).timestamp()
        seconds_until_exp = payload["exp"] - now
        assert 3580 < seconds_until_exp < 3610


class TestSetAuthCookie:
    """Tests for set_auth_cookie() helper."""

    def test_sets_cookie_with_correct_name(self):
        """Cookie name matches settings.auth_cookie_name."""
        response = Mock()
        set_auth_cookie(response, "test-token")
        response.set_cookie.assert_called_once()
        kwargs = response.set_cookie.call_args.kwargs
        assert kwargs["key"] == "zentropy.session-token"

    def test_cookie_is_httponly(self):
        """Cookie has httponly flag (prevents XSS cookie theft)."""
        response = Mock()
        set_auth_cookie(response, "test-token")
        kwargs = response.set_cookie.call_args.kwargs
        assert kwargs["httponly"] is True

    def test_cookie_value_is_token(self):
        """Cookie value is the JWT token."""
        response = Mock()
        set_auth_cookie(response, "my-jwt-token")
        kwargs = response.set_cookie.call_args.kwargs
        assert kwargs["value"] == "my-jwt-token"

    def test_cookie_path_is_root(self):
        """Cookie path is / so it's sent with all requests."""
        response = Mock()
        set_auth_cookie(response, "test-token")
        kwargs = response.set_cookie.call_args.kwargs
        assert kwargs["path"] == "/"


class TestValidatePasswordStrength:
    """Tests for validate_password_strength().

    REQ-013 §10.8: 8-128 chars, letter + number + special character.
    """

    def test_valid_password_passes(self):
        """Strong password passes without raising."""
        validate_password_strength("ValidP@ss1")

    def test_too_short_raises(self):
        """Password under 8 characters raises ValidationError."""
        with pytest.raises(ValidationError, match="at least 8 characters"):
            validate_password_strength("Sh0rt!")

    def test_too_long_raises(self):
        """Password over 128 characters raises ValidationError."""
        with pytest.raises(ValidationError, match="at most 128 characters"):
            validate_password_strength("A1!" + "a" * 126)

    def test_no_letter_raises(self):
        """Password without letters raises ValidationError."""
        with pytest.raises(ValidationError, match="at least one letter"):
            validate_password_strength("12345678!")

    def test_no_number_raises(self):
        """Password without numbers raises ValidationError."""
        with pytest.raises(ValidationError, match="at least one number"):
            validate_password_strength("Password!")

    def test_no_special_char_raises(self):
        """Password without special characters raises ValidationError."""
        with pytest.raises(ValidationError, match="at least one special character"):
            validate_password_strength("Password1")

    def test_exactly_8_chars_passes(self):
        """Minimum length boundary passes."""
        validate_password_strength("P@ssw0rd")

    def test_exactly_128_chars_passes(self):
        """Maximum length boundary passes."""
        validate_password_strength("A1!" + "a" * 125)


class TestCheckPasswordBreached:
    """Tests for check_password_breached() HIBP k-anonymity check.

    REQ-013 §10.8: Uses Have I Been Pwned Pwned Passwords API.
    """

    async def test_not_breached_returns_false(self):
        """Password not in breach database returns False."""
        with patch(
            "app.core.auth._fetch_hibp_range",
            new_callable=AsyncMock,
            return_value="OTHER_SUFFIX:5\nDIFFERENT_SUFFIX:10",
        ):
            result = await check_password_breached("UniqueP@ss1")
            assert result is False

    async def test_breached_returns_true(self):
        """Password found in breach database returns True."""
        password = "password"
        sha1 = hashlib.sha1(password.encode()).hexdigest().upper()  # nosec B324
        suffix = sha1[5:]

        with patch(
            "app.core.auth._fetch_hibp_range",
            new_callable=AsyncMock,
            return_value=f"OTHER:5\n{suffix}:1234\nANOTHER:10",
        ):
            result = await check_password_breached(password)
            assert result is True

    async def test_api_error_returns_false(self):
        """HIBP API failure fails open (allows password)."""
        with patch(
            "app.core.auth._fetch_hibp_range",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await check_password_breached("SomeP@ss1")
            assert result is False

    async def test_uses_k_anonymity_prefix(self):
        """Only first 5 chars of SHA-1 hash sent to HIBP API."""
        password = "TestP@ss1"
        sha1 = hashlib.sha1(password.encode()).hexdigest().upper()  # nosec B324
        prefix = sha1[:5]

        with patch(
            "app.core.auth._fetch_hibp_range",
            new_callable=AsyncMock,
            return_value="SUFFIX:1",
        ) as mock_fetch:
            await check_password_breached(password)
            mock_fetch.assert_called_once_with(prefix)


class TestDummyHash:
    """Tests for DUMMY_HASH constant."""

    def test_is_valid_bcrypt(self):
        """DUMMY_HASH is a valid bcrypt hash (for timing defense)."""
        assert DUMMY_HASH.startswith(b"$2b$") or DUMMY_HASH.startswith(b"$2a$")

    def test_comparison_completes_without_error(self):
        """bcrypt.checkpw with DUMMY_HASH returns False without crashing."""
        result = bcrypt.checkpw(b"anything", DUMMY_HASH)
        assert result is False
