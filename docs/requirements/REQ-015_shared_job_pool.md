# REQ-015: Shared Job Pool

**Status:** Implemented
**PRD Reference:** §4.2 Scouter, §6 Data Strategy
**Last Updated:** 2026-02-27

---

## 1. Overview

This document specifies the shared job pool architecture for Zentropy Scout. Currently, job postings are per-user (each persona has its own copy). This requirement transforms jobs into a shared community resource: one canonical record per job, surfaced to any user whose persona is a relevant match.

**Key Principle:** Jobs are factual data — they don't "belong" to anyone. What's per-user is the *relationship* to the job (scores, status, notes, application). The more users search, the richer the pool gets for everyone, and redundant API calls decrease over time.

**Example:** User A's Scouter finds a "Senior Scrum Master" job on Adzuna. User B has a Scrum Master persona but hasn't run their Scouter yet. User B should see that job automatically because the pool surfacing logic detects a match.

**Scope:**
- Schema split: `job_postings` → shared pool + per-user link table
- Child table reassignment (extracted_skills, job_embeddings)
- Global deduplication (across all users)
- Job surfacing logic (matching shared jobs to personas)
- Privacy boundaries (users cannot see who else found/applied)
- Scouter agent changes (check pool before creating)
- API changes (return joined shared + per-user data)
- Migration from current per-user schema

**Out of scope:** Job recommendation engine (ML-based), user-to-user social features, employer-side job management, job freshness cron (can add later).

---

## 2. Dependencies

### 2.1 This Document Depends On

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-003 Job Posting Schema v0.4 | Schema | Field definitions, dedup rules, ghost detection |
| REQ-005 Database Schema v0.10 | Schema | Entity relationships, FK chain |
| REQ-006 API Contract v0.8 | Integration | Endpoint structure, response envelopes |
| REQ-007 Agent Behavior v0.5 | Integration | Scouter graph, Strategist scoring |
| REQ-008 Scoring Algorithm v0.2 | Integration | Fit/stretch scoring against persona |
| REQ-014 Multi-Tenant Data Isolation v0.1 | Prerequisite | Tier classification, ownership patterns |

### 2.2 Other Documents Depend On This

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-014 Multi-Tenant Data Isolation | Update required | Entity ownership graph changes (§4.1) |

---

## 3. Design Decisions & Rationale

### 3.1 Schema Strategy: Split Into Shared + Per-User

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------:|
| Split `job_postings` into shared pool + per-user link | ✅ | Clean separation of factual job data (shared) from user-specific data (scores, status). One canonical record per job reduces storage and enables cross-user surfacing. |
| Copy-on-discover (each user gets their own copy) | — | Current design. Wastes storage, prevents cross-user discovery, requires more API calls. N users × M jobs = N×M rows instead of M. |
| Shared pool with materialized views per user | — | Operational complexity. Views must refresh on every score change. Harder to reason about than explicit link table. |

### 3.2 Surfacing Strategy: Score-on-Discovery + Periodic Sweep

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------:|
| Score on discovery + periodic sweep | ✅ | When a new job enters the pool, score it against active personas with matching keywords. Periodic sweep catches personas created after the job. Balances freshness with cost. |
| Real-time push to all users | — | Expensive. Every new job triggers N scoring calls. Not justified at MVP scale. |
| Pull-only (users must search) | — | Misses the key value proposition — jobs should appear automatically for matching users. |

### 3.3 Privacy Model: Anonymous Pool

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------:|
| Anonymous — no cross-user visibility | ✅ | Users cannot see who discovered a job, who applied, or how many others are tracking it. Jobs appear as if they came from the system. Simplest privacy model. |
| Aggregated stats ("12 others applied") | Deferred | Useful signal but adds complexity and privacy questions. Can add later with opt-in. |

---

## 4. Schema Changes

### 4.1 Modified: `job_postings` → Shared Pool (Tier 0)

The existing `job_postings` table becomes the shared canonical record. Changes:

