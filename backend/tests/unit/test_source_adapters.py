"""Tests for job source adapters.

REQ-007 §6.3: Source Adapters

Tests verify:
- Adapter factory
- Concrete adapters (Adzuna, RemoteOK, TheMuse, USAJobs)
- Normalization to common schema
"""

# =============================================================================
# Adapter Factory Tests (§6.3)
# =============================================================================


class TestAdapterFactory:
    """Tests for getting source adapters by name.

    REQ-007 §6.3: Factory pattern for source adapters.
    """

    def test_factory_raises_when_source_unknown(self) -> None:
        """get_source_adapter raises ValueError for unknown source names."""
        import pytest

        from app.adapters.sources import get_source_adapter

        with pytest.raises(ValueError, match="Unknown source"):
            get_source_adapter("UnknownSource")


# =============================================================================
# Adzuna Adapter Tests (§6.3)
# =============================================================================


class TestAdzunaAdapter:
    """Tests for the Adzuna job source adapter.

    REQ-007 §6.3: Adzuna REST API adapter (250/day free tier).
    """

    def test_normalize_converts_adzuna_response_to_raw_job(self) -> None:
        """normalize converts Adzuna API response to RawJob."""
        from app.adapters.sources.adzuna import AdzunaAdapter
        from app.adapters.sources.base import RawJob

        adapter = AdzunaAdapter()

        # Sample Adzuna API response
        adzuna_job = {
            "id": "12345",
            "title": "Python Developer",
            "company": {"display_name": "Tech Corp"},
            "description": "We are looking for a Python developer...",
            "redirect_url": "https://www.adzuna.com/land/ad/12345",
            "location": {"display_name": "San Francisco, CA"},
            "salary_min": 100000,
            "salary_max": 150000,
            "created": "2025-01-15T12:00:00Z",
        }

        raw_job = adapter.normalize(adzuna_job)

        assert isinstance(raw_job, RawJob)
        assert raw_job.external_id == "12345"
        assert raw_job.title == "Python Developer"
        assert raw_job.company == "Tech Corp"
        assert raw_job.description == "We are looking for a Python developer..."
        assert raw_job.source_url == "https://www.adzuna.com/land/ad/12345"
        assert raw_job.location == "San Francisco, CA"
        assert raw_job.salary_min == 100000
        assert raw_job.salary_max == 150000

    def test_normalize_handles_missing_optional_fields(self) -> None:
        """normalize handles Adzuna response without optional fields."""
        from app.adapters.sources.adzuna import AdzunaAdapter

        adapter = AdzunaAdapter()

        # Minimal Adzuna response
        adzuna_job = {
            "id": "67890",
            "title": "Software Engineer",
            "company": {"display_name": "Startup Inc"},
            "description": "Join our team!",
            "redirect_url": "https://www.adzuna.com/land/ad/67890",
        }

        raw_job = adapter.normalize(adzuna_job)

        assert raw_job.external_id == "67890"
        assert raw_job.title == "Software Engineer"
        assert raw_job.location is None
        assert raw_job.salary_min is None
        assert raw_job.salary_max is None


# =============================================================================
# RemoteOK Adapter Tests (§6.3)
# =============================================================================


class TestRemoteOKAdapter:
    """Tests for the RemoteOK job source adapter.

    REQ-007 §6.3: RemoteOK REST API adapter (generous rate limits).
    """

    def test_normalize_converts_remoteok_response_to_raw_job(self) -> None:
        """normalize converts RemoteOK API response to RawJob."""
        from app.adapters.sources.base import RawJob
        from app.adapters.sources.remoteok import RemoteOKAdapter

        adapter = RemoteOKAdapter()

        # Sample RemoteOK API response
        remoteok_job = {
            "id": "rok-999",
            "position": "Backend Engineer",
            "company": "Remote Corp",
            "description": "Build distributed systems...",
            "url": "https://remoteok.com/jobs/rok-999",
            "location": "Worldwide",
            "salary_min": 120000,
            "salary_max": 180000,
        }

        raw_job = adapter.normalize(remoteok_job)

        assert isinstance(raw_job, RawJob)
        assert raw_job.external_id == "rok-999"
        assert raw_job.title == "Backend Engineer"
        assert raw_job.company == "Remote Corp"
        assert raw_job.source_url == "https://remoteok.com/jobs/rok-999"


# =============================================================================
# The Muse Adapter Tests (§6.3)
# =============================================================================


class TestTheMuseAdapter:
    """Tests for The Muse job source adapter.

    REQ-007 §6.3: The Muse REST API adapter (3600/hour).
    """

    def test_normalize_converts_muse_response_to_raw_job(self) -> None:
        """normalize converts The Muse API response to RawJob."""
        from app.adapters.sources.base import RawJob
        from app.adapters.sources.themuse import TheMuseAdapter

        adapter = TheMuseAdapter()

        # Sample The Muse API response
        muse_job = {
            "id": 123456,
            "name": "Product Manager",
            "company": {"name": "Awesome Company"},
            "contents": "Lead product development...",
            "refs": {"landing_page": "https://www.themuse.com/jobs/123456"},
            "locations": [{"name": "New York, NY"}],
        }

        raw_job = adapter.normalize(muse_job)

        assert isinstance(raw_job, RawJob)
        assert raw_job.external_id == "123456"
        assert raw_job.title == "Product Manager"
        assert raw_job.company == "Awesome Company"
        assert raw_job.location == "New York, NY"


