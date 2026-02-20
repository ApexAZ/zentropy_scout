# REQ-014: Multi-Tenant Data Isolation

**Status:** Draft
**PRD Reference:** §5 Architecture, §6 Data Strategy
**Last Updated:** 2026-02-18

---

## 1. Overview

This document specifies the multi-tenant data isolation strategy for Zentropy Scout. It ensures that authenticated users (REQ-013) can only access their own data — personas, jobs, applications, resumes, cover letters, and all derived content.

**Key Principle:** Authorization answers "what can you see?" Every query must be scoped to the authenticated user. Cross-tenant data leakage is a critical security defect.

**Scope:**
- Row-level data isolation through the existing `persona.user_id` FK chain
- Ownership verification patterns for all API endpoints
- Agent scoping (LangGraph agents receive user context)
- Database indexes for tenant-scoped queries
- Migration from single-user to multi-user
- Cross-tenant leakage testing strategy

**Out of scope:** Row-Level Security (RLS) policies in PostgreSQL (defense-in-depth, can add later), per-user storage quotas, per-user LLM API key (BYOK), admin dashboard.

---

## 2. Dependencies

### 2.1 This Document Depends On

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-005 Database Schema v0.10 | Schema | Entity relationships, FK chain |
| REQ-006 API Contract v0.8 | Integration | Authorization pattern (§6.2), endpoint inventory |
| REQ-007 Agent Behavior v0.5 | Integration | Agent state includes `user_id` (§4.1, §15) |
| REQ-013 Authentication v0.1 | Prerequisite | Provides authenticated `user_id` |

### 2.2 Other Documents Depend On This

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-015 Shared Job Pool | Update required | Entity ownership graph changes — job_postings moves to Tier 0 |

---

## 3. Design Decisions & Rationale

### 3.1 Isolation Strategy: Application-Level Row Filtering

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| Application-level row filtering | ✅ | Explicit, auditable, testable. Every query includes `WHERE persona.user_id = :user_id`. Developers can see and verify the isolation logic. Works with any database. |
| PostgreSQL Row-Level Security (RLS) | Deferred | Defense-in-depth addition for later. RLS policies are invisible — harder to audit and debug. Requires `SET ROLE` per-request, adding latency. Better as a second layer, not the primary mechanism. |
| Schema-per-tenant | — | Massive operational overhead. Migrations must run per-schema. Connection pooling is complex. Only justified at 10,000+ tenants. |

**Future enhancement:** Add RLS policies as a defense-in-depth layer after the application-level filtering is verified by integration tests.