| Change | Before | After |
|--------|--------|-------|
| `persona_id` FK | Required (Tier 2) | **Removed** — jobs are global |
| `status` | Discovered/Dismissed/Applied/Expired | **Replaced** with `is_active` boolean |
| `is_favorite` | Per-user flag | **Removed** — moves to persona_jobs |
| `fit_score` | Per-user score | **Removed** — moves to persona_jobs |
| `stretch_score` | Per-user score | **Removed** — moves to persona_jobs |
| `failed_non_negotiables` | Per-user filter result | **Removed** — moves to persona_jobs |
| `dismissed_at` | Per-user timestamp | **Removed** — moves to persona_jobs |
| New: `is_active` | — | Boolean, default true. False when job confirmed expired. |
| `score_details` | Per-user JSONB | **Removed** — moves to persona_jobs |

**Retained on `job_postings`** (all job-intrinsic, factual data):
- `id`, `source_id`, `external_id`
- `job_title`, `company_name`, `company_url`, `location`, `work_model`, `seniority_level`
- `salary_min`, `salary_max`, `salary_currency`
- `description`, `culture_text`, `requirements`, `years_experience_min`, `years_experience_max`
- `posted_date`, `application_deadline`
- `source_url`, `apply_url`, `raw_text`
- `description_hash`, `repost_count`, `previous_posting_ids`
- `ghost_score`, `ghost_signals`, `also_found_on` (internal only — see §8.4)
- `first_seen_date`, `last_verified_at`, `expired_at`
- `created_at`, `updated_at`

**Removed from design: `discovered_by_user_id`.** Originally proposed as an analytics-only FK to `users.id`. Removed because: (1) storing cross-tenant identity references on a shared table creates privacy liability, (2) GDPR erasure requires nulling or cascading on user deletion, (3) ORM eager loading or error messages could leak the value. Discovery attribution is tracked in application logs instead — no column needed.

**Updated indexes** (remove persona-scoped indexes, add global ones):

```sql
-- Remove persona-scoped indexes
DROP INDEX IF EXISTS idx_job_postings_persona_id;
DROP INDEX IF EXISTS idx_job_postings_persona_id_status;
DROP INDEX IF EXISTS idx_job_postings_persona_id_fit_score;

-- Add global indexes
CREATE INDEX IF NOT EXISTS idx_job_postings_is_active ON job_postings(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_job_postings_company_name_job_title ON job_postings(company_name, job_title);
CREATE INDEX IF NOT EXISTS idx_job_postings_first_seen_date ON job_postings(first_seen_date DESC);
```

Existing global indexes remain: `idx_job_postings_description_hash`, `idx_job_postings_company_name`, `idx_job_postings_source_id`, `idx_job_postings_source_id_external_id`.

### 4.2 New: `persona_jobs` — Per-User Relationship (Tier 2)

This table holds every user-specific field that was removed from `job_postings`:

```sql
CREATE TABLE persona_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    persona_id UUID NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    job_posting_id UUID NOT NULL REFERENCES job_postings(id) ON DELETE RESTRICT,
        -- RESTRICT, not CASCADE: shared jobs must not be casually deleted
        -- while any user has a relationship to them.

    -- User relationship
    status VARCHAR(20) NOT NULL DEFAULT 'Discovered'
        CHECK (status IN ('Discovered', 'Dismissed', 'Applied')),
        -- No 'Saved' status — REQ-003 §18.6 decided to use is_favorite flag instead.
        -- No 'Expired' — expiry is a shared job property (job_postings.is_active).
        --   The API response includes job.is_active alongside persona_jobs.status.
    is_favorite BOOLEAN NOT NULL DEFAULT false,
    dismissed_at TIMESTAMPTZ,

    -- Per-user scoring (from Strategist)
    fit_score INTEGER CHECK (fit_score >= 0 AND fit_score <= 100),
    stretch_score INTEGER CHECK (stretch_score >= 0 AND stretch_score <= 100),
    failed_non_negotiables JSONB,
    score_details JSONB,        -- Full scoring breakdown from Strategist (moved from job_postings)

    -- Discovery metadata
    discovery_method VARCHAR(20) NOT NULL DEFAULT 'pool'
        CHECK (discovery_method IN ('scouter', 'manual', 'pool')),
        -- scouter: user's own Scouter found it
        -- manual: user submitted it (extension/add-job)
        -- pool: surfaced from shared pool by matching
        -- Named 'discovery_method' (not 'source') to avoid confusion
        -- with job_postings.source_id which references the job_sources table.

    -- Timestamps
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    scored_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- One link per persona per job
    UNIQUE (persona_id, job_posting_id)
);

-- Indexes
CREATE INDEX idx_persona_jobs_persona ON persona_jobs(persona_id);
CREATE INDEX idx_persona_jobs_job ON persona_jobs(job_posting_id);
CREATE INDEX idx_persona_jobs_status ON persona_jobs(persona_id, status);
CREATE INDEX idx_persona_jobs_fit ON persona_jobs(persona_id, fit_score DESC)
    WHERE status = 'Discovered';
```

