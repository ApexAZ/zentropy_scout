# REQ-034: Job Source Adapter Implementation & AI-Driven Search Profiles

**Status:** Planned
**Version:** 0.1
**PRD Reference:** §4.2 Scouter, §6 Data Strategy
**Backlog Item:** #31
**Last Updated:** 2026-04-03
**Traces To:** REQ-007 §6.3, REQ-015 §7, REQ-016 §1.4, REQ-003 §4.1

---

## §1 Overview & Motivation

### 1.1 What This Document Covers

The Scouter's job sourcing pipeline (`JobFetchService`, source adapters, `PoolSurfacingWorker`) is
scaffolded and the orchestration is fully implemented, but four key gaps remain:

1. **`fetch_jobs()` is stubbed** on all four source adapters — every call returns `[]`
2. **`SearchParams` is hardcoded** — all polls search for `["software", "engineer"]` regardless of persona
3. **No poll scheduler** — polls only trigger on manual user request; scheduled polling never fires
4. **Skill extraction is stubbed** — `extract_skills_and_culture()` returns a placeholder with empty lists

This REQ specifies:

- The **AI-generated `SearchProfile`** — a structured set of search criteria derived from the persona,
  split into fit and stretch buckets, reviewed by the user, and stored in the DB
- **`fetch_jobs()` implementation** for all four adapters, including per-source auth, query parameters,
  pagination, and delta strategies
- **`SearchParams` construction** from persona and `SearchProfile` data
- **`search_bucket` field** on `PersonaJob` to track fit vs. stretch provenance end-to-end
- **Poll scheduler** — background worker that triggers `JobFetchService.run_poll()` on schedule
- **Skill extraction wiring** — LLM call replacing the placeholder
- **UI** — onboarding step and job search settings tab

### 1.2 What Does NOT Change

- `JobSourceAdapter` interface (`base.py`) — interface is correct, only `fetch_jobs()` bodies change
- All four `normalize()` methods — fully implemented, untouched
- `JobFetchService.run_poll()` pipeline orchestration — untouched
- Global deduplication service — untouched
- Pool surfacing worker — untouched
- `PollingConfiguration`, `UserSourcePreference` models — minor additions only (§5.4)
- Ghost detection service — untouched
- Job scoring service — untouched

### 1.3 Design Philosophy

**Pull broadly, deduplicate centrally.** At the API volumes available (see §3), pulling all available
jobs per source is viable for most sources. The 4-step dedup pipeline handles known-job elimination
efficiently — Step 1 (`source_id + external_id` exact match) exits immediately for jobs already in
the pool. Network cost is low; LLM extraction cost is amortized once per unique job across all users.

**AI earns its cost at query-generation time, not poll time.** The AI runs once to generate the
`SearchProfile` from persona data, user reviews and approves it, and the polling algorithm uses stored
criteria mechanically. The AI is not involved in the polling loop or matching — the existing
`JobScoringService` (embedding-based) handles relevance.

---

## §2 Dependencies & Prerequisites

### 2.1 This Document Depends On

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-001 Persona Schema v0.8 | Entity | `target_roles`, `target_skills`, `stretch_appetite`, `polling_frequency`, `minimum_fit_threshold` |
| REQ-003 Job Posting Schema v0.4 | Entity | `JobPosting`, `PersonaJob`, `JobSource`, `PollingConfiguration` |
| REQ-005 Database Schema v0.10 | Schema | All relevant tables |
| REQ-007 Agent Behavior v0.5 | Context | §6.3 source adapter interface (superseded here for implementation detail) |
| REQ-015 Shared Job Pool v0.1 | Architecture | Pool-first lookup, crowdsourcing model, `discovery_method` enum |
| REQ-016 Scouter Service Layer v1.1 | Architecture | `JobFetchService`, `JobEnrichmentService`, adapter registry |

### 2.2 Other Documents Depend On This

| Document | How |
|----------|-----|
| REQ-007 §6.3 | Source adapter interface is implemented here |
| REQ-015 §7 | Poll scheduler specified here completes the polling trigger gap |

