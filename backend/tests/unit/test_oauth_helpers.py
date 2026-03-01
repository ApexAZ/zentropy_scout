"""Tests for OAuth helpers — PKCE, state cookies, and provider configs.

REQ-013 §4.1, §4.2, §10.4: PKCE code verifier/challenge, state parameter
management via signed cookies, and provider endpoint configuration.
"""

import base64
import hashlib
import re
import time

import jwt
import pytest

from app.core.oauth import (
    OAuthProviderConfig,
    create_oauth_state_cookie,
    generate_code_challenge,
    generate_code_verifier,
    get_provider_config,
    validate_oauth_state_cookie,
)
from tests.conftest import TEST_AUTH_SECRET

# ===================================================================
# PKCE Code Verifier / Challenge (RFC 7636)
# ===================================================================


class TestGenerateCodeVerifier:
    """Tests for PKCE code verifier generation."""

    def test_uses_only_unreserved_characters(self):
        """Code verifier must use only unreserved characters per RFC 7636."""
        verifier = generate_code_verifier()
        # RFC 7636 §4.1: unreserved = ALPHA / DIGIT / "-" / "." / "_" / "~"
        assert re.fullmatch(r"[A-Za-z0-9\-._~]+", verifier)

    def test_generates_unique_values(self):
        """Each call should produce a different verifier."""
        v1 = generate_code_verifier()
        v2 = generate_code_verifier()
        assert v1 != v2


class TestGenerateCodeChallenge:
    """Tests for PKCE code challenge generation."""

    def test_matches_s256_spec(self):
        """Code challenge must be BASE64URL(SHA256(code_verifier)) per RFC 7636."""
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        challenge = generate_code_challenge(verifier)

        # Manually compute expected value
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

        assert challenge == expected

    def test_deterministic_for_same_input(self):
        """Same verifier always produces the same challenge."""
        verifier = generate_code_verifier()
        c1 = generate_code_challenge(verifier)
        c2 = generate_code_challenge(verifier)
        assert c1 == c2


# ===================================================================
# State Cookie (CSRF protection + PKCE storage between requests)
# ===================================================================


class TestCreateOAuthStateCookie:
    """Tests for OAuth state cookie creation."""

    def test_returns_signed_jwt_string(self):
        """State cookie should be a valid JWT."""
        value = create_oauth_state_cookie(
            state="test-state",
            code_verifier="test-verifier",
            secret=TEST_AUTH_SECRET,
        )
        # Should be decodable as JWT
        payload = jwt.decode(value, TEST_AUTH_SECRET, algorithms=["HS256"])
        assert payload["state"] == "test-state"
        assert payload["code_verifier"] == "test-verifier"

    def test_includes_expiry(self):
        """State cookie JWT should expire (short-lived)."""
        value = create_oauth_state_cookie(
            state="s", code_verifier="v", secret=TEST_AUTH_SECRET
        )
        payload = jwt.decode(
            value, TEST_AUTH_SECRET, algorithms=["HS256"], options={"verify_exp": False}
        )
        assert "exp" in payload
        # Should expire within ~10 minutes
        assert payload["exp"] - time.time() <= 600


class TestValidateOAuthStateCookie:
    """Tests for OAuth state cookie validation."""

    def test_returns_code_verifier_on_valid_cookie(self):
        """Valid cookie + matching state returns the code_verifier."""
        cookie = create_oauth_state_cookie(
            state="good-state", code_verifier="my-verifier", secret=TEST_AUTH_SECRET
        )
        verifier = validate_oauth_state_cookie(
            cookie_value=cookie, expected_state="good-state", secret=TEST_AUTH_SECRET
        )
        assert verifier == "my-verifier"

    def test_returns_none_on_mismatched_state(self):
        """Mismatched state (CSRF attempt) returns None."""
        cookie = create_oauth_state_cookie(
            state="real-state", code_verifier="v", secret=TEST_AUTH_SECRET
        )
        result = validate_oauth_state_cookie(
            cookie_value=cookie, expected_state="forged-state", secret=TEST_AUTH_SECRET
        )
        assert result is None

    def test_returns_none_on_tampered_cookie(self):
        """Tampered (re-signed with wrong key) cookie returns None."""
        # Sign with a different secret
        bad_cookie = create_oauth_state_cookie(
            state="state",
            code_verifier="v",
            secret="wrong-secret-that-is-at-least-32-chars",  # gitleaks:allow
        )
        result = validate_oauth_state_cookie(
            cookie_value=bad_cookie, expected_state="state", secret=TEST_AUTH_SECRET
        )
        assert result is None

    def test_returns_none_on_expired_cookie(self):
        """Expired cookie returns None."""
        cookie = create_oauth_state_cookie(
            state="state",
            code_verifier="v",
            secret=TEST_AUTH_SECRET,
            ttl_seconds=0,
        )
        # Cookie expires immediately
        result = validate_oauth_state_cookie(
            cookie_value=cookie, expected_state="state", secret=TEST_AUTH_SECRET
        )
        assert result is None

    def test_returns_none_on_garbage_input(self):
        """Non-JWT garbage returns None."""
        result = validate_oauth_state_cookie(
            cookie_value="not-a-jwt", expected_state="state", secret=TEST_AUTH_SECRET
        )
        assert result is None


# ===================================================================
# Provider Configuration
# ===================================================================


class TestGetProviderConfig:
    """Tests for OAuth provider configuration."""

    def test_google_config_has_correct_endpoints(self):
        """Google provider has correct OAuth URLs and scopes."""
        config = get_provider_config("google")
        assert isinstance(config, OAuthProviderConfig)
        assert "accounts.google.com" in config.authorization_url
        assert "googleapis.com" in config.token_url
        assert (
            "googleapis.com" in config.userinfo_url or "google" in config.userinfo_url
        )
        assert "openid" in config.scopes
        assert "email" in config.scopes
        assert "profile" in config.scopes

    def test_linkedin_config_has_correct_endpoints(self):
        """LinkedIn provider has correct OAuth URLs and scopes."""
        config = get_provider_config("linkedin")
        assert isinstance(config, OAuthProviderConfig)
        assert "linkedin.com" in config.authorization_url
        assert "linkedin.com" in config.token_url
        assert "linkedin.com" in config.userinfo_url
        assert "openid" in config.scopes
        assert "email" in config.scopes
        assert "profile" in config.scopes

    def test_unknown_provider_raises_value_error(self):
        """Unsupported provider raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported"):
            get_provider_config("facebook")

    def test_provider_name_is_case_sensitive(self):
        """Provider name lookup is case-sensitive."""
        with pytest.raises(ValueError, match="Unsupported"):
            get_provider_config("Google")