**Key constraints:**
- `UNIQUE (persona_id, job_posting_id)` — a persona can only have one relationship with a given job.
- `ON DELETE RESTRICT` on `job_posting_id` — prevents accidental deletion of shared jobs that have user relationships. To remove a shared job, all `persona_jobs` links must be explicitly removed first (e.g., via a cleanup cron).

### 4.3 Child Tables

| Child Table | Current Parent | After | Notes |
|-------------|---------------|-------|-------|
| `extracted_skills` | `job_posting_id` → `job_postings` | Same | Job-intrinsic. No change. |
| `job_embeddings` | `job_posting_id` → `job_postings` | Same | Job-intrinsic. No change. |
| `applications` | `persona_id` → `personas` | Same + new FK | See §4.4. |
| `job_variants` | `base_resume_id` → `base_resumes` | Same | Persona-scoped through base_resumes. No change. |
| `cover_letters` | `persona_id` → `personas`, `job_posting_id` → `job_postings` | Same | `job_posting_id` FK uses `ON DELETE RESTRICT` — shared jobs with cover letters cannot be deleted. |

**RESTRICT FK constraint note:** `applications`, `cover_letters`, and `job_variants` all have `ON DELETE RESTRICT` FKs pointing to `job_postings`. This means shared job postings with dependent records cannot be deleted. This is the correct behavior for a shared pool — jobs with active relationships should never be silently removed. The migration dedup step (§11.3) must reassign these FKs before merging duplicates.

### 4.4 Updated FK: `applications`

Applications currently reference a job posting. With the split, they should reference both:

```sql
-- applications table (existing)
ALTER TABLE applications
    ADD COLUMN persona_job_id UUID REFERENCES persona_jobs(id) ON DELETE SET NULL;
```

This links the application back to the user's job relationship (scores, discovery source). The existing `persona_id` FK remains for direct ownership isolation.

**Migration:** Backfill `persona_job_id` from existing data by matching `applications.persona_id` + job reference.

### 4.5 Status Lifecycle (Two-Table Model)

The status lifecycle from REQ-003 §6.1 is split across two tables:

**Shared `job_postings.is_active`:**
```
true (default) → false (job confirmed expired or removed)
```
This is a one-way transition. Once a job is marked inactive, it stays inactive. Inactive jobs are still visible to users who have `persona_jobs` links (e.g., "You applied to this job — it has since expired").

**Per-user `persona_jobs.status`:**
```
Discovered → Dismissed    (user dismisses job)
Discovered → Applied      (user submits application)
Dismissed  → Discovered   (user un-dismisses — restores job to feed)
```

**Expiry interaction:** When a shared job becomes `is_active = false`:
- Users' `persona_jobs.status` does NOT change — their relationship is independent
- The API response includes `job.is_active` alongside `persona_jobs.status`
- The frontend renders "This job has expired" based on `is_active = false`
- A user with `status = 'Applied'` sees: "Applied — job has since expired"
- Aligns with REQ-003 §6.1: "Applied → Expired: Application continues independently"