---

## §3 API Reference & Rate Limits

This section captures verified API documentation for all four sources. It is reference material
for implementation — do not implement from memory.

### 3.1 Adzuna

**Registration:** developer.adzuna.com → `app_id` + `app_key`
**Env vars:** `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`

**Endpoint:**
```
GET https://api.adzuna.com/v1/api/jobs/{country}/search/{page}
    ?app_id={app_id}
    &app_key={app_key}
    &results_per_page={n}
    &what={keywords}
    &where={location}
    &max_days_old={n}
    &full_time=1        (optional)
    &permanent=1        (optional)
```

**Pagination:** Page number is a URL path segment (1-indexed). `results_per_page` default ~20;
maximum is undocumented in the API spec — test with key to determine ceiling (likely 50).

**Rate limits (per API key, verified from ToS):**

| Window | Limit |
|--------|-------|
| Per minute | 25 requests |
| Per day | 250 requests |
| Per week | 1,000 requests |
| Per month | 2,500 requests |

The weekly cap (1,000) is the binding constraint mid-week — not the daily cap × 7. At ~20 jobs/call,
250 calls/day = ~5,000 jobs/day; 1,000 calls/week = ~20,000 jobs/week from this source.

**Commercial use:** No self-serve paid tier. Enterprise/SaaS use requires a negotiated licence
agreement via developer.adzuna.com. At MVP scale (low user count), the free tier is sufficient.
Re-evaluate when weekly polls approach 800+ calls.

**Delta strategy:** Use `max_days_old` query parameter.
Calculate as: `max(1, ceil((now - last_poll_at).total_seconds() / 86400) + 1)`
On first poll (no `last_poll_at`): use `max_days_old=7` to seed recent jobs.

**Country codes:** `us`, `gb`, `au`, `ca`, `de`, `fr`, `in`, `nz`, `pl`, `ru`, `za`

### 3.2 The Muse

**Registration:** themuse.com/developers/api/v2 → `api_key`
**Env var:** `THE_MUSE_API_KEY`

**Endpoint:**
```
GET https://www.themuse.com/api/public/jobs
    ?api_key={api_key}
    &page={n}
    &category={category}    (optional)
    &level={level}          (optional)
    &location={location}    (optional)
```

**Pagination:** Zero-indexed `page` param. Fixed page size of **20 results** (not configurable).
Response includes `page_count` (total pages) and `page` (current). Total dataset: ~9,000 active jobs
(~450 pages). Out-of-range page returns 0 results.

**Rate limits (per API key):**

| Window | Limit |
|--------|-------|
| Per hour | 3,600 requests (registered key) |
| Per hour | 500 requests (no key) |

No daily or monthly cap documented. Response headers: `X-RateLimit-Limit`,
`X-RateLimit-Remaining`, `X-RateLimit-Reset` (seconds to reset).

**No paid tier.** Two tiers only: unregistered (500/hr) and registered (3,600/hr).

**Delta strategy:** No date filter parameter. Full re-fetch on every poll. The dedup pipeline
(Step 1: `source_id + external_id` exact match) exits immediately for known jobs — the cost
is network only, not LLM. At 450 calls to fetch the full dataset, this is well within the
3,600/hr limit even if run repeatedly.

**Category values** (partial — check API docs for full list): `Engineering`, `Data Science`,
`Product`, `Design`, `Marketing`, `Operations`, `Finance`, `Legal`, `HR & Recruiting`

**Level values:** `Entry Level`, `Mid Level`, `Senior Level`, `Management`, `Executive`

### 3.3 RemoteOK

**Registration:** None required.
**Env var:** None.

**Endpoint:**
```
GET https://remoteok.com/api
    ?tag={tag}    (optional — filter by tag)
```

**Pagination:** None. One call returns the entire dataset (~97 jobs as of 2026-04).
Results are in reverse-chronological order. The first element (index 0) is a metadata/legal
notice object — skip it when iterating.

