# REQ-006: API Contract

**Status:** Draft  
**PRD Reference:** §6 Technical Architecture  
**Last Updated:** 2026-01-25

---

## 1. Overview

This document defines the API contract for Zentropy Scout: endpoint design, authentication model, request/response schemas, and integration patterns.

**Key Principle:** The API is the single point of entry for all data modifications. All clients (frontend, Chrome extension, internal agents) go through the API. This ensures consistent validation, tenant isolation, and auditability.

---

## 2. Design Decisions & Rationale

### 2.1 API Style: REST

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| REST | ✅ | Simpler to learn and implement. Better HTTP caching. Extensive tooling and tutorials. Easier to secure (permissions map to endpoints). More accessible for self-hosters and open-source contributors. |
| GraphQL | — | More flexible for multiple clients with different data needs, but steeper learning curve. Adds complexity for caching and auth. Better suited when client diversity is a known problem. |
| Hybrid | — | Unnecessary complexity for MVP. Can add GraphQL layer later if needed. |

**Escape hatch:** If endpoints proliferate with `?include=` patterns to avoid round-trips, GraphQL may become worthwhile. Not there yet.

### 2.2 Deployment Model: Local-First, Multi-Tenant Ready

| Mode | Description | User Context Source |
|------|-------------|---------------------|
| **Local (MVP)** | Single user, self-hosted | `DEFAULT_USER_ID` env var |
| **Hosted (Future)** | Multi-tenant, real auth | JWT token or session |

**Design principle:** The API always expects a user context. The source of that context is a configuration choice, not a code fork.

```
# Middleware pseudo-code
def get_current_user_id(request):
    if config.AUTH_ENABLED:
        return extract_from_token(request)  # Future
    else:
        return config.DEFAULT_USER_ID       # Now
```

**Rationale:**
- Same code path for local and hosted — no forked logic
- Multi-tenant isolation enforced from day 1 (just with one tenant)
- Self-hosters get simplicity: clone, set env var, run
- Swap in real auth later by changing config, not code

### 2.3 Architecture: API-Mediated Agents

All writes go through the API. Agents (Scouter, Ghostwriter) are internal API clients.

```
┌─────────────────────┐     ┌─────────────────────┐
│  Chrome Extension   │     │  Frontend (React)   │
│  (untrusted)        │     │  (untrusted)        │
└─────────┬───────────┘     └─────────┬───────────┘
          │                           │
          │ HTTP                      │ HTTP
          ▼                           ▼
┌─────────────────────────────────────────────────┐
│                      API                         │
│  • Validates all input                          │
│  • Enforces tenant isolation                    │
│  • Single source of truth for business rules    │
└───────────────────────┬─────────────────────────┘
                        │
          ┌─────────────┴─────────────┐
          ▼                           ▼
   ┌─────────────┐             ┌─────────────┐
   │   Scouter   │             │ Ghostwriter │
   │  (worker)   │             │  (worker)   │
   └──────┬──────┘             └──────┬──────┘
          │                           │
          │ Internal calls            │ Internal calls
          └───────────┬───────────────┘
                      ▼
              ┌─────────────┐
              │     API     │
              └──────┬──────┘
                     ▼
              ┌─────────────┐
              │  Database   │
              └─────────────┘
```

**Data sources and trust levels:**

| Source | Trust Level | Flow |
|--------|-------------|------|
| Chrome Extension | Untrusted | HTTP → API (validates & sanitizes) |
| External Job APIs (Adzuna, etc.) | Semi-trusted | Scouter polls → API (validates schema) |
| Ghostwriter output | Trusted (our code) | Internal call → API (still enforces tenant isolation) |
| Frontend | Untrusted | HTTP → API (validates & authorizes) |

**Rationale:**
- **Tenant isolation in one place:** API enforces "you can only access your own data." Agents don't re-implement this.
- **Validation consistency:** All job postings validated identically regardless of source.
- **Auditability:** Every write logged at API layer.
- **Self-hosted simplicity:** "Internal calls" are direct function calls locally, HTTP when distributed.
- **Scalability path:** Agents become separate services calling the API. No architecture change, just deployment.

