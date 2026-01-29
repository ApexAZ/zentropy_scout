"""Base agent utilities and API client abstraction.

This module implements the API-mediated agent architecture defined in REQ-006 §2.3.

Architecture Pattern:
    All writes go through the API. Agents (Scouter, Ghostwriter) are internal API
    clients — they do NOT bypass the API to write directly to the database.

    ┌─────────────────┐         ┌──────────────┐
    │  Chrome Extension│         │ Frontend     │
    │  (untrusted)    │         │ (untrusted)  │
    └────────┬────────┘         └──────┬───────┘
             │ HTTP                    │ HTTP
             ▼                         ▼
    ┌─────────────────────────────────────────────┐
    │                      API                     │
    │  • Validates all input                       │
    │  • Enforces tenant isolation                 │
    │  • Single source of truth for business rules │
    └───────────────────────┬─────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
       ┌─────────────┐             ┌─────────────┐
       │   Scouter   │             │ Ghostwriter │
       │  (worker)   │             │  (worker)   │
       └──────┬──────┘             └──────┬──────┘
              │ Internal calls            │ Internal calls
              └───────────┬───────────────┘
                          ▼
                  ┌─────────────┐
                  │     API     │  (service layer, not HTTP)
                  └──────┬──────┘
                         ▼
                  ┌─────────────┐
                  │  Database   │
                  └─────────────┘

Implementation Modes:
    - LOCAL: Direct function calls to service layer (no HTTP overhead)
    - HOSTED: HTTP calls via httpx (future, for distributed deployment)

Usage:
    from app.agents.base import get_agent_client

    client = get_agent_client()
    jobs = await client.list_job_postings(user_id, status="New")
    await client.update_job_posting(job_id, {"status": "Reviewed"})

Type Notes:
    This module uses `dict[str, Any]` for API request/response data rather than
    typed Pydantic models. This is intentional: the agent client is a thin
    abstraction over the API layer, which already validates data using Pydantic
    schemas. Duplicating those schemas here would create maintenance burden and
    coupling. Agents receive raw dict data matching the API's response envelope.
"""

from abc import ABC, abstractmethod
from typing import Any, Protocol
from uuid import UUID

from app.core.config import settings


