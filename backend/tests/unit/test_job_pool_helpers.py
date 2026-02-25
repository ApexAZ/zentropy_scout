"""Tests for job pool helper functions.

REQ-016 §6.4: Description hashing and dedup data transformation.
"""

import hashlib
import uuid
from datetime import date
from typing import Any

import pytest

from app.repositories.job_pool_repository import (
    _build_dedup_job_data,
    _compute_description_hash,
)

_TODAY = date.today()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_job() -> dict[str, Any]:
    """Raw job dict as produced by source adapters."""
    return {
        "external_id": "ext-001",
        "title": "Software Engineer",
        "company": "Acme Corp",
        "description": "Build great software",
        "source_url": "https://example.com/job/1",
        "location": "Remote",
        "salary_min": 100000,
        "salary_max": 150000,
        "posted_date": _TODAY,
        "source_name": "Adzuna",
    }


# ---------------------------------------------------------------------------
# _compute_description_hash
# ---------------------------------------------------------------------------


class TestComputeDescriptionHash:
    """Tests for SHA-256 description hashing."""

    def test_returns_sha256_hex_digest(self):
        """Hash is a 64-character hex string."""
        result = _compute_description_hash("some text")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_text_produces_same_hash(self):
        """Deterministic — same input, same output."""
        h1 = _compute_description_hash("Build great software")
        h2 = _compute_description_hash("Build great software")
        assert h1 == h2

    def test_different_text_produces_different_hash(self):
        """Different inputs produce different outputs."""
        h1 = _compute_description_hash("Build great software")
        h2 = _compute_description_hash("Analyze data trends")
        assert h1 != h2

    def test_known_value(self):
        """Hash of known input matches pre-computed value."""
        # Frozen-test: verify against a known SHA-256 digest
        assert _compute_description_hash("Build great software") == (
            hashlib.sha256(b"Build great software").hexdigest()
        )


# ---------------------------------------------------------------------------
# _build_dedup_job_data
# ---------------------------------------------------------------------------


class TestBuildDedupJobData:
    """Tests for transforming raw job dicts into dedup service input."""

    def test_includes_required_fields(self, sample_job: dict[str, Any]):
        """Required fields are mapped from job dict."""
        source_id = uuid.uuid4()
        result = _build_dedup_job_data(sample_job, source_id)

        assert result["source_id"] == source_id
        assert result["job_title"] == "Software Engineer"
        assert result["company_name"] == "Acme Corp"
        assert result["description"] == "Build great software"
        assert result["first_seen_date"] == _TODAY

    def test_computes_description_hash(self, sample_job: dict[str, Any]):
        """Description hash is computed from description text."""
        source_id = uuid.uuid4()
        result = _build_dedup_job_data(sample_job, source_id)
        expected_hash = hashlib.sha256(b"Build great software").hexdigest()
        assert result["description_hash"] == expected_hash

    def test_includes_optional_fields(self, sample_job: dict[str, Any]):
        """Optional fields are passed through."""
        source_id = uuid.uuid4()
        result = _build_dedup_job_data(sample_job, source_id)

        assert result["external_id"] == "ext-001"
        assert result["source_url"] == "https://example.com/job/1"
        assert result["location"] == "Remote"
        assert result["salary_min"] == 100000
        assert result["salary_max"] == 150000

    def test_handles_missing_optional_fields(self):
        """Missing optional fields default to None."""
        minimal_job: dict[str, Any] = {"description": "Minimal job"}
        source_id = uuid.uuid4()
        result = _build_dedup_job_data(minimal_job, source_id)

        assert result["job_title"] == ""
        assert result["company_name"] == ""
        assert result["external_id"] is None
        assert result["location"] is None