### 2.4 Chat Agent with Tools

The user interacts with the system via a conversational AI agent (LangGraph). The agent is a first-class API client — it interprets user intent, selects tools, and calls the same REST endpoints the frontend uses.

```
User: "Mark job 29583 as favorite"
         │
         ▼
┌─────────────────────────────────┐
│     LangGraph Agent             │
│  • Interprets user intent       │
│  • Selects tool: favorite_job   │
│  • Calls tool with job_id       │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│     Tool: favorite_job          │
│  → PATCH /job-postings/29583    │
│    { "is_favorite": true }      │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│            API                  │
│  • Validates request            │
│  • Confirms user owns job       │
│  • Updates database             │
│  • Returns success              │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│     Agent Response (SSE)        │
│  "Done, I've favorited job      │
│   29583 - the Scrum Master      │
│   role at Acme Corp."           │
└─────────────────────────────────┘
```

**Agent Tool Categories:**

| Category | Example Tools | Maps To |
|----------|---------------|---------|
| Job Management | `favorite_job`, `dismiss_job`, `get_job_details` | `/job-postings/*` |
| Application | `mark_applied`, `update_status`, `add_timeline_note` | `/applications/*` |
| Resume/Cover Letter | `approve_variant`, `regenerate_cover_letter` | `/job-variants/*`, `/cover-letters/*` |
| Search/Query | `find_jobs_by_company`, `show_pending_applications` | GET endpoints with filters |

**Rationale:**
- **Same validation path:** Agent actions go through API, same as frontend. No backdoors.
- **Auditable:** Every agent action is an API call — logged and traceable.
- **Consistent behavior:** If frontend can't do it, agent can't do it.
- **Tool simplicity:** Tools are thin wrappers around REST calls, not custom logic.

### 2.5 Real-Time Communication: SSE

Server-Sent Events (SSE) provide real-time updates for agent chat and data changes.

| Interaction | Method | Why |
|-------------|--------|-----|
| Agent chat responses | **SSE (streaming)** | Token-by-token LLM output requires streaming |
| Agent tool execution feedback | **SSE (streaming)** | "Updating job... Done." — user sees it happen |
| Dashboard reflecting changes | **SSE events** | Agent favorites a job → dashboard updates instantly |
| Background Scouter results | **Polling + manual refresh** | User isn't watching; checks in later |

**Single SSE connection handles both chat and data events:**

```
SSE Stream
├── type: "chat_token"     → append to chat UI
├── type: "chat_token"     → append to chat UI  
├── type: "tool_result"    → show "✓ Job favorited"
├── type: "data_changed"   → dashboard: update job 29583
└── type: "chat_token"     → append to chat UI
```

**SSE Event Types:**

| Event Type | Payload | Frontend Action |
|------------|---------|-----------------|
| `chat_token` | `{ "text": "..." }` | Append to chat message |
| `chat_done` | `{ "message_id": "..." }` | Mark message complete |
| `tool_start` | `{ "tool": "favorite_job", "args": {...} }` | Show "working..." indicator |
| `tool_result` | `{ "tool": "favorite_job", "success": true }` | Show result, clear indicator |
| `data_changed` | `{ "resource": "job-posting", "id": "...", "action": "updated" }` | Refresh that resource in UI |

**Page Load + Refresh:**

| Trigger | Behavior |
|---------|----------|
| Page load | Fetch current state via REST, establish SSE connection |
| Manual refresh button | Re-fetch via REST (user-initiated) |
| SSE `data_changed` event | Update specific resource without full refresh |
| Tab inactive > 5 min | Reconnect SSE + refresh on return |

**Rationale:**
- **SSE vs WebSockets:** SSE is simpler, one-way push is sufficient. User input goes via REST POST.
- **Single connection:** One SSE stream for chat + data changes. No connection juggling.
- **Graceful fallback:** If SSE disconnects, user can still manually refresh.

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| Polling only | — | Sluggish UX during agent chat; can't stream LLM tokens |
| WebSockets | — | Bidirectional not needed; more complexity |
| SSE | ✅ | Simple, one-way push, handles both chat streaming and data events |

