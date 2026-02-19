"""OAuth HTTP client — token exchange and userinfo fetching.

REQ-013 §4.1, §4.2: HTTP client functions for exchanging authorization
codes for tokens and fetching user info from OAuth providers.
"""

from typing import Any

import httpx

from app.core.config import settings
from app.core.oauth import get_provider_config

# HTTP client timeout for OAuth token exchange and userinfo
_OAUTH_HTTP_TIMEOUT = 10.0

# Map provider names to settings attribute prefixes
_PROVIDER_CREDENTIALS = {
    "google": ("google_client_id", "google_client_secret"),
    "linkedin": ("linkedin_client_id", "linkedin_client_secret"),
}


async def exchange_code_for_tokens(
    *,
    provider: str,
    code: str,
    code_verifier: str,
    redirect_uri: str,
) -> dict[str, Any]:
    """Exchange authorization code for OAuth tokens.

    Args:
        provider: Provider name.
        code: Authorization code from callback.
        code_verifier: PKCE code verifier.
        redirect_uri: Callback URL used in initiation.

    Returns:
        Token response dict (access_token, id_token, refresh_token, etc.).

    Raises:
        httpx.HTTPStatusError: If token exchange fails.
    """
    config = get_provider_config(provider)
    cred_attrs = _PROVIDER_CREDENTIALS[provider]
    client_id = getattr(settings, cred_attrs[0])
    client_secret = getattr(settings, cred_attrs[1]).get_secret_value()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            config.token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
                "code_verifier": code_verifier,
            },
            timeout=_OAUTH_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result


async def fetch_userinfo(
    *,
    provider: str,
    access_token: str,
) -> dict[str, Any]:
    """Fetch user info from the OAuth provider.

    Args:
        provider: Provider name.
        access_token: OAuth access token.

    Returns:
        User info dict (sub, email, email_verified, name, picture).

    Raises:
        httpx.HTTPStatusError: If userinfo request fails.
    """
    config = get_provider_config(provider)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            config.userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=_OAUTH_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result
