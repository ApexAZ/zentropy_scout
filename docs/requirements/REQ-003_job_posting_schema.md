# REQ-003: Job Posting Schema

**Status:** Draft  
**PRD Reference:** §4.2 Scouter Agent, §7 Job Discovery  
**Last Updated:** 2025-01-25

---

## 1. Overview

This document defines the schema for job postings: how they're discovered, what data is extracted, how ghost jobs are detected, and the lifecycle from discovery to application or dismissal.

**Key Principle:** Job Postings represent opportunities in the market. They are discovered automatically by the Scouter agent and matched against the user's Persona. The user decides whether to pursue (creating an Application) or dismiss.

### 1.1 Problem Context

Job seekers face several pain points this schema addresses:

| Pain Point | How We Address It |
|------------|-------------------|
| **Missed opportunities** | Automated discovery from multiple sources, user doesn't have to manually search |
| **Ghost jobs wasting time** | Ghost detection scoring warns users before they invest effort |
| **Information overload** | Matching scores filter and prioritize relevant jobs |
| **Losing track of jobs** | Structured status tracking, favorites, history preservation |
| **Applying to same reposted job** | Repost detection links history, agent provides context |

---

## 2. Entity Relationships

```
Job Sources (APIs, Extension, Manual)
    │
    └── Scouter Agent
            │
            └── Job Posting (discovered)
                    │
                    ├── Matched against Persona (REQ-001)
                    │       │
                    │       ├── Fit Score
                    │       └── Stretch Score
                    │
                    ├── Ghost Detection
                    │       │
                    │       └── Ghost Score + Signals
                    │
                    └── User Decision
                            │
                            ├── Dismissed
                            ├── Applied → Application (REQ-004)
                            └── Expired (job no longer available)
```

---

## 3. Dependencies

### 3.1 This Document Depends On

| Dependency | Type | Fields Used |
|------------|------|-------------|
| REQ-001 Persona Schema | Matching | Skills (§3.5), Non-Negotiables (§3.8), Growth Targets (§3.9), Discovery Preferences (§3.10) |

### 3.2 Other Documents Depend On This

| Document | Dependency | Notes |
|----------|------------|-------|
| REQ-002b Cover Letter Schema | Foreign Key | `job_posting_id` |
| REQ-004 Application Schema | Foreign Key | `job_posting_id` |
| REQ-005 Database Schema | All field definitions | ERD built from REQ-001 through REQ-004 |

---

## 4. Job Sources

### 4.1 MVP Sources

| Source | Type | Coverage | Best For |
|--------|------|----------|----------|
| **Adzuna** | Aggregator API | US, UK, EU, AU | Broad white-collar |
| **The Muse** | Aggregator API | US-focused | PM, curated companies |
| **RemoteOK** | Aggregator API | Global remote | Remote tech/Agile |
| **USAJobs** | Government API | US federal | Government roles |
| **Chrome Extension** | User capture | Any site | LinkedIn, Indeed, any |
| **Manual Paste** | User input | Any | Fallback |

### 4.2 Source Registry (Global)

System-level table of available job sources. Shared across all users.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | UUID | ✅ | |
| source_name | String | ✅ | e.g., "Adzuna", "Chrome Extension" |
| source_type | Enum | ✅ | API / Extension / Manual |
| description | String | ✅ | For user tooltip — explains what this source is and what jobs it's good for |
| api_endpoint | String | Optional | Base URL for API sources |
| is_active | Boolean | ✅ | System-level enable/disable (for maintenance, deprecation) |
| display_order | Integer | ✅ | Default ordering |

### 4.2b User Source Preferences (Per-Persona)

User-level preferences for job sources.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | UUID | ✅ | |
| persona_id | UUID | ✅ | FK to Persona |
| source_id | UUID | ✅ | FK to Source Registry |
| is_enabled | Boolean | ✅ | User toggle — can disable sources they don't want |
| display_order | Integer | Optional | User can reorder; null = use global default |

**Initialization:** When Persona is created, User Source Preferences are created for all active sources with `is_enabled = true`.

### 4.3 Agent Source Selection