### 2.6 Bulk Operations: Explicit Endpoints Where Needed

**Philosophy:** Follow Stripe's approach — simple, clear endpoints. Add explicit bulk operations only where users actually need them.

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| No bulk operations | — | Poor UX when dismissing 20 jobs = 20 requests |
| Explicit bulk endpoints (B) | ✅ | Clear intent, simple implementation, easy to document |
| Generic `/bulk` endpoint (C) | — | Over-engineered; Google/Microsoft use this for 100s of resources, we have ~15 |
| PATCH with array (D) | — | Partial failure handling is awkward; more flexibility than needed |

**MVP Bulk Endpoints:**

| Endpoint | Body | Use Case |
|----------|------|----------|
| `POST /job-postings/bulk-dismiss` | `{ "ids": ["uuid1", "uuid2"] }` | Clear out uninteresting jobs |
| `POST /job-postings/bulk-favorite` | `{ "ids": [...], "is_favorite": true }` | Batch favorite/unfavorite |
| `POST /applications/bulk-archive` | `{ "ids": [...] }` | Clean up old applications |

**Add more only when usage demands it.**

**Response Format (partial success allowed):**

```json
{
  "data": {
    "succeeded": ["uuid1", "uuid2"],
    "failed": [
      { "id": "uuid3", "error": "NOT_FOUND" },
      { "id": "uuid4", "error": "FORBIDDEN" }
    ]
  }
}
```

**HTTP Status:**
- `200 OK` — all succeeded, or partial success (check `failed` array)
- `400 Bad Request` — malformed request (missing ids, invalid format)
- `401/403` — auth issues (before processing any items)

### 2.7 File Upload & Download

**File Types in the System:**

| Entity | Direction | Purpose |
|--------|-----------|---------|
| ResumeFile | Upload | Original resume uploaded during onboarding |
| BaseResume.rendered_document | Generated | Anchor PDF for each role-based master resume |
| SubmittedResumePDF | Download | Immutable PDF submitted with application |
| SubmittedCoverLetterPDF | Download | Immutable PDF submitted with application |

**Upload Approach: Direct POST with multipart/form-data**

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| Direct POST (multipart/form-data) | ✅ | Simple, one request. No external storage dependencies. Works locally. |
| Presigned URL (S3-style) | — | Requires object storage. Adds complexity. Better for large files or high volume. |
| Base64 in JSON | — | 33% size overhead. Memory-intensive. Breaks REST conventions. |

**Why Direct POST for MVP:**
- Files are small (resumes typically <5MB)
- Local-first deployment has no S3
- Simplicity wins for self-hosted users

**Can add presigned URL flow later if moving to hosted with object storage.**

**Upload Endpoint:**