**`is_favorite` is orthogonal to status** (per REQ-003 §18.6 design decision). A user can favorite any job regardless of status. This replaces the previously-considered `Saved` status.

---

## 5. Updated Entity Ownership Graph

This updates REQ-014 §4.1:

```
Tier 0 — Global (no tenant isolation)
  ├── job_sources              Shared catalog of external job sources
  └── job_postings             Shared job pool (CHANGED from Tier 2)
        ├── extracted_skills   Job-intrinsic skill extraction
        └── job_embeddings     Job-intrinsic vector embeddings

Tier 0 — Tenant Root
  └── users                    Authenticated user identity

Tier 1 — Direct User Ownership
  └── personas                 user_id → users.id

Tier 2 — Persona-Scoped
  ├── persona_jobs             persona_id → personas.id (NEW — per-user job link)
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
  └── cover_letters            persona_id → personas.id

Tier 3+ — unchanged (bullets, job_variants, applications, etc.)
```

**Key change:** `job_postings` moves from Tier 2 to Tier 0. Its children (`extracted_skills`, `job_embeddings`) follow. The new `persona_jobs` table becomes the Tier 2 link.

---

## 6. Global Deduplication

### 6.1 Current State

Deduplication (REQ-003 §8–9) currently runs per-persona. With the shared pool, it becomes **global** — the same dedup logic, but checking against all jobs in the pool regardless of who discovered them.

### 6.2 Dedup Flow (Updated)

```
New job arrives (from any user's Scouter, manual ingest, etc.)
    │
    ├─ Check 1: source_id + external_id match → UPDATE existing job
    ├─ Check 2: description_hash match → ADD to also_found_on
    ├─ Check 3: company + title + description similarity → LINK as repost
    └─ Check 4: No match → CREATE new job in shared pool
    │
    ├─ Create persona_jobs link for discovering user
    └─ Trigger surfacing (§7) for other matching personas
```

### 6.3 Dedup Benefits

| Metric | Before (per-user) | After (shared pool) |
|--------|-------------------|---------------------|
| Storage | N users × M jobs = N×M rows | M shared + N×M links (links are small) |
| API calls | Each user's Scouter fetches independently | First user caches the job; subsequent users skip the API call |
| Dedup scope | Within one persona | Across all users — catches cross-user duplicates |
| Embeddings | N copies of same embedding | One embedding per job |

---

## 7. Job Surfacing Logic

### 7.1 Surfacing Architecture: Background Process (Not Per-User)

**CRITICAL:** Surfacing is a **system-level background process**, not part of any individual user's Scouter run. A user's Scouter reads other users' persona data to score against — this is a cross-tenant operation that violates the application-level tenant isolation model (REQ-014 §7). The surfacing worker runs with system-level privileges, separate from user-scoped agents.

**Pool Surfacing Worker** — a periodic background task (cron or task queue):

1. **On schedule (e.g., every 15 minutes)** — Check for new jobs in the pool since last run. Score each against active personas that haven't seen it yet.
2. **On persona update** — When a user updates their persona (new skills, new preferences), queue a re-evaluation of recent pool jobs against the updated persona.
3. **On Scouter completion** — When a user's Scouter adds new jobs to the pool, notify the surfacing worker to process them (via task queue or flag).

### 7.2 Matching Criteria

A shared job should be surfaced to a persona if **any** of these conditions are met:

1. **Keyword match** — Job title or extracted skills overlap with persona's skills (hard or soft). Use existing skill matching logic from REQ-008.
2. **Embedding similarity** — Job requirements embedding is within threshold of persona embedding. Use existing cosine similarity from REQ-008 §3.
3. **Seniority/work model match** — Job's seniority level and work model align with persona preferences (from custom_non_negotiables).

**Threshold:** Only create a `persona_jobs` link if the fit_score ≥ the target persona's `minimum_fit_threshold` (REQ-003 §10.5, default 50). This prevents surfacing jobs the user would never see — their own threshold would hide them. Using the persona's configured threshold (not a global constant) respects per-user preferences.