Agent selects sources based on Persona:

| Persona Signal | Sources Prioritized |
|----------------|---------------------|
| `remote_preference = "Remote Only"` | RemoteOK |
| `target_roles` includes government | USAJobs |
| General | Adzuna, The Muse, all enabled |

Agent explains reasoning to user.

### 4.4 Polling Configuration

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | UUID | ✅ | |
| persona_id | UUID | ✅ | FK to Persona |
| polling_frequency | Enum | ✅ | Daily / Twice Daily / Weekly / Manual Only |
| last_poll_at | Timestamp | Optional | |
| next_poll_at | Timestamp | Optional | Calculated from frequency |

**Default:** Daily polling. User can change frequency or trigger manual poll.

---

## 5. Field Definitions

### 5.1 Job Posting

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| id | UUID | ✅ | No | Internal ID |
| persona_id | UUID | ✅ | No | FK to Persona (owner) |
| external_id | String | Optional | No | ID from source system |
| source_id | UUID | ✅ | No | FK to Source Registry (primary source) |
| also_found_on | JSONB | Optional | No | Other sources where job was found (see §9.2) |
| job_title | String | ✅ | No | |
| company_name | String | ✅ | No | |
| company_url | String | Optional | No | Company website |
| location | String | Optional | No | City, state, country |
| work_model | Enum | Optional | No | Remote / Hybrid / On-site |
| seniority_level | Enum | Optional | No | Entry / Mid / Senior / Lead / Executive |
| salary_min | Integer | Optional | No | |
| salary_max | Integer | Optional | No | |
| salary_currency | String | Optional | No | USD, EUR, etc. |
| description | String | ✅ | No | Full job description |
| requirements | String | Optional | No | Skills, experience, education |
| years_experience_min | Integer | Optional | No | Minimum years requested |
| years_experience_max | Integer | Optional | No | Maximum years (if range specified) |
| posted_date | Date | Optional | No | When job was posted (from source) |
| application_deadline | Date | Optional | No | If specified |
| source_url | String | Optional | No | Where we found it |
| apply_url | String | Optional | No | Direct link to ATS/application |
| raw_text | String | Optional | No | Original unprocessed text |
| status | Enum | ✅ | No | Discovered / Dismissed / Applied / Expired |
| is_favorite | Boolean | ✅ | No | User flag, default false |
| fit_score | Integer | Optional | No | 0-100, match against Persona |
| stretch_score | Integer | Optional | No | 0-100, growth alignment |
| failed_non_negotiables | JSONB | Optional | No | Which non-negotiables this job violates (see §10.4) |
| first_seen_date | Date | ✅ | No | When Scout discovered it |
| last_verified_at | Timestamp | Optional | No | Last time we confirmed job still exists |
| created_at | Timestamp | ✅ | No | |
| updated_at | Timestamp | ✅ | No | |
| dismissed_at | Timestamp | Optional | No | When user dismissed |
| expired_at | Timestamp | Optional | No | When job became unavailable |

### 5.2 Ghost Detection Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| description_hash | String | ✅ | SHA-256 of description for dedup |
| repost_count | Integer | ✅ | Default 0, incremented on repost detection |
| previous_posting_ids | List of UUIDs | Optional | Links to prior versions of same job |
| ghost_score | Integer | ✅ | 0-100, calculated |
| ghost_signals | JSONB | Optional | Which factors triggered |

### 5.3 Extracted Skills

Skills extracted from job posting for matching.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | UUID | ✅ | |
| job_posting_id | UUID | ✅ | FK to Job Posting |
| skill_name | String | ✅ | Extracted skill |
| skill_type | Enum | ✅ | Hard / Soft |
| is_required | Boolean | ✅ | Required vs. nice-to-have |
| years_requested | Integer | Optional | If specified |

---

## 6. Status Definitions

| Status | Meaning | Triggered By |
|--------|---------|--------------|
| Discovered | Scout found it, user hasn't acted | Initial discovery |
| Dismissed | User not interested | User action |
| Applied | User pursuing — Application created | Application creation |
| Expired | Job no longer available | Scout detection or user action |

