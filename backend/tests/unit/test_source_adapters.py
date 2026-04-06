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


def _make_async_http_client_mock(
    side_effect_or_return: Any,
) -> AsyncMock:
    """Build a mock httpx AsyncClient context manager for adapter tests.

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
        mock_client = _make_async_http_client_mock(
            _make_http_response(json_body=page_data)
        )

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
        mock_client = _make_async_http_client_mock(
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
        mock_client = _make_async_http_client_mock(
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
        mock_client = _make_async_http_client_mock(
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
        mock_client = _make_async_http_client_mock(
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
        mock_client = _make_async_http_client_mock(
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
        mock_client = _make_async_http_client_mock(
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
        mock_client = _make_async_http_client_mock(_make_http_response(status_code=500))

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
        mock_client = _make_async_http_client_mock(httpx.TimeoutException("timed out"))

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


# =============================================================================
# The Muse fetch_jobs() Tests (REQ-034 §5.3)
# =============================================================================


def _make_muse_job(job_id: int = 1, title: str = "Python Developer") -> dict[str, Any]:
    """Build a minimal The Muse API job result dict."""
    return {
        "id": job_id,
        "name": title,
        "company": {"name": "Test Corp"},
        "contents": "Do things",
        "refs": {"landing_page": f"https://www.themuse.com/jobs/{job_id}"},
        "locations": [{"name": "Remote"}],
    }


def _make_muse_response(
    jobs: list[dict[str, Any]],
    page_count: int = 1,
) -> dict[str, Any]:
    """Build a The Muse paginated response envelope."""
    return {"results": jobs, "page_count": page_count, "total": len(jobs)}


def _muse_settings_mock(api_key: str | None = "test-muse-key") -> MagicMock:
    """Build a settings mock with optional The Muse API key (SecretStr pattern)."""
    s = MagicMock()
    if api_key is not None:
        k = MagicMock()
        k.get_secret_value.return_value = api_key
        s.the_muse_api_key = k
    else:
        s.the_muse_api_key = None
    return s


class TestTheMuseFetchJobs:
    """Tests for TheMuseAdapter.fetch_jobs() per REQ-034 §5.3.

    Uses AsyncMock to mock httpx.AsyncClient — no network calls.
    """

    async def test_makes_unauthenticated_request_when_api_key_missing(self) -> None:
        """fetch_jobs omits api_key param (unauthenticated tier) when key is None."""
        from app.adapters.sources.themuse import TheMuseAdapter

        adapter = TheMuseAdapter()
        mock_client = _make_async_http_client_mock(
            _make_http_response(json_body=_make_muse_response([], page_count=1))
        )

        params = _make_search_params(keywords=["python"])
        with (
            patch(
                "app.adapters.sources.themuse.settings",
                _muse_settings_mock(api_key=None),
            ),
            patch(
                "app.adapters.sources.themuse.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            result = await adapter.fetch_jobs(params)

        assert result == []
        call_kwargs = mock_client.get.call_args
        assert "api_key" not in call_kwargs.kwargs.get("params", {})

    async def test_includes_api_key_in_request_when_configured(self) -> None:
        """fetch_jobs includes api_key query param when the_muse_api_key is set."""
        from app.adapters.sources.themuse import TheMuseAdapter

        adapter = TheMuseAdapter()
        mock_client = _make_async_http_client_mock(
            _make_http_response(json_body=_make_muse_response([], page_count=1))
        )

        params = _make_search_params(keywords=["python"])
        with (
            patch(
                "app.adapters.sources.themuse.settings",
                _muse_settings_mock(api_key="my-key"),
            ),
            patch(
                "app.adapters.sources.themuse.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            await adapter.fetch_jobs(params)

        call_kwargs = mock_client.get.call_args
        assert call_kwargs.kwargs["params"]["api_key"] == "my-key"

    async def test_single_page_returns_keyword_matching_jobs(self) -> None:
        """fetch_jobs returns normalized jobs whose titles match keywords."""
        from app.adapters.sources.themuse import TheMuseAdapter

        adapter = TheMuseAdapter()
        jobs = [
            _make_muse_job(1, "Python Developer"),
            _make_muse_job(2, "Python Engineer"),
        ]
        mock_client = _make_async_http_client_mock(
            _make_http_response(json_body=_make_muse_response(jobs, page_count=1))
        )

        params = _make_search_params(keywords=["python"])
        with (
            patch("app.adapters.sources.themuse.settings", _muse_settings_mock()),
            patch(
                "app.adapters.sources.themuse.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            result = await adapter.fetch_jobs(params)

        assert len(result) == 2
        assert result[0].external_id == "1"
        assert result[1].external_id == "2"

    async def test_keyword_filter_discards_non_matching_jobs(self) -> None:
        """fetch_jobs discards jobs whose titles don't contain any keyword."""
        from app.adapters.sources.themuse import TheMuseAdapter

        adapter = TheMuseAdapter()
        jobs = [
            _make_muse_job(1, "Python Developer"),
            _make_muse_job(2, "Marketing Manager"),
            _make_muse_job(3, "Senior Python Engineer"),
        ]
        mock_client = _make_async_http_client_mock(
            _make_http_response(json_body=_make_muse_response(jobs, page_count=1))
        )

        params = _make_search_params(keywords=["python"])
        with (
            patch("app.adapters.sources.themuse.settings", _muse_settings_mock()),
            patch(
                "app.adapters.sources.themuse.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            result = await adapter.fetch_jobs(params)

        assert len(result) == 2
        assert {r.external_id for r in result} == {"1", "3"}

    async def test_keyword_filter_is_case_insensitive(self) -> None:
        """fetch_jobs keyword filter matches regardless of case."""
        from app.adapters.sources.themuse import TheMuseAdapter

        adapter = TheMuseAdapter()
        jobs = [
            _make_muse_job(1, "PYTHON DEVELOPER"),
            _make_muse_job(2, "Python Engineer"),
            _make_muse_job(3, "Accountant"),
        ]
        mock_client = _make_async_http_client_mock(
            _make_http_response(json_body=_make_muse_response(jobs, page_count=1))
        )

        params = _make_search_params(keywords=["python"])
        with (
            patch("app.adapters.sources.themuse.settings", _muse_settings_mock()),
            patch(
                "app.adapters.sources.themuse.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            result = await adapter.fetch_jobs(params)

        assert len(result) == 2

    async def test_keyword_filter_matches_any_keyword(self) -> None:
        """fetch_jobs keeps job if ANY keyword in params.keywords matches title."""
        from app.adapters.sources.themuse import TheMuseAdapter

        adapter = TheMuseAdapter()
        jobs = [
            _make_muse_job(1, "Python Developer"),
            _make_muse_job(2, "Java Engineer"),
            _make_muse_job(3, "Project Manager"),
        ]
        mock_client = _make_async_http_client_mock(
            _make_http_response(json_body=_make_muse_response(jobs, page_count=1))
        )

        params = _make_search_params(keywords=["python", "java"])
        with (
            patch("app.adapters.sources.themuse.settings", _muse_settings_mock()),
            patch(
                "app.adapters.sources.themuse.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            result = await adapter.fetch_jobs(params)

        assert len(result) == 2
        assert {r.external_id for r in result} == {"1", "2"}

    async def test_pagination_fetches_all_pages_until_page_count(self) -> None:
        """fetch_jobs paginates through all pages (0-indexed) until page >= page_count."""
        from app.adapters.sources.themuse import TheMuseAdapter

        adapter = TheMuseAdapter()
        page0_jobs = [_make_muse_job(i, "Python Dev") for i in range(1, 4)]
        page1_jobs = [_make_muse_job(i, "Python Dev") for i in range(4, 7)]
        mock_client = _make_async_http_client_mock(
            [
                _make_http_response(
                    json_body=_make_muse_response(page0_jobs, page_count=2)
                ),
                _make_http_response(
                    json_body=_make_muse_response(page1_jobs, page_count=2)
                ),
            ]
        )

        params = _make_search_params(keywords=["python"])
        with (
            patch("app.adapters.sources.themuse.settings", _muse_settings_mock()),
            patch(
                "app.adapters.sources.themuse.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            result = await adapter.fetch_jobs(params)

        assert len(result) == 6
        assert mock_client.get.call_count == 2

    async def test_pagination_stops_when_page_count_reached(self) -> None:
        """fetch_jobs stops after the last page (page_count=1 means only page 0)."""
        from app.adapters.sources.themuse import TheMuseAdapter

        adapter = TheMuseAdapter()
        mock_client = _make_async_http_client_mock(
            _make_http_response(
                json_body=_make_muse_response(
                    [_make_muse_job(1, "Python Dev")], page_count=1
                )
            )
        )

        params = _make_search_params(keywords=["python"])
        with (
            patch("app.adapters.sources.themuse.settings", _muse_settings_mock()),
            patch(
                "app.adapters.sources.themuse.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            result = await adapter.fetch_jobs(params)

        assert len(result) == 1
        assert mock_client.get.call_count == 1

    async def test_pagination_stops_early_when_results_empty(self) -> None:
        """fetch_jobs stops early when results list is empty before page_count reached."""
        from app.adapters.sources.themuse import TheMuseAdapter

        adapter = TheMuseAdapter()
        # page_count=5 but first page returns no results — should stop after one call
        mock_client = _make_async_http_client_mock(
            _make_http_response(json_body=_make_muse_response([], page_count=5))
        )

        params = _make_search_params(keywords=["python"])
        with (
            patch("app.adapters.sources.themuse.settings", _muse_settings_mock()),
            patch(
                "app.adapters.sources.themuse.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            result = await adapter.fetch_jobs(params)

        assert result == []
        assert mock_client.get.call_count == 1

    async def test_raises_source_error_with_retry_after_on_429(self) -> None:
        """fetch_jobs raises SourceError(RATE_LIMITED) with retry_after on 429."""
        import pytest

        from app.adapters.sources.themuse import TheMuseAdapter
        from app.services.discovery.scouter_errors import SourceError, SourceErrorType

        adapter = TheMuseAdapter()
        mock_client = _make_async_http_client_mock(
            _make_http_response(status_code=429, headers={"Retry-After": "30"})
        )

        params = _make_search_params(keywords=["python"])
        with (
            patch("app.adapters.sources.themuse.settings", _muse_settings_mock()),
            patch(
                "app.adapters.sources.themuse.httpx.AsyncClient",
                return_value=mock_client,
            ),
            pytest.raises(SourceError) as exc_info,
        ):
            await adapter.fetch_jobs(params)

        assert exc_info.value.error_type == SourceErrorType.RATE_LIMITED
        assert exc_info.value.rate_limit_info is not None
        assert exc_info.value.rate_limit_info.retry_after_seconds == 30

    async def test_raises_source_error_on_500(self) -> None:
        """fetch_jobs raises SourceError(API_DOWN) on HTTP 500."""
        import pytest

        from app.adapters.sources.themuse import TheMuseAdapter
        from app.services.discovery.scouter_errors import SourceError, SourceErrorType

        adapter = TheMuseAdapter()
        mock_client = _make_async_http_client_mock(_make_http_response(status_code=500))

        params = _make_search_params(keywords=["python"])
        with (
            patch("app.adapters.sources.themuse.settings", _muse_settings_mock()),
            patch(
                "app.adapters.sources.themuse.httpx.AsyncClient",
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

        from app.adapters.sources.themuse import TheMuseAdapter
        from app.services.discovery.scouter_errors import SourceError, SourceErrorType

        adapter = TheMuseAdapter()
        mock_client = _make_async_http_client_mock(httpx.TimeoutException("timed out"))

        params = _make_search_params(keywords=["python"])
        with (
            patch("app.adapters.sources.themuse.settings", _muse_settings_mock()),
            patch(
                "app.adapters.sources.themuse.httpx.AsyncClient",
                return_value=mock_client,
            ),
            pytest.raises(SourceError) as exc_info,
        ):
            await adapter.fetch_jobs(params)

        assert exc_info.value.error_type == SourceErrorType.TIMEOUT


# =============================================================================
# RemoteOK fetch_jobs() Tests (REQ-034 §5.3)
# =============================================================================


def _make_remoteok_api_job(
    job_id: str = "rok-1",
    position: str = "Backend Engineer",
) -> dict[str, Any]:
    """Build a minimal RemoteOK API job dict."""
    return {
        "id": job_id,
        "position": position,
        "company": "Remote Corp",
        "description": "Build distributed systems",
        "url": f"https://remoteok.com/remote-jobs/{job_id}",
    }


def _make_remoteok_api_response(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build a RemoteOK API response list with metadata object at index 0.

    The real RemoteOK API prepends a legal/metadata notice at index 0.
    RemoteOKAdapter.fetch_jobs() skips this object and processes indices 1+.
    """
    metadata: dict[str, Any] = {
        "legal": "RemoteOK Terms",
        "apiVersion": "11",
        "url": "https://remoteok.com/api",
    }
    return [metadata, *jobs]


class TestRemoteOKFetchJobs:
    """Tests for RemoteOKAdapter.fetch_jobs() per REQ-034 §5.3.

    Uses AsyncMock to mock httpx.AsyncClient — no network calls.
    RemoteOK requires no credentials: no settings mock needed.
    """

    async def test_skips_metadata_at_index_zero_and_returns_jobs(self) -> None:
        """fetch_jobs skips index-0 metadata object and returns remaining jobs."""
        from app.adapters.sources.remoteok import RemoteOKAdapter

        adapter = RemoteOKAdapter()
        jobs = [_make_remoteok_api_job("1"), _make_remoteok_api_job("2")]
        mock_client = _make_async_http_client_mock(
            _make_http_response(json_body=_make_remoteok_api_response(jobs))
        )

        params = _make_search_params(keywords=["backend"])
        with patch(
            "app.adapters.sources.remoteok.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await adapter.fetch_jobs(params)

        assert len(result) == 2
        assert result[0].external_id == "1"
        assert result[1].external_id == "2"

    async def test_makes_single_http_call_no_pagination(self) -> None:
        """fetch_jobs makes exactly one GET call (no pagination)."""
        from app.adapters.sources.remoteok import RemoteOKAdapter

        adapter = RemoteOKAdapter()
        mock_client = _make_async_http_client_mock(
            _make_http_response(
                json_body=_make_remoteok_api_response(
                    [_make_remoteok_api_job("1"), _make_remoteok_api_job("2")]
                )
            )
        )

        params = _make_search_params(keywords=["backend"])
        with patch(
            "app.adapters.sources.remoteok.httpx.AsyncClient",
            return_value=mock_client,
        ):
            await adapter.fetch_jobs(params)

        assert mock_client.get.call_count == 1

    async def test_appends_tag_param_when_remoteok_tags_set(self) -> None:
        """fetch_jobs passes first remoteok_tag as ?tag= query param."""
        from app.adapters.sources.base import SearchParams
        from app.adapters.sources.remoteok import RemoteOKAdapter

        adapter = RemoteOKAdapter()
        mock_client = _make_async_http_client_mock(
            _make_http_response(json_body=_make_remoteok_api_response([]))
        )

        params = SearchParams(keywords=["python"], remoteok_tags=["python", "backend"])
        with patch(
            "app.adapters.sources.remoteok.httpx.AsyncClient",
            return_value=mock_client,
        ):
            await adapter.fetch_jobs(params)

        call_kwargs = mock_client.get.call_args
        assert call_kwargs.kwargs["params"]["tag"] == "python"

    async def test_omits_tag_param_when_remoteok_tags_empty(self) -> None:
        """fetch_jobs omits ?tag when remoteok_tags is an empty list."""
        from app.adapters.sources.base import SearchParams
        from app.adapters.sources.remoteok import RemoteOKAdapter

        adapter = RemoteOKAdapter()
        mock_client = _make_async_http_client_mock(
            _make_http_response(json_body=_make_remoteok_api_response([]))
        )

        params = SearchParams(keywords=["python"], remoteok_tags=[])
        with patch(
            "app.adapters.sources.remoteok.httpx.AsyncClient",
            return_value=mock_client,
        ):
            await adapter.fetch_jobs(params)

        call_kwargs = mock_client.get.call_args
        assert "tag" not in call_kwargs.kwargs.get("params", {})

    async def test_omits_tag_param_when_remoteok_tags_none(self) -> None:
        """fetch_jobs omits ?tag when remoteok_tags is None."""
        from app.adapters.sources.remoteok import RemoteOKAdapter

        adapter = RemoteOKAdapter()
        mock_client = _make_async_http_client_mock(
            _make_http_response(json_body=_make_remoteok_api_response([]))
        )

        params = _make_search_params(keywords=["python"])
        with patch(
            "app.adapters.sources.remoteok.httpx.AsyncClient",
            return_value=mock_client,
        ):
            await adapter.fetch_jobs(params)

        call_kwargs = mock_client.get.call_args
        assert "tag" not in call_kwargs.kwargs.get("params", {})

    async def test_returns_empty_list_when_no_jobs_after_metadata(self) -> None:
        """fetch_jobs returns [] when response contains only the metadata object."""
        from app.adapters.sources.remoteok import RemoteOKAdapter

        adapter = RemoteOKAdapter()
        mock_client = _make_async_http_client_mock(
            _make_http_response(json_body=_make_remoteok_api_response([]))
        )

        params = _make_search_params(keywords=["python"])
        with patch(
            "app.adapters.sources.remoteok.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await adapter.fetch_jobs(params)

        assert result == []

    async def test_skips_malformed_jobs_and_continues(self) -> None:
        """fetch_jobs skips jobs where normalize() raises KeyError and processes remaining."""
        from app.adapters.sources.remoteok import RemoteOKAdapter

        adapter = RemoteOKAdapter()
        # Missing 'position' field will cause KeyError in normalize()
        bad_job: dict[str, Any] = {
            "id": "bad",
            "company": "Bad Corp",
            "description": "No title",
            "url": "https://remoteok.com/remote-jobs/bad",
        }
        good_job = _make_remoteok_api_job("good")
        mock_client = _make_async_http_client_mock(
            _make_http_response(
                json_body=_make_remoteok_api_response([bad_job, good_job])
            )
        )

        params = _make_search_params(keywords=["python"])
        with patch(
            "app.adapters.sources.remoteok.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await adapter.fetch_jobs(params)

        assert len(result) == 1
        assert result[0].external_id == "good"

    async def test_raises_source_error_with_retry_after_on_429(self) -> None:
        """fetch_jobs raises SourceError(RATE_LIMITED) with retry_after seconds on 429."""
        import pytest

        from app.adapters.sources.remoteok import RemoteOKAdapter
        from app.services.discovery.scouter_errors import SourceError, SourceErrorType

        adapter = RemoteOKAdapter()
        mock_client = _make_async_http_client_mock(
            _make_http_response(status_code=429, headers={"Retry-After": "120"})
        )

        params = _make_search_params(keywords=["python"])
        with (
            patch(
                "app.adapters.sources.remoteok.httpx.AsyncClient",
                return_value=mock_client,
            ),
            pytest.raises(SourceError) as exc_info,
        ):
            await adapter.fetch_jobs(params)

        assert exc_info.value.error_type == SourceErrorType.RATE_LIMITED
        assert exc_info.value.rate_limit_info is not None
        assert exc_info.value.rate_limit_info.retry_after_seconds == 120

    async def test_raises_source_error_on_429_without_retry_after_header(self) -> None:
        """fetch_jobs raises SourceError(RATE_LIMITED) with rate_limit_info=None when header absent."""
        import pytest

        from app.adapters.sources.remoteok import RemoteOKAdapter
        from app.services.discovery.scouter_errors import SourceError, SourceErrorType

        adapter = RemoteOKAdapter()
        # 429 with no Retry-After header
        mock_client = _make_async_http_client_mock(_make_http_response(status_code=429))

        params = _make_search_params(keywords=["python"])
        with (
            patch(
                "app.adapters.sources.remoteok.httpx.AsyncClient",
                return_value=mock_client,
            ),
            pytest.raises(SourceError) as exc_info,
        ):
            await adapter.fetch_jobs(params)

        assert exc_info.value.error_type == SourceErrorType.RATE_LIMITED
        assert exc_info.value.rate_limit_info is None

    async def test_raises_source_error_on_429_with_non_integer_retry_after(
        self,
    ) -> None:
        """fetch_jobs raises SourceError(RATE_LIMITED) with rate_limit_info=None on HTTP-date Retry-After."""
        import pytest

        from app.adapters.sources.remoteok import RemoteOKAdapter
        from app.services.discovery.scouter_errors import SourceError, SourceErrorType

        adapter = RemoteOKAdapter()
        # Non-integer Retry-After (HTTP-date format) — ValueError guard should yield rate_limit_info=None
        mock_client = _make_async_http_client_mock(
            _make_http_response(
                status_code=429,
                headers={"Retry-After": "Fri, 01 Jan 2027 00:00:00 GMT"},
            )
        )

        params = _make_search_params(keywords=["python"])
        with (
            patch(
                "app.adapters.sources.remoteok.httpx.AsyncClient",
                return_value=mock_client,
            ),
            pytest.raises(SourceError) as exc_info,
        ):
            await adapter.fetch_jobs(params)

        assert exc_info.value.error_type == SourceErrorType.RATE_LIMITED
        assert exc_info.value.rate_limit_info is None

    async def test_raises_source_error_on_500(self) -> None:
        """fetch_jobs raises SourceError(API_DOWN) on HTTP 500."""
        import pytest

        from app.adapters.sources.remoteok import RemoteOKAdapter
        from app.services.discovery.scouter_errors import SourceError, SourceErrorType

        adapter = RemoteOKAdapter()
        mock_client = _make_async_http_client_mock(_make_http_response(status_code=500))

        params = _make_search_params(keywords=["python"])
        with (
            patch(
                "app.adapters.sources.remoteok.httpx.AsyncClient",
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

        from app.adapters.sources.remoteok import RemoteOKAdapter
        from app.services.discovery.scouter_errors import SourceError, SourceErrorType

        adapter = RemoteOKAdapter()
        mock_client = _make_async_http_client_mock(httpx.TimeoutException("timed out"))

        params = _make_search_params(keywords=["python"])
        with (
            patch(
                "app.adapters.sources.remoteok.httpx.AsyncClient",
                return_value=mock_client,
            ),
            pytest.raises(SourceError) as exc_info,
        ):
            await adapter.fetch_jobs(params)

        assert exc_info.value.error_type == SourceErrorType.TIMEOUT

    async def test_raises_source_error_on_network_error(self) -> None:
        """fetch_jobs raises SourceError(NETWORK_ERROR) on httpx.RequestError."""
        import httpx
        import pytest

        from app.adapters.sources.remoteok import RemoteOKAdapter
        from app.services.discovery.scouter_errors import SourceError, SourceErrorType

        adapter = RemoteOKAdapter()
        mock_client = _make_async_http_client_mock(
            httpx.ConnectError("connection refused")
        )

        params = _make_search_params(keywords=["python"])
        with (
            patch(
                "app.adapters.sources.remoteok.httpx.AsyncClient",
                return_value=mock_client,
            ),
            pytest.raises(SourceError) as exc_info,
        ):
            await adapter.fetch_jobs(params)

        assert exc_info.value.error_type == SourceErrorType.NETWORK_ERROR
