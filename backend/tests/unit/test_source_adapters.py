"""Tests for job source adapters.

REQ-007 §6.3: Source Adapters

Tests verify:
- Abstract interface (JobSourceAdapter)
- SearchParams and RawJob types
- Adapter factory
- Concrete adapters (Adzuna, RemoteOK, TheMuse, USAJobs)
- Normalization to common schema
"""

from abc import ABC
from dataclasses import fields

# =============================================================================
# Base Interface Tests (§6.3)
# =============================================================================


class TestJobSourceAdapterInterface:
    """Tests for the JobSourceAdapter abstract base class.

    REQ-007 §6.3: Source adapters implement fetch_jobs() and normalize().
    """

    def test_interface_is_abstract_base_class(self) -> None:
        """JobSourceAdapter is an abstract base class that cannot be instantiated."""
        from app.adapters.sources.base import JobSourceAdapter

        assert issubclass(JobSourceAdapter, ABC)

    def test_interface_defines_fetch_jobs_method(self) -> None:
        """JobSourceAdapter declares abstract fetch_jobs method."""
        from app.adapters.sources.base import JobSourceAdapter

        assert hasattr(JobSourceAdapter, "fetch_jobs")
        # Verify it's abstract by checking __abstractmethods__
        assert "fetch_jobs" in JobSourceAdapter.__abstractmethods__

    def test_interface_defines_normalize_method(self) -> None:
        """JobSourceAdapter declares abstract normalize method."""
        from app.adapters.sources.base import JobSourceAdapter

        assert hasattr(JobSourceAdapter, "normalize")
        assert "normalize" in JobSourceAdapter.__abstractmethods__

    def test_interface_defines_source_name_property(self) -> None:
        """JobSourceAdapter declares abstract source_name property."""
        from app.adapters.sources.base import JobSourceAdapter

        assert "source_name" in JobSourceAdapter.__abstractmethods__


class TestSearchParams:
    """Tests for SearchParams dataclass.

    REQ-007 §6.3: Search parameters for job queries.
    """

    def test_search_params_is_dataclass(self) -> None:
        """SearchParams is a dataclass with expected fields."""
        from app.adapters.sources.base import SearchParams

        # Should be able to instantiate with required fields
        params = SearchParams(keywords=["python", "developer"])
        assert params.keywords == ["python", "developer"]

    def test_search_params_has_keywords_field(self) -> None:
        """SearchParams has keywords field for job title/skill search."""
        from app.adapters.sources.base import SearchParams

        field_names = [f.name for f in fields(SearchParams)]
        assert "keywords" in field_names

    def test_search_params_has_location_field(self) -> None:
        """SearchParams has optional location field."""
        from app.adapters.sources.base import SearchParams

        params = SearchParams(keywords=["python"], location="San Francisco, CA")
        assert params.location == "San Francisco, CA"

    def test_search_params_has_remote_only_field(self) -> None:
        """SearchParams has remote_only flag for filtering."""
        from app.adapters.sources.base import SearchParams

        params = SearchParams(keywords=["python"], remote_only=True)
        assert params.remote_only is True

    def test_search_params_has_page_and_limit_fields(self) -> None:
        """SearchParams has pagination fields."""
        from app.adapters.sources.base import SearchParams

        params = SearchParams(keywords=["python"], page=2, results_per_page=50)
        assert params.page == 2
        assert params.results_per_page == 50


