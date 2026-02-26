---
name: zentropy-api
description: |
  FastAPI patterns for Zentropy Scout REST API. Load this skill when:
  - Creating or modifying API endpoints
  - Writing routers, services, or response models
  - Implementing authentication, pagination, or error handling
  - Someone mentions "endpoint", "router", "REST", "response", or "API"
---

# FastAPI API Patterns

## Architecture: API-Mediated Everything

**All writes go through the API.** Agents, frontend, and extension are API clients.

```
Frontend / Extension / Agents
            │
            ▼
        ┌───────┐
        │  API  │ ← Validates, authorizes, logs
        └───┬───┘
            │
            ▼
       Repository → Database
```

**Why:** Single point for validation, tenant isolation, auditability.

---

## URL Structure

```
/api/v1/{resource}
/api/v1/{resource}/{id}
/api/v1/{resource}/{id}/{sub-resource}
```

**Examples:**
- `GET /api/v1/job-postings`
- `GET /api/v1/personas/{id}/skills`
- `POST /api/v1/job-postings/bulk-dismiss`

---

## Layer Organization

```
backend/app/
├── routers/           # FastAPI routers (thin, just HTTP)
│   ├── personas.py
│   ├── job_postings.py
│   └── __init__.py    # Mounts all routers
├── services/          # Business logic
│   ├── persona_service.py
│   └── job_service.py
├── repositories/      # Database access
│   ├── persona_repository.py
│   └── job_repository.py
├── schemas/           # Pydantic models
│   ├── persona.py     # PersonaCreate, PersonaUpdate, PersonaResponse
│   └── common.py      # Pagination, ErrorResponse
└── dependencies/      # FastAPI dependencies
    ├── auth.py        # get_current_user
    └── database.py    # get_db
```

---

## Response Envelope

**Success (single):**
```json
{"data": {...}}
```

**Success (collection):**
```json
{
  "data": [...],
  "meta": {"total": 42, "page": 1, "per_page": 20}
}
```

**Error:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable message",
    "details": [...]
  }
}
```

---

## Response Models

```python
from typing import Generic, TypeVar, Optional, List
from pydantic import BaseModel

T = TypeVar("T")

class DataResponse(BaseModel, Generic[T]):
    """Single resource response."""
    data: T

class PaginationMeta(BaseModel):
    total: int
    page: int
    per_page: int

class ListResponse(BaseModel, Generic[T]):
    """Collection response with pagination."""
    data: List[T]
    meta: PaginationMeta

class ErrorDetail(BaseModel):
    field: Optional[str] = None
    message: str

class ErrorResponse(BaseModel):
    error: dict  # {"code": str, "message": str, "details": List[ErrorDetail]}
```

---

## Router Pattern

```python
from fastapi import APIRouter, Depends, HTTPException, status
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.schemas.persona import PersonaCreate, PersonaResponse
from app.services.persona_service import PersonaService

router = APIRouter(prefix="/personas", tags=["personas"])

@router.post(
    "",
    response_model=DataResponse[PersonaResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_persona(
    persona_in: PersonaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DataResponse[PersonaResponse]:
    """Create a new persona.

    Args:
        persona_in: Persona creation data.

    Returns:
        The created persona wrapped in data envelope.

    Raises:
        HTTPException: 400 if validation fails.
    """
    service = PersonaService(db)
    persona = await service.create(persona_in, user_id=current_user.id)
    return DataResponse(data=PersonaResponse.model_validate(persona))
```

---

## Pagination

```python
from fastapi import Query

@router.get("", response_model=ListResponse[JobPostingResponse])
async def list_job_postings(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    sort: Optional[str] = Query(None),  # "-fit_score" = descending
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ListResponse[JobPostingResponse]:
    """List job postings with filtering and sorting."""
    service = JobPostingService(db)
    items, total = await service.list(
        user_id=current_user.id,
        status=status,
        sort=sort,
        page=page,
        per_page=per_page,
    )
    return ListResponse(
        data=[JobPostingResponse.model_validate(i) for i in items],
        meta=PaginationMeta(total=total, page=page, per_page=per_page),
    )
```

---

## Error Handling

### HTTP Status Codes

| Code | When |
|------|------|
| 200 | GET, PUT, PATCH success |
| 201 | POST success (created) |
| 204 | DELETE success |
| 400 | Validation error, malformed JSON |
| 401 | Missing/invalid auth |
| 403 | Valid auth but not your resource |
| 404 | Resource not found |
| 409 | Conflict (duplicate) |
| 422 | Business rule violation |
| 500 | Server error |

### Error Codes

```python
class ErrorCode:
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    FORBIDDEN = "FORBIDDEN"
    DUPLICATE = "DUPLICATE"
    INVALID_STATE = "INVALID_STATE_TRANSITION"
```

### Exception Handler

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from app.exceptions import ZentropyError, NotFoundError

@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=404,
        content={"error": {"code": "NOT_FOUND", "message": str(exc)}},
    )
```

---

## Authentication (MVP)

**Local mode:** No token, user from env var.

```python
# app/dependencies/auth.py
from app.core.config import settings

async def get_current_user() -> str:
    """Get current user ID.

    MVP: Returns DEFAULT_USER_ID from env.
    Future: Extract from JWT token.
    """
    return settings.DEFAULT_USER_ID
```

**Future hosted mode:** Swap implementation, not endpoint code.

---

## File Upload/Download

**Upload (multipart/form-data):**
```python
from fastapi import UploadFile, File

@router.post("/resume-files", response_model=DataResponse[ResumeFileResponse])
async def upload_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    content = await file.read()
    # Store as BYTEA in database (see zentropy-db)
    ...
```

**Download:**
```python
from fastapi.responses import Response

@router.get("/{id}/download")
async def download_resume(id: UUID, ...):
    resume = await service.get(id)
    return Response(
        content=resume.pdf_content,  # BYTEA from DB
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{resume.filename}"'},
    )
```

---

## Bulk Operations

**Explicit endpoints, not generic:**

```python
@router.post("/bulk-dismiss", response_model=BulkResponse)
async def bulk_dismiss(
    request: BulkDismissRequest,  # {"ids": ["uuid1", "uuid2"]}
    ...
):
    """Dismiss multiple job postings."""
    succeeded, failed = await service.bulk_dismiss(request.ids, user_id)
    return BulkResponse(
        data={"succeeded": succeeded, "failed": failed}
    )
```

**Response allows partial success:**
```json
{
  "data": {
    "succeeded": ["uuid1", "uuid2"],
    "failed": [{"id": "uuid3", "error": "NOT_FOUND"}]
  }
}
```

---

## Dependency Injection

```python
# app/dependencies/database.py
from app.core.database import async_session_maker

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

---

## Testing API Endpoints

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_create_persona(client: AsyncClient):
    response = await client.post(
        "/api/v1/personas",
        json={"full_name": "Test User", "email": "test@example.com"},
    )
    assert response.status_code == 201
    assert response.json()["data"]["full_name"] == "Test User"
```

---

## Checklist

Before committing an endpoint:

- [ ] Response wrapped in `DataResponse` or `ListResponse`
- [ ] Error responses use `ErrorResponse` shape
- [ ] `get_current_user` dependency for auth
- [ ] Docstring with Args/Returns/Raises
- [ ] Status codes match table above
- [ ] Test covers success and error cases