### 6.1 Status Transitions

```
Discovered → Dismissed (user action)
          → Applied (Application created)
          → Expired (job taken down)

Dismissed → Expired (job taken down)

Applied → Expired (job taken down — Application continues independently)
```

**Note:** Job Posting status is about the *job*, not the user's application outcome. Application status (REQ-004) tracks the user's journey.

---

## 7. Ghost Detection

### 7.1 Purpose

Identify job postings that may not represent genuine hiring intent, so user can make informed decisions.

### 7.2 Detection Signals

| Signal | Weight | Scoring |
|--------|--------|---------|
| Days open | 30% | 0-30 days = 0, 31-60 = 50, 60+ = 100 |
| Repost count | 30% | 0 = 0, 1 = 30, 2 = 60, 3+ = 100 |
| Description vagueness | 20% | NLP-based (missing specifics) |
| Missing critical fields | 10% | Salary, deadline, location |
| Requirement mismatch | 10% | Seniority vs. experience years |

### 7.3 Ghost Score Interpretation

| Score | Label | Agent Behavior |
|-------|-------|----------------|
| 0-25 | Fresh | No warning |
| 26-50 | Moderate | Light warning about age/history |
| 51-75 | Elevated | Clear warning, recommend verification |
| 76-100 | High Risk | Strong warning, suggest skipping |

### 7.4 Agent Communication

Agent explains reasoning:
> "Heads up — this role has been posted for 47 days and was reposted twice before. Ghost score: 65. I'd recommend reaching out to verify it's still active before applying."

### 7.5 Ghost Signals JSONB Structure

```json
{
  "days_open": 47,
  "days_open_score": 50,
  "repost_count": 2,
  "repost_score": 60,
  "vagueness_score": 30,
  "missing_fields": ["salary", "deadline"],
  "missing_fields_score": 50,
  "requirement_mismatch": false,
  "requirement_mismatch_score": 0,
  "calculated_at": "2025-01-25T12:00:00Z"
}
```

---

## 8. Repost Detection

### 8.1 Detection Criteria

| Check | Match Criteria | Confidence |
|-------|----------------|------------|
| Exact match | Same source + same external ID | High |
| Likely repost | Same company + same title + description similarity >85% | High |
| Possible repost | Same company + similar title + description similarity >70% | Medium |

**"Similar title" definition:**
- Normalize: lowercase, remove punctuation, trim whitespace
- Match if:
  - Levenshtein distance ≤ 3 characters, OR
  - One title contains the other (e.g., "Senior Scrum Master" contains "Scrum Master"), OR
  - Titles share ≥80% of words (ignoring order)
  
Examples:
| Title A | Title B | Similar? |
|---------|---------|----------|
| "Scrum Master" | "Scrum Master" | ✅ Exact |
| "Senior Scrum Master" | "Scrum Master" | ✅ Contains |
| "Scrum Master II" | "Scrum Master 2" | ✅ Levenshtein |
| "Scrum Master" | "Product Owner" | ❌ Different |
| "Agile Coach / Scrum Master" | "Scrum Master / Agile Coach" | ✅ 100% word overlap |

### 8.2 Repost Handling

When repost detected:

| Action | Purpose |
|--------|---------|
| Create new Job Posting record | Fresh opportunity for user |
| Status = Discovered | User can act on it |
| Link `previous_posting_ids` | Track lineage |
| Increment `repost_count` | Ghost detection |
| Recalculate `ghost_score` | Reflects pattern |

### 8.3 Agent Context

If user previously applied to an earlier version:
> "This role was posted before. You applied on January 15th and were rejected on February 1st. This appears to be a repost. Want me to evaluate it fresh?"

---

## 9. Deduplication

### 9.1 Within Same Source

If same `external_id` from same source:
- Update existing record (refresh data)
- Don't create duplicate

### 9.2 Across Sources (Primary + Also Found On)

Same job may appear on multiple sources (e.g., Adzuna + LinkedIn via Extension).

**Problem with separate records:** User applies to Adzuna version → LinkedIn version stays "Discovered" → User sees same job twice with different states. Confusing.