**Rate limits:** None published. Responses are served via Cloudflare CDN with a
**1-hour cache** (`cache-control: max-age=3600`). Calling more than once per hour returns
the same cached data. Treat as a natural 1-call-per-hour ceiling.

**Delta strategy:** No date filter. Pull all (~97 jobs) once per hour at most. Reverse-chrono
order means you could stop iterating early once you encounter a previously-seen `external_id`,
but given the small dataset size, full pull + dedup is simpler and equally efficient.

**Tag-based filtering:** RemoteOK does not support keyword search — it uses a fixed tag
taxonomy. Tags include: `javascript`, `react`, `python`, `golang`, `devops`, `design`,
`product`, `marketing`, `backend`, `frontend`, `fullstack`, `mobile`, `data`, `infra`,
`saas`, `senior`, `manager`, among others. See remoteok.com/remote-[tag]-jobs for discovery.

**Tag mapping:** The `SearchProfile` stores `remoteok_tags: list[str]` generated by AI
at profile creation time (see §4.3). The adapter uses these tags rather than keyword search.
If no tags are configured, pull without a `?tag` filter (returns all jobs).

### 3.4 USAJobs

**Registration:** developer.usajobs.gov → email-based registration
**Env vars:** `USAJOBS_USER_AGENT` (app name string), `USAJOBS_EMAIL`

**Endpoint:**
```
GET https://data.usajobs.gov/api/Search
    ?Keyword={keywords}
    &LocationName={location}
    &ResultsPerPage={n}         (max 500, default 25)
    &Page={n}                   (1-indexed)
    &DatePosted={n}             (relative: jobs posted in last N days)
    &RemoteIndicator=True       (optional — remote jobs only)
    &PositionScheduleTypeCode=F (optional — full-time only)
```

**Auth:** Header-based (not query param):
```
Authorization: USAJOBS-DEMO-TOKEN  (literal string — no token value for free tier)
User-Agent: {USAJOBS_USER_AGENT}
Email-Address: {USAJOBS_EMAIL}
Host: data.usajobs.gov
```

**Pagination:** `ResultsPerPage` max **500** per call. `Page` is 1-indexed.
Maximum **10,000 rows per query** across all pages (20 pages × 500 = 10,000).

**Rate limits:** No time-based rate limit documented. Only the 10,000 row/query data cap applies.
USAJobs is effectively unlimited for polling purposes.

**Delta strategy:** Use `DatePosted` (relative days since last poll).
Calculate as: `max(1, ceil((now - last_poll_at).total_seconds() / 86400) + 1)`
On first poll: use `DatePosted=7`. Same calculation as Adzuna.

**Response structure** (deeply nested — handled by existing `normalize()`):
```
SearchResult.SearchResultItems[].MatchedObjectDescriptor
  ├── PositionTitle
  ├── OrganizationName
  ├── UserArea.Details.JobSummary
  ├── PositionLocation[0].LocationName
  ├── PositionRemuneration[0] (MinimumRange, MaximumRange, CurrencyCode)
  └── ApplyURI[0]
```

---

## §4 SearchProfile — AI-Generated Search Criteria

### 4.1 Concept

The `SearchProfile` is a structured set of search criteria generated by AI from the persona,
reviewed and approved by the user, and stored persistently. It drives `SearchParams` construction
at poll time. The AI runs once at profile creation and again when the persona changes materially —
not on every poll.

### 4.2 Data Model

**New table: `search_profiles`**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `id` | UUID | ✅ | PK |
| `persona_id` | UUID FK | ✅ | UNIQUE — one profile per persona |
| `fit_searches` | JSONB | ✅ | List of `SearchBucket` objects (current-fit roles) |
| `stretch_searches` | JSONB | ✅ | List of `SearchBucket` objects (growth-target roles) |
| `persona_fingerprint` | String(64) | ✅ | SHA-256 of material persona fields at generation time |
| `is_stale` | Boolean | ✅ | True when persona delta detected since last generation |
| `generated_at` | DateTime | ✅ | When AI generated this profile |
| `approved_at` | DateTime | ✅ | When user approved (or auto-approved on generation) |
| `created_at` | DateTime | ✅ | Server timestamp |
| `updated_at` | DateTime | ✅ | Server timestamp |