### 7.3 Surfacing Does NOT Mean Notification

Surfacing creates a `persona_jobs` record with `status='Discovered'` and `discovery_method='pool'`. The job appears in the user's job dashboard on their next visit. There is no push notification, email, or real-time alert. The user sees it naturally when browsing.

### 7.4 Rate Limiting Surfacing

To prevent runaway scoring costs:

- **Max jobs per surfacing pass:** 50 (process newest first)
- **Max personas per new job:** 100 (score highest-overlap personas first)
- **Cooldown:** Don't re-surface jobs that were already scored for a persona (check `persona_jobs` UNIQUE constraint)
- **Lightweight pre-screen:** Before running full scoring (which requires persona data + LLM), apply a cheap keyword overlap check. Only run full scoring if keyword overlap suggests a potential match. This avoids N×M full scoring calls.

---

## 8. Privacy Boundaries

### 8.1 What Users CAN See

- Jobs in their `persona_jobs` list (discovered by their Scouter, manually added, or surfaced from pool)
- Their own scores, status, notes, and application history for each job
- The job's factual data (title, company, description, skills, ghost score)

### 8.2 What Users CANNOT See

| Data | Visible? | Why |
|------|----------|-----|
| Who discovered the job first | No | Not stored in the database (tracked in logs only) |
| How many other users are tracking this job | No | Prevents competitive anxiety |
| Other users' scores for this job | No | Scores are persona-specific |
| Other users' application status | No | Private employment data |
| `also_found_on` details | No | Contains cross-source timestamps that could reveal other users' Scouter timing |
| Whether a job came from the pool vs. their own Scouter | Minimal | `discovery_method` field exists but UI shows all jobs the same way |

### 8.3 API Enforcement

The API never returns cross-user aggregation or internal metadata. Response schemas explicitly exclude these fields:

```python
class JobPostingResponse(BaseModel):
    """Public job data — shared pool fields only."""
    id: uuid.UUID
    job_title: str
    company_name: str
    is_active: bool
    # ... all factual fields
    # NO also_found_on (internal cross-source tracking)
    # NO user_count or other cross-user aggregations

class PersonaJobResponse(BaseModel):
    """Per-user job relationship."""
    id: uuid.UUID
    job: JobPostingResponse  # Nested shared data
    status: str
    fit_score: int | None
    stretch_score: int | None
    is_favorite: bool
    discovery_method: str  # scouter | manual | pool
    discovered_at: datetime
```

### 8.4 Content Security for Shared Pool

The shared pool creates a new attack surface: **LLM prompt injection via pool poisoning.** A malicious user can submit a crafted "job posting" containing injection payloads. When other users' agents process this job (for scoring, skill matching, etc.), the injected text is sent to the LLM alongside the victim's persona data.

**Mitigations (all required):**

1. **Sanitize on read:** All shared pool content MUST pass through `sanitize_llm_input()` (from `backend/app/core/llm_sanitization.py`) before being included in any LLM prompt. This is the existing 8-stage sanitization pipeline (NFKC, zero-width strip, combining mark strip, confusable mapping, control chars, injection patterns, NFC).

2. **Validate on write:** The ingest endpoint (`POST /job-postings/ingest/confirm`) must reject job descriptions that contain detected prompt injection patterns. Use the injection pattern detection from the sanitization pipeline as a pre-check.

3. **Quarantine user-submitted jobs:** Jobs submitted via manual ingest (`discovery_method='manual'`) are only visible to the submitting user until independently confirmed. A job is "confirmed" when:
   - A different user's Scouter finds the same job via API fetch (dedup match), OR
   - A system admin approves it (future feature), OR
   - **7-day auto-release:** The quarantine expires 7 days after submission with no rejection signal. Rationale: jobs from niche boards may never be independently confirmed by another Scouter. A time-based release prevents legitimate jobs from being permanently quarantined. If a quarantined job receives a report or fails re-validation during the 7-day window, the quarantine extends indefinitely until admin review.

   Until confirmed, the job exists in the shared pool but the surfacing worker skips it for other users. This prevents a single malicious user from poisoning other users' feeds.

