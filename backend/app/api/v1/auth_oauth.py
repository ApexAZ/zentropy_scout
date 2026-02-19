"""OAuth authentication endpoints.

REQ-013 §4.1, §4.2, §7.5: OAuth initiation and callback for
Google and LinkedIn. Uses PKCE for authorization code flow.
"""

import logging
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from starlette.responses import Response

from app.api.deps import DbSession
from app.core.account_linking import (
    AccountLinkingBlockedError,
    find_or_create_user_for_oauth,
)
from app.core.auth import create_jwt, set_auth_cookie
from app.core.config import settings
from app.core.errors import ValidationError
from app.core.oauth import (
    create_oauth_state_cookie,
    generate_code_challenge,
    generate_code_verifier,
    get_provider_config,
    validate_oauth_state_cookie,
)
from app.core.oauth_client import exchange_code_for_tokens, fetch_userinfo
from app.core.rate_limiting import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

# Cookie name for OAuth state/PKCE storage
_OAUTH_STATE_COOKIE = "oauth_state"

# Map provider names to settings attribute prefixes
_PROVIDER_CREDENTIALS = {
    "google": ("google_client_id", "google_client_secret"),
    "linkedin": ("linkedin_client_id", "linkedin_client_secret"),
}


def _get_api_callback_url(request: Request, provider: str) -> str:
    """Build the OAuth callback URL from the request's base URL.

    Args:
        request: FastAPI request.
        provider: Provider name.

    Returns:
        Full callback URL using the request's scheme and host.
    """
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/v1/auth/callback/{provider}"


# ===================================================================
# GET /auth/providers/{provider} — OAuth Initiation
# ===================================================================


@router.get("/providers/{provider}")
@limiter.limit("10/hour")
async def oauth_initiate(
    provider: str,
    request: Request,
) -> Response:
    """Redirect to OAuth provider's authorization URL.

    REQ-013 §4.1, §4.2: Generates PKCE code verifier + challenge,
    state parameter for CSRF protection, stores in signed cookie,
    and redirects to provider.

    Rate limit: 10 per hour per IP.
    """
    # Validate provider
    try:
        config = get_provider_config(provider)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    # Get client credentials
    cred_attrs = _PROVIDER_CREDENTIALS.get(provider)
    if not cred_attrs:
        raise ValidationError(f"Unsupported OAuth provider: {provider}")

    client_id = getattr(settings, cred_attrs[0])
    if not client_id:
        raise ValidationError(f"OAuth provider {provider} is not configured")

    # Generate PKCE code verifier + challenge
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    # Generate state parameter for CSRF protection
    state = secrets.token_urlsafe(32)

    # Store state + code_verifier in signed cookie
    state_cookie = create_oauth_state_cookie(
        state=state,
        code_verifier=code_verifier,
        secret=settings.auth_secret.get_secret_value(),
    )

    # Build authorization URL
    callback_url = _get_api_callback_url(request, provider)
    params = {
        "client_id": client_id,
        "redirect_uri": callback_url,
        "response_type": "code",
        "scope": " ".join(config.scopes),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    # Google-specific: request offline access for refresh token
    if provider == "google":
        params["access_type"] = "offline"
        params["prompt"] = "consent"

    auth_url = f"{config.authorization_url}?{urlencode(params)}"

    # Set state cookie and redirect
    redirect = RedirectResponse(url=auth_url, status_code=307)
    redirect.set_cookie(
        key=_OAUTH_STATE_COOKIE,
        value=state_cookie,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=600,  # 10 minutes
        path="/api/v1/auth/callback",
    )
    return redirect


# ===================================================================
# GET /auth/callback/{provider} — OAuth Callback
# ===================================================================


@router.get("/callback/{provider}")
@limiter.limit("20/hour")
async def oauth_callback(
    provider: str,
    request: Request,
    db: DbSession,
    code: str | None = None,
    state: str | None = None,
) -> Response:
    """Handle OAuth provider callback after user consent.

    REQ-013 §4.1, §4.2, §7.5: Validates state, exchanges code for tokens,
    fetches user info, creates/links account, issues JWT cookie, and
    redirects to frontend.
    """
    # Validate required parameters
    if not code:
        raise ValidationError("Missing authorization code")

    if not state:
        raise ValidationError("Missing state parameter")

    # Validate provider
    try:
        get_provider_config(provider)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    # Validate state cookie
    state_cookie = request.cookies.get(_OAUTH_STATE_COOKIE)
    if not state_cookie:
        raise ValidationError("Missing OAuth state cookie")

    code_verifier = validate_oauth_state_cookie(
        cookie_value=state_cookie,
        expected_state=state,
        secret=settings.auth_secret.get_secret_value(),
    )
    if not code_verifier:
        raise ValidationError("Invalid or expired OAuth state")

    # Exchange code for tokens
    callback_url = _get_api_callback_url(request, provider)
    try:
        tokens = await exchange_code_for_tokens(
            provider=provider,
            code=code,
            code_verifier=code_verifier,
            redirect_uri=callback_url,
        )
    except httpx.HTTPStatusError:
        logger.exception("OAuth token exchange failed", extra={"provider": provider})
        raise ValidationError("OAuth authentication failed") from None

    # Fetch user info
    access_token = tokens.get("access_token")
    if not access_token:
        raise ValidationError("OAuth provider did not return access token")

    try:
        userinfo = await fetch_userinfo(
            provider=provider,
            access_token=access_token,
        )
    except httpx.HTTPStatusError:
        logger.exception("OAuth userinfo fetch failed", extra={"provider": provider})
        raise ValidationError("Could not retrieve user information") from None

    # Extract user info
    provider_account_id = userinfo.get("sub", "")
    email = userinfo.get("email", "")
    email_verified = userinfo.get("email_verified", False)
    name = userinfo.get("name")
    image = userinfo.get("picture")

    if not email or not provider_account_id:
        raise ValidationError("OAuth provider did not return required user info")

    # Find or create user (account linking logic)
    try:
        user, _created = await find_or_create_user_for_oauth(
            db=db,
            email=email,
            email_verified_by_provider=email_verified,
            provider=provider,
            provider_account_id=provider_account_id,
            name=name,
            image=image,
        )
    except AccountLinkingBlockedError:
        logger.warning(
            "Account linking blocked",
            extra={"provider": provider},
        )
        raise ValidationError(
            "An account with this email already exists. "
            "Please sign in with your original method first."
        ) from None
    await db.commit()

    # Issue JWT cookie
    token = create_jwt(
        user_id=str(user.id),
        secret=settings.auth_secret.get_secret_value(),
    )

    # Redirect to frontend
    redirect_url = settings.frontend_url
    redirect = RedirectResponse(url=redirect_url, status_code=307)
    set_auth_cookie(redirect, token)

    # Clear state cookie
    redirect.delete_cookie(
        key=_OAUTH_STATE_COOKIE,
        path="/api/v1/auth/callback",
    )

    return redirect
