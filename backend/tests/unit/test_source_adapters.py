"""Tests for job source adapters.

REQ-007 §6.3: Source Adapters
REQ-034 §5.3: fetch_jobs() implementations for Adzuna, The Muse, RemoteOK, USAJobs

Tests verify:
- Adapter factory
- Concrete adapters (Adzuna, RemoteOK, TheMuse, USAJobs)
- Normalization to common schema
- fetch_jobs() pagination, delta params, error handling, credential-missing skip
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

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


# =============================================================================
# Adzuna fetch_jobs() Tests (REQ-034 §5.3)
# =============================================================================


def _make_adzuna_job(job_id: str = "123", title: str = "Python Dev") -> dict[str, Any]:
    """Build a minimal Adzuna API job result dict."""
    return {
        "id": job_id,
        "title": title,
        "company": {"display_name": "Test Corp"},
        "description": "Do things",
        "redirect_url": f"https://adzuna.com/jobs/{job_id}",
    }


def _make_http_response(
    status_code: int = 200,
    json_body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> MagicMock:
    """Build a mock httpx Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.json.return_value = json_body or {}
    return resp


def _make_search_params(
    keywords: list[str],
    location: str | None = None,
    remote_only: bool = False,
    results_per_page: int = 25,
    max_days_old: int | None = None,
) -> Any:
    """Build a SearchParams for adapter fetch_jobs() tests."""
    from app.adapters.sources.base import SearchParams

    return SearchParams(
        keywords=keywords,
        location=location,
        remote_only=remote_only,
        results_per_page=results_per_page,
        max_days_old=max_days_old,
    )


def _make_adzuna_mock_client(
    side_effect_or_return: Any,
) -> AsyncMock:
    """Build a mock httpx AsyncClient context manager.

    Args:
        side_effect_or_return: A list of responses for sequential calls,
            a single response object for a constant return value, or an
            Exception instance to be raised on get(). Exception-raising
            paths can also be constructed inline for clarity.
    """
    mock_client = AsyncMock()
    if isinstance(side_effect_or_return, (BaseException, list)):
        mock_client.get = AsyncMock(side_effect=side_effect_or_return)
    else:
        mock_client.get = AsyncMock(return_value=side_effect_or_return)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def _adzuna_settings_mock(
    app_id: str | None = "test-app-id",
    app_key: str | None = "test-app-key",
) -> MagicMock:
    """Build a settings mock with Adzuna credentials."""
    s = MagicMock()
    s.adzuna_app_id = app_id
    if app_key is not None:
        k = MagicMock()
        k.get_secret_value.return_value = app_key
        s.adzuna_app_key = k
    else:
        s.adzuna_app_key = None
    return s