4. **Rate limit manual submissions:** Max 20 manual job submissions per user per day. Prevents bulk pool poisoning.

**Timing side channel mitigation:** The ingest endpoint should return responses in consistent time regardless of whether the job was already in the pool (dedup hit) or is new (requires LLM extraction). Defer extraction to a background task and return immediately with a "processing" status in all cases.

---

## 9. API Changes

### 9.1 Endpoint Updates

| Endpoint | Change | Notes |
|----------|--------|-------|
| `GET /job-postings` | **Returns persona_jobs** — joined with shared job data, filtered by user's persona | Was: query job_postings WHERE persona_id. Now: query persona_jobs JOIN job_postings WHERE persona.user_id |
| `GET /job-postings/{id}` | **Lookup via persona_jobs** — return 404 if user has no link to this job | Prevents browsing the entire shared pool directly |
| `POST /job-postings` | **Creates in shared pool** + creates persona_jobs link | Dedup check first. If job already exists, just create the link. |
| `PATCH /job-postings/{id}` | **Updates persona_jobs fields** (status, favorite, dismissed_at) | Shared job data is immutable from user API. Only per-user fields change. |
| `POST /job-postings/ingest` | **Unchanged** — still returns preview | Preview is stateless |
| `POST /job-postings/ingest/confirm` | **Creates in shared pool** + creates persona_jobs link | Same as POST but from ingest flow |
| `POST /job-postings/bulk-dismiss` | **Updates persona_jobs** — sets status=Dismissed | No change to shared pool |
| `POST /job-postings/bulk-favorite` | **Updates persona_jobs** — toggles is_favorite | No change to shared pool |

### 9.2 New Endpoint

```
POST /job-postings/rescore
```

Triggers re-scoring of a persona's discovered jobs. Useful after persona updates. Calls Strategist to recalculate fit_score and stretch_score for all `persona_jobs` with `status = 'Discovered'`.

---

## 10. Scouter Agent Changes

### 10.1 Updated Scouter Flow

The Scouter graph is updated to check the shared pool and save to it. **Surfacing to other personas is NOT part of the Scouter** — it runs as a separate background process (§7.1).

```
get_enabled_sources
    ↓
fetch_sources (parallel API calls — unchanged)
    ↓
merge_results (unchanged)
    ↓
check_shared_pool (REPLACES deduplicate_jobs — global dedup, not per-persona)
    │
    ├─ Already in pool → Create persona_jobs link only (skip extraction)
    └─ New to pool → Continue to extraction
    ↓
extract_skills (unchanged — only for truly new jobs)
    ↓
calculate_ghost_score (unchanged)
    ↓
save_to_pool (REPLACES save_jobs — saves to shared job_postings, then creates persona_jobs link)
    ↓
notify_surfacing_worker (NEW — signals the background worker that new jobs are available)
    ↓
invoke_strategist (unchanged — scores for discovering user only)
    ↓
update_poll_state (unchanged)
```

**Node mapping from REQ-007 §15.3:**
- `deduplicate_jobs` → replaced by `check_shared_pool` (global dedup instead of per-persona)
- `save_jobs` → replaced by `save_to_pool` (writes to shared pool + creates persona_jobs link)
- `surface_to_other_personas` → removed from Scouter. Handled by Pool Surfacing Worker (§7.1).

### 10.2 Key Optimization

When a user's Scouter runs and finds 20 jobs, but 15 already exist in the pool (found by other users' Scouters), only 5 need LLM extraction. This is the core efficiency gain — API calls and LLM costs decrease as the pool grows.

### 10.3 Pool Check Step