class TestRawJob:
    """Tests for RawJob dataclass.

    REQ-007 §6.3: Raw job data before normalization.
    """

    def test_raw_job_is_dataclass(self) -> None:
        """RawJob is a dataclass for source-specific job data."""
        from app.adapters.sources.base import RawJob

        job = RawJob(
            external_id="job-123",
            title="Python Developer",
            company="Acme Corp",
            description="Build things",
            source_url="https://example.com/job/123",
        )
        assert job.external_id == "job-123"
        assert job.title == "Python Developer"

    def test_raw_job_has_required_fields(self) -> None:
        """RawJob has minimum required fields from any source."""
        from app.adapters.sources.base import RawJob

        required_fields = {
            "external_id",
            "title",
            "company",
            "description",
            "source_url",
        }
        field_names = {f.name for f in fields(RawJob)}
        assert required_fields.issubset(field_names)

    def test_raw_job_has_optional_location_field(self) -> None:
        """RawJob has optional location field."""
        from app.adapters.sources.base import RawJob

        job = RawJob(
            external_id="1",
            title="Dev",
            company="Co",
            description="Desc",
            source_url="http://x",
            location="NYC",
        )
        assert job.location == "NYC"

    def test_raw_job_has_optional_salary_fields(self) -> None:
        """RawJob has optional salary_min and salary_max fields."""
        from app.adapters.sources.base import RawJob

        job = RawJob(
            external_id="1",
            title="Dev",
            company="Co",
            description="Desc",
            source_url="http://x",
            salary_min=100000,
            salary_max=150000,
        )
        assert job.salary_min == 100000
        assert job.salary_max == 150000

    def test_raw_job_has_optional_raw_data_field(self) -> None:
        """RawJob has raw_data field for full source response."""
        from app.adapters.sources.base import RawJob

        # WHY: Some sources return extra fields we might want later
        raw_data = {"extra_field": "value", "nested": {"key": "val"}}
        job = RawJob(
            external_id="1",
            title="Dev",
            company="Co",
            description="Desc",
            source_url="http://x",
            raw_data=raw_data,
        )
        assert job.raw_data == raw_data


# =============================================================================
# Adapter Factory Tests (§6.3)
# =============================================================================


class TestAdapterFactory:
    """Tests for getting source adapters by name.

    REQ-007 §6.3: Factory pattern for source adapters.
    """

    def test_factory_returns_adzuna_adapter_when_name_is_adzuna(self) -> None:
        """get_source_adapter returns AdzunaAdapter for 'Adzuna'."""
        from app.adapters.sources import get_source_adapter
        from app.adapters.sources.adzuna import AdzunaAdapter

        adapter = get_source_adapter("Adzuna")
        assert isinstance(adapter, AdzunaAdapter)

    def test_factory_returns_remoteok_adapter_when_name_is_remoteok(self) -> None:
        """get_source_adapter returns RemoteOKAdapter for 'RemoteOK'."""
        from app.adapters.sources import get_source_adapter
        from app.adapters.sources.remoteok import RemoteOKAdapter

        adapter = get_source_adapter("RemoteOK")
        assert isinstance(adapter, RemoteOKAdapter)

    def test_factory_returns_muse_adapter_when_name_is_the_muse(self) -> None:
        """get_source_adapter returns TheMuseAdapter for 'The Muse'."""
        from app.adapters.sources import get_source_adapter
        from app.adapters.sources.themuse import TheMuseAdapter

        adapter = get_source_adapter("The Muse")
        assert isinstance(adapter, TheMuseAdapter)

    def test_factory_returns_usajobs_adapter_when_name_is_usajobs(self) -> None:
        """get_source_adapter returns USAJobsAdapter for 'USAJobs'."""
        from app.adapters.sources import get_source_adapter
        from app.adapters.sources.usajobs import USAJobsAdapter

        adapter = get_source_adapter("USAJobs")
        assert isinstance(adapter, USAJobsAdapter)

    def test_factory_raises_when_source_unknown(self) -> None:
        """get_source_adapter raises ValueError for unknown source names."""
        import pytest

        from app.adapters.sources import get_source_adapter

        with pytest.raises(ValueError, match="Unknown source"):
            get_source_adapter("UnknownSource")

    def test_factory_handles_case_insensitive_names(self) -> None:
        """get_source_adapter matches source names case-insensitively."""
        from app.adapters.sources import get_source_adapter
        from app.adapters.sources.adzuna import AdzunaAdapter

        adapter = get_source_adapter("adzuna")
        assert isinstance(adapter, AdzunaAdapter)


# =============================================================================
# Adzuna Adapter Tests (§6.3)
# =============================================================================