class TestAdzunaFetchJobs:
    """Tests for AdzunaAdapter.fetch_jobs() per REQ-034 §5.3.

    Uses AsyncMock to mock httpx.AsyncClient — no network calls.
    """

    async def test_returns_empty_list_when_credentials_missing(self) -> None:
        """fetch_jobs returns [] without making HTTP calls when creds are None."""
        from app.adapters.sources.adzuna import AdzunaAdapter

        adapter = AdzunaAdapter()
        params = _make_search_params(keywords=["python"])
        with (
            patch("app.adapters.sources.adzuna.settings") as mock_settings,
            patch("app.adapters.sources.adzuna.httpx") as mock_httpx,
        ):
            mock_settings.adzuna_app_id = None
            mock_settings.adzuna_app_key = None
            result = await adapter.fetch_jobs(params)
        assert result == []
        mock_httpx.AsyncClient.assert_not_called()

    async def test_single_page_returns_normalized_jobs(self) -> None:
        """fetch_jobs returns normalized jobs when page has fewer than results_per_page."""
        from app.adapters.sources.adzuna import AdzunaAdapter

        adapter = AdzunaAdapter()
        page_data = {"results": [_make_adzuna_job("1"), _make_adzuna_job("2")]}
        mock_client = _make_adzuna_mock_client(_make_http_response(json_body=page_data))

        params = _make_search_params(keywords=["python"], results_per_page=25)
        with (
            patch("app.adapters.sources.adzuna.settings", _adzuna_settings_mock()),
            patch(
                "app.adapters.sources.adzuna.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            result = await adapter.fetch_jobs(params)

        assert len(result) == 2
        assert result[0].external_id == "1"
        assert result[1].external_id == "2"

    async def test_pagination_continues_on_full_page(self) -> None:
        """fetch_jobs fetches page 2 when page 1 returns exactly results_per_page results."""
        from app.adapters.sources.adzuna import AdzunaAdapter

        adapter = AdzunaAdapter()
        page1 = {"results": [_make_adzuna_job("1"), _make_adzuna_job("2")]}
        page2 = {"results": []}
        mock_client = _make_adzuna_mock_client(
            [_make_http_response(json_body=page1), _make_http_response(json_body=page2)]
        )

        params = _make_search_params(keywords=["python"], results_per_page=2)
        with (
            patch("app.adapters.sources.adzuna.settings", _adzuna_settings_mock()),
            patch(
                "app.adapters.sources.adzuna.httpx.AsyncClient",
                return_value=mock_client,
            ),
            patch("app.adapters.sources.adzuna.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await adapter.fetch_jobs(params)

        assert len(result) == 2
        assert mock_client.get.call_count == 2

    async def test_pagination_stops_on_partial_page(self) -> None:
        """fetch_jobs stops after page returning fewer results than results_per_page."""
        from app.adapters.sources.adzuna import AdzunaAdapter

        adapter = AdzunaAdapter()
        page1 = {"results": [_make_adzuna_job(str(i)) for i in range(3)]}
        page2 = {"results": [_make_adzuna_job("99")]}
        mock_client = _make_adzuna_mock_client(
            [_make_http_response(json_body=page1), _make_http_response(json_body=page2)]
        )

        params = _make_search_params(keywords=["python"], results_per_page=3)
        with (
            patch("app.adapters.sources.adzuna.settings", _adzuna_settings_mock()),
            patch(
                "app.adapters.sources.adzuna.httpx.AsyncClient",
                return_value=mock_client,
            ),
            patch("app.adapters.sources.adzuna.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await adapter.fetch_jobs(params)

        assert len(result) == 4  # 3 from page 1 + 1 from page 2
        assert mock_client.get.call_count == 2

    async def test_includes_max_days_old_in_query_params(self) -> None:
        """fetch_jobs passes max_days_old as query param when set."""
        from app.adapters.sources.adzuna import AdzunaAdapter

        adapter = AdzunaAdapter()
        mock_client = _make_adzuna_mock_client(
            _make_http_response(json_body={"results": []})
        )

        params = _make_search_params(keywords=["python"], max_days_old=7)
        with (
            patch("app.adapters.sources.adzuna.settings", _adzuna_settings_mock()),
            patch(
                "app.adapters.sources.adzuna.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            await adapter.fetch_jobs(params)

        call_kwargs = mock_client.get.call_args
        assert call_kwargs.kwargs["params"]["max_days_old"] == 7

    async def test_uses_remote_where_when_remote_only(self) -> None:
        """fetch_jobs sets where=remote when params.remote_only is True."""
        from app.adapters.sources.adzuna import AdzunaAdapter

        adapter = AdzunaAdapter()
        mock_client = _make_adzuna_mock_client(
            _make_http_response(json_body={"results": []})
        )

        params = _make_search_params(keywords=["python"], remote_only=True)
        with (
            patch("app.adapters.sources.adzuna.settings", _adzuna_settings_mock()),
            patch(
                "app.adapters.sources.adzuna.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            await adapter.fetch_jobs(params)

        call_kwargs = mock_client.get.call_args
        assert call_kwargs.kwargs["params"]["where"] == "remote"

    async def test_uses_location_where_when_not_remote_only(self) -> None:
        """fetch_jobs sets where=location when location is set and not remote_only."""
        from app.adapters.sources.adzuna import AdzunaAdapter

        adapter = AdzunaAdapter()
        mock_client = _make_adzuna_mock_client(
            _make_http_response(json_body={"results": []})
        )

        params = _make_search_params(keywords=["python"], location="San Francisco")
        with (
            patch("app.adapters.sources.adzuna.settings", _adzuna_settings_mock()),
            patch(
                "app.adapters.sources.adzuna.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            await adapter.fetch_jobs(params)

        call_kwargs = mock_client.get.call_args
        assert call_kwargs.kwargs["params"]["where"] == "San Francisco"

    async def test_raises_source_error_with_retry_after_on_429(self) -> None:
        """fetch_jobs raises SourceError(RATE_LIMITED) with retry_after seconds on 429."""
        import pytest

        from app.adapters.sources.adzuna import AdzunaAdapter
        from app.services.discovery.scouter_errors import SourceError, SourceErrorType

        adapter = AdzunaAdapter()
        mock_client = _make_adzuna_mock_client(
            _make_http_response(status_code=429, headers={"Retry-After": "60"})
        )

        params = _make_search_params(keywords=["python"])
        with (
            patch("app.adapters.sources.adzuna.settings", _adzuna_settings_mock()),
            patch(
                "app.adapters.sources.adzuna.httpx.AsyncClient",
                return_value=mock_client,
            ),
            pytest.raises(SourceError) as exc_info,
        ):
            await adapter.fetch_jobs(params)

        assert exc_info.value.error_type == SourceErrorType.RATE_LIMITED
        assert exc_info.value.rate_limit_info is not None
        assert exc_info.value.rate_limit_info.retry_after_seconds == 60

    async def test_raises_source_error_on_500(self) -> None:
        """fetch_jobs raises SourceError(API_DOWN) on HTTP 500."""
        import pytest

        from app.adapters.sources.adzuna import AdzunaAdapter
        from app.services.discovery.scouter_errors import SourceError, SourceErrorType

        adapter = AdzunaAdapter()
        mock_client = _make_adzuna_mock_client(_make_http_response(status_code=500))

        params = _make_search_params(keywords=["python"])
        with (
            patch("app.adapters.sources.adzuna.settings", _adzuna_settings_mock()),
            patch(
                "app.adapters.sources.adzuna.httpx.AsyncClient",
                return_value=mock_client,
            ),
            pytest.raises(SourceError) as exc_info,
        ):
            await adapter.fetch_jobs(params)

        assert exc_info.value.error_type == SourceErrorType.API_DOWN

    async def test_raises_source_error_on_timeout(self) -> None:
        """fetch_jobs raises SourceError(TIMEOUT) on httpx.TimeoutException."""
        import httpx
        import pytest

        from app.adapters.sources.adzuna import AdzunaAdapter
        from app.services.discovery.scouter_errors import SourceError, SourceErrorType

        adapter = AdzunaAdapter()
        mock_client = _make_adzuna_mock_client(httpx.TimeoutException("timed out"))

        params = _make_search_params(keywords=["python"])
        with (
            patch("app.adapters.sources.adzuna.settings", _adzuna_settings_mock()),
            patch(
                "app.adapters.sources.adzuna.httpx.AsyncClient",
                return_value=mock_client,
            ),
            pytest.raises(SourceError) as exc_info,
        ):
            await adapter.fetch_jobs(params)

        assert exc_info.value.error_type == SourceErrorType.TIMEOUT