```python
async def check_shared_pool_node(state: ScouterState) -> dict:
    """Check which fetched jobs already exist in the shared pool."""
    new_jobs = []
    existing_jobs = []

    for job in state["merged_jobs"]:
        # Check by source+external_id, then by description_hash
        match = await dedup_service.find_in_pool(
            source_id=job["source_id"],
            external_id=job["external_id"],
            description_hash=job.get("description_hash"),
        )
        if match:
            existing_jobs.append(match)
        else:
            new_jobs.append(job)

    return {
        "new_jobs": new_jobs,           # Need extraction
        "existing_pool_jobs": existing_jobs,  # Just need persona_jobs link
    }
```

**Race condition handling:** If two Scouters discover the same new job simultaneously, both will attempt to INSERT into the shared pool. Add a UNIQUE constraint on `(source_id, external_id)` WHERE both are NOT NULL, and use `ON CONFLICT DO NOTHING` (or `DO UPDATE SET last_verified_at = now()`) to handle the race gracefully. The losing Scouter should then look up the existing record and create its `persona_jobs` link.

---

## 11. Migration Strategy

### 11.1 Migration Steps

```
Step 1: Create persona_jobs table (empty)
Step 2: Add is_active column to job_postings (default true)
Step 3: Add UNIQUE constraint on job_postings(source_id, external_id) WHERE both NOT NULL
Step 4: Backfill persona_jobs from existing job_postings data
Step 5: Backfill is_active (true for status != 'Expired', false for Expired)
Step 6: Dedup: merge duplicate job_postings (§11.3 — reassign child FKs, then delete duplicates)
Step 7: Add persona_job_id FK to applications (backfill from persona_id + job_posting_id)
Step 8: Drop per-user columns from job_postings (status, is_favorite, fit_score, stretch_score, score_details, failed_non_negotiables, dismissed_at)
Step 9: Drop persona_id FK from job_postings
Step 10: Update indexes (drop persona-scoped, add global)
```

**Downtime requirement:** Steps 8-9 change the schema in a breaking way. The application should be stopped during this migration to avoid in-flight requests using the old schema. Alternatively, use a blue-green deployment with the new code deployed after the migration completes.

### 11.2 Backfill Query

```sql
-- Step 4: Create persona_jobs links from existing per-user data
INSERT INTO persona_jobs (
    persona_id, job_posting_id, status, is_favorite,
    fit_score, stretch_score, failed_non_negotiables, score_details,
    dismissed_at, discovery_method, discovered_at, scored_at,
    created_at, updated_at
)
SELECT
    jp.persona_id,
    jp.id,
    CASE jp.status
        WHEN 'Expired' THEN 'Discovered'  -- Expired is now on shared table (is_active=false)
        ELSE jp.status
    END,
    jp.is_favorite,
    jp.fit_score,
    jp.stretch_score,
    jp.failed_non_negotiables,
    jp.score_details,
    jp.dismissed_at,
    'scouter',  -- All existing jobs were found by user's own Scouter
    jp.first_seen_date,
    CASE WHEN jp.fit_score IS NOT NULL THEN jp.updated_at END,
    jp.created_at,
    jp.updated_at
FROM job_postings jp;
```

### 11.3 Dedup During Migration

Existing data may have duplicate jobs across personas (same job found by multiple users independently). The migration must deduplicate:

1. Group `job_postings` by `description_hash`
2. For each group with >1 row: pick the oldest row as the "canonical" record
3. **Reassign child FKs:** Update `applications.job_posting_id`, `cover_letters.job_posting_id`, `job_variants.job_posting_id`, `extracted_skills.job_posting_id`, and `job_embeddings.job_posting_id` on duplicate rows to point to the canonical record. This is required because these tables use `ON DELETE RESTRICT` — deleting duplicates would fail without reassignment.
4. Merge `also_found_on` from duplicates into the canonical record
5. Ensure `persona_jobs` links exist for all personas that referenced duplicates (Step 4 already created them from the original `persona_id`)
6. Delete the duplicate `job_postings` rows (now safe — no child FKs point to them)

**Data integrity note:** SHA-256 hash collisions are astronomically unlikely but theoretically possible. Before merging, verify that `company_name` matches across the group. Skip merging if company names differ (hash collision on genuinely different jobs).

### 11.4 Reversibility