class TestAdzunaAdapter:
    """Tests for the Adzuna job source adapter.

    REQ-007 §6.3: Adzuna REST API adapter (250/day free tier).
    """

    def test_adapter_inherits_from_base(self) -> None:
        """AdzunaAdapter inherits from JobSourceAdapter."""
        from app.adapters.sources.adzuna import AdzunaAdapter
        from app.adapters.sources.base import JobSourceAdapter

        assert issubclass(AdzunaAdapter, JobSourceAdapter)

    def test_adapter_has_source_name_adzuna(self) -> None:
        """AdzunaAdapter.source_name returns 'Adzuna'."""
        from app.adapters.sources.adzuna import AdzunaAdapter

        adapter = AdzunaAdapter()
        assert adapter.source_name == "Adzuna"

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

    def test_adapter_inherits_from_base(self) -> None:
        """RemoteOKAdapter inherits from JobSourceAdapter."""
        from app.adapters.sources.base import JobSourceAdapter
        from app.adapters.sources.remoteok import RemoteOKAdapter

        assert issubclass(RemoteOKAdapter, JobSourceAdapter)

    def test_adapter_has_source_name_remoteok(self) -> None:
        """RemoteOKAdapter.source_name returns 'RemoteOK'."""
        from app.adapters.sources.remoteok import RemoteOKAdapter

        adapter = RemoteOKAdapter()
        assert adapter.source_name == "RemoteOK"

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

    def test_adapter_inherits_from_base(self) -> None:
        """TheMuseAdapter inherits from JobSourceAdapter."""
        from app.adapters.sources.base import JobSourceAdapter
        from app.adapters.sources.themuse import TheMuseAdapter

        assert issubclass(TheMuseAdapter, JobSourceAdapter)

    def test_adapter_has_source_name_the_muse(self) -> None:
        """TheMuseAdapter.source_name returns 'The Muse'."""
        from app.adapters.sources.themuse import TheMuseAdapter

        adapter = TheMuseAdapter()
        assert adapter.source_name == "The Muse"

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

    def test_adapter_inherits_from_base(self) -> None:
        """USAJobsAdapter inherits from JobSourceAdapter."""
        from app.adapters.sources.base import JobSourceAdapter
        from app.adapters.sources.usajobs import USAJobsAdapter

        assert issubclass(USAJobsAdapter, JobSourceAdapter)

    def test_adapter_has_source_name_usajobs(self) -> None:
        """USAJobsAdapter.source_name returns 'USAJobs'."""
        from app.adapters.sources.usajobs import USAJobsAdapter

        adapter = USAJobsAdapter()
        assert adapter.source_name == "USAJobs"

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


class TestAdapterFetchJobsReturnsEmpty:
    """Tests verifying fetch_jobs returns empty until API integration.

    REQ-007 §6.3: API integration is deferred to Discovery Flow.
    """

    async def test_adzuna_fetch_jobs_returns_empty_list(self) -> None:
        """AdzunaAdapter.fetch_jobs returns empty list (deferred implementation)."""
        from app.adapters.sources.adzuna import AdzunaAdapter
        from app.adapters.sources.base import SearchParams

        adapter = AdzunaAdapter()
        params = SearchParams(keywords=["python"])

        result = await adapter.fetch_jobs(params)

        assert result == []

    async def test_remoteok_fetch_jobs_returns_empty_list(self) -> None:
        """RemoteOKAdapter.fetch_jobs returns empty list (deferred implementation)."""
        from app.adapters.sources.base import SearchParams
        from app.adapters.sources.remoteok import RemoteOKAdapter

        adapter = RemoteOKAdapter()
        params = SearchParams(keywords=["python"])

        result = await adapter.fetch_jobs(params)

        assert result == []

    async def test_themuse_fetch_jobs_returns_empty_list(self) -> None:
        """TheMuseAdapter.fetch_jobs returns empty list (deferred implementation)."""
        from app.adapters.sources.base import SearchParams
        from app.adapters.sources.themuse import TheMuseAdapter

        adapter = TheMuseAdapter()
        params = SearchParams(keywords=["python"])

        result = await adapter.fetch_jobs(params)

        assert result == []

    async def test_usajobs_fetch_jobs_returns_empty_list(self) -> None:
        """USAJobsAdapter.fetch_jobs returns empty list (deferred implementation)."""
        from app.adapters.sources.base import SearchParams
        from app.adapters.sources.usajobs import USAJobsAdapter

        adapter = USAJobsAdapter()
        params = SearchParams(keywords=["python"])

        result = await adapter.fetch_jobs(params)

        assert result == []


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