**Solution:** Primary record with `also_found_on` tracking.

| Field | Type | Notes |
|-------|------|-------|
| `also_found_on` | JSONB | List of other sources where this job was found |

**Detection:** When new job matches existing by `description_hash` or company + title + >85% similarity:
1. Don't create new record
2. Add source to `also_found_on` on existing record
3. Preserve best data (prefer source with more complete fields)

**JSONB Structure:**
```json
{
  "sources": [
    {
      "source_id": "uuid-of-linkedin",
      "external_id": "linkedin-job-123",
      "source_url": "https://linkedin.com/jobs/...",
      "found_at": "2025-01-25T12:00:00Z"
    }
  ]
}
```

**Agent communication:**
> "This Scrum Master role at Acme Corp was also found on LinkedIn and Indeed."

### 9.3 Deduplication Priority

When merging data from multiple sources:

| Field | Priority |
|-------|----------|
| `salary_min`, `salary_max` | Prefer source that has it |
| `apply_url` | Prefer company ATS URL over aggregator |
| `posted_date` | Prefer earliest date found |
| `description` | Prefer longest/most complete |

---

## 10. Matching (Summary)

Detailed matching algorithm in REQ-008. Summary here:

### 10.1 Fit Score (0-100)

How well user's current skills/experience match job requirements.

| Factor | Weight |
|--------|--------|
| Hard skills match | 40% |
| Soft skills match | 20% |
| Experience level | 20% |
| Location/logistics | 20% |

### 10.2 Stretch Score (0-100)

How well job aligns with user's growth goals.

| Factor | Weight |
|--------|--------|
| Target role alignment | 50% |
| Target skills exposure | 50% |

### 10.3 Display

Agent shows both scores:
> "Fit: 87% | Stretch: +15% toward your Kubernetes goal"

### 10.4 Non-Negotiables Filtering

Jobs are filtered against Persona Non-Negotiables (REQ-001 §3.6) before being shown to user.

| Non-Negotiable | Filter Behavior |
|----------------|-----------------|
| `minimum_base_salary` | Exclude if `salary_max < minimum_base_salary` (if salary disclosed) |
| `remote_preference = "Remote Only"` | Exclude if `work_model != Remote` |
| `remote_preference = "Hybrid OK"` | Exclude if `work_model = On-site` |
| `commutable_cities` | Exclude if `location` not in list AND `work_model != Remote` |
| `custom_non_negotiables` (Exclude type) | Exclude if `company_name` matches filter value |

**Jobs that fail non-negotiables:**
- Are NOT shown in default job list
- Stored in `failed_non_negotiables` JSONB field for transparency
- User can opt to "Show all jobs" to see filtered jobs with warnings
- Agent explains: "I filtered out 12 jobs that didn't meet your requirements (salary below minimum, on-site only, etc.)"

**`failed_non_negotiables` JSONB structure:**
```json
{
  "filters_failed": [
    {"filter": "minimum_base_salary", "job_value": 90000, "persona_value": 120000},
    {"filter": "remote_preference", "job_value": "On-site", "persona_value": "Remote Only"}
  ]
}
```

### 10.5 Minimum Fit Threshold

User can configure minimum Fit Score to see a job (stored in Persona preferences).

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `minimum_fit_threshold` | Integer | 50 | Jobs below this score not shown by default |

- Jobs below threshold are discovered and stored but not surfaced
- User can adjust threshold or opt to "Show all matches"
- Agent explains: "I found 23 jobs, showing 15 above your 60% fit threshold"

---

## 11. Favorite Flag

| Field | Type | Notes |
|-------|------|-------|
| `is_favorite` | Boolean | User can toggle on any job |

- Independent of status
- User can favorite Discovered, Dismissed, Applied, or Expired jobs
- UI can filter "Show favorites"
- Does not affect workflow or retention

---

## 12. Retention Policy

| Status | Archive Trigger | Delete Trigger |
|--------|-----------------|----------------|
| Discovered | 60 days with no action | 180 days after archive |
| Dismissed | Immediate archive | 180 days after archive |
| Applied | Follows Application lifecycle | Follows Application |
| Expired | 60 days after expired | 180 days after archive |