```
POST /api/v1/resume-files
Content-Type: multipart/form-data

file: <binary>
```

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "file_name": "Brian_Resume_2026.pdf",
    "file_type": "PDF",
    "file_size_bytes": 245000,
    "uploaded_at": "2026-01-25T10:00:00Z"
  }
}
```

**Download Endpoints:**

```
GET /api/v1/submitted-resume-pdfs/{id}/download
GET /api/v1/submitted-cover-letter-pdfs/{id}/download
GET /api/v1/base-resumes/{id}/download
```

Returns binary file with appropriate `Content-Type` and `Content-Disposition` headers.

**Base Resume Download Clarification:**

`GET /base-resumes/{id}/download` returns the **stored `rendered_document` blob** (see REQ-002 §4.2, REQ-005 BaseResume table). It does NOT generate the PDF on-demand.

- The PDF is rendered once when the BaseResume is created/updated
- User reviews and approves the rendered document
- The approved PDF is stored in `rendered_document`
- Download endpoint serves that stored blob

This ensures consistency — every download returns the exact same document that was approved as the anchor.

---

## 3. Dependencies

### 3.1 This Document Depends On

| Dependency | Type | Notes |
|------------|------|-------|
| REQ-001 Persona Schema v0.7 | Entity definitions | Persona, WorkHistory, Skill, etc. |
| REQ-002 Resume Schema v0.7 | Entity definitions | BaseResume (with rendered_document), JobVariant, SubmittedPDF |
| REQ-002b Cover Letter Schema v0.5 | Entity definitions | CoverLetter, SubmittedCoverLetterPDF |
| REQ-003 Job Posting Schema v0.3 | Entity definitions | JobPosting, JobSource, ExtractedSkill |
| REQ-004 Application Schema v0.5 | Entity definitions | Application, TimelineEvent |
| REQ-005 Database Schema v0.10 | Complete ERD | All tables, relationships, constraints |

### 3.2 Other Documents Depend On This

| Document | Dependency | Notes |
|----------|------------|-------|
| (Future) Frontend Implementation | Endpoint contracts | Request/response schemas |
| (Future) Chrome Extension | Endpoint contracts | Job submission endpoint |
| (Future) Agent Implementation | Internal API contracts | Scouter, Ghostwriter integration |

---

## 4. API Consumers

| Consumer | Auth Mode | Notes |
|----------|-----------|-------|
| Web Frontend | User auth (env var now, token later) | Primary UI client |
| Chrome Extension | User auth | Submits scraped job postings |
| Chat Agent (LangGraph) | Internal/service | User-facing agent; calls API via tools |
| Scouter Agent | Internal/service | Polls external APIs, writes job postings |
| Ghostwriter Agent | Internal/service | Generates drafts, writes variants/cover letters |
| Mobile App (future) | User auth | Same API, different client |

---

## 5. Endpoint Design

### 5.1 URL Structure

```
/api/v1/{resource}
/api/v1/{resource}/{id}
/api/v1/{resource}/{id}/{sub-resource}
```

**Versioning:** Path-based (`/v1/`). Allows breaking changes in `/v2/` without disrupting existing clients.

### 5.2 Resource Mapping

| Resource | Endpoints | Notes |
|----------|-----------|-------|
| `personas` | CRUD | User profile — most users have exactly one |
| `personas/{id}/work-history` | CRUD | Nested under persona |
| `personas/{id}/skills` | CRUD | Nested under persona |
| `personas/{id}/education` | CRUD | Nested under persona |
| `personas/{id}/certifications` | CRUD | Nested under persona |
| `personas/{id}/achievement-stories` | CRUD | Nested under persona |
| `personas/{id}/voice-profile` | Read/Update | 1:1 with persona, no create/delete |
| `personas/{id}/custom-non-negotiables` | CRUD | Custom filters (e.g., "No Amazon subsidiaries") |
| `base-resumes` | CRUD | Filtered by current user's persona |
| `job-variants` | CRUD | |
| `job-postings` | CRUD | Chrome extension POSTs here |
| `job-postings/{id}/extracted-skills` | Read | Extracted by Scouter, read-only for clients |
| `applications` | CRUD | |
| `applications/{id}/timeline` | CRUD | |
| `cover-letters` | CRUD | |
| `job-sources` | Read | System-managed, users can toggle preferences |
| `user-source-preferences` | Read/Update | Per-user source settings |
| `chat/messages` | POST | Send message to agent, returns message ID |
| `chat/stream` | GET (SSE) | Establish SSE connection for chat + data events |
| `refresh` | POST | Force re-fetch from external job sources (Scouter) |
| `job-postings/bulk-dismiss` | POST | Bulk dismiss jobs (see §2.6) |
| `job-postings/bulk-favorite` | POST | Bulk favorite/unfavorite jobs (see §2.6) |
| `applications/bulk-archive` | POST | Bulk archive applications (see §2.6) |
| `resume-files` | POST | Upload original resume during onboarding (see §2.7) |
| `base-resumes/{id}/download` | GET | Download rendered anchor PDF |
| `submitted-resume-pdfs/{id}/download` | GET | Download submitted resume PDF |
| `submitted-cover-letter-pdfs/{id}/download` | GET | Download submitted cover letter PDF |
| `persona-change-flags` | GET, PATCH | Pending Persona changes for HITL sync (see §5.4) |
| `personas/{id}/embeddings/regenerate` | POST | Trigger Persona embedding regeneration (see REQ-007 §7.1) |
| `job-postings/rescore` | POST | Re-run Strategist scoring on all Discovered jobs (see REQ-007 §7.1) |

### 5.3 Standard HTTP Methods

| Method | Purpose | Idempotent |
|--------|---------|------------|
| GET | Read resource(s) | Yes |
| POST | Create resource | No |
| PUT | Full replace | Yes |
| PATCH | Partial update | Yes |
| DELETE | Remove resource | Yes |

### 5.4 Persona Change Flags (HITL Sync)

When a user adds new skills, jobs, or other Persona data, the system flags pending changes that may need to be synced to BaseResumes. See REQ-002 §6.3.

**Endpoints:**

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/persona-change-flags?status=Pending` | List pending sync flags |
| PATCH | `/persona-change-flags/{id}` | Resolve a flag |