**`SearchBucket` JSONB shape** (per item in `fit_searches` / `stretch_searches`):

```json
{
  "label": "Senior Product Manager",
  "keywords": ["product manager", "product strategy", "roadmap", "agile"],
  "titles": ["Senior Product Manager", "Group Product Manager", "Product Lead"],
  "remoteok_tags": ["product", "saas", "senior"],
  "location": null
}
```

### 4.3 AI Generation

**Task type:** New `TaskType.SEARCH_PROFILE_GENERATION` (add to `TaskType` enum)
**Model:** Gemini Flash (cost-optimized; same as extraction — ~$0.001/call)
**Provider:** Routed via existing `MeteredLLMProvider` with balance gate

**Input to AI:** Full persona snapshot including:
- `job_titles` (from experiences)
- `skills` (hard and soft, required and preferred)
- `target_roles`, `target_skills`, `stretch_appetite` (Growth Targets)
- `location_preferences`, `remote_preference`
- `target_industries`, `preferred_company_sizes` (if set)

**Expected output:** Structured JSON with `fit_searches` and `stretch_searches` arrays,
each containing `SearchBucket` objects. AI also maps keywords to RemoteOK tags in the same pass.

**Fit bucket generation:** Derived from current experience level, existing skills, and
current job titles. Represents roles the user can do now.

**Stretch bucket generation:** Derived from `target_roles` and `target_skills`. Scaled by
`stretch_appetite`:
- `Low` → stretch titles are 1 level above current
- `Medium` → stretch titles are 1-2 levels above
- `High` → stretch titles may be 2+ levels above; include adjacent role families

**RemoteOK tag mapping:** AI maps each bucket's keywords to the closest matching RemoteOK
tags and stores them in `remoteok_tags`. If no good mapping exists, leave empty
(adapter falls back to unfiltered pull).

### 4.4 Persona Fingerprint & Staleness Detection

**Fingerprint fields** (material changes trigger re-generation):

```python
FINGERPRINT_FIELDS = [
    "skills",               # list of skill names
    "target_roles",
    "target_skills",
    "stretch_appetite",
    "location_preferences",
    "remote_preference",
]
```

Non-material fields (bio, display name, summary text) do NOT trigger re-generation.

**Staleness flow:**
1. On every `PATCH /personas/{id}`, compute new fingerprint
2. Compare to `search_profiles.persona_fingerprint`
3. If different → set `is_stale = True`
4. Frontend checks `is_stale` on persona/jobs pages and shows banner:
   _"Your job search criteria may be outdated. Refresh them?"_
5. User accepts → AI re-generates → user reviews → approved

**User ignoring staleness:** Profile remains in use indefinitely until explicitly refreshed.
No auto-regeneration — user controls their search criteria.

### 4.5 User Review UI

**Onboarding (last step):** After the Growth Targets step, add a new final step:
"Review your job search criteria." Display the AI-generated `SearchProfile` with fit and
stretch buckets. User can add/remove keywords and titles per bucket. Approve to proceed.

**Settings — Job Search tab (new):** Post-onboarding access to the `SearchProfile`.
Allows editing of fit and stretch buckets, manual keyword addition, and triggering a
fresh AI regeneration. Also shows current poll schedule (`polling_frequency`,
`last_poll_at`, `next_poll_at`) and enabled sources per persona.

---

## §5 SearchParams Construction & fetch_jobs() Implementation

### 5.1 SearchParams Additions

Extend `base.py` `SearchParams` with delta fields:

```python
@dataclass
class SearchParams:
    keywords: list[str]
    location: str | None = None
    remote_only: bool = False
    page: int = 1
    results_per_page: int = 25
    max_days_old: int | None = None      # NEW — Adzuna, USAJobs
    posted_after: datetime | None = None  # NEW — internal reference; adapters translate
```