### 12.1 Favorites Override

**Favorited jobs are excluded from auto-archive regardless of status.**

| Scenario | Behavior |
|----------|----------|
| Discovered + Favorited | No auto-archive until unfavorited |
| Dismissed + Favorited | No auto-archive until unfavorited |
| Expired + Favorited | No auto-archive until unfavorited |

User must unfavorite a job before it will enter the normal retention lifecycle.

**Rationale:** User explicitly marked this job as important. Respect that intent.

### 12.2 Expiration Detection

How the system detects when a job is no longer available:

| Method | Trigger | Reliability |
|--------|---------|-------------|
| **API re-query** | Periodic check for Applied jobs | High — if API supports lookup by ID |
| **Source URL check** | HTTP request returns 404/gone | Medium — URLs can change |
| **User report** | User marks as expired | High — manual but reliable |
| **Deadline passed** | `application_deadline` < today | High — if deadline was specified |

**Implementation:**
- Agent periodically re-verifies Applied jobs (daily for first 2 weeks, weekly after)
- `last_verified_at` timestamp tracks last successful verification
- If job not found, status → Expired, agent notifies user
- User can always manually mark as Expired

**Agent communication:**
> "Heads up — the Scrum Master role at Acme Corp appears to have been taken down. I've marked it as expired."

---

## 13. Workflow Integration

### 13.1 Discovery Flow

```
Polling trigger (scheduled or manual)
    │
    ├── Agent queries enabled sources
    │
    ├── For each job found:
    │       │
    │       ├── Check deduplication
    │       │       │
    │       │       ├── Exact match → Update existing
    │       │       ├── Repost detected → Create new, link previous
    │       │       └── New job → Create record
    │       │
    │       ├── Extract skills from description
    │       │
    │       ├── Calculate Fit Score + Stretch Score
    │       │
    │       ├── Calculate Ghost Score
    │       │
    │       └── Status = Discovered
    │
    └── Agent presents matches to user
            │
            └── Sorted by Fit Score (configurable)
```

### 13.2 User Review Flow

```
User reviews Discovered jobs
    │
    ├── Dismiss → Status = Dismissed, dismissed_at = now
    │
    ├── Favorite → is_favorite = true (no status change)
    │
    ├── Apply → 
    │       │
    │       ├── Status = Applied
    │       ├── Application record created (REQ-004)
    │       ├── Cover Letter drafted (REQ-002b)
    │       └── Resume selected/tailored (REQ-002)
    │
    └── Ignore → Stays Discovered (auto-archives after 60 days)
```

---

## 14. Agent Behavior

### 14.1 Source Selection

Agent selects sources based on Persona profile and explains:
> "Based on your preference for remote work, I'm prioritizing RemoteOK and filtering Adzuna for remote positions."

### 14.2 Match Presentation

Agent presents top matches:
> "I found 7 new matches today. Top 3:
> 1. Senior Scrum Master at Acme Corp — Fit: 92%, remote, $140-160k
> 2. Agile Coach at TechCo — Fit: 88%, Stretch: +12% toward your SAFe goal
> 3. Product Owner at StartupX — Fit: 85%, but ghost score is elevated (58)"

### 14.3 Ghost Warnings

Agent proactively warns:
> "Quick note: 2 of today's matches have been open for over 45 days. I've flagged them in case you want to verify they're still active."

---

## 15. Validation Rules

| Rule | Description |
|------|-------------|
| Required fields | job_title, company_name, description, source_id |
| Valid source reference | source_id must reference valid Source Registry entry |
| Status transitions | Only valid transitions allowed (see §6.1) |
| Repost linking | previous_posting_ids must reference valid Job Posting IDs |
| Score ranges | fit_score, stretch_score, ghost_score must be 0-100 |

---

## 16. Privacy & Security Notes

### 16.1 PII Fields

Job Postings contain no user PII. Company/job data is public.

### 16.2 Data Residency

- All data stored locally in PostgreSQL for MVP
- Job descriptions may be sent to LLM for skill extraction
- No job data shared externally