### 3.2 Ownership Enforcement: Join-Through-Persona Pattern

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| JOIN through persona chain | ✅ | Only `personas` has a direct `user_id` FK. All other tables (23 of 25) inherit isolation through their FK to `persona_id`. This is already the schema design — no migration needed. Consistent single pattern for all queries. |
| Add `user_id` to every table | — | Denormalization. Creates 23 extra FK columns. Risk of `user_id` drifting out of sync with persona ownership. More indexes, more storage, more migration work. Only justified if JOIN performance is a problem (it won't be at MVP scale). |

---

## 4. Entity Ownership Graph

### 4.1 Tier Classification

All 25 database tables classified by their distance from the `users` table:

```
Tier 0 — Global (no tenant isolation)
  └── job_sources              Shared catalog of external job sources

Tier 0 — Tenant Root
  └── users                    Authenticated user identity (REQ-013)

Tier 1 — Direct User Ownership
  └── personas                 user_id → users.id (EXISTING FK)

Tier 2 — Persona-Scoped (15 tables)
  ├── work_histories           persona_id → personas.id
  ├── skills                   persona_id → personas.id
  ├── educations               persona_id → personas.id
  ├── certifications           persona_id → personas.id
  ├── achievement_stories      persona_id → personas.id
  ├── voice_profiles           persona_id → personas.id (unique)
  ├── custom_non_negotiables   persona_id → personas.id
  ├── persona_embeddings       persona_id → personas.id
  ├── persona_change_flags     persona_id → personas.id
  ├── resume_files             persona_id → personas.id
  ├── base_resumes             persona_id → personas.id
  ├── user_source_preferences  persona_id → personas.id
  ├── polling_configurations   persona_id → personas.id (unique)
  ├── job_postings             persona_id → personas.id
  └── cover_letters            persona_id → personas.id

Tier 3 — Child of Tier 2 (4 tables)
  ├── bullets                  work_history_id → work_histories.id
  ├── extracted_skills         job_posting_id → job_postings.id
  ├── job_embeddings           job_posting_id → job_postings.id
  └── job_variants             base_resume_id → base_resumes.id

Tier 4 — Deep Children (3 tables)
  ├── applications             persona_id → personas.id (also direct FK)
  ├── submitted_resume_pdfs    application_id → applications.id
  └── submitted_cover_letter_pdfs  cover_letter_id → cover_letters.id

Tier 5 — Deepest Children (1 table)
  └── timeline_events          application_id → applications.id
```

### 4.2 Isolation Rules

| Table Tier | Isolation Method | Example |
|------------|-----------------|---------|
| Tier 0 (global) | No filtering — shared across all tenants | `SELECT * FROM job_sources` |
| Tier 1 (personas) | Direct `WHERE user_id = :uid` | `SELECT * FROM personas WHERE user_id = :uid` |
| Tier 2 | JOIN to personas | `SELECT * FROM skills JOIN personas ON skills.persona_id = personas.id WHERE personas.user_id = :uid` |
| Tier 3 | JOIN through Tier 2 parent to personas | `SELECT * FROM bullets JOIN work_histories ON ... JOIN personas ON ... WHERE personas.user_id = :uid` |
| Tier 4+ | JOIN through chain to personas | Same pattern, deeper chain |

**Shortcut for Tier 2 with known persona_id:** If the caller already has a verified `persona_id` (e.g., from a previous ownership check), child queries can use `WHERE persona_id = :verified_persona_id` without re-joining to personas.

**Multi-persona users:** A user can have multiple personas. List endpoints (e.g., `GET /personas`) return all personas for the authenticated user. Child entity endpoints (e.g., `GET /job-postings`) are scoped to a specific persona — the user must select which persona to view. Cross-persona visibility within the same user is intentional: a user owns all their personas and can switch between them. Tenant isolation prevents User A from seeing User B's data, not User A's Persona 1 from seeing User A's Persona 2.

---

## 5. Ownership Verification Patterns

### 5.1 Pattern A: Direct Persona Lookup

For endpoints that operate on personas directly:

```python
async def get_persona(persona_id: UUID, user_id: UUID, db: AsyncSession) -> Persona:
    result = await db.execute(
        select(Persona).where(
            Persona.id == persona_id,
            Persona.user_id == user_id,
        )
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise NotFoundError("Persona not found")  # 404, not 403
    return persona
```

**Security note:** Return 404 (not 403) when the resource exists but belongs to another user. This prevents enumeration attacks — the attacker cannot distinguish "doesn't exist" from "exists but not yours."

### 5.2 Pattern B: Join Through Persona

For endpoints that operate on Tier 2+ entities:

```python
async def get_base_resume(resume_id: UUID, user_id: UUID, db: AsyncSession) -> BaseResume:
    result = await db.execute(
        select(BaseResume)
        .join(Persona, BaseResume.persona_id == Persona.id)
        .where(
            BaseResume.id == resume_id,
            Persona.user_id == user_id,
        )
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise NotFoundError("Resume not found")
    return resume
```

### 5.3 Pattern C: Deep Join for Tier 3+

For entities nested multiple levels deep:

```python
async def get_bullet(bullet_id: UUID, user_id: UUID, db: AsyncSession) -> Bullet:
    result = await db.execute(
        select(Bullet)
        .join(WorkHistory, Bullet.work_history_id == WorkHistory.id)
        .join(Persona, WorkHistory.persona_id == Persona.id)
        .where(
            Bullet.id == bullet_id,
            Persona.user_id == user_id,
        )
    )
    bullet = result.scalar_one_or_none()
    if not bullet:
        raise NotFoundError("Bullet not found")
    return bullet
```

### 5.4 Pattern D: List Queries

All list endpoints must be scoped to the authenticated user:

```python
async def list_job_postings(user_id: UUID, persona_id: UUID, db: AsyncSession):
    result = await db.execute(
        select(JobPosting)
        .join(Persona, JobPosting.persona_id == Persona.id)
        .where(
            Persona.id == persona_id,
            Persona.user_id == user_id,  # Tenant isolation
        )
        .order_by(JobPosting.created_at.desc())
    )
    return result.scalars().all()
```

---

## 6. API Endpoint Audit

### 6.1 Current State

All endpoints already inject `CurrentUserId` dependency but not all verify ownership consistently. The following audit classifies each endpoint:

| Router | Prefix | Ownership Enforced? | Notes |
|--------|--------|---------------------|-------|
| personas | `/personas` | Partial | List filters by user_id. Detail/update are stubs (TODO). |
| job_postings | `/job-postings` | Yes | Ingest and list filter through persona. |
| base_resumes | `/base-resumes` | Yes | All operations JOIN to personas. Reference implementation. |
| job_variants | `/job-variants` | Yes | Ownership verified through base_resume → persona chain. |
| applications | `/applications` | Partial | List is a stub (TODO). |
| cover_letters | `/cover-letters` | Partial | List is a stub (TODO). |
| job_sources | `/job-sources` | N/A | Global table, read-only. No tenant filtering needed. |
| user_source_preferences | `/user-source-preferences` | Partial | Stub (TODO). |
| chat | `/chat` | Yes | User_id injected, messages scoped. |
| persona_change_flags | `/persona-change-flags` | Yes | Filtered by persona_id with user check. |
| files (resume_files) | `/resume-files` | Yes | JOIN through persona. |
| files (submitted PDFs) | `/submitted-*-pdfs` | Yes | Complex ownership through application/cover_letter chain. |
| refresh | `/refresh` | Yes | Scoped to persona. |

### 6.2 Required Work

Endpoints marked "Partial" or "Stub (TODO)" must be updated to enforce ownership:

1. **`/personas/{id}`** — GET/PATCH/DELETE must verify `persona.user_id = current_user_id`
2. **`/applications`** — List must filter through `persona.user_id`
3. **`/cover-letters`** — List must filter through `persona.user_id`
4. **`/user-source-preferences`** — All operations must verify persona ownership

**Pattern to follow:** `base_resumes.py` (see `_get_owned_resume()` helper function) is the reference implementation for the join-through-persona ownership pattern.

---

## 7. Agent Scoping

### 7.1 Agent State Includes user_id

All LangGraph agents already include `user_id` in their state (REQ-007 §4.1):

```python
class BaseAgentState(TypedDict):
    user_id: str
    persona_id: str
    # ...
```

### 7.2 Agents Are Internal API Clients

Per REQ-006 §2.3, agents write through the API. The API enforces tenant isolation on all writes. Agents cannot bypass the ownership checks.

### 7.3 Agent-Initiated Queries

Agents that read data directly (not through the API) must include user_id filtering. **This is a convention, not an enforcement mechanism.** To reduce the risk of developer error, agents should use a `TenantScopedSession` wrapper:

```python
# Recommended: TenantScopedSession wraps AsyncSession with automatic user_id filtering
class TenantScopedSession:
    """Database session that automatically scopes queries to a user."""

    def __init__(self, db: AsyncSession, user_id: uuid.UUID):
        self._db = db
        self._user_id = user_id

    async def get_persona(self, persona_id: uuid.UUID) -> Persona:
        """Fetch persona with automatic ownership check."""
        result = await self._db.execute(
            select(Persona).where(
                Persona.id == persona_id,
                Persona.user_id == self._user_id,
            )
        )
        persona = result.scalar_one_or_none()
        if not persona:
            raise NotFoundError("Persona not found")
        return persona

# Usage in agent nodes
async def get_persona_preferences(state: ScouterState, db: AsyncSession):
    scoped = TenantScopedSession(db, uuid.UUID(state["user_id"]))
    persona = await scoped.get_persona(uuid.UUID(state["persona_id"]))
```

**Warning:** Raw `AsyncSession` access in agents bypasses tenant isolation. All agent database reads should go through `TenantScopedSession` or the repository layer (which already includes ownership checks). Code review must flag any raw session usage in agent code.

---

## 8. Database Changes

### 8.1 Indexes for Tenant-Scoped Queries

All indexes required for tenant-scoped queries already exist from the initial schema migrations (002–005). Migration 011 renamed all 49 pre-existing indexes to the explicit `idx_{table}_{column}` convention for AI-searchability. The 4 auth indexes from migration 010 already followed this convention.

**Convention:** `idx_{exact_table_name}_{exact_column_names}` — enables grep/search by table name or column name.

Key tenant-scoped indexes (all created in migrations 002–005, renamed in 011):

```sql
-- Tier 1: Persona lookup by user
-- idx_personas_user_id ON personas(user_id)

-- Tier 2: Common filtered lookups
-- idx_job_postings_persona_id ON job_postings(persona_id)
-- idx_cover_letters_persona_id ON cover_letters(persona_id)
-- idx_applications_persona_id ON applications(persona_id)
-- idx_base_resumes_persona_id ON base_resumes(persona_id)
-- idx_work_histories_persona_id ON work_histories(persona_id)
-- idx_skills_persona_id ON skills(persona_id)
```

For the complete list of all 53 indexes and their naming, see migration 011 (`011_rename_indexes.py`).

### 8.2 No Schema Changes

The existing schema already supports multi-tenancy:
- `users.id` exists
- `personas.user_id` FK exists
- All Tier 2+ tables have `persona_id` FK

No new columns or tables are needed for tenant isolation. The changes are:
1. Standardize index naming convention (§8.1, migration 011)
2. Fix endpoints that don't enforce ownership (§6.2)
3. Add integration tests (§9)

---

## 9. Migration from Single-User

### 9.1 Feature Flag

Multi-tenant isolation is always active — the `persona.user_id` check applies regardless of `AUTH_ENABLED`. The difference is:

| Mode | User Identity Source | Isolation Behavior |
|------|---------------------|-------------------|
| `AUTH_ENABLED=false` | `DEFAULT_USER_ID` env var | All queries scoped to one user (effectively single-tenant) |
| `AUTH_ENABLED=true` | JWT cookie (REQ-013) | All queries scoped to authenticated user (full multi-tenant) |

**No feature flag needed for isolation itself.** The same code path handles both modes.

### 9.2 Existing Data

When switching from local mode to hosted mode:
1. Existing user row remains in `users` table
2. Existing personas remain attached to that user via `user_id` FK
3. First authenticated user who matches the existing user's email gets all existing data
4. New users start with empty personas (through onboarding)

### 9.3 No Bulk Migration

The schema already supports multi-tenancy. No `ALTER TABLE` or data backfill needed. The only changes are:
- Application-level: Fix ownership enforcement in stub endpoints
- Infrastructure-level: Add missing indexes

---

## 10. Testing Strategy

### 10.1 Cross-Tenant Leakage Tests

**Critical test category.** Every API endpoint must be tested with two users to verify isolation.

**Test pattern:**

```python
async def test_user_cannot_see_other_users_personas(
    client_user_a: AsyncClient,
    client_user_b: AsyncClient,
    persona_user_a: Persona,
):
    """User B cannot access User A's persona."""
    response = await client_user_b.get(f"/api/v1/personas/{persona_user_a.id}")
    assert response.status_code == 404  # Not 403 — prevents enumeration
```

**Test matrix:**

| Operation | Test |
|-----------|------|
| GET detail | User B gets 404 for User A's resource |
| GET list | User B sees empty list (no User A data) |
| PATCH | User B gets 404 trying to update User A's resource |
| DELETE | User B gets 404 trying to delete User A's resource |
| POST (create) | User B cannot create resources under User A's persona |

### 10.2 Test Fixtures

```python
# conftest.py additions

@pytest.fixture
async def user_a(db: AsyncSession) -> User:
    user = User(id=uuid.uuid4(), email="alice@example.com")
    db.add(user)
    await db.commit()
    return user

@pytest.fixture
async def user_b(db: AsyncSession) -> User:
    user = User(id=uuid.uuid4(), email="bob@example.com")
    db.add(user)
    await db.commit()
    return user

@pytest.fixture
async def client_user_a(user_a: User) -> AsyncClient:
    """Authenticated client for User A."""
    # Override get_current_user_id to return user_a.id
    ...

@pytest.fixture
async def client_user_b(user_b: User) -> AsyncClient:
    """Authenticated client for User B."""
    # Override get_current_user_id to return user_b.id
    ...
```

### 10.3 Coverage Target

Every router in §6.1 must have at least one cross-tenant leakage test covering:
1. **Detail endpoint** — GET by ID returns 404 for wrong user
2. **List endpoint** — GET list returns only own data
3. **Mutation endpoint** — PATCH/DELETE returns 404 for wrong user

---

## 11. Open Questions

| # | Question | Status | Notes |
|---|----------|--------|-------|
| 1 | Add PostgreSQL Row-Level Security (RLS) as defense-in-depth? | Deferred | Good second layer but adds operational complexity. Add after application-level tests pass. |
| 2 | Per-user LLM API key support (BYOK)? | Deferred | Requires key storage, encryption, per-request provider instantiation. Future feature. |
| 3 | Per-user storage quotas (max personas, max resumes)? | Deferred | Not needed for MVP. Add when pricing model is defined. |
| 4 | Data export for GDPR compliance? | Deferred | Required before EU launch. Export all user data as JSON/ZIP. |
| 5 | Account deletion cascade behavior? | Proposed: Full cascade | Delete user → delete all personas → cascade delete all child data. Auth.js `ON DELETE CASCADE` handles accounts/sessions. |

---

## 12. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-18 | v0.1 | Initial draft — row-level filtering, endpoint audit, testing strategy |
| 2026-02-18 | v0.2 | Added TenantScopedSession pattern for agent isolation (§7.3), clarified multi-persona visibility (§4.2), added REQ-015 dependency (§2.2) |
