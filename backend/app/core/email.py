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


async def send_magic_link_email(
    *, to_email: str, token: str, purpose: str = "sign_in"
) -> None:
    """Send a magic link sign-in email via Resend.

    Constructs a verification URL pointing to the backend directly. The user
    clicks the link, the backend verifies the token, sets a JWT cookie, and
    redirects to the frontend.

    Args:
        to_email: Recipient email address.
        token: Plain (unhashed) magic link token.
        purpose: ``"sign_in"`` or ``"password_reset"``. Passed through to
            the verify endpoint so it can issue a password-reset JWT.
    """
    url_params: dict[str, str] = {"token": token, "identifier": to_email}
    if purpose == "password_reset":
        url_params["purpose"] = purpose
    params = urlencode(url_params, quote_via=quote)
    verify_url = f"{settings.backend_url}/api/v1/auth/verify-magic-link?{params}"

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