**GET Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "change_type": "Skill",
      "change_id": "skill-uuid",
      "change_summary": "Added skill: Kubernetes",
      "suggested_action": "Add to all Base Resumes",
      "status": "Pending",
      "created_at": "2026-01-25T10:00:00Z"
    }
  ]
}
```

**PATCH Request (resolve):**
```json
{
  "status": "Resolved",
  "resolution": "added_to_all"  // or "added_to_some", "skipped"
}
```

**Resolution Values:**
- `added_to_all` — Applied to all BaseResumes
- `added_to_some` — Applied to selected BaseResumes (agent tracks which)
- `skipped` — User declined to add

### 5.5 Standard Filtering & Sorting

All GET collection endpoints support standard query parameters for filtering and sorting.

**Sorting:**

| Parameter | Example | Notes |
|-----------|---------|-------|
| `sort` | `?sort=created_at` | Ascending by field |
| `sort` | `?sort=-created_at` | Descending (prefix with `-`) |
| `sort` | `?sort=-fit_score,title` | Multiple fields, comma-separated |

**Filtering:**

| Parameter | Example | Notes |
|-----------|---------|-------|
| `{field}` | `?status=Applied` | Exact match |
| `{field}` | `?status=Applied,Interviewing` | Match any (OR) |

**Common Filters by Resource:**

| Resource | Useful Filters |
|----------|----------------|
| `job-postings` | `status`, `is_favorite`, `fit_score_min`, `company_name` |
| `applications` | `status`, `applied_after`, `applied_before` |
| `job-variants` | `status`, `base_resume_id` |
| `persona-change-flags` | `status` |

**Example:**
```
GET /job-postings?status=Discovered&is_favorite=true&sort=-fit_score
```
Returns discovered, favorited jobs sorted by highest fit score first.

---

## 6. Authentication & Authorization

### 6.1 Authentication (Who are you?)

**MVP (Local Mode):**
- No token required
- `DEFAULT_USER_ID` env var provides user context
- All requests implicitly authenticated as that user

**Future (Hosted Mode):**
- Bearer token in `Authorization` header
- Token contains `user_id` claim
- Options: JWT (stateless), session cookie (stateful), OAuth provider

**Extension point:** Auth is injected via middleware. Swap implementations without changing endpoint code.

### 6.2 Authorization (What can you do?)

**Simple rule:** Users can only access resources belonging to their Persona.

Every endpoint filters by `persona.user_id = current_user_id`. This is enforced at the API layer, not the database.

| Request | Check |
|---------|-------|
| `GET /base-resumes` | Return only where `persona.user_id = current_user` |
| `PATCH /job-postings/123` | Verify job posting's persona belongs to current user |
| `DELETE /applications/456` | Verify application's persona belongs to current user |

**No role-based access for MVP.** All authenticated users have full access to their own data, zero access to others' data.

---

## 7. Request/Response Format

### 7.1 Content Type

```
Content-Type: application/json
Accept: application/json
```

### 7.2 Response Envelope

**Success (single resource):**
```json
{
  "data": { ... }
}
```

**Success (collection):**
```json
{
  "data": [ ... ],
  "meta": {
    "total": 42,
    "page": 1,
    "per_page": 20
  }
}
```

**Error:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable message",
    "details": [ ... ]
  }
}
```