### 5.2 SearchParams Construction from Persona + SearchProfile

Replace the hardcoded `SearchParams(keywords=["software", "engineer"])` in
`JobFetchService` with dynamic construction from the persona's `SearchProfile`.

**Per-bucket construction:**

```python
def build_search_params(
    bucket: SearchBucket,
    persona: Persona,
    last_poll_at: datetime | None,
    *,
    results_per_page: int = 50,
) -> SearchParams:
    max_days_old = None
    if last_poll_at:
        days = max(1, ceil((now - last_poll_at).total_seconds() / 86400) + 1)
        max_days_old = days
    else:
        max_days_old = 7   # seed window on first poll

    return SearchParams(
        keywords=bucket.keywords + bucket.titles,
        location=bucket.location or persona.home_city,
        remote_only=(persona.remote_preference == "Remote Only"),
        results_per_page=results_per_page,
        max_days_old=max_days_old,
        posted_after=(now - timedelta(days=max_days_old)) if max_days_old else None,
    )
```

**Poll loop:** For each persona, run polls for **all fit buckets** then **all stretch buckets**,
tagging each resulting `PersonaJob` with the appropriate `search_bucket` value (see §6).

### 5.3 Per-Adapter fetch_jobs() Specification

#### Adzuna

```python
async def fetch_jobs(self, params: SearchParams) -> list[RawJob]:
    # Build query params
    query = {
        "app_id": settings.adzuna_app_id,
        "app_key": settings.adzuna_app_key,
        "results_per_page": params.results_per_page,
        "what": " ".join(params.keywords),
        "content-type": "application/json",
    }
    if params.location:
        query["where"] = params.location
    if params.max_days_old:
        query["max_days_old"] = params.max_days_old
    if params.remote_only:
        query["where"] = "remote"  # Adzuna uses "remote" as a location

    # Paginate — stop when page returns 0 results or results < results_per_page
    # Respect: 25 req/min burst cap (add asyncio.sleep(2.4) between pages if paginating)
    url = f"https://api.adzuna.com/v1/api/jobs/us/search/{params.page}"
    # Use httpx.AsyncClient for async HTTP
    # Call normalize() on each item in response["results"]
```

#### The Muse

```python
async def fetch_jobs(self, params: SearchParams) -> list[RawJob]:
    # No delta support — always fetch from page 0
    # Pagination: fetch until page >= response["page_count"] or no results
    # Fixed 20 results per page; params.results_per_page is ignored
    query = {
        "api_key": settings.the_muse_api_key,
        "page": params.page,
    }
    # Keyword matching: The Muse has no keyword param — filter client-side
    # after normalize(), discard jobs where none of params.keywords appear
    # in the normalized title or description (case-insensitive substring match)
    url = "https://www.themuse.com/api/public/jobs"
    # Call normalize() on each item in response["results"]
```

**Note on The Muse keyword filtering:** Since the API has no keyword or text-search parameter,
keyword filtering must happen client-side after normalization. Only return jobs where at least
one of `params.keywords` appears in `raw_job.title` (case-insensitive). This prevents
irrelevant jobs from filling the shared pool.

#### RemoteOK

```python
async def fetch_jobs(self, params: SearchParams) -> list[RawJob]:
    # Single call returns entire dataset (no pagination)
    # Use tags from SearchBucket.remoteok_tags if available
    # CDN cache: 1-hour max — poll scheduler should not exceed 1x/hour for this source

    if params.remoteok_tags:    # Add remoteok_tags to SearchParams (see §5.1 note below)
        url = f"https://remoteok.com/api?tag={params.remoteok_tags[0]}"
    else:
        url = "https://remoteok.com/api"

    # Skip index 0 (metadata/legal notice item)
    # Call normalize() on items[1:]
```

**Note:** Add `remoteok_tags: list[str] | None = None` to `SearchParams` for RemoteOK
tag pass-through from `SearchBucket`.

#### USAJobs