The migration is **not trivially reversible** once per-user columns are dropped (Step 6-7). The Alembic downgrade should:
- Re-add columns to `job_postings`
- Backfill from `persona_jobs`
- Drop `persona_jobs` table

---

## 12. Testing Strategy

### 12.1 Shared Pool Tests

| Test | What It Verifies |
|------|-----------------|
| Two users submit same job URL → one pool entry, two persona_jobs links | Dedup works globally |
| User A's Scouter finds job → User B (matching persona) sees it | Surfacing logic works |
| User C (non-matching persona) does NOT see it | Threshold filtering works |
| User dismisses a job → other users' views unaffected | Per-user isolation |
| User applies → shared job data unchanged | Shared pool is read-only from user perspective |
| Job expires (`is_active=false`) → API response includes `job.is_active=false` alongside unchanged `persona_jobs.status` | Expiry visible without status change |

### 12.2 Privacy & Security Tests

| Test | What It Verifies |
|------|-----------------|
| GET /job-postings/{id} response has no `also_found_on` | Privacy enforcement |
| GET /job-postings list has no cross-user aggregation | Privacy enforcement |
| User cannot access another user's persona_jobs | Tenant isolation (REQ-014) |
| Job description with prompt injection payload → rejected on ingest | Content security (§8.4) |
| Quarantined manual job not surfaced to other users | Pool poisoning defense (§8.4) |
| Manual submission rate limit enforced (20/day) | Anti-spam (§8.4) |
| Ingest response time consistent for new vs. existing jobs | Timing side channel defense (§8.4) |

### 12.3 Migration Tests

| Test | What It Verifies |
|------|-----------------|
| Upgrade: existing data migrated correctly to persona_jobs | Backfill works |
| Upgrade: duplicates across personas deduplicated | Dedup during migration |
| Downgrade: persona_jobs data restored to job_postings | Reversibility |

---

## 13. Open Questions

| # | Question | Status | Notes |
|---|----------|--------|-------|
| 1 | Should surfacing run as a background task or inline with Scouter? | Decided: Background | Required for tenant isolation — surfacing reads other users' persona data (cross-tenant operation). Must be a system-level process, not part of a user's Scouter run. See §7.1. |
| 2 | What's the fit_score threshold for surfacing? | Decided: Per-persona | Uses target persona's `minimum_fit_threshold` (REQ-003 §10.5, default 50). Avoids creating persona_jobs records users would never see. See §7.2. |
| 3 | Should users be able to browse the full shared pool? | Proposed: No | Users only see jobs surfaced to their persona. Prevents information overload and maintains relevance. |
| 4 | Add "trending jobs" (jobs many personas match)? | Deferred | Nice signal but adds cross-user aggregation. Privacy implications need thought. |
| 5 | Job freshness/expiry cron to mark stale jobs inactive? | Deferred | Useful for pool hygiene. Check `last_verified_at` and mark inactive after N days. Without this, the pool grows unbounded. Add as a separate task soon after initial implementation. |
| 6 | GDPR right to erasure vs. shared pool? | Proposed: Community data | Shared pool jobs are "community contributed" — not subject to individual deletion. On user deletion, only `persona_jobs` links and application logs are removed. The shared job record remains. Document this in GDPR compliance materials. |

---

## 14. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-18 | v0.1 | Initial draft — schema split, dedup, surfacing, privacy, migration |
| 2026-02-18 | v0.2 | Security hardening — removed `discovered_by_user_id` (privacy risk), removed `Saved` status (REQ-003 conflict), added content security §8.4 (pool poisoning, quarantine, rate limits), moved surfacing to background process (tenant isolation), fixed `ON DELETE RESTRICT`, added `score_details` to persona_jobs, renamed `source` to `discovery_method`, added status lifecycle §4.5, fixed migration for RESTRICT FK reassignment, added race condition handling, added timing side channel mitigation |
| 2026-02-18 | v0.3 | Added 7-day quarantine auto-release with rejection-signal extension (§8.4) — prevents niche-board jobs from being permanently quarantined |