### 7.3 Pagination

Query params for collections:
- `page` (default: 1)
- `per_page` (default: 20, max: 100)

---

## 8. Error Handling

### 8.1 HTTP Status Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| 200 | OK | Successful GET, PUT, PATCH |
| 201 | Created | Successful POST |
| 204 | No Content | Successful DELETE |
| 400 | Bad Request | Validation error, malformed JSON |
| 401 | Unauthorized | Missing or invalid auth |
| 403 | Forbidden | Valid auth, but not allowed (wrong tenant) |
| 404 | Not Found | Resource doesn't exist (or not yours) |
| 409 | Conflict | Duplicate (e.g., applying to same job twice) |
| 422 | Unprocessable Entity | Valid JSON, but business rule violation |
| 500 | Internal Server Error | Bug, unexpected failure |

### 8.2 Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Field validation failed |
| `UNAUTHORIZED` | 401 | Auth required |
| `FORBIDDEN` | 403 | Not your resource |
| `NOT_FOUND` | 404 | Resource doesn't exist |
| `DUPLICATE_APPLICATION` | 409 | Already applied to this job posting |
| `INVALID_STATE_TRANSITION` | 422 | E.g., approving already-approved variant |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## 9. Open Questions

| # | Question | Status | Notes |
|---|----------|--------|-------|
| 1 | Rate limiting strategy? | **Deferred** | Skip for MVP. Add Redis-backed solution when hosting. Easy to add later — middleware wraps existing endpoints. |
| 2 | Webhook events for integrations? | **Deferred** | Skip for MVP. LangGraph agents handle automation, not external webhooks. Easy to add later if needed. |
| 3 | Bulk operations? | **Resolved** | Explicit bulk endpoints where needed (Stripe philosophy). MVP: bulk-dismiss, bulk-favorite, bulk-archive. See §2.6. |
| 4 | Real-time updates? | **Resolved** | SSE for agent chat streaming + data change events. Polling for "what's new" on page load. Manual refresh button available. See §2.5. |
| 5 | File upload/download flow? | **Resolved** | See §2.7. Direct POST (multipart/form-data) for uploads. Direct GET for downloads. No presigned URLs for MVP. |

---

## 10. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-25 | 0.1 | Initial draft. Documented API style decision (REST), deployment model (local-first, multi-tenant ready), and architecture (API-mediated agents). Added endpoint structure, auth model, error handling. |
| 2026-01-25 | 0.2 | Added §2.4 Chat Agent with Tools (LangGraph agent as API client, tool categories). Added §2.5 Real-Time Communication (SSE for chat streaming and data events, polling + manual refresh for background updates). Resolved open questions: rate limiting deferred, webhooks deferred, real-time resolved. |
| 2026-01-25 | 0.3 | Added §2.6 Bulk Operations (Stripe philosophy — explicit endpoints where needed). MVP bulk endpoints: bulk-dismiss, bulk-favorite, bulk-archive. Added bulk endpoints to resource mapping. |
| 2026-01-25 | 0.4 | Added §2.7 File Upload & Download (direct POST with multipart/form-data for uploads, direct GET for downloads). Resolved open question #5. Updated dependency versions (REQ-002 v0.7, REQ-005 v0.9). All open questions now resolved or deferred. |
| 2026-01-25 | 0.5 | Peer review fixes: Added §5.4 Persona Change Flags endpoints (HITL sync for new skills/jobs). Added §5.5 Standard Filtering & Sorting (sort, filter query params). Updated dependency versions (REQ-004 v0.5, REQ-005 v0.10). |
| 2026-01-25 | 0.6 | Peer review fixes (cont.): Added `custom-non-negotiables` CRUD endpoints to resource mapping. Added Base Resume Download clarification (serves stored blob, not on-demand generation). |
| 2026-01-25 | 0.7 | Added embedding regeneration and job rescore endpoints to support REQ-007 agent flows: `POST /personas/{id}/embeddings/regenerate`, `POST /job-postings/rescore`. |
