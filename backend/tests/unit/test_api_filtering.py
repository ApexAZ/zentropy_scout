"""Tests for API filtering and sorting utilities.

REQ-006 §5.5: Standard filtering & sorting for collection endpoints.
"""

from app.core.filtering import FilterParams, SortParams, parse_filter_value, parse_sort


class TestParseSortSingle:
    """Tests for parsing single sort field."""

    def test_ascending_sort(self):
        """Positive field name should sort ascending."""
        result = parse_sort("created_at")
        assert result == [("created_at", "asc")]

    def test_descending_sort_with_minus_prefix(self):
        """Negative prefix should sort descending."""
        result = parse_sort("-created_at")
        assert result == [("created_at", "desc")]


class TestParseSortMultiple:
    """Tests for parsing multiple sort fields."""

    def test_multiple_fields_comma_separated(self):
        """Multiple fields should be comma-separated."""
        result = parse_sort("-fit_score,title")
        assert result == [("fit_score", "desc"), ("title", "asc")]

    def test_multiple_fields_mixed_directions(self):
        """Each field can have independent sort direction."""
        result = parse_sort("-created_at,company_name,-fit_score")
        assert result == [
            ("created_at", "desc"),
            ("company_name", "asc"),
            ("fit_score", "desc"),
        ]


class TestParseSortEdgeCases:
    """Tests for sort edge cases."""

    def test_empty_sort_returns_empty_list(self):
        """Empty or None sort should return empty list."""
        assert parse_sort("") == []
        assert parse_sort(None) == []

    def test_whitespace_trimmed(self):
        """Whitespace around field names should be trimmed."""
        result = parse_sort(" created_at , -title ")
        assert result == [("created_at", "asc"), ("title", "desc")]


class TestParseFilterValue:
    """Tests for parsing filter values."""

    def test_single_value(self):
        """Single value returns list with one item."""
        result = parse_filter_value("Applied")
        assert result == ["Applied"]

    def test_multiple_values_comma_separated(self):
        """Multiple values are comma-separated (OR logic)."""
        result = parse_filter_value("Applied,Interviewing")
        assert result == ["Applied", "Interviewing"]

    def test_empty_value_returns_empty_list(self):
        """Empty value returns empty list."""
        assert parse_filter_value("") == []
        assert parse_filter_value(None) == []

    def test_whitespace_trimmed(self):
        """Whitespace around values should be trimmed."""
        result = parse_filter_value(" Applied , Interviewing ")
        assert result == ["Applied", "Interviewing"]


class TestSortParams:
    """Tests for SortParams dataclass."""

    def test_from_query_string(self):
        """SortParams should parse from query string."""
        params = SortParams.from_query("-fit_score,title")
        assert params.fields == [("fit_score", "desc"), ("title", "asc")]

    def test_is_empty_when_no_fields(self):
        """is_empty should return True when no sort fields."""
        params = SortParams.from_query("")
        assert params.is_empty() is True

    def test_is_not_empty_when_has_fields(self):
        """is_empty should return False when has sort fields."""
        params = SortParams.from_query("created_at")
        assert params.is_empty() is False


class TestFilterParams:
    """Tests for FilterParams model."""

    def test_create_filter_params_subclass(self):
        """Can create FilterParams subclass with typed fields."""

        class JobPostingFilters(FilterParams):
            status: list[str] | None = None
            is_favorite: bool | None = None
            fit_score_min: float | None = None
            company_name: list[str] | None = None

        filters = JobPostingFilters(status=["Discovered", "Applied"])
        assert filters.status == ["Discovered", "Applied"]
        assert filters.is_favorite is None

    def test_active_filters_excludes_none(self):
        """active_filters should exclude None values."""

        class JobPostingFilters(FilterParams):
            status: list[str] | None = None
            is_favorite: bool | None = None

        filters = JobPostingFilters(status=["Discovered"])
        active = filters.active_filters()
        assert "status" in active
        assert "is_favorite" not in active

    def test_active_filters_includes_false(self):
        """active_filters should include False boolean values."""

        class JobPostingFilters(FilterParams):
            is_favorite: bool | None = None

        filters = JobPostingFilters(is_favorite=False)
        active = filters.active_filters()
        assert "is_favorite" in active
        assert active["is_favorite"] is False


class TestFilterParamsListConversion:
    """Tests for filter value list conversion."""

    def test_status_filter_with_comma_separated_values(self):
        """Status filter should accept comma-separated values from query."""

        class ApplicationFilters(FilterParams):
            status: list[str] | None = None

        # Simulate what FastAPI would do with ?status=Applied,Interviewing
        values = parse_filter_value("Applied,Interviewing")
        filters = ApplicationFilters(status=values)
        assert filters.status == ["Applied", "Interviewing"]


class TestSortParamsDependency:
    """Tests for sort_params FastAPI dependency."""

    def test_sort_params_creates_sort_params(self):
        """sort_params dependency should create SortParams."""
        from app.core.filtering import sort_params

        result = sort_params("-fit_score,title")
        assert isinstance(result, SortParams)
        assert result.fields == [("fit_score", "desc"), ("title", "asc")]

    def test_sort_params_default_empty(self):
        """sort_params should default to empty."""
        from app.core.filtering import sort_params

        result = sort_params(None)
        assert result.is_empty() is True


class TestResourceFilterClasses:
    """Tests for resource-specific filter classes."""

    def test_job_posting_filters_has_expected_fields(self):
        """JobPostingFilters should have status, is_favorite, fit_score_min."""
        from app.core.filtering import JobPostingFilters

        filters = JobPostingFilters(
            status=["Discovered"],
            is_favorite=True,
            fit_score_min=0.7,
            company_name=["Acme"],
        )
        assert filters.status == ["Discovered"]
        assert filters.is_favorite is True
        assert filters.fit_score_min == 0.7
        assert filters.company_name == ["Acme"]

    def test_application_filters_has_expected_fields(self):
        """ApplicationFilters should have status, applied_after, applied_before."""
        from datetime import date

        from app.core.filtering import ApplicationFilters

        filters = ApplicationFilters(
            status=["Applied"],
            applied_after=date(2024, 1, 1),
            applied_before=date(2024, 12, 31),
        )
        assert filters.status == ["Applied"]
        assert filters.applied_after == date(2024, 1, 1)
        assert filters.applied_before == date(2024, 12, 31)

    def test_job_variant_filters_has_expected_fields(self):
        """JobVariantFilters should have status, base_resume_id."""
        import uuid

        from app.core.filtering import JobVariantFilters

        resume_id = uuid.uuid4()
        filters = JobVariantFilters(status=["Draft"], base_resume_id=resume_id)
        assert filters.status == ["Draft"]
        assert filters.base_resume_id == resume_id

    def test_persona_change_flag_filters_has_expected_fields(self):
        """PersonaChangeFlagFilters should have status filter."""
        from app.core.filtering import PersonaChangeFlagFilters

        filters = PersonaChangeFlagFilters(status=["Pending"])
        assert filters.status == ["Pending"]