class AgentAPIClient(Protocol):
    """Protocol defining the interface agents use to interact with the API.

    This abstraction allows agents to work identically in local mode (direct
    service calls) and hosted mode (HTTP calls). All methods enforce tenant
    isolation by requiring user_id.

    Methods are grouped by resource type matching the REST API structure.
    """

    # -------------------------------------------------------------------------
    # Job Postings
    # -------------------------------------------------------------------------

    async def list_job_postings(
        self,
        user_id: str,
        *,
        status: str | None = None,
        source: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        """List job postings for a user with optional filtering.

        Args:
            user_id: The user's ID (tenant isolation).
            status: Filter by status (New, Reviewed, Applied, etc.).
            source: Filter by source (LinkedIn, Indeed, etc.).
            page: Page number for pagination.
            per_page: Items per page.

        Returns:
            Dict with 'data' (list) and 'meta' (pagination info).
        """
        ...

    async def create_job_posting(
        self,
        user_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new job posting.

        Args:
            user_id: The user's ID (tenant isolation).
            data: Job posting data including url, raw_text, etc.

        Returns:
            Dict with 'data' containing the created job posting.
        """
        ...

    async def update_job_posting(
        self,
        job_posting_id: str | UUID,
        user_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing job posting.

        Args:
            job_posting_id: The job posting's ID.
            user_id: The user's ID (tenant isolation).
            data: Fields to update.

        Returns:
            Dict with 'data' containing the updated job posting.
        """
        ...

    async def get_job_posting(
        self,
        job_posting_id: str | UUID,
        user_id: str,
    ) -> dict[str, Any]:
        """Get a job posting by ID.

        Args:
            job_posting_id: The job posting's ID.
            user_id: The user's ID (tenant isolation).

        Returns:
            Dict with 'data' containing the job posting.
        """
        ...

    async def bulk_dismiss_job_postings(
        self,
        user_id: str,
        job_ids: list[str],
    ) -> dict[str, Any]:
        """Bulk dismiss multiple job postings.

        Args:
            user_id: The user's ID (tenant isolation).
            job_ids: List of job posting IDs to dismiss.

        Returns:
            Dict with bulk operation result.
        """
        ...

    async def bulk_favorite_job_postings(
        self,
        user_id: str,
        job_ids: list[str],
        *,
        is_favorite: bool = True,
    ) -> dict[str, Any]:
        """Bulk favorite/unfavorite multiple job postings.

        Args:
            user_id: The user's ID (tenant isolation).
            job_ids: List of job posting IDs.
            is_favorite: True to favorite, False to unfavorite.

        Returns:
            Dict with bulk operation result.
        """
        ...

    # -------------------------------------------------------------------------
    # Personas
    # -------------------------------------------------------------------------

    async def get_persona(
        self,
        persona_id: str | UUID,
        user_id: str,
    ) -> dict[str, Any]:
        """Get a persona by ID.

        Args:
            persona_id: The persona's ID.
            user_id: The user's ID (tenant isolation).

        Returns:
            Dict with 'data' containing the persona.
        """
        ...

    async def update_persona(
        self,
        persona_id: str | UUID,
        user_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing persona.

        Args:
            persona_id: The persona's ID.
            user_id: The user's ID (tenant isolation).
            data: Fields to update.

        Returns:
            Dict with 'data' containing the updated persona.
        """
        ...

    # -------------------------------------------------------------------------
    # Job Variants (Tailored Resumes)
    # -------------------------------------------------------------------------

    async def list_job_variants(
        self,
        user_id: str,
        *,
        status: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        """List job variants for a user.

        Args:
            user_id: The user's ID (tenant isolation).
            status: Filter by status (Draft, Approved, etc.).
            page: Page number for pagination.
            per_page: Items per page.

        Returns:
            Dict with 'data' (list) and 'meta' (pagination info).
        """
        ...

    async def create_job_variant(
        self,
        user_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new job variant (tailored resume).

        Args:
            user_id: The user's ID (tenant isolation).
            data: Variant data including job_posting_id, base_resume_id, etc.

        Returns:
            Dict with 'data' containing the created variant.
        """
        ...

    async def get_job_variant(
        self,
        job_variant_id: str | UUID,
        user_id: str,
    ) -> dict[str, Any]:
        """Get a job variant by ID.

        Args:
            job_variant_id: The variant's ID.
            user_id: The user's ID (tenant isolation).

        Returns:
            Dict with 'data' containing the variant.
        """
        ...

    async def update_job_variant(
        self,
        job_variant_id: str | UUID,
        user_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing job variant.

        Args:
            job_variant_id: The variant's ID.
            user_id: The user's ID (tenant isolation).
            data: Fields to update.

        Returns:
            Dict with 'data' containing the updated variant.
        """
        ...

    # -------------------------------------------------------------------------
    # Cover Letters
    # -------------------------------------------------------------------------

    async def get_cover_letter(
        self,
        cover_letter_id: str | UUID,
        user_id: str,
    ) -> dict[str, Any]:
        """Get a cover letter by ID.

        Args:
            cover_letter_id: The cover letter's ID.
            user_id: The user's ID (tenant isolation).

        Returns:
            Dict with 'data' containing the cover letter.
        """
        ...

    async def create_cover_letter(
        self,
        user_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new cover letter.

        Args:
            user_id: The user's ID (tenant isolation).
            data: Cover letter data including job_variant_id, content, etc.

        Returns:
            Dict with 'data' containing the created cover letter.
        """
        ...

    async def update_cover_letter(
        self,
        cover_letter_id: str | UUID,
        user_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing cover letter.

        Args:
            cover_letter_id: The cover letter's ID.
            user_id: The user's ID (tenant isolation).
            data: Fields to update.

        Returns:
            Dict with 'data' containing the updated cover letter.
        """
        ...

    async def regenerate_cover_letter(
        self,
        cover_letter_id: str | UUID,
        user_id: str,
    ) -> dict[str, Any]:
        """Request regeneration of a cover letter.

        Args:
            cover_letter_id: The cover letter's ID.
            user_id: The user's ID (tenant isolation).

        Returns:
            Dict with 'data' containing the regeneration status.
        """
        ...

    # -------------------------------------------------------------------------
    # Applications
    # -------------------------------------------------------------------------

    async def list_applications(
        self,
        user_id: str,
        *,
        status: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        """List applications for a user.

        Args:
            user_id: The user's ID (tenant isolation).
            status: Filter by status (Applied, Interviewing, etc.).
            page: Page number for pagination.
            per_page: Items per page.

        Returns:
            Dict with 'data' (list) and 'meta' (pagination info).
        """
        ...

    async def get_application(
        self,
        application_id: str | UUID,
        user_id: str,
    ) -> dict[str, Any]:
        """Get an application by ID.

        Args:
            application_id: The application's ID.
            user_id: The user's ID (tenant isolation).

        Returns:
            Dict with 'data' containing the application.
        """
        ...

    async def create_application(
        self,
        user_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new application.

        Args:
            user_id: The user's ID (tenant isolation).
            data: Application data including job_posting_id, status, etc.

        Returns:
            Dict with 'data' containing the created application.
        """
        ...

    async def update_application(
        self,
        application_id: str | UUID,
        user_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing application.

        Args:
            application_id: The application's ID.
            user_id: The user's ID (tenant isolation).
            data: Fields to update.

        Returns:
            Dict with 'data' containing the updated application.
        """
        ...

    # -------------------------------------------------------------------------
    # Base Resumes
    # -------------------------------------------------------------------------

    async def list_base_resumes(
        self,
        user_id: str,
        *,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        """List base resumes for a user.

        Args:
            user_id: The user's ID (tenant isolation).
            page: Page number for pagination.
            per_page: Items per page.

        Returns:
            Dict with 'data' (list) and 'meta' (pagination info).
        """
        ...

    async def get_base_resume(
        self,
        base_resume_id: str | UUID,
        user_id: str,
    ) -> dict[str, Any]:
        """Get a base resume by ID.

        Args:
            base_resume_id: The base resume's ID.
            user_id: The user's ID (tenant isolation).

        Returns:
            Dict with 'data' containing the base resume.
        """
        ...

    # -------------------------------------------------------------------------
    # Persona Change Flags
    # -------------------------------------------------------------------------

    async def list_persona_change_flags(
        self,
        user_id: str,
        *,
        resolved: bool | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        """List persona change flags for a user.

        Args:
            user_id: The user's ID (tenant isolation).
            resolved: Filter by resolved status.
            page: Page number for pagination.
            per_page: Items per page.

        Returns:
            Dict with 'data' (list) and 'meta' (pagination info).
        """
        ...

    async def update_persona_change_flag(
        self,
        flag_id: str | UUID,
        user_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update a persona change flag.

        Args:
            flag_id: The flag's ID.
            user_id: The user's ID (tenant isolation).
            data: Fields to update (e.g., resolved=True).

        Returns:
            Dict with 'data' containing the updated flag.
        """
        ...

    # -------------------------------------------------------------------------
    # Refresh / Triggers
    # -------------------------------------------------------------------------

    async def trigger_refresh(
        self,
        user_id: str,
    ) -> dict[str, Any]:
        """Trigger a job refresh for the user.

        Args:
            user_id: The user's ID (tenant isolation).

        Returns:
            Dict with refresh status.
        """
        ...


class BaseAgentClient(ABC):
    """Abstract base class for agent API clients.

    Provides common functionality and enforces the interface. Concrete
    implementations handle the actual API communication.
    """

    @abstractmethod
    async def _request(
        self,
        method: str,
        path: str,
        user_id: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an API request.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE).
            path: API path (e.g., '/job-postings').
            user_id: User ID for tenant isolation.
            params: Query parameters.
            data: Request body data.

        Returns:
            Response data as dict.

        Raises:
            APIError subclasses for error responses.
        """
        ...

    # -------------------------------------------------------------------------
    # Job Postings Implementation
    # -------------------------------------------------------------------------

    async def list_job_postings(
        self,
        user_id: str,
        *,
        status: str | None = None,
        source: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        """List job postings for a user."""
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        if status:
            params["status"] = status
        if source:
            params["source"] = source
        return await self._request("GET", "/job-postings", user_id, params=params)

    async def create_job_posting(
        self,
        user_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new job posting."""
        return await self._request("POST", "/job-postings", user_id, data=data)

    async def update_job_posting(
        self,
        job_posting_id: str | UUID,
        user_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing job posting."""
        return await self._request(
            "PATCH",
            f"/job-postings/{job_posting_id}",
            user_id,
            data=data,
        )

    async def get_job_posting(
        self,
        job_posting_id: str | UUID,
        user_id: str,
    ) -> dict[str, Any]:
        """Get a job posting by ID."""
        return await self._request("GET", f"/job-postings/{job_posting_id}", user_id)

    async def bulk_dismiss_job_postings(
        self,
        user_id: str,
        job_ids: list[str],
    ) -> dict[str, Any]:
        """Bulk dismiss multiple job postings."""
        return await self._request(
            "POST",
            "/job-postings/bulk-dismiss",
            user_id,
            data={"ids": job_ids},
        )

    async def bulk_favorite_job_postings(
        self,
        user_id: str,
        job_ids: list[str],
        *,
        is_favorite: bool = True,
    ) -> dict[str, Any]:
        """Bulk favorite/unfavorite multiple job postings."""
        return await self._request(
            "POST",
            "/job-postings/bulk-favorite",
            user_id,
            data={"ids": job_ids, "is_favorite": is_favorite},
        )

    # -------------------------------------------------------------------------
    # Personas Implementation
    # -------------------------------------------------------------------------

    async def get_persona(
        self,
        persona_id: str | UUID,
        user_id: str,
    ) -> dict[str, Any]:
        """Get a persona by ID."""
        return await self._request("GET", f"/personas/{persona_id}", user_id)

    async def update_persona(
        self,
        persona_id: str | UUID,
        user_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing persona."""
        return await self._request(
            "PATCH",
            f"/personas/{persona_id}",
            user_id,
            data=data,
        )

    # -------------------------------------------------------------------------
    # Job Variants Implementation
    # -------------------------------------------------------------------------

    async def list_job_variants(
        self,
        user_id: str,
        *,
        status: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        """List job variants for a user."""
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        if status:
            params["status"] = status
        return await self._request("GET", "/job-variants", user_id, params=params)

    async def create_job_variant(
        self,
        user_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new job variant."""
        return await self._request("POST", "/job-variants", user_id, data=data)

    async def get_job_variant(
        self,
        job_variant_id: str | UUID,
        user_id: str,
    ) -> dict[str, Any]:
        """Get a job variant by ID."""
        return await self._request("GET", f"/job-variants/{job_variant_id}", user_id)

    async def update_job_variant(
        self,
        job_variant_id: str | UUID,
        user_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing job variant."""
        return await self._request(
            "PATCH",
            f"/job-variants/{job_variant_id}",
            user_id,
            data=data,
        )

    # -------------------------------------------------------------------------
    # Cover Letters Implementation
    # -------------------------------------------------------------------------

    async def get_cover_letter(
        self,
        cover_letter_id: str | UUID,
        user_id: str,
    ) -> dict[str, Any]:
        """Get a cover letter by ID."""
        return await self._request("GET", f"/cover-letters/{cover_letter_id}", user_id)

    async def create_cover_letter(
        self,
        user_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new cover letter."""
        return await self._request("POST", "/cover-letters", user_id, data=data)

    async def update_cover_letter(
        self,
        cover_letter_id: str | UUID,
        user_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing cover letter."""
        return await self._request(
            "PATCH",
            f"/cover-letters/{cover_letter_id}",
            user_id,
            data=data,
        )

    async def regenerate_cover_letter(
        self,
        cover_letter_id: str | UUID,
        user_id: str,
    ) -> dict[str, Any]:
        """Request regeneration of a cover letter."""
        return await self._request(
            "POST",
            f"/cover-letters/{cover_letter_id}/regenerate",
            user_id,
        )

    # -------------------------------------------------------------------------
    # Applications Implementation
    # -------------------------------------------------------------------------

    async def list_applications(
        self,
        user_id: str,
        *,
        status: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        """List applications for a user."""
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        if status:
            params["status"] = status
        return await self._request("GET", "/applications", user_id, params=params)

    async def get_application(
        self,
        application_id: str | UUID,
        user_id: str,
    ) -> dict[str, Any]:
        """Get an application by ID."""
        return await self._request("GET", f"/applications/{application_id}", user_id)

    async def create_application(
        self,
        user_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new application."""
        return await self._request("POST", "/applications", user_id, data=data)

    async def update_application(
        self,
        application_id: str | UUID,
        user_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing application."""
        return await self._request(
            "PATCH",
            f"/applications/{application_id}",
            user_id,
            data=data,
        )

    # -------------------------------------------------------------------------
    # Base Resumes Implementation
    # -------------------------------------------------------------------------

    async def list_base_resumes(
        self,
        user_id: str,
        *,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        """List base resumes for a user."""
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        return await self._request("GET", "/base-resumes", user_id, params=params)

    async def get_base_resume(
        self,
        base_resume_id: str | UUID,
        user_id: str,
    ) -> dict[str, Any]:
        """Get a base resume by ID."""
        return await self._request("GET", f"/base-resumes/{base_resume_id}", user_id)

    # -------------------------------------------------------------------------
    # Persona Change Flags Implementation
    # -------------------------------------------------------------------------

    async def list_persona_change_flags(
        self,
        user_id: str,
        *,
        resolved: bool | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        """List persona change flags for a user."""
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        if resolved is not None:
            params["resolved"] = resolved
        return await self._request(
            "GET", "/persona-change-flags", user_id, params=params
        )

    async def update_persona_change_flag(
        self,
        flag_id: str | UUID,
        user_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update a persona change flag."""
        return await self._request(
            "PATCH",
            f"/persona-change-flags/{flag_id}",
            user_id,
            data=data,
        )

    # -------------------------------------------------------------------------
    # Refresh Implementation
    # -------------------------------------------------------------------------

    async def trigger_refresh(
        self,
        user_id: str,
    ) -> dict[str, Any]:
        """Trigger a job refresh for the user."""
        return await self._request("POST", "/refresh", user_id)


class LocalAgentClient(BaseAgentClient):
    """Agent client for local mode using direct service calls.

    In local mode, agents call services directly without HTTP overhead.
    This is the recommended mode for single-user local deployment.

    The client maintains a reference to the database session and calls
    service layer methods directly, while still respecting the API's
    validation and authorization rules.

    Note:
        Implementation requires the service layer from Phase 2 (Agent Framework).
        The _request method will be completed when services are implemented in
        Phase 2.1 (LangGraph Foundation, REQ-007 §3).
    """

    def __init__(self) -> None:
        """Initialize the local agent client."""
        # Service instances will be injected when services are implemented.
        # For now, the _request method raises NotImplementedError.
        pass

    async def _request(
        self,
        method: str,
        path: str,
        user_id: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a request via direct service calls.

        This method will be implemented when the service layer is complete.
        It will route requests to the appropriate service methods.

        Args:
            method: HTTP method (maps to service operations).
            path: API path (maps to resource/action).
            user_id: User ID for tenant isolation.
            params: Query parameters (for filtering/pagination).
            data: Request body data.

        Returns:
            Response data matching API response envelope.

        Raises:
            NotImplementedError: Until services are implemented.
        """
        # WHY: This placeholder ensures the architecture is in place before
        # services are implemented. Agents can be developed against this
        # interface and will work once services are added.
        raise NotImplementedError(
            f"LocalAgentClient._request not yet implemented. "
            f"Services layer required. Path: {method} {path}"
        )


class HTTPAgentClient(BaseAgentClient):
    """Agent client for hosted mode using HTTP calls.

    In hosted mode, agents call the API via HTTP. This enables distributed
    deployment where agents run as separate services.

    Note:
        This is a future implementation for hosted/multi-tenant mode.
        Not required for MVP local deployment. Will use httpx for HTTP
        communication when distributed deployment is supported.
    """

    def __init__(self, base_url: str | None = None) -> None:
        """Initialize the HTTP agent client.

        Args:
            base_url: API base URL. Defaults to http://localhost:8000/api/v1.
        """
        self.base_url = base_url or f"http://localhost:{settings.api_port}/api/v1"

    async def _request(
        self,
        method: str,
        path: str,
        user_id: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a request via HTTP.

        Future implementation using httpx.

        Args:
            method: HTTP method.
            path: API path.
            user_id: User ID (sent as header for tenant isolation).
            params: Query parameters.
            data: Request body data.

        Returns:
            Response data from API.

        Raises:
            NotImplementedError: Until hosted mode is implemented.
        """
        # WHY: Placeholder for future hosted mode. The same agent code will
        # work with either client implementation.
        raise NotImplementedError(
            "HTTPAgentClient not yet implemented. "
            "This is for future hosted/distributed deployment."
        )


# Module-level singleton for the agent client
_agent_client: BaseAgentClient | None = None


def get_agent_client() -> BaseAgentClient:
    """Get the configured agent API client.

    Returns the appropriate client based on deployment mode:
    - LOCAL: LocalAgentClient (direct service calls)
    - HOSTED: HTTPAgentClient (HTTP calls) [future]

    Returns:
        Configured agent client instance.

    Example:
        client = get_agent_client()
        jobs = await client.list_job_postings(user_id, status="New")
    """
    global _agent_client

    if _agent_client is None:
        # WHY: Default to local mode for MVP. Hosted mode will be enabled
        # via configuration when multi-tenant support is added.
        _agent_client = LocalAgentClient()

    return _agent_client


def reset_agent_client() -> None:
    """Reset the agent client singleton.

    Useful for testing to inject mock clients.
    """
    global _agent_client
    _agent_client = None