```python
async def fetch_jobs(self, params: SearchParams) -> list[RawJob]:
    headers = {
        "Authorization": "USAJOBS-DEMO-TOKEN",
        "User-Agent": settings.usajobs_user_agent,
        "Email-Address": settings.usajobs_email,
        "Host": "data.usajobs.gov",
    }
    query = {
        "Keyword": " ".join(params.keywords),
        "ResultsPerPage": min(params.results_per_page, 500),   # cap at 500
        "Page": params.page,
    }
    if params.location and not params.remote_only:
        query["LocationName"] = params.location
    if params.remote_only:
        query["RemoteIndicator"] = "True"
    if params.max_days_old:
        query["DatePosted"] = params.max_days_old

    url = "https://data.usajobs.gov/api/Search"
    # Response: SearchResult.SearchResultItems[] → each item passed to normalize()
    # Paginate until TotalJobs / ResultsPerPage pages fetched, max 20 pages (10k row cap)
```

### 5.4 PollingConfiguration Additions

Add cursor field to support RemoteOK early-exit and per-source state:

| Field | Type | Notes |
|-------|------|-------|
| `last_seen_external_ids` | JSONB | `{"RemoteOK": "12345", ...}` — per-source last seen ID for early-exit |

RemoteOK adapter checks this cursor: stop iterating when `raw_job.external_id == last_seen_id`.
Update cursor after each successful poll.

### 5.5 Error Handling

All `fetch_jobs()` implementations must:
- Raise `SourceError` (existing class) on HTTP 4xx/5xx — caught by `fetch_from_sources()`
- Handle 429 Too Many Requests: raise `SourceError` with `retry_after` if header present
- On timeout (30s default): raise `SourceError`
- Partial failure is safe — one source failing does not abort other sources (existing behavior)

Use `httpx.AsyncClient` for all HTTP calls (already in project dependencies).

---

## §6 search_bucket Field on PersonaJob

### 6.1 Schema Addition

Add column to `persona_jobs` table:

```python
search_bucket: Mapped[str | None] = mapped_column(
    String(20),
    nullable=True,
    CheckConstraint("search_bucket IN ('fit', 'stretch', 'manual', 'pool')"),
)
```

| Value | Set When |
|-------|----------|
| `fit` | Job found via a fit-bucket `SearchProfile` search |
| `stretch` | Job found via a stretch-bucket `SearchProfile` search |
| `manual` | User manually submitted via ingest endpoint |
| `pool` | Surfaced by `PoolSurfacingWorker` to a persona that didn't find it directly |

**Note:** `pool` surfaced jobs inherit the `search_bucket` of the discovering persona's original
link. If no source bucket is known, `pool` is used as the fallback.

### 6.2 Passing search_bucket Through the Pipeline

The `search_bucket` value must flow from `JobFetchService` through the dedup pipeline to
`PersonaJob` creation. Extend `deduplicate_and_save()` to accept `search_bucket`:

```python
async def deduplicate_and_save(
    db: AsyncSession,
    *,
    job_data: dict[str, Any],
    persona_id: uuid.UUID,
    user_id: uuid.UUID,
    discovery_method: Literal["scouter", "manual", "pool"] = "scouter",
    search_bucket: Literal["fit", "stretch", "manual", "pool"] | None = None,  # NEW
) -> DeduplicationOutcome:
```

`JobFetchService` passes `search_bucket="fit"` or `search_bucket="stretch"` based on which
bucket's `SearchParams` was active during the fetch.

---

## §7 Poll Scheduler

### 7.1 Motivation

`PollingConfiguration.next_poll_at` is calculated after every poll but nothing reads it to
trigger the next one. Polls only fire on manual user request. This gap means the entire
scheduled polling model (Daily, Twice Daily, Weekly) is non-functional.

### 7.2 Implementation

New background worker: `PollSchedulerWorker` (alongside `PoolSurfacingWorker` and
`ReservationSweepWorker` in the FastAPI lifespan).