---

## 17. Open Questions

| # | Question | Status |
|---|----------|--------|
| 1 | Rate limits for each API? | TBD — need to verify free tier limits |
| 2 | Description similarity algorithm? | TBD — cosine similarity on embeddings vs. text hash |
| 3 | NLP model for vagueness detection? | TBD — may use LLM or simpler heuristics |
| 4 | Chrome extension technical approach? | TBD — defer to implementation |

---

## 18. Design Decisions & Rationale

This section preserves context for implementation. Future developers (including AI agents) should understand not just WHAT but WHY.

### 18.1 Job Source Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| MVP sources | Scraping LinkedIn / Official APIs only / Aggregator APIs / Chrome Extension | Aggregator APIs + Chrome Extension | Scraping violates TOS and risks bans. Official APIs are expensive/limited. Aggregators (Adzuna, The Muse, RemoteOK, USAJobs) are free, TOS-compliant, and provide good coverage. Chrome extension captures what user browses without automation. |
| EU job sources | Include Arbeitnow, Jobicy | Defer to post-MVP | Only ~10-20% of EU jobs sponsor visas, and most don't disclose sponsorship. Complexity outweighs benefit for MVP. RemoteOK captures some EU remote jobs. |
| Source registry scope | Per-user sources / Global sources / Hybrid | Global registry + per-user preferences | Sources themselves are system-level (API endpoints, descriptions). User preferences (enabled/disabled, order) are per-Persona. Clean separation. |

### 18.2 Ghost Detection Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Ghost detection approach | Binary flag / Scored system / No detection | Weighted scoring (0-100) | Research shows 18-30% of jobs are ghosts. Binary is too coarse. Scoring lets users make informed decisions rather than hard filtering. |
| Scoring weights | Equal weights / Research-based weights | Days open (30%) + Repost count (30%) + Vagueness (20%) + Missing fields (10%) + Requirement mismatch (10%) | Research most frequently cited "continuously open" and "repeatedly posted" as top indicators. Weighted accordingly. |
| User experience | Hard filter ghost jobs / Soft warnings / Hidden scoring | Soft warnings with visible score | Users should decide. Agent warns but doesn't block. Transparency builds trust. |

### 18.3 Repost Handling Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Repost treatment | Same record updated / New record linked / New record unlinked | New record + linked via `previous_posting_ids` | User deserves fresh opportunity (they may want to reapply). But system needs to track pattern for ghost detection and provide context about prior application. |

### 18.4 Cross-Source Deduplication Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Same job on multiple sources | Separate records / Merge into one / Primary + references | Primary record + `also_found_on` | Separate records causes confusion (same job, different states). Full merge loses source context. Primary + references preserves both user clarity and data richness. |

### 18.5 Non-Negotiables Filtering Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Filter behavior | Hard filter (hide) / Soft filter (show with warning) / No filter | Hard filter by default, opt-in to see all | Non-negotiables are defined by user as hard requirements. Showing jobs that violate them wastes user time. But user can override to see everything if they want flexibility. |

### 18.6 Status Lifecycle Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| "Saved" status | Include Saved status / Use favorite flag | Favorite flag (not status) | Status represents workflow state. "Saved" is user preference orthogonal to workflow. User can favorite any status. Cleaner model. |
| Job vs Application status | Combined lifecycle / Separate lifecycles | Separate — Job Posting status is about the job, Application status is about user's pursuit | Job can expire while Application is still active (interviewing). Keeps concerns separate. Application doesn't "close" when job expires — user might still get hired from their existing application. |

---

## 19. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2025-01-25 | 0.1 | Initial draft from discovery interview |
| 2025-01-25 | 0.2 | Added: Problem context (§1.1), Source Registry split into global + user prefs (§4.2b), Cross-source dedup with `also_found_on` (§9.2), Non-Negotiables filtering (§10.4), Minimum fit threshold (§10.5), Expiration detection (§12.2), `seniority_level` and `years_experience` fields, "similar title" definition (§8.1), Decision Log (§18). Fixed: Retention conflict with favorites (§12.1). |
