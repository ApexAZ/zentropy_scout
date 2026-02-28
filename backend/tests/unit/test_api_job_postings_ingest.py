"""Tests for Job Posting Ingest endpoint.

REQ-006 §5.6: Chrome extension job posting ingest flow.

These tests verify:
- POST /job-postings/ingest (raw text extraction)
- POST /job-postings/ingest/confirm (create from preview)
- Error handling (duplicate URL, extraction failed, token expired)
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient

from app.api.deps import require_sufficient_balance
from app.core.errors import InsufficientBalanceError

# =============================================================================
# Schema Validation Tests
# =============================================================================


class TestIngestRequestSchema:
    """Tests for IngestJobPostingRequest validation.

    Verifies required fields, empty validation, and URL format checking.
    """

    @pytest.mark.asyncio
    async def test_ingest_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Ingest endpoint returns 401 without authentication."""
        response = await unauthenticated_client.post(
            "/api/v1/job-postings/ingest",
            json={
                "raw_text": "Job posting text",
                "source_url": "https://example.com/job",
                "source_name": "Example",
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_ingest_requires_raw_text(self, client: AsyncClient) -> None:
        """Ingest requires raw_text field."""
        response = await client.post(
            "/api/v1/job-postings/ingest",
            json={
                "source_url": "https://example.com/job",
                "source_name": "Example",
            },
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_ingest_accepts_missing_source_url(
        self,
        client: AsyncClient,
        mock_llm: Any,  # noqa: ARG002
    ) -> None:
        """Ingest succeeds without source_url (optional field)."""
        response = await client.post(
            "/api/v1/job-postings/ingest",
            json={
                "raw_text": "Job posting text",
                "source_name": "Example",
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "preview" in data
        assert "confirmation_token" in data

    @pytest.mark.asyncio
    async def test_ingest_requires_source_name(self, client: AsyncClient) -> None:
        """Ingest requires source_name field."""
        response = await client.post(
            "/api/v1/job-postings/ingest",
            json={
                "raw_text": "Job posting text",
                "source_url": "https://example.com/job",
            },
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_ingest_raw_text_not_empty(self, client: AsyncClient) -> None:
        """Ingest raw_text cannot be empty."""
        response = await client.post(
            "/api/v1/job-postings/ingest",
            json={
                "raw_text": "",
                "source_url": "https://example.com/job",
                "source_name": "Example",
            },
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_ingest_source_url_must_be_valid(self, client: AsyncClient) -> None:
        """Ingest source_url must be a valid URL."""
        response = await client.post(
            "/api/v1/job-postings/ingest",
            json={
                "raw_text": "Job posting text",
                "source_url": "not-a-valid-url",
                "source_name": "Example",
            },
        )
        assert response.status_code == 400


# =============================================================================
# Successful Ingest Tests
# =============================================================================


class TestIngestSuccess:
    """Tests for successful ingest flow.

    Verifies preview response structure, extracted fields, token format,
    and expiration timing.
    """

    @pytest.mark.asyncio
    async def test_ingest_returns_preview(
        self,
        client: AsyncClient,
        mock_llm: Any,  # noqa: ARG002
    ) -> None:
        """Ingest returns preview with extracted fields."""
        response = await client.post(
            "/api/v1/job-postings/ingest",
            json={
                "raw_text": "Senior Software Engineer at Acme Corp. "
                "Location: San Francisco. Salary: $150k-$200k.",
                "source_url": "https://linkedin.com/jobs/view/12345",
                "source_name": "LinkedIn",
            },
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert "preview" in data
        assert "confirmation_token" in data
        assert "expires_at" in data

    @pytest.mark.asyncio
    async def test_ingest_preview_has_extracted_fields(
        self,
        client: AsyncClient,
        mock_llm: Any,  # noqa: ARG002
    ) -> None:
        """Preview contains extracted job details."""
        response = await client.post(
            "/api/v1/job-postings/ingest",
            json={
                "raw_text": "Senior Software Engineer at Acme Corp",
                "source_url": "https://example.com/job/1",
                "source_name": "Example",
            },
        )

        preview = response.json()["data"]["preview"]
        # Preview should have key fields (may be null if extraction fails)
        assert "job_title" in preview
        assert "company_name" in preview
        assert "location" in preview
        assert "extracted_skills" in preview
        assert "description_snippet" in preview

    @pytest.mark.asyncio
    async def test_ingest_confirmation_token_is_uuid(
        self,
        client: AsyncClient,
        mock_llm: Any,  # noqa: ARG002
    ) -> None:
        """Confirmation token is a valid UUID."""
        response = await client.post(
            "/api/v1/job-postings/ingest",
            json={
                "raw_text": "Job posting text",
                "source_url": "https://example.com/job/2",
                "source_name": "Example",
            },
        )

        token = response.json()["data"]["confirmation_token"]
        # Should be a valid UUID
        uuid.UUID(token)

    @pytest.mark.asyncio
    async def test_ingest_expires_at_is_future(
        self,
        client: AsyncClient,
        mock_llm: Any,  # noqa: ARG002
    ) -> None:
        """Expiration time is in the future."""
        response = await client.post(
            "/api/v1/job-postings/ingest",
            json={
                "raw_text": "Job posting text",
                "source_url": "https://example.com/job/3",
                "source_name": "Example",
            },
        )

        expires_at = response.json()["data"]["expires_at"]
        expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        now = datetime.now(UTC)
        assert expires_dt > now


# =============================================================================
# Duplicate Detection Tests
# =============================================================================


class TestIngestDuplicateDetection:
    """Tests for duplicate URL detection.

    Verifies 409 response when ingesting a URL that already exists.
    """

    @pytest.mark.asyncio
    async def test_ingest_detects_duplicate_url(
        self,
        client: AsyncClient,
        mock_llm: Any,  # noqa: ARG002
    ) -> None:
        """Ingest returns 409 if URL already exists."""
        source_url = "https://example.com/job/duplicate"

        # First ingest + confirm to create the job
        response1 = await client.post(
            "/api/v1/job-postings/ingest",
            json={
                "raw_text": "First job posting",
                "source_url": source_url,
                "source_name": "Example",
            },
        )
        assert response1.status_code == 200
        token = response1.json()["data"]["confirmation_token"]

        # Confirm the first ingest
        await client.post(
            "/api/v1/job-postings/ingest/confirm",
            json={"confirmation_token": token},
        )

        # Second ingest with same URL should fail
        response2 = await client.post(
            "/api/v1/job-postings/ingest",
            json={
                "raw_text": "Second job posting",
                "source_url": source_url,
                "source_name": "Example",
            },
        )

        assert response2.status_code == 409
        error = response2.json()["error"]
        assert error["code"] == "DUPLICATE_JOB"
        assert "existing_id" in error or "existing_id" in str(error.get("details", []))


# =============================================================================
# Confirmation Tests
# =============================================================================


class TestIngestConfirm:
    """Tests for POST /job-postings/ingest/confirm.

    Verifies auth requirement, token validation, job posting creation,
    response structure, and modification support.
    """

    @pytest.mark.asyncio
    async def test_confirm_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Confirm endpoint returns 401 without authentication."""
        response = await unauthenticated_client.post(
            "/api/v1/job-postings/ingest/confirm",
            json={"confirmation_token": str(uuid.uuid4())},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_confirm_requires_token(self, client: AsyncClient) -> None:
        """Confirm requires confirmation_token field."""
        response = await client.post(
            "/api/v1/job-postings/ingest/confirm",
            json={},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_confirm_creates_job_posting(
        self,
        client: AsyncClient,
        mock_llm: Any,  # noqa: ARG002
    ) -> None:
        """Confirming a valid token creates the job posting."""
        # First, ingest to get a token
        ingest_response = await client.post(
            "/api/v1/job-postings/ingest",
            json={
                "raw_text": "Software Engineer at Test Corp",
                "source_url": "https://example.com/job/confirm-test",
                "source_name": "Example",
            },
        )
        token = ingest_response.json()["data"]["confirmation_token"]

        # Confirm the ingest
        confirm_response = await client.post(
            "/api/v1/job-postings/ingest/confirm",
            json={"confirmation_token": token},
        )

        assert confirm_response.status_code == 201
        data = confirm_response.json()["data"]
        assert "id" in data
        # Should be a valid UUID
        uuid.UUID(data["id"])

    @pytest.mark.asyncio
    async def test_confirm_returns_full_job_posting(
        self,
        client: AsyncClient,
        mock_llm: Any,  # noqa: ARG002
    ) -> None:
        """Confirm returns full job posting data."""
        ingest_response = await client.post(
            "/api/v1/job-postings/ingest",
            json={
                "raw_text": "Software Engineer at Test Corp",
                "source_url": "https://example.com/job/confirm-full",
                "source_name": "Example",
            },
        )
        token = ingest_response.json()["data"]["confirmation_token"]

        confirm_response = await client.post(
            "/api/v1/job-postings/ingest/confirm",
            json={"confirmation_token": token},
        )

        data = confirm_response.json()["data"]
        assert "id" in data
        assert "job" in data
        assert "job_title" in data["job"]
        assert "company_name" in data["job"]
        assert "status" in data

    @pytest.mark.asyncio
    async def test_confirm_accepts_modifications(
        self,
        client: AsyncClient,
        mock_llm: Any,  # noqa: ARG002
    ) -> None:
        """Confirm can modify extracted fields."""
        ingest_response = await client.post(
            "/api/v1/job-postings/ingest",
            json={
                "raw_text": "Software Engineer at Test Corp",
                "source_url": "https://example.com/job/confirm-modify",
                "source_name": "Example",
            },
        )
        token = ingest_response.json()["data"]["confirmation_token"]

        # Confirm with modifications
        confirm_response = await client.post(
            "/api/v1/job-postings/ingest/confirm",
            json={
                "confirmation_token": token,
                "modifications": {"job_title": "Sr. Software Engineer"},
            },
        )

        assert confirm_response.status_code == 201
        data = confirm_response.json()["data"]
        assert data["job"]["job_title"] == "Sr. Software Engineer"


# =============================================================================
# Token Error Cases
# =============================================================================


class TestIngestTokenErrors:
    """Tests for token-related error cases.

    Verifies invalid token handling, token reuse prevention, and expiration.
    """

    @pytest.mark.asyncio
    async def test_confirm_invalid_token_returns_404(self, client: AsyncClient) -> None:
        """Confirm with unknown token returns 404."""
        response = await client.post(
            "/api/v1/job-postings/ingest/confirm",
            json={"confirmation_token": str(uuid.uuid4())},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_confirm_token_cannot_be_reused(
        self,
        client: AsyncClient,
        mock_llm: Any,  # noqa: ARG002
    ) -> None:
        """Token can only be used once."""
        ingest_response = await client.post(
            "/api/v1/job-postings/ingest",
            json={
                "raw_text": "Software Engineer at Test Corp",
                "source_url": "https://example.com/job/token-reuse",
                "source_name": "Example",
            },
        )
        token = ingest_response.json()["data"]["confirmation_token"]

        # First confirm succeeds
        first_confirm = await client.post(
            "/api/v1/job-postings/ingest/confirm",
            json={"confirmation_token": token},
        )
        assert first_confirm.status_code == 201

        # Second confirm with same token fails
        second_confirm = await client.post(
            "/api/v1/job-postings/ingest/confirm",
            json={"confirmation_token": token},
        )
        assert second_confirm.status_code == 404

    @pytest.mark.asyncio
    async def test_confirm_expired_token_returns_404(
        self,
        client: AsyncClient,
        mock_llm: Any,  # noqa: ARG002
    ) -> None:
        """Confirm with expired token returns 404.

        Simulates token expiration by directly manipulating the stored data.
        """
        from datetime import UTC, datetime, timedelta

        from app.services.ingest_token_store import get_token_store

        # First, ingest to get a token
        ingest_response = await client.post(
            "/api/v1/job-postings/ingest",
            json={
                "raw_text": "Software Engineer at Test Corp",
                "source_url": "https://example.com/job/token-expired",
                "source_name": "Example",
            },
        )
        token = ingest_response.json()["data"]["confirmation_token"]

        # Manually expire the token by setting expires_at to the past
        token_store = get_token_store()
        stored_data = token_store._store.get(token)
        if stored_data:
            stored_data.expires_at = datetime.now(UTC) - timedelta(minutes=1)

        # Confirm with expired token should fail
        confirm_response = await client.post(
            "/api/v1/job-postings/ingest/confirm",
            json={"confirmation_token": token},
        )
        assert confirm_response.status_code == 404


# =============================================================================
# Modification Security Tests
# =============================================================================


class TestIngestModificationSecurity:
    """Tests for modification field whitelist validation.

    Security: Prevents mass assignment of sensitive fields.
    """

    @pytest.mark.asyncio
    async def test_confirm_rejects_disallowed_modification_keys(
        self,
        client: AsyncClient,
        mock_llm: Any,  # noqa: ARG002
    ) -> None:
        """Confirm rejects modification keys not in whitelist."""
        ingest_response = await client.post(
            "/api/v1/job-postings/ingest",
            json={
                "raw_text": "Software Engineer at Test Corp",
                "source_url": "https://example.com/job/security-test-1",
                "source_name": "Example",
            },
        )
        token = ingest_response.json()["data"]["confirmation_token"]

        # Try to inject disallowed fields
        confirm_response = await client.post(
            "/api/v1/job-postings/ingest/confirm",
            json={
                "confirmation_token": token,
                "modifications": {
                    "id": str(uuid.uuid4()),  # Should NOT be allowed
                    "persona_id": str(uuid.uuid4()),  # Should NOT be allowed
                    "job_title": "Valid Title",  # This IS allowed
                },
            },
        )

        assert confirm_response.status_code == 400
        error = confirm_response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert "Invalid modification keys" in error["message"]
        assert "id" in error["message"]
        assert "persona_id" in error["message"]

    @pytest.mark.asyncio
    async def test_confirm_accepts_all_allowed_modification_keys(
        self,
        client: AsyncClient,
        mock_llm: Any,  # noqa: ARG002
    ) -> None:
        """Confirm accepts all whitelisted modification keys."""
        ingest_response = await client.post(
            "/api/v1/job-postings/ingest",
            json={
                "raw_text": "Software Engineer at Test Corp",
                "source_url": "https://example.com/job/security-test-2",
                "source_name": "Example",
            },
        )
        token = ingest_response.json()["data"]["confirmation_token"]

        # All allowed fields should work
        confirm_response = await client.post(
            "/api/v1/job-postings/ingest/confirm",
            json={
                "confirmation_token": token,
                "modifications": {
                    "job_title": "Senior Engineer",
                    "company_name": "Great Corp",
                    "location": "Remote",
                    "salary_min": 100000,
                    "salary_max": 150000,
                    "salary_currency": "USD",
                },
            },
        )

        assert confirm_response.status_code == 201
        data = confirm_response.json()["data"]
        assert data["job"]["job_title"] == "Senior Engineer"
        assert data["job"]["company_name"] == "Great Corp"
        assert data["job"]["location"] == "Remote"
        assert data["job"]["salary_min"] == 100000
        assert data["job"]["salary_max"] == 150000
        assert data["job"]["salary_currency"] == "USD"


# =============================================================================
# Balance Gating Tests (REQ-020 §7)
# =============================================================================

_ZERO = Decimal("0.000000")


class TestIngestBalanceGating:
    """Tests for 402 balance gating on ingest endpoint.

    REQ-020 §7.1: LLM-triggering endpoints require sufficient balance.
    """

    @pytest.mark.asyncio
    async def test_ingest_returns_402_when_insufficient_balance(
        self, client: AsyncClient
    ) -> None:
        """Ingest returns 402 when user has insufficient balance."""
        from app.main import app

        async def raise_insufficient_balance() -> None:
            raise InsufficientBalanceError(balance=_ZERO, minimum_required=_ZERO)

        app.dependency_overrides[require_sufficient_balance] = (
            raise_insufficient_balance
        )
        try:
            response = await client.post(
                "/api/v1/job-postings/ingest",
                json={
                    "raw_text": "Job posting text",
                    "source_url": "https://example.com/job/402-test",
                    "source_name": "Example",
                },
            )
            assert response.status_code == 402
            error = response.json()["error"]
            assert error["code"] == "INSUFFICIENT_BALANCE"
            assert "$0.00" in error["message"]
        finally:
            app.dependency_overrides.pop(require_sufficient_balance, None)
