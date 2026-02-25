"""Tests for NullByteMiddleware (CWE-158).

VULN-001: PostgreSQL rejects null bytes in UTF-8 strings, but Pydantic str
validation passes them through. The middleware strips null bytes at the ASGI
level before they reach any handler.
"""

from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI, UploadFile
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.main import create_app


@pytest.fixture
def app() -> FastAPI:
    """Create test application instance with NullByteMiddleware."""
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# Shared Pydantic models for body tests


class _TextBody(BaseModel):
    text: str


class _InnerModel(BaseModel):
    value: str


class _OuterModel(BaseModel):
    inner: _InnerModel


class TestNullByteInQueryString:
    """Null bytes in query parameters should be stripped."""

    @pytest.mark.asyncio
    async def test_null_byte_stripped_from_query_param(self, app, client):
        """Query parameter with %00 should have null bytes stripped."""
        received_params: dict = {}

        @app.get("/test/null-check")
        async def capture_query(q: str = ""):
            received_params["q"] = q
            return {"q": q}

        response = await client.get("/test/null-check?q=hello%00world")
        assert response.status_code == 200
        assert received_params["q"] == "helloworld"

    @pytest.mark.asyncio
    async def test_clean_query_param_unchanged(self, app, client):
        """Query parameter without null bytes should pass through unchanged."""

        @app.get("/test/clean-check")
        async def capture_clean(q: str = ""):
            return {"q": q}

        response = await client.get("/test/clean-check?q=hello+world")
        assert response.status_code == 200
        assert response.json()["q"] == "hello world"

    @pytest.mark.asyncio
    async def test_only_null_bytes_produces_empty_string(self, app, client):
        """Query parameter that is entirely null bytes should become empty."""

        @app.get("/test/all-null")
        async def capture_all_null(q: str = ""):
            return {"q": q}

        response = await client.get("/test/all-null?q=%00%00%00")
        assert response.status_code == 200
        assert response.json()["q"] == ""

    @pytest.mark.asyncio
    async def test_multiple_query_params_all_cleaned(self, app, client):
        """Null bytes should be stripped from all query parameters."""
        received: dict = {}

        @app.get("/test/multi-params")
        async def capture_multi(a: str = "", b: str = ""):
            received["a"] = a
            received["b"] = b
            return received

        response = await client.get("/test/multi-params?a=x%00y&b=p%00q")
        assert response.status_code == 200
        assert received["a"] == "xy"
        assert received["b"] == "pq"


class TestNullByteInRequestBody:
    """Null bytes in JSON request bodies should be stripped."""

    @pytest.mark.asyncio
    async def test_null_byte_stripped_from_json_body(self, app, client):
        """JSON body with \\u0000 should have null bytes stripped."""
        received: dict = {}

        @app.post("/test/body-null")
        async def capture_body(body: _TextBody):
            received["text"] = body.text
            return {"text": body.text}

        response = await client.post(
            "/test/body-null",
            json={"text": "hello\x00world"},
        )
        assert response.status_code == 200
        assert received["text"] == "helloworld"

    @pytest.mark.asyncio
    async def test_clean_json_body_unchanged(self, app, client):
        """JSON body without null bytes should pass through unchanged."""

        @app.post("/test/body-clean")
        async def capture_clean_body(body: _TextBody):
            return {"text": body.text}

        response = await client.post(
            "/test/body-clean",
            json={"text": "hello world"},
        )
        assert response.status_code == 200
        assert response.json()["text"] == "hello world"

    @pytest.mark.asyncio
    async def test_nested_json_null_bytes_stripped(self, app, client):
        """Null bytes in nested JSON fields should be stripped."""
        received: dict = {}

        @app.post("/test/nested-null")
        async def capture_nested(body: _OuterModel):
            received["value"] = body.inner.value
            return {"value": body.inner.value}

        response = await client.post(
            "/test/nested-null",
            json={"inner": {"value": "a\x00b"}},
        )
        assert response.status_code == 200
        assert received["value"] == "ab"

    @pytest.mark.asyncio
    async def test_malformed_json_body_passed_through(self, app, client):
        """Non-JSON body with application/json Content-Type should not crash."""

        @app.post("/test/malformed")
        async def echo_raw():
            return {"ok": True}

        response = await client.post(
            "/test/malformed",
            content=b"not json at all",
            headers={"Content-Type": "application/json"},
        )
        # FastAPI returns 422 for invalid JSON body (Pydantic validation error)
        # The important thing is it doesn't crash (500)
        assert response.status_code != 500


class TestNullByteMiddlewarePassthrough:
    """Middleware should not interfere with non-HTTP or clean traffic."""

    @pytest.mark.asyncio
    async def test_health_endpoint_unaffected(self, client):
        """Health endpoint should work normally (no null bytes)."""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_file_upload_unaffected(self, app, client):
        """Binary file uploads should not have null bytes stripped.

        The middleware only strips null bytes from text-based content
        (query strings and JSON bodies). Binary uploads (multipart/form-data)
        contain null bytes legitimately and should not be modified.
        """
        received_content: dict = {}

        @app.post("/test/upload")
        async def capture_upload(file: UploadFile):
            content = await file.read()
            received_content["bytes"] = content
            return {"size": len(content)}

        # PDF files naturally contain null bytes
        binary_data = b"PDF\x00content\x00here"
        response = await client.post(
            "/test/upload",
            files={"file": ("test.pdf", binary_data, "application/pdf")},
        )
        assert response.status_code == 200
        # Binary content should NOT have null bytes stripped
        assert received_content["bytes"] == binary_data
