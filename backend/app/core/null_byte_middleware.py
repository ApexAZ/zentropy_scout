"""ASGI middleware to strip null bytes from HTTP requests (CWE-158).

VULN-001: PostgreSQL rejects null bytes (\\x00) in UTF-8 strings, but
Pydantic's str validation passes them through. This middleware strips
null bytes at the ASGI transport level before they reach any handler.

Scope:
- Query strings: strips both literal \\x00 and percent-encoded %00
- JSON request bodies: parses JSON, recursively strips \\x00 from all
  string values and keys, re-serializes. This handles the \\u0000 JSON
  escape which produces null bytes after parsing.
- Binary uploads: NOT modified (multipart/form-data uses different
  Content-Type, so the JSON body handler does not activate)

This is a raw ASGI middleware (not BaseHTTPMiddleware) for direct access
to scope["query_string"] and the receive callable.
"""

from __future__ import annotations

import json
import re
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

_JSON_CONTENT_TYPE = b"application/json"
"""Content-Type prefix for JSON bodies (the only text format we strip)."""

_PERCENT_NULL_RE = re.compile(rb"%00", re.IGNORECASE)
"""Matches percent-encoded null bytes (%00) in raw query strings.

Case-insensitive to catch both ``%00`` and ``%0a``-adjacent patterns.
Note: double-encoding (``%2500``) is out of scope because Starlette only
decodes one level of percent-encoding.
"""

_MAX_JSON_BODY_SIZE = 10 * 1024 * 1024
"""Maximum JSON body size (bytes) the middleware will parse for sanitization.

Bodies exceeding this limit are passed through unsanitized to avoid
memory exhaustion. Downstream validators (Pydantic field limits, etc.)
still apply.
"""

_MAX_NESTING_DEPTH = 64
"""Maximum JSON nesting depth for recursive null byte stripping.

Prevents stack overflow on crafted deeply-nested payloads. Values beyond
this depth are passed through unsanitized.
"""


class NullByteMiddleware:
    """Strip null bytes from query strings and JSON request bodies.

    PostgreSQL cannot store null bytes in text columns. Without this
    middleware, a request containing %00 (query) or \\u0000 (JSON) causes
    asyncpg.CharacterNotInRepertoireError -> HTTP 500.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialize with the next ASGI application.

        Args:
            app: The next ASGI application in the middleware chain.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process ASGI request, stripping null bytes from HTTP traffic.

        Args:
            scope: ASGI connection scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Strip null bytes from query string (literal \x00 and percent-encoded %00)
        query_string = scope.get("query_string", b"")
        if b"\x00" in query_string or b"%00" in query_string.lower():
            cleaned = query_string.replace(b"\x00", b"")
            scope["query_string"] = _PERCENT_NULL_RE.sub(b"", cleaned)

        # For JSON bodies: parse, strip null bytes from strings, re-serialize
        if _is_json_request(scope):
            original_receive = receive
            body_consumed = False

            async def sanitized_receive() -> dict[str, Any]:
                nonlocal body_consumed

                if body_consumed:
                    return {
                        "type": "http.request",
                        "body": b"",
                        "more_body": False,
                    }

                # Buffer the full body (may arrive in multiple chunks)
                body_parts: list[bytes] = []
                total_size = 0
                oversized = False
                while True:
                    message = await original_receive()
                    body = message.get("body", b"")
                    if body:
                        total_size += len(body)
                        body_parts.append(body)
                        if total_size > _MAX_JSON_BODY_SIZE:
                            oversized = True
                    if not message.get("more_body", False):
                        break

                body_consumed = True
                full_body = b"".join(body_parts)

                # Only sanitize if within size limit
                if full_body and not oversized:
                    full_body = _strip_null_bytes_from_json(full_body)

                return {
                    "type": "http.request",
                    "body": full_body,
                    "more_body": False,
                }

            await self.app(scope, sanitized_receive, send)
        else:
            await self.app(scope, receive, send)


def _is_json_request(scope: Scope) -> bool:
    """Check if the request has a JSON content type.

    Args:
        scope: ASGI connection scope with headers.

    Returns:
        True if Content-Type starts with application/json.
    """
    for header_name, header_value in scope.get("headers", []):
        if header_name.lower() == b"content-type":
            return bool(header_value.startswith(_JSON_CONTENT_TYPE))
    return False


def _strip_null_bytes_from_json(body: bytes) -> bytes:
    """Parse JSON body, strip null bytes from all string values, re-serialize.

    JSON encodes null bytes as the \\u0000 escape sequence. After parsing,
    these become actual \\x00 characters in Python strings. This function
    strips them and re-serializes to clean JSON.

    Args:
        body: Raw JSON body bytes.

    Returns:
        Cleaned JSON body bytes, or original body if parsing fails.
    """
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return body

    try:
        cleaned = _strip_recursive(data)
    except RecursionError:
        return body

    try:
        return json.dumps(cleaned, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError):
        return body


def _strip_recursive(value: Any, depth: int = 0) -> Any:
    """Recursively strip null bytes from all strings in a JSON structure.

    Args:
        value: JSON-compatible value (dict, list, str, int, etc.).
            Any is justified: JSON values have no common base type.
        depth: Current recursion depth (safety limit).

    Returns:
        The same structure with null bytes removed from all strings.
    """
    if depth > _MAX_NESTING_DEPTH:
        return value
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, dict):
        return {
            k.replace("\x00", "") if isinstance(k, str) else k: _strip_recursive(
                v, depth + 1
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_strip_recursive(item, depth + 1) for item in value]
    return value
