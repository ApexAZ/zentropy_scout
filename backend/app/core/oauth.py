"""OAuth utilities — PKCE, state cookies, and provider configuration.

REQ-013 §4.1, §4.2, §10.4: PKCE code verifier/challenge generation,
state parameter management via signed JWT cookies, and OAuth provider
endpoint configuration for Google and LinkedIn.
"""

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass

import jwt

# PKCE code verifier length (RFC 7636 allows 43-128)
_VERIFIER_LENGTH = 128

# Characters allowed in PKCE code verifier (RFC 7636 §4.1)
# unreserved = ALPHA / DIGIT / "-" / "." / "_" / "~"
_UNRESERVED_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"

# Default TTL for OAuth state cookie (10 minutes)
_DEFAULT_STATE_TTL = 600


def generate_code_verifier() -> str:
    """Generate a PKCE code verifier.

    RFC 7636 §4.1: 128-character string from unreserved characters.

    Returns:
        Random 128-character code verifier string.
    """
    return "".join(secrets.choice(_UNRESERVED_CHARS) for _ in range(_VERIFIER_LENGTH))


def generate_code_challenge(verifier: str) -> str:
    """Generate a PKCE code challenge from a verifier.

    RFC 7636 §4.2: BASE64URL(SHA256(code_verifier)), no padding.

    Args:
        verifier: PKCE code verifier string.

    Returns:
        Base64url-encoded SHA256 hash without padding.
    """
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def create_oauth_state_cookie(
    *,
    state: str,
    code_verifier: str,
    secret: str,
    ttl_seconds: int = _DEFAULT_STATE_TTL,
) -> str:
    """Create a signed JWT cookie containing OAuth state and PKCE verifier.

    Stored as a cookie between the initiation redirect and callback.
    Signed with HS256 to prevent tampering.

    Args:
        state: Random state parameter for CSRF protection.
        code_verifier: PKCE code verifier to use in token exchange.
        secret: HMAC signing secret.
        ttl_seconds: Cookie expiry in seconds (default 10 minutes).

    Returns:
        Signed JWT string.
    """
    payload = {
        "state": state,
        "code_verifier": code_verifier,
        "exp": int(time.time()) + ttl_seconds,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def validate_oauth_state_cookie(
    *,
    cookie_value: str,
    expected_state: str,
    secret: str,
) -> str | None:
    """Validate an OAuth state cookie and return the PKCE code verifier.

    Verifies JWT signature, expiry, and state match. Returns the
    code_verifier if valid, None if any check fails.

    Args:
        cookie_value: JWT string from the oauth_state cookie.
        expected_state: State parameter from the callback query string.
        secret: HMAC signing secret.

    Returns:
        Code verifier string if valid, None otherwise.
    """
    try:
        payload = jwt.decode(cookie_value, secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None

    if payload.get("state") != expected_state:
        return None

    return payload.get("code_verifier")


# ===================================================================
# OAuth Provider Configuration
# ===================================================================


@dataclass(frozen=True)
class OAuthProviderConfig:
    """Configuration for an OAuth provider.

    Attributes:
        authorization_url: Provider's authorization endpoint.
        token_url: Provider's token exchange endpoint.
        userinfo_url: Provider's userinfo endpoint.
        scopes: OAuth scopes to request.
    """

    authorization_url: str
    token_url: str
    userinfo_url: str
    scopes: tuple[str, ...]


_PROVIDERS: dict[str, OAuthProviderConfig] = {
    "google": OAuthProviderConfig(  # nosec B106 — token_url is an endpoint, not a password
        authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        scopes=("openid", "email", "profile"),
    ),
    "linkedin": OAuthProviderConfig(  # nosec B106 — token_url is an endpoint, not a password
        authorization_url="https://www.linkedin.com/oauth/v2/authorization",
        token_url="https://www.linkedin.com/oauth/v2/accessToken",
        userinfo_url="https://api.linkedin.com/v2/userinfo",
        scopes=("openid", "email", "profile"),
    ),
}


def get_provider_config(provider: str) -> OAuthProviderConfig:
    """Get OAuth configuration for a provider.

    Args:
        provider: Provider name (e.g., "google", "linkedin").

    Returns:
        OAuthProviderConfig for the provider.

    Raises:
        ValueError: If provider is not supported.
    """
    config = _PROVIDERS.get(provider)
    if config is None:
        msg = f"Unsupported OAuth provider: {provider}"
        raise ValueError(msg)
    return config
