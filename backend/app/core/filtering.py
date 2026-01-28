"""Filtering and sorting utilities for API endpoints.

REQ-006 §5.5: Standard filtering & sorting for collection endpoints.

Sorting:
    - `?sort=created_at` - Ascending by field
    - `?sort=-created_at` - Descending (prefix with `-`)
    - `?sort=-fit_score,title` - Multiple fields, comma-separated

Filtering:
    - `?status=Applied` - Exact match
    - `?status=Applied,Interviewing` - Match any (OR)

Example:
    GET /job-postings?status=Discovered&is_favorite=true&sort=-fit_score
"""

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from fastapi import Query
from pydantic import BaseModel


def parse_sort(sort_param: str | None) -> list[tuple[str, str]]:
    """Parse sort query parameter into field/direction tuples.

    Args:
        sort_param: Raw sort query string (e.g., "-fit_score,title").

    Returns:
        List of (field_name, direction) tuples.
        Direction is "asc" or "desc".

    Examples:
        >>> parse_sort("-fit_score,title")
        [("fit_score", "desc"), ("title", "asc")]

        >>> parse_sort("created_at")
        [("created_at", "asc")]
    """
    if not sort_param:
        return []

    result: list[tuple[str, str]] = []
    for part in sort_param.split(","):
        field_name = part.strip()
        if not field_name:
            continue

        if field_name.startswith("-"):
            result.append((field_name[1:].strip(), "desc"))
        else:
            result.append((field_name, "asc"))

    return result


def parse_filter_value(value: str | None) -> list[str]:
    """Parse filter value into list of values (for OR matching).

    Args:
        value: Raw filter value (e.g., "Applied,Interviewing").

    Returns:
        List of individual values, trimmed.

    Examples:
        >>> parse_filter_value("Applied,Interviewing")
        ["Applied", "Interviewing"]

        >>> parse_filter_value("Applied")
        ["Applied"]
    """
    if not value:
        return []

    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass
class SortParams:
    """Parsed sort parameters for a query.

    Attributes:
        fields: List of (field_name, direction) tuples.
    """

    fields: list[tuple[str, str]] = field(default_factory=list)

    @classmethod
    def from_query(cls, sort_param: str | None) -> "SortParams":
        """Create SortParams from query string.

        Args:
            sort_param: Raw sort query string.

        Returns:
            Parsed SortParams instance.
        """
        return cls(fields=parse_sort(sort_param))

    def is_empty(self) -> bool:
        """Check if no sort fields are specified.

        Returns:
            True if no sort fields, False otherwise.
        """
        return len(self.fields) == 0


class FilterParams(BaseModel):
    """Base class for filter parameters.

    Subclass this with typed fields for each resource's filters.

    Example:
        class JobPostingFilters(FilterParams):
            status: list[str] | None = None
            is_favorite: bool | None = None
            fit_score_min: float | None = None
    """

    model_config = {"extra": "ignore"}

    def active_filters(self) -> dict[str, Any]:
        """Get only the non-None filter values.

        Returns:
            Dict of field names to their values, excluding None.
            Values use Any because filter types vary: str, bool, float,
            list[str], date, uuid.UUID, etc.
        """
        return {
            field_name: value
            for field_name, value in self.model_dump().items()
            if value is not None
        }


# =============================================================================
# FastAPI Dependency Function
# =============================================================================


def sort_params(
    sort: str | None = Query(  # noqa: B008
        default=None,
        description="Sort fields. Use `-` prefix for descending. Comma-separate multiple.",
        examples=["-fit_score,title", "created_at", "-created_at"],
    ),
) -> SortParams:
    """FastAPI dependency for parsing sort query parameter.

    Usage:
        @router.get("")
        async def list_items(
            sort: SortParams = Depends(sort_params),
        ):
            ...

    Args:
        sort: Raw sort query parameter.

    Returns:
        Parsed SortParams instance.
    """
    return SortParams.from_query(sort)


# =============================================================================
# Resource-Specific Filter Classes (REQ-006 §5.5)
# =============================================================================


class JobPostingFilters(FilterParams):
    """Filter parameters for job postings.

    REQ-006 §5.5: Common filters for job-postings resource.
    """

    status: list[str] | None = None
    is_favorite: bool | None = None
    fit_score_min: float | None = None
    company_name: list[str] | None = None


class ApplicationFilters(FilterParams):
    """Filter parameters for applications.

    REQ-006 §5.5: Common filters for applications resource.
    """

    status: list[str] | None = None
    applied_after: date | None = None
    applied_before: date | None = None


class JobVariantFilters(FilterParams):
    """Filter parameters for job variants.

    REQ-006 §5.5: Common filters for job-variants resource.
    """

    status: list[str] | None = None
    base_resume_id: uuid.UUID | None = None


class PersonaChangeFlagFilters(FilterParams):
    """Filter parameters for persona change flags.

    REQ-006 §5.5: Common filters for persona-change-flags resource.
    """

    status: list[str] | None = None