# =============================================================================
# USAJobs Adapter Tests (§6.3)
# =============================================================================


class TestUSAJobsAdapter:
    """Tests for the USAJobs job source adapter.

    REQ-007 §6.3: USAJobs REST API adapter (200/day).
    """

    def test_normalize_converts_usajobs_response_to_raw_job(self) -> None:
        """normalize converts USAJobs API response to RawJob."""
        from app.adapters.sources.base import RawJob
        from app.adapters.sources.usajobs import USAJobsAdapter

        adapter = USAJobsAdapter()

        # Sample USAJobs API response
        usajobs_job = {
            "MatchedObjectId": "usa-12345",
            "MatchedObjectDescriptor": {
                "PositionTitle": "IT Specialist",
                "OrganizationName": "Department of Commerce",
                "UserArea": {
                    "Details": {
                        "JobSummary": "Serve as IT specialist...",
                    }
                },
                "PositionLocation": [{"LocationName": "Washington, DC"}],
                "PositionRemuneration": [
                    {
                        "MinimumRange": "80000",
                        "MaximumRange": "120000",
                    }
                ],
                "ApplyURI": ["https://www.usajobs.gov/job/usa-12345"],
            },
        }

        raw_job = adapter.normalize(usajobs_job)

        assert isinstance(raw_job, RawJob)
        assert raw_job.external_id == "usa-12345"
        assert raw_job.title == "IT Specialist"
        assert raw_job.company == "Department of Commerce"
        assert raw_job.location == "Washington, DC"
        assert raw_job.salary_min == 80000
        assert raw_job.salary_max == 120000
        # USAJobs is US-only, so currency is always USD
        assert raw_job.salary_currency == "USD"

    def test_normalize_omits_currency_when_no_salary(self) -> None:
        """normalize sets salary_currency to None when no salary data exists."""
        from app.adapters.sources.usajobs import USAJobsAdapter

        adapter = USAJobsAdapter()

        # USAJobs job without salary info
        usajobs_job = {
            "MatchedObjectId": "usa-no-salary",
            "MatchedObjectDescriptor": {
                "PositionTitle": "Park Ranger",
                "OrganizationName": "National Park Service",
                "UserArea": {
                    "Details": {
                        "JobSummary": "Protect natural resources...",
                    }
                },
                "PositionLocation": [{"LocationName": "Yellowstone, WY"}],
                "PositionRemuneration": [],
                "ApplyURI": ["https://www.usajobs.gov/job/usa-no-salary"],
            },
        }

        raw_job = adapter.normalize(usajobs_job)

        assert raw_job.salary_min is None
        assert raw_job.salary_max is None
        assert raw_job.salary_currency is None


# =============================================================================
# Edge Case Tests (§6.3)
# =============================================================================


class TestAdapterNormalizeMissingRequiredKeys:
    """Tests for normalize behavior with missing required fields.

    These tests verify that adapters raise KeyError when required fields
    are missing from the API response.
    """

    def test_adzuna_normalize_raises_when_id_missing(self) -> None:
        """AdzunaAdapter.normalize raises KeyError when 'id' is missing."""
        import pytest

        from app.adapters.sources.adzuna import AdzunaAdapter

        adapter = AdzunaAdapter()
        incomplete_response = {
            "title": "Python Developer",
            "company": {"display_name": "Tech Corp"},
            "description": "Build things",
            "redirect_url": "https://example.com",
        }

        with pytest.raises(KeyError):
            adapter.normalize(incomplete_response)

    def test_remoteok_normalize_raises_when_position_missing(self) -> None:
        """RemoteOKAdapter.normalize raises KeyError when 'position' is missing."""
        import pytest

        from app.adapters.sources.remoteok import RemoteOKAdapter

        adapter = RemoteOKAdapter()
        incomplete_response = {
            "id": "rok-123",
            "company": "Remote Corp",
            "description": "Build things",
            "url": "https://example.com",
        }

        with pytest.raises(KeyError):
            adapter.normalize(incomplete_response)

    def test_themuse_normalize_raises_when_name_missing(self) -> None:
        """TheMuseAdapter.normalize raises KeyError when 'name' is missing."""
        import pytest

        from app.adapters.sources.themuse import TheMuseAdapter

        adapter = TheMuseAdapter()
        incomplete_response = {
            "id": 123,
            "company": {"name": "Awesome Company"},
            "contents": "Lead product...",
            "refs": {"landing_page": "https://example.com"},
        }

        with pytest.raises(KeyError):
            adapter.normalize(incomplete_response)

    def test_usajobs_normalize_raises_when_id_missing(self) -> None:
        """USAJobsAdapter.normalize raises KeyError when 'MatchedObjectId' is missing."""
        import pytest

        from app.adapters.sources.usajobs import USAJobsAdapter

        adapter = USAJobsAdapter()
        incomplete_response = {
            "MatchedObjectDescriptor": {
                "PositionTitle": "IT Specialist",
            }
        }

        with pytest.raises(KeyError):
            adapter.normalize(incomplete_response)