```python
class PollSchedulerWorker:
    interval_seconds: int = 1800   # check every 30 minutes

    async def _run_loop(self) -> None:
        # On first run: look back 24hrs to catch personas that missed their window
        # Each pass:
        #   1. Query all personas where next_poll_at <= now AND onboarding_complete = True
        #      AND polling_frequency != 'Manual Only'
        #   2. For each, resolve enabled_sources from UserSourcePreference
        #   3. Create JobFetchService and call run_poll()
        #   4. Update PollingConfiguration with new last_poll_at / next_poll_at
        #   5. Limit concurrent persona polls to avoid DB contention (max 5 at once)
```

**Concurrency:** Use `asyncio.Semaphore(5)` to limit simultaneous persona polls.
One persona's poll failure does not affect others.

**Startup:** Registered in `main.py` lifespan alongside existing workers.

---

## §8 Skill Extraction Wiring

### 8.1 Current State

`JobEnrichmentService.extract_skills_and_culture()` (line ~183) returns:
```python
return {"required_skills": [], "preferred_skills": [], "culture_text": None}
```
This is an intentional placeholder. The surrounding pipeline (truncation to 15k chars,
sanitization via `sanitize_llm_input()`) is already implemented.

### 8.2 Implementation

Wire the LLM call using the existing provider pattern:

- **Task type:** `TaskType.EXTRACTION` (already defined)
- **Model:** Gemini Flash (cost-optimized for high-volume extraction)
- **Input:** Sanitized, truncated description (existing code handles this)
- **Output:** Parse structured JSON response into `required_skills`, `preferred_skills`,
  `culture_text`
- **Fallback:** On LLM failure, return empty extraction (existing behavior) — do not
  block job save

The `extract_skills_and_culture()` method already receives `provider: LLMProvider | None`.
If `provider` is `None`, return empty extraction (test/stub mode). If present, make the call.

---

## §9 Frontend Changes

### 9.1 Onboarding Step Addition

Add a final onboarding step after the existing Growth Targets step (currently step 9).
New step: **"Your Job Search Criteria"** — displays the AI-generated `SearchProfile` with
fit and stretch buckets as editable tag lists. User can add/remove keywords and titles.
A "Looks good" button approves and sets `search_profiles.approved_at`.

