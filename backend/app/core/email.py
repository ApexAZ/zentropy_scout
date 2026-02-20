"""Email sending via Resend API.

REQ-013 §3.3, §4.4: Simple HTTP POST to Resend for magic link emails.
Uses plain-text email format initially (custom templates deferred per §12).
"""

import logging
from urllib.parse import quote, urlencode

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_RESEND_API_URL = "https://api.resend.com/emails"
_RESEND_TIMEOUT = 10.0


async def send_magic_link_email(*, to_email: str, token: str) -> None:
    """Send a magic link sign-in email via Resend.

    Constructs a verification URL using frontend_url. This assumes the
    frontend proxies /api/v1/ requests to the FastAPI backend. The user
    clicks the link, the backend verifies the token and sets a JWT cookie,
    then redirects to the frontend.

    Args:
        to_email: Recipient email address.
        token: Plain (unhashed) magic link token.
    """
    params = urlencode({"token": token, "identifier": to_email}, quote_via=quote)
    verify_url = f"{settings.frontend_url}/api/v1/auth/verify-magic-link?{params}"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _RESEND_API_URL,
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key.get_secret_value()}",
                },
                json={
                    "from": settings.email_from,
                    "to": to_email,
                    "subject": "Sign in to Zentropy Scout",
                    "text": (
                        f"Click this link to sign in:\n\n{verify_url}\n\n"
                        "This link expires in 10 minutes. "
                        "If you didn't request this, you can safely ignore this email."
                    ),
                },
                timeout=_RESEND_TIMEOUT,
            )
            resp.raise_for_status()
    except Exception:
        logger.warning("Failed to send magic link email", exc_info=True)