The AI call to generate the `SearchProfile` fires automatically when the user reaches this
step (triggering in the background while they're still on Growth Targets if possible).

### 9.2 Job Search Settings Tab

New tab in the Settings page: **"Job Search"**. Contains:

- **Search Criteria** — editable view of `SearchProfile` fit and stretch buckets
- **Poll Schedule** — shows `polling_frequency`, `last_poll_at`, `next_poll_at`; link to
  change polling frequency in Persona preferences
- **Job Sources** — toggle enabled/disabled per source (existing `UserSourcePreference`,
  currently not exposed in UI)
- **Refresh Criteria** — button to trigger AI regeneration of `SearchProfile`
- **Staleness banner** — shown when `is_stale = True`: "Your persona has changed since
  your search criteria were last generated. Refresh them?"

### 9.3 Job Card Visual Treatment — Fit vs. Stretch

**Fit jobs** (search_bucket = 'fit' or fit_score > stretch_score):
- Display: `{fit_score}% match` label in primary color (existing behavior)
- No additional indicator

**Stretch / Growth jobs** (search_bucket = 'stretch' or stretch_score > fit_score):
- Display: amber chip reading **"Growth Role"** in the card header
- Score label changes from "match" to "stretch": `{stretch_score}% stretch`
- Color: amber (`--color-logo-accent`) — consistent with brand palette (REQ-033)

**Decision rule** (when both scores are available):
- If `stretch_score > fit_score + 10`: show as stretch/growth
- Otherwise: show as fit (avoids flicker on near-equal scores)

---

## §10 Environment Variables

New env vars required (add to `.env.example`):

| Variable | Required | Notes |
|----------|----------|-------|
| `ADZUNA_APP_ID` | For Adzuna polling | From developer.adzuna.com registration |
| `ADZUNA_APP_KEY` | For Adzuna polling | From developer.adzuna.com registration |
| `THE_MUSE_API_KEY` | For The Muse polling | From themuse.com/developers/api/v2 |
| `USAJOBS_USER_AGENT` | For USAJobs polling | App name string (e.g., "ZentropyScount/1.0") |
| `USAJOBS_EMAIL` | For USAJobs polling | Email used at developer.usajobs.gov registration |

RemoteOK requires no credentials.

All five vars are optional at runtime — if missing, the corresponding adapter is skipped
with a warning log. The pipeline continues with remaining sources.

---

## §11 Database Migration Summary

| Change | Type | Table |
|--------|------|-------|
| New `search_profiles` table | CREATE TABLE | — |
| Add `search_bucket` column | ALTER TABLE | `persona_jobs` |
| Add `last_seen_external_ids` JSONB column | ALTER TABLE | `polling_configurations` |
| New `SEARCH_PROFILE_GENERATION` task type | Seed data | `task_routing_config` |

---

## §12 Implementation Notes for Coding Agent

1. **Use `httpx.AsyncClient`** for all adapter HTTP calls — already in project dependencies.
   Create a single client per adapter instance and close on cleanup.

2. **Rate limit headroom for Adzuna:** The weekly cap (1,000) is tighter than daily×7.
   The poll scheduler should spread persona polls across the week, not burst-fire all
   on Monday morning.

3. **The Muse client-side keyword filtering** is a meaningful cost — fetching all 450 pages
   to get 9,000 jobs and then discarding 95% is wasteful. Consider limiting The Muse polls
   to a category filter (`?category=Engineering`) when the persona's role family is known,
   then applying keyword filter within that category.

4. **RemoteOK tag mapping quality** determines result relevance. If the AI produces poor
   tags, fall back to unfiltered pull + client-side keyword filter (same approach as The Muse).

5. **`search_bucket` must be set before `deduplicate_and_save()`** is called. The bucket
   is known from which `SearchProfile` bucket produced the `SearchParams`, not from the job data.

6. **SearchProfile generation should be non-blocking during onboarding** — trigger the AI
   call when the user enters the Growth Targets step, display a loading state on the new
   criteria step while generation is in progress.

7. **Alembic migration:** Add `search_profiles` table migration with appropriate FKs and
   unique constraint on `persona_id`. Add `search_bucket` column to `persona_jobs` with
   `nullable=True` (existing rows have no bucket). Add `last_seen_external_ids` as JSONB
   with `server_default='{}'`.

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-03 | Pull broadly, deduplicate centrally | At available API volumes (5k jobs/day from Adzuna alone), broad pulls are viable. Dedup Step 1 exits immediately for known jobs. |
| 2026-04-03 | AI generates SearchProfile once, algorithm polls repeatedly | AI cost at query-generation time only. Embedding-based scoring handles relevance — no AI in the polling loop. |
| 2026-04-03 | Two search buckets (fit + stretch) | `target_roles`/`target_skills` already in persona schema. Stretch bucket feeds existing `stretch_score` with source jobs it would otherwise never see. |
| 2026-04-03 | Adzuna requires negotiated licence at scale | Free tier (250/day, 1k/week) is sufficient for MVP. Re-evaluate when weekly polls approach 800 calls. |
| 2026-04-03 | The Muse: full re-fetch, client-side keyword filter | No date filter available. 450 calls to get full dataset is well within 3,600/hr limit. Category filter mitigates wasted calls. |
| 2026-04-03 | RemoteOK: tag-based, 1 call gets all jobs | No pagination, 1-hr CDN cache, ~97 jobs total. Simplest possible integration. |
| 2026-04-03 | USAJobs: DatePosted delta, ResultsPerPage=500 | No time-based rate limit. Can pull 500 jobs/call. DatePosted parameter narrows to new jobs since last poll. |
| 2026-04-03 | `search_bucket` as separate column, not overloading `discovery_method` | Keeps provenance (how found: scouter/manual/pool) separate from search intent (fit/stretch). Both are useful independently. |
