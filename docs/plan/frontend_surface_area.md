# Zentropy Scout — Frontend Surface Area Audit

**Created:** 2026-02-08
**Source:** Phase 0 audit of REQ-001 through REQ-010 (excluding REQ-005, REQ-009, REQ-011)

This document captures every API endpoint, SSE event, HITL checkpoint, user decision, and display requirement the frontend must support. Organized by UI area, not by source REQ.

---

## Table of Contents

1. [Chat Interface](#1-chat-interface)
2. [Onboarding Flow](#2-onboarding-flow)
3. [Persona Management](#3-persona-management)
4. [Job Dashboard & Scoring](#4-job-dashboard--scoring)
5. [Resume Management](#5-resume-management)
6. [Cover Letter Management](#6-cover-letter-management)
7. [Application Tracking](#7-application-tracking)
8. [Settings & Configuration](#8-settings--configuration)
9. [Shared Patterns & API Conventions](#9-shared-patterns--api-conventions)
10. [Backend Prerequisites (Gaps)](#10-backend-prerequisites-gaps)

---

## 1. Chat Interface

**Sources:** REQ-006 §2.4-2.5, REQ-007 §4, §9.3, §15.1

### 1.1 Architecture

- User input: `POST /api/v1/chat/messages` (REST, rate-limited 10/min)
- Agent responses: `GET /api/v1/chat/stream` (SSE, single persistent connection)
- SSE carries both chat streaming and data-change events on one connection

### 1.2 SSE Event Types

| Event | Payload | Frontend Action |
|-------|---------|-----------------|
| `chat_token` | `{ "text": "..." }` | Append text to current message bubble |
| `chat_done` | `{ "message_id": "..." }` | Mark message complete, re-enable user input |
| `tool_start` | `{ "tool": "favorite_job", "args": {...} }` | Show inline "working..." indicator |
| `tool_result` | `{ "tool": "favorite_job", "success": true }` | Show result, clear indicator |
| `data_changed` | `{ "resource": "job-posting", "id": "...", "action": "updated" }` | Refresh specific resource in UI |

### 1.3 Reconnection Protocol

| Trigger | Behavior |
|---------|----------|
| Page load | Fetch current state via REST, then establish SSE |
| Manual refresh | Re-fetch via REST |
| `data_changed` event | Update specific resource (no full refresh) |
| Tab inactive > 5 min | Reconnect SSE + full REST refresh on return |
| SSE disconnect | Graceful fallback to manual refresh |

### 1.4 Message Rendering Formats

| Context | Format |
|---------|--------|
| Single job details | Structured card (title, company, score, etc.) |
| Job list | Compact list (score, company, title) |
| Status update | Brief confirmation + next steps suggestion |
| Error | Explanation + suggested corrective action |
| Complex analysis | Prose with key points highlighted |

### 1.5 Ambiguity Resolution (REQ-007 §4.4)

Three prompt types the UI must render:

| Type | Example | UI Element |
|------|---------|------------|
| Numbered options | "Which job? 1. Scrum Master at Acme 2. PM at TechCo" | Clickable/selectable list items |
| Open-ended question | "When is the interview scheduled?" | Standard text input |
| Destructive confirmation | "This will dismiss 15 jobs. Proceed?" | Confirmation prompt (yes/no) |

Intent confidence threshold: <70% → agent asks for clarification before acting.

### 1.6 Tool Execution Visualization (REQ-007 §9.3)

Tools execute inline within the chat stream. The UI shows:
- Spinner + action label on `tool_start` (e.g., "Favoriting job...")
- Success/failure badge on `tool_result`
- These interleave with `chat_token` events

### 1.7 Design Decision

Verbose progress by default — "users want to see agents working; builds trust" (REQ-007 §13.2). Don't hide or minimize agent activity.

---

## 2. Onboarding Flow

**Sources:** REQ-001 §6, REQ-007 §5, §15.2

### 2.1 Entry Gate

| User State | Behavior |
|------------|----------|
| New user (no persona) | Auto-start onboarding |
| `onboarding_complete = false` | Resume from `onboarding_step` |
| Onboarded | Show dashboard with full functionality |

### 2.2 Step-by-Step Flow (12 steps)

| Step | Name | Optional? | UI Mode | Key Details |
|------|------|-----------|---------|-------------|
| 1 | `resume_upload` | Yes | File upload | PDF/DOCX drag-and-drop; `POST /resume-files`; extraction pre-populates steps 3-5 |
| 2 | `basic_info` | No | Form | name, email, phone, location, LinkedIn, portfolio |
| 3 | `work_history` | No (min 1 job) | Confirm/edit | Confirm extracted jobs if resume uploaded; min 1 bullet per job |
| 4 | `education` | Yes | Confirm/edit | Skippable |
| 5 | `skills` | No | Rate proficiency | Each skill: Learning / Familiar / Proficient / Expert; dynamic category by type |
| 6 | `certifications` | Yes | Form | Skippable |
| 7 | `achievement_stories` | No | Conversational | 3-5 stories, Context/Action/Outcome structure; agent probes for metrics |
| 8 | `non_negotiables` | No | Form | Remote pref, salary, location, exclusions, custom filters |
| 9 | `growth_targets` | No | Form | Target roles, target skills, stretch appetite (Low/Medium/High) |
| 10 | `voice_profile` | No | Review/edit | Agent-derived from conversation, user reviews and edits traits |
| 11 | `review` | No | Summary | Full persona review, can go back and edit any section |
| 12 | `base_resume_setup` | No | Wizard | "What role are you targeting?" → select items → generate anchor PDF |

### 2.3 Checkpoint/Resume (REQ-007 §5.4)

| Scenario | Behavior |
|----------|----------|
| User exits mid-flow | State saved at current `onboarding_step` |
| User returns | "Welcome back! We were working on [step]. Ready to continue?" |
| Checkpoint TTL | 24 hours in Redis; expired → "Let's start fresh" |
| User wants restart | "Start fresh or continue where we left off?" |

### 2.4 Post-Onboarding Updates (REQ-007 §5.5)

Users can update persona anytime via:
1. Direct editing in the UI
2. Conversation with the agent ("I got a new certification")
3. Re-running specific onboarding steps

When persona updates: embeddings regenerate → all Discovered jobs rescored.

### 2.5 Completion

- Sets `onboarding_complete = true` on persona
- Transitions from onboarding UI to standard chat + dashboard

---

## 3. Persona Management

**Sources:** REQ-001, REQ-006 §5.2-5.4

### 3.1 Sections and Editable Fields

#### 3.1.1 Basic Info (REQ-001 §3.1)

| Field | Type | Required | PII | Constraints |
|-------|------|----------|-----|-------------|
| `full_name` | VARCHAR(255) | Yes | Yes | |
| `email` | VARCHAR(255) | Yes | Yes | UNIQUE |
| `phone` | VARCHAR(50) | Yes | Yes | |
| `linkedin_url` | VARCHAR(500) | No | Yes | URL validation |
| `portfolio_url` | VARCHAR(500) | No | No | URL validation |
| `home_city` | VARCHAR(100) | Yes | Yes | |
| `home_state` | VARCHAR(100) | Yes | Yes | |
| `home_country` | VARCHAR(100) | Yes | No | |

#### 3.1.2 Professional Overview (REQ-001 §3.1b)

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `professional_summary` | TEXT | No | 2-4 sentences recommended |
| `years_experience` | INTEGER | No | Self-reported |
| `current_role` | VARCHAR(255) | No | |
| `current_company` | VARCHAR(255) | No | |

#### 3.1.3 Work History (REQ-001 §3.2) — Collection, ordered by `display_order`

**Job Entry:**

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `job_title` | VARCHAR(255) | Yes | |
| `company_name` | VARCHAR(255) | Yes | |
| `company_industry` | VARCHAR(100) | No | Agent may auto-populate |
| `location` | VARCHAR(255) | Yes | "City, State/Country" |
| `work_model` | Enum | Yes | Remote / Hybrid / Onsite |
| `start_date` | DATE | Yes | Month/Year |
| `end_date` | DATE | Conditional | NULL if `is_current = true` |
| `is_current` | BOOLEAN | Yes | Default: false |
| `description` | TEXT | No | High-level role summary |
| `display_order` | INTEGER | Yes | For reordering |

**Accomplishment Bullet** (nested, min 1 per job):

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `text` | TEXT | Yes | The accomplishment statement |
| `skills_demonstrated` | JSONB (UUID list) | No | Links to Skills |
| `metrics` | VARCHAR(255) | No | Quantified results |
| `display_order` | INTEGER | Yes | Order within job |

#### 3.1.4 Education (REQ-001 §3.3) — Collection, optional

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `degree` | VARCHAR(100) | Yes (if adding) | |
| `field_of_study` | VARCHAR(255) | Yes (if adding) | |
| `institution` | VARCHAR(255) | Yes (if adding) | |
| `graduation_year` | INTEGER | Yes (if adding) | |
| `gpa` | DECIMAL(3,2) | No | Range 0.00-4.00 |
| `honors` | VARCHAR(255) | No | |
| `display_order` | INTEGER | Yes | |

#### 3.1.5 Skills (REQ-001 §3.4) — Collection

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `skill_name` | VARCHAR(100) | Yes | UNIQUE per persona |
| `skill_type` | Enum | Yes | Hard / Soft |
| `category` | VARCHAR(100) | Yes | Predefined defaults + custom |
| `proficiency` | Enum | Yes | Learning / Familiar / Proficient / Expert |
| `years_used` | INTEGER | Yes | |
| `last_used` | VARCHAR(20) | Yes | "Current" or year string |
| `display_order` | INTEGER | Yes | |

All 6 content fields required — no partial entries.

**Hard Skill categories:** Programming Language, Framework / Library, Tool / Software, Platform / Infrastructure, Methodology, Domain Knowledge, (Custom).

**Soft Skill categories:** Leadership & Management, Communication, Collaboration, Problem Solving, Adaptability, (Custom).

**Proficiency scale (for tooltips):**

| Level | Label | Definition |
|-------|-------|------------|
| 1 | Learning | Currently studying, no professional use yet |
| 2 | Familiar | Have used professionally, would need ramp-up |
| 3 | Proficient | Can work independently, solid experience |
| 4 | Expert | Deep expertise, could teach others |

#### 3.1.6 Certifications (REQ-001 §3.5) — Collection, optional

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `certification_name` | VARCHAR(255) | Yes (if adding) | |
| `issuing_organization` | VARCHAR(255) | Yes (if adding) | |
| `date_obtained` | DATE | Yes (if adding) | |
| `expiration_date` | DATE | No | NULL = "No Expiration" |
| `credential_id` | VARCHAR(100) | No | |
| `verification_url` | VARCHAR(500) | No | URL validation |
| `display_order` | INTEGER | Yes | |

#### 3.1.7 Achievement Stories (REQ-001 §3.6) — Collection

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `title` | VARCHAR(255) | Yes | Short identifier |
| `context` | TEXT | Yes | 1-2 sentences: situation |
| `action` | TEXT | Yes | What did you do? |
| `outcome` | TEXT | Yes | Result, quantified if possible |
| `skills_demonstrated` | JSONB (UUID list) | No | Links to Skills |
| `related_job_id` | UUID | No | Links to WorkHistory; FK ON DELETE SET NULL |
| `display_order` | INTEGER | Yes | |

Agent encourages 3-5 minimum during onboarding.

#### 3.1.8 Voice Profile (REQ-001 §3.7) — Singleton (1:1 with Persona)

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `tone` | TEXT | Yes | e.g., "Direct, confident, avoids buzzwords" |
| `sentence_style` | TEXT | Yes | e.g., "Short sentences, active voice" |
| `vocabulary_level` | TEXT | Yes | e.g., "Technical when relevant, otherwise plain English" |
| `personality_markers` | TEXT | No | |
| `sample_phrases` | JSONB (string list) | No | Tag-style input |
| `things_to_avoid` | JSONB (string list) | No | Blacklist — drives cover letter validation |
| `writing_sample_text` | TEXT | No | Raw text for voice derivation |

Agent-derived then user-reviewed. Not a blank form — presented for approval/editing.

#### 3.1.9 Non-Negotiables (REQ-001 §3.8)

**Location (§3.8.1):**

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `commutable_cities` | JSONB (string list) | Conditional | Required unless Remote Only |
| `max_commute_minutes` | INTEGER | No | |
| `remote_preference` | Enum | Yes | Remote Only / Hybrid OK / Onsite OK / No Preference |
| `relocation_open` | BOOLEAN | Yes | Default: false |
| `relocation_cities` | JSONB (string list) | No | Only relevant if `relocation_open = true` |

**Compensation (§3.8.2):**

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `minimum_base_salary` | INTEGER | No | Annual, PII |
| `salary_currency` | VARCHAR(10) | No | Default: "USD" |

**Other Filters (§3.8.3):**

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `visa_sponsorship_required` | BOOLEAN | Yes | Default: false |
| `industry_exclusions` | JSONB (string list) | No | Tag-style input |
| `company_size_preference` | Enum | No | Startup / Mid-size / Enterprise / No Preference |
| `max_travel_percent` | Enum | No | None / <25% / <50% / Any |

**Custom Non-Negotiables (§3.8.4) — CRUD Collection:**

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `filter_name` | VARCHAR(255) | Yes | Human-readable label |
| `filter_type` | Enum | Yes | Exclude / Require |
| `filter_value` | TEXT | Yes | Free text, can be comma-separated |
| `filter_field` | VARCHAR(100) | Yes | Job field to check (suggest: company_name, description, job_title) |

API: `CRUD /api/v1/personas/{id}/custom-non-negotiables`

#### 3.1.10 Growth Targets (REQ-001 §3.9)

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `target_roles` | JSONB (string list) | No | Tag-style input |
| `target_skills` | JSONB (string list) | No | Tag-style input |
| `stretch_appetite` | Enum | Yes | Low / Medium / High. Default: Medium |

`stretch_appetite` affects how the Scoring Engine weighs growth opportunities.

#### 3.1.11 Discovery Preferences (REQ-001 §3.10)

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `minimum_fit_threshold` | INTEGER | Yes | 50 | 0-100. Jobs below hidden by default |
| `polling_frequency` | Enum | Yes | Daily | Daily / Twice Daily / Weekly / Manual Only |
| `auto_draft_threshold` | INTEGER | Yes | 90 | 0-100. Triggers Ghostwriter auto-drafting |

`auto_draft_threshold` should logically be >= `minimum_fit_threshold`. UI should warn if inverted.

### 3.2 Persona API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET/POST | `/api/v1/personas` | List/create |
| GET/PUT/PATCH/DELETE | `/api/v1/personas/{id}` | Single persona CRUD |
| CRUD | `/api/v1/personas/{id}/work-history` | Work history entries |
| CRUD | `/api/v1/personas/{id}/skills` | Skills |
| CRUD | `/api/v1/personas/{id}/education` | Education records |
| CRUD | `/api/v1/personas/{id}/certifications` | Certifications |
| CRUD | `/api/v1/personas/{id}/achievement-stories` | Stories |
| GET/PUT/PATCH | `/api/v1/personas/{id}/voice-profile` | Voice profile (1:1, no create/delete) |
| CRUD | `/api/v1/personas/{id}/custom-non-negotiables` | Custom filters |
| POST | `/api/v1/personas/{id}/embeddings/regenerate` | Trigger embedding regeneration |

### 3.3 Conditional Field Logic

| Condition | Effect |
|-----------|--------|
| `is_current = true` | Disable/hide `end_date` |
| `relocation_open = false` | Hide `relocation_cities` |
| `remote_preference = "Remote Only"` | Hide `commutable_cities` / `max_commute_minutes` |
| Certification `expiration_date = null` | Show "No Expiration" toggle |
| `skill_type = Hard` | Show Hard Skill category options |
| `skill_type = Soft` | Show Soft Skill category options |

### 3.4 Deletion Handling (REQ-001 §7b)

The most complex interaction in persona management:

**Reference check before every delete of:** Job, Bullet, Skill, Education, Certification, Achievement Story.

**Where references are checked:**
- Jobs: `BaseResume.included_jobs`
- Bullets: `BaseResume.job_bullet_selections`, `BaseResume.job_bullet_order`
- Skills: `BaseResume.skills_emphasis`
- Education: `BaseResume.included_education`
- Certifications: `BaseResume.included_certifications`
- Achievement Stories: `CoverLetter.achievement_stories_used` (draft only)

**Three-option dialog when references exist:**
1. "Remove from all and delete" — cascade remove references, then delete
2. "Cancel" — no action
3. "Review each" — show list of affected Base Resumes/Cover Letters, user decides per item

**Immutable entity block:** If referenced by Approved Job Variant or Approved Cover Letter, deletion is blocked. Show: "This item is part of an application you submitted to [Company]. You can archive that application first."

**No-reference case:** Delete immediately without dialog.

### 3.5 PersonaChangeFlags (REQ-006 §5.4)

When new items are added to the Persona post-onboarding, flags are created for Base Resume review.

**API:**
- `GET /api/v1/persona-change-flags?status=Pending` — list pending flags
- `PATCH /api/v1/persona-change-flags/{id}` — resolve a flag

**Flag shape:**
```json
{
  "id": "uuid",
  "change_type": "Skill",
  "change_id": "skill-uuid",
  "change_summary": "Added skill: Kubernetes",
  "suggested_action": "Add to all Base Resumes",
  "status": "Pending",
  "created_at": "2026-01-25T10:00:00Z"
}
```

**Resolution options:** `added_to_all`, `added_to_some`, `skipped`

**UI:** Notification badge with pending count; per-flag resolution interface.

### 3.6 Reordering

Six collections support `display_order` with drag-and-drop or up/down controls:
- Work history jobs
- Bullets within each job
- Education entries
- Skills (within type)
- Certifications
- Achievement stories

### 3.7 Embedding Staleness Indicator

Embeddings regenerate automatically when source fields change (via `source_hash`). Three types: `hard_skills`, `soft_skills`, `logistics`. Frontend may need a "re-indexing" or "updating match profile" status indicator after persona edits.

---

## 4. Job Dashboard & Scoring

**Sources:** REQ-003, REQ-006 §5.5, REQ-007 §6-7, REQ-008

### 4.1 Job Posting Display Fields

| Field | Type | Display Notes |
|-------|------|---------------|
| `job_title` | String | Required, primary heading |
| `company_name` | String | Required, with optional link to `company_url` |
| `company_url` | String (opt) | Clickable link |
| `location` | String (opt) | City/state/country |
| `work_model` | Enum | Remote / Hybrid / Onsite badge |
| `seniority_level` | Enum | Entry / Mid / Senior / Lead / Executive badge |
| `salary_min` / `salary_max` | Integer (opt) | Display as range "$140k-$160k" |
| `salary_currency` | String (opt) | USD, EUR, etc. |
| `description` | String | Full job description (long text) |
| `requirements` | String (opt) | Skills/experience section |
| `culture_text` | String (opt) | Extracted culture/values text |
| `years_experience_min` / `max` | Integer (opt) | Display as range |
| `posted_date` | Date (opt) | "Posted X days ago" |
| `application_deadline` | Date (opt) | Prominent if present; drives expiration warnings |
| `source_url` | String (opt) | "View original" link |
| `apply_url` | String (opt) | "Apply now" button |
| `fit_score` | Integer 0-100 (nullable) | Primary score indicator |
| `stretch_score` | Integer 0-100 (nullable) | Secondary score indicator |
| `ghost_score` | Integer 0-100 | Warning indicator |
| `is_favorite` | Boolean | Heart/star toggle |
| `status` | Enum | Discovered / Dismissed / Applied / Expired |
| `first_seen_date` | Date | "Discovered X days ago" |

### 4.2 Score Presentation (REQ-008 §7)

Fit and Stretch are **independent dimensions** — no combined recommendation label (§7.3 cancelled).

**Fit Score tiers:**

| Range | Label |
|-------|-------|
| 90-100 | High |
| 75-89 | Medium |
| 60-74 | Low |
| 0-59 | Poor |

**Stretch Score tiers:**

| Range | Label |
|-------|-------|
| 80-100 | High Growth |
| 60-79 | Moderate Growth |
| 40-59 | Lateral |
| 0-39 | Low Growth |

**Null scores:** When non-negotiables failed, both are `null`. Display "Not scored" or "Failed non-negotiables" — not 0.

### 4.3 Score Component Drill-Down (REQ-008 §4.7, §5.5)

**Fit Score — 5 components:**

| Component | Weight | Measures |
|-----------|--------|----------|
| `hard_skills` | 40% | Technical skills (proficiency-weighted) |
| `soft_skills` | 15% | Interpersonal skills (embedding similarity) |
| `experience_level` | 25% | Years match |
| `role_title` | 10% | Title similarity |
| `location_logistics` | 10% | Work model alignment |

**Stretch Score — 3 components:**

| Component | Weight | Measures |
|-----------|--------|----------|
| `target_role` | 50% | Title match to target roles |
| `target_skills` | 40% | Target skills in job requirements |
| `growth_trajectory` | 10% | Step up / lateral / step down |

Each component returns a 0-100 sub-score. Weights are **read-only** in MVP (user customization deferred to v2).

### 4.4 Score Explanation (REQ-008 §8)

`ScoreExplanation` structure:

| Field | Content | Display Style |
|-------|---------|---------------|
| `summary` | 2-3 sentence overview | Prominent at top of detail |
| `strengths` | Matched skills, experience fit | Green check list |
| `gaps` | Missing skills, experience shortfall | Amber/red list |
| `stretch_opportunities` | Target skill/role matches | Blue/purple list |
| `warnings` | Salary undisclosed, ghost risk, overqualification | Alert callouts |

### 4.5 Non-Negotiables Filter (REQ-003 §10.4, REQ-008 §3)

Jobs failing non-negotiables are hidden by default.

**"Show filtered jobs" toggle:** Reveals filtered jobs with per-filter failure explanations.

**`failed_non_negotiables` array:**
```json
{
  "filters_failed": [
    {"filter": "minimum_base_salary", "job_value": 90000, "persona_value": 120000},
    {"filter": "remote_preference", "job_value": "Onsite", "persona_value": "Remote Only"}
  ]
}
```

**Undisclosed data warnings** (not failures):
- Salary not disclosed → passes filter with benefit of doubt + warning
- Work model unknown → assumed Onsite (conservative) + warning
- Visa sponsorship unknown → passes + warning

### 4.6 Minimum Fit Threshold (REQ-003 §10.5)

`minimum_fit_threshold` (default 50) on Persona. Jobs below hidden but tracked.

- "Show all matches" toggle overrides threshold
- Agent explains: "Found 23 jobs, showing 15 above your 60% fit threshold"

### 4.7 Ghost Detection (REQ-003 §7)

| Score Range | Label | Indicator |
|-------------|-------|-----------|
| 0-25 | Fresh | No warning |
| 26-50 | Moderate | Light warning (amber) |
| 51-75 | Elevated | Clear warning (orange) |
| 76-100 | High Risk | Strong warning (red) |

**Ghost signals** (`ghost_signals` JSONB):

| Signal | Display |
|--------|---------|
| `days_open` | "Open for X days" |
| `repost_count` | "Reposted X times" |
| `vagueness_score` | "Description lacks specifics" |
| `missing_fields` | "Missing: salary, deadline" |
| `requirement_mismatch` | "Seniority vs. experience mismatch" |

Design decision: agent warns but doesn't block. Transparency builds trust.

### 4.8 Cross-Source Display (REQ-003 §9.2)

`also_found_on` JSONB field:
```json
{
  "sources": [
    {"source_id": "uuid", "external_id": "...", "source_url": "https://...", "found_at": "..."}
  ]
}
```

Display: "Also found on: LinkedIn, Indeed" with clickable links. One record per job across sources (system merges best data per field).

### 4.9 Repost History (REQ-003 §8)

| Element | Display |
|---------|---------|
| `repost_count > 0` | "Reposted X times" badge |
| `previous_posting_ids` | Link to prior postings |
| Prior application | "You applied on [date] and were [status]" |

Detection confidence: Exact (same source+ID), Likely (>85% similarity), Possible (>70% similarity).

### 4.10 Status Transitions (REQ-003 §6)

| From | To | Trigger |
|------|----|---------|
| Discovered | Dismissed | User action |
| Discovered | Applied | Application created |
| Discovered | Expired | System or user |
| Dismissed | Expired | System |
| Applied | Expired | System (job taken down; Application continues independently) |

**Favorite toggle:** Independent of status — works in any status.

### 4.11 Expiration Notifications (REQ-003 §12.2)

- Show `last_verified_at` timestamp
- "Mark as Expired" button for manual reports
- Agent notifies when jobs auto-expire
- Favorited jobs excluded from auto-archive
- Retention: Discovered/Expired → 60 days → archive → 180 days → delete

### 4.12 Filtering & Sorting (REQ-006 §5.5)

| Parameter | Example |
|-----------|---------|
| Sort | `?sort=-fit_score,title` |
| Status filter | `?status=Discovered` |
| Favorite filter | `?is_favorite=true` |
| Score filter | `?fit_score_min=70` |
| Company filter | `?company_name=Acme` |

### 4.13 Bulk Operations (REQ-006 §2.6)

| Endpoint | Payload |
|----------|---------|
| `POST /job-postings/bulk-dismiss` | `{ "ids": ["uuid1", ...] }` |
| `POST /job-postings/bulk-favorite` | `{ "ids": [...], "is_favorite": true }` |

Response: `{ "data": { "succeeded": [...], "failed": [...] } }`

### 4.14 Manual Job Ingest — Two-Step Flow (REQ-006 §5.6)

**Step 1:** `POST /job-postings/ingest`
```json
{ "raw_text": "...", "source_url": "https://...", "source_name": "LinkedIn" }
```
Returns preview with `confirmation_token` (15min expiry).

**Step 2:** `POST /job-postings/ingest/confirm`
```json
{ "confirmation_token": "...", "modifications": { "job_title": "Sr. Engineer" } }
```
Returns full JobPosting. Strategist scoring queued automatically.

**Errors:** 422 EXTRACTION_FAILED, 409 DUPLICATE_JOB (includes `existing_id`), 410 TOKEN_EXPIRED. Rate limit: 10/min.

### 4.15 Extracted Skills Display (REQ-003 §5.3)

Read-only, populated by Scouter. API: `GET /job-postings/{id}/extracted-skills`

| Field | Display |
|-------|---------|
| `skill_name` | Skill tag/chip |
| `skill_type` | Hard / Soft (color-coded or grouped) |
| `is_required` | "Required" vs "Nice to have" badge |
| `years_requested` | "5+ years" if present |

### 4.16 Scouter Progress (REQ-007 §6, §9.1)

- Manual "Refresh Jobs" button → `POST /api/v1/refresh`
- Chat command: "Find new jobs"
- Progress messages in chat: "Searching Adzuna... Found 12 new jobs. Scoring..."
- Error handling: source failures reported, other sources continue

### 4.17 Score Refresh (REQ-007 §7.1)

Triggers: persona skill change, non-negotiable change, work history change, manual `POST /job-postings/rescore`.

UI should show "Rescoring..." indicator during recalculation.

### 4.18 Auto-Draft Trigger (REQ-007 §15.4)

When `fit_score >= persona.auto_draft_threshold` (default 90), Ghostwriter auto-triggers. Notification: "This job scored 92% fit — I'm automatically drafting materials for you."

---

## 5. Resume Management

**Sources:** REQ-002, REQ-006 §2.7/§5.2, REQ-007 §8, REQ-010 §4/§9

### 5.1 Entity Types

| Entity | Purpose | Status Values |
|--------|---------|---------------|
| Resume File | Original uploaded PDF/DOCX | `is_active` boolean |
| Base Resume | Master resume per role type | Active / Archived |
| Job Variant | Tailored for specific job | Draft / Approved / Archived |
| Submitted PDF | Immutable snapshot | (no status — immutable) |

### 5.2 Base Resume Creation Wizard (REQ-002 §4.2)

User selects from Persona data:

| Selection | Field | Required | Notes |
|-----------|-------|----------|-------|
| Name/role label | `name` | Yes | Unique per Persona |
| Target role category | `role_type` | Yes | |
| Summary | `summary` | Yes | Role-specific text |
| Jobs to include | `included_jobs` | Yes | List of Job IDs |
| Bullets per job | `job_bullet_selections` | Yes | JSONB: `{job_id: [bullet_ids]}` |
| Bullet ordering | `job_bullet_order` | Yes | JSONB: `{job_id: [ordered_bullet_ids]}` |
| Education | `included_education` | No | `null` = show all |
| Certifications | `included_certifications` | No | `null` = show all |
| Skills to highlight | `skills_emphasis` | No | List of Skill IDs |
| Primary flag | `is_primary` | Yes | Exactly one `true` per Persona |
| Display ordering | `display_order` | Yes | |

### 5.3 Render/Approve Cycle (REQ-002 §4.2)

1. User creates Base Resume with content selections
2. System renders PDF → stores in `rendered_document` (BYTEA)
3. User reviews anchor document
4. User approves (explicit action)
5. On content selection changes → re-render needed → re-approval required

Frontend must track whether selections changed since last render.

### 5.4 Job Variant Workflow (REQ-002 §4.3, REQ-007 §8)

**Creation:** Agent creates variant in Draft status after evaluating job fit.

**What variants can modify:**

| Allowed | NOT Allowed |
|---------|-------------|
| Reorder bullets within jobs | Add content not in Persona |
| Adjust summary wording (tone, emphasis) | Rewrite summary completely |
| Highlight different skills from BaseResume list | Add skills not in BaseResume |
| Minor keyword alignment | Change job history |

Guideline: "Recognizably the same resume. Minor variations, not different documents."

**Draft behavior:** Inherited fields (`included_jobs`, `job_bullet_selections`, etc.) read from Base Resume at render time. Only `summary`, `job_bullet_order`, and `modifications_description` stored on variant.

**Approval:** Snapshots ALL inherited fields into `snapshot_*` fields. Immutable after approval. Cannot be edited.

**Race conditions (REQ-007 §8.2):**

| Scenario | Behavior |
|----------|----------|
| Draft already in progress | Return existing draft with progress indicator |
| Previous draft exists | "Overwrite existing draft?" prompt |
| Approved variant exists | Block: "You already approved materials for this job" |
| Explicit regeneration | Archive old draft, create new |

### 5.5 Variant Review Display (REQ-010 §9, REQ-007 §8.7)

Agent reasoning format:
```
I've prepared materials for **{job_title}** at **{company_name}**:

**Resume Adjustments:**
- Summary missing key terms: added emphasis on "SAFe" and "enterprise transformation"
- Reordered bullets in TechCorp role to lead with SAFe implementation (was position 4)
```

**Content comparison:**
- Summary diff: base vs. variant (highlight changes)
- Bullet order comparison: old vs. new positions per job
- `modifications_description` as plain-language explanation
- Toggle between "Original" and "Tailored" views
- "No changes needed" state when `action == "use_base"`

### 5.6 Modification Guardrails (REQ-010 §4.4)

Validation checks:

| Check | Violation Message |
|-------|-------------------|
| New bullets added | "Variant contains bullets not in BaseResume: {ids}" |
| Summary length > 20% change | "Summary length changed by 35% (max 20%)" |
| Skills not in Persona | "Summary mentions skills not in Persona: {'Go', 'Rust'}" |

Display violations as actionable errors before user can approve.

### 5.7 PDF Preview/Download

| Endpoint | What It Serves |
|----------|---------------|
| `GET /base-resumes/{id}/download` | Stored anchor PDF (pre-rendered, not on-demand) |
| `GET /submitted-resume-pdfs/{id}/download` | Immutable submitted snapshot |

PDF generation triggered on first download; subsequent downloads return stored version. All BYTEA in PostgreSQL.

### 5.8 Resume API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/v1/resume-files` | Upload resume (`multipart/form-data`, max ~5MB) |
| CRUD | `/api/v1/base-resumes` | Base resume management |
| GET | `/api/v1/base-resumes/{id}/download` | Download anchor PDF |
| CRUD | `/api/v1/job-variants` | Job variant management |
| GET | `/api/v1/submitted-resume-pdfs/{id}/download` | Download submitted PDF |

Filtering: `job-variants` supports `?status=...&base_resume_id=...`

### 5.9 User Actions

| Action | Entity | Constraints |
|--------|--------|-------------|
| Create | Base Resume | name unique, all IDs valid, exactly one `is_primary` |
| Update | Base Resume | Triggers re-render, re-approval needed |
| Archive/Restore | Base Resume | Status toggle |
| Approve | Job Variant (Draft) | Snapshots inherited fields, immutable after |
| Archive | Job Variant | Status toggle |
| Pin | Job Variant | Excludes from auto-archive |
| Hard Delete | Archived items only | With confirmation dialog |
| Regenerate PDF | Job Variant (Draft only) | Blocked once Approved |

---

## 6. Cover Letter Management

**Sources:** REQ-002b, REQ-006 §5.2, REQ-007 §8, REQ-010 §5/§7/§9

### 6.1 Lifecycle

| Status | Meaning | Transitions To | Trigger |
|--------|---------|----------------|---------|
| Draft | Agent-generated, awaiting review | Approved, Archived | System (auto-draft ≥90% fit) or user (manual request) |
| Approved | User approved, linked to Application | Archived | User (explicit approval) |
| Archived | Hidden, follows retention | (terminal) | System (60 days after terminal) or user (dismiss) |

**Constraint:** One cover letter per Application. Immutable after approval.

### 6.2 Editor Interface (REQ-002b §7.3)

- `draft_text` editable while Draft status
- Overwritten on each edit (no revision history in MVP)
- Editor **disabled/read-only** once Approved
- No "un-approve" flow

### 6.3 Agent Reasoning Display (REQ-010 §9, REQ-002b §4.1)

**Story selection reasoning** (stored in `agent_reasoning`):
> "Selected 'Turned around failing project' because it demonstrates leadership under pressure and aligns with the job's emphasis on 'driving results in ambiguous situations'."

**Structured reasoning summary:**
```
**Cover Letter Stories:**
- *Turned around failing project* — Demonstrates leadership; aligns with company culture
- *Scaled Agile adoption* — Demonstrates SAFe, Agile Coaching; quantified impact
```

**Story traceability:** `achievement_stories_used` (list of Story IDs) enables linking back to Persona stories.

**Selection factors:** Skills match, recency, quantified impact, culture alignment, freshness penalty (used 3+ in last 30 days).

### 6.4 Regeneration Feedback (REQ-010 §7)

| Category | User Example | System Effect |
|----------|-------------|---------------|
| Story rejection | "Don't use the failing project story" | Exclude story, select next best |
| Tone adjustment | "Make it less formal" | Add tone override |
| Length adjustment | "Make it shorter" | Adjust word count target |
| Focus shift | "Focus more on technical skills" | Add emphasis instruction |
| Complete redo | "Start fresh" | Clear context, full regeneration |

**API:** `POST /cover-letters/{id}/regenerate`

**Parameters:** `feedback` (text, max 500 chars), `excluded_story_ids` (UUID list), `tone_override` (string), `word_count_target` (min/max tuple).

### 6.5 Validation Display (REQ-010 §5.4)

```json
{
  "passed": true,
  "issues": [{"severity": "warning", "rule": "length_max", "message": "Long: 380 words (target 250-350)"}],
  "word_count": 380
}
```

| Rule | Severity | Message Example |
|------|----------|-----------------|
| `length_min` | error | "Too short: 180 words (minimum 250)" |
| `length_max` | warning | "Long: 380 words (target 250-350)" |
| `blacklist_violation` | error | "Contains avoided phrase: 'synergy'" |
| `company_specificity` | warning | "Company name not in opening paragraph" |
| `metric_accuracy` | error | "Metric '40% increase' may be misattributed" |
| `potential_fabrication` | warning | "Draft mentions skills not in selected stories" |

Errors block presentation (system auto-regenerates). Warnings shown but don't block.

### 6.6 Achievement Story Override (REQ-010 §5.2)

- Display selected stories with titles, rationale, and score
- User can exclude stories and trigger regeneration with next-best
- Freshness count: how many times each story used recently

**Edge cases:**
- No stories → skip cover letter, explain to user
- No matching stories (scores < 20) → use top 2 with disclaimer
- Only 1 story → shorter letter (200-250 words)
- All stories have freshness penalty → ignore penalty

### 6.7 Voice Profile Indicator

- Show which voice profile was applied (e.g., "Written in your voice: Direct, confident")
- Warning if voice profile incomplete (defaults used)
- Blacklist violations highlighted in validation

### 6.8 PDF Preview/Download (REQ-002b §7.4)

- PDF generated when user clicks "Download" (not on approval)
- Must be Approved before PDF generation
- Endpoint: `GET /submitted-cover-letter-pdfs/{id}/download`
- Orphan cleanup: PDFs with null `application_id` purged after 7 days

### 6.9 Approval Flow

1. User reviews Draft (edit, regenerate, view reasoning/validation)
2. User clicks "Approve" → `PATCH /cover-letters/{id}` with `status=Approved`
3. `final_text = draft_text`, immutable after
4. User downloads PDF
5. User applies externally
6. User marks "Applied" → PDF linked to Application

### 6.10 Cover Letter API

| Method | Endpoint | Purpose |
|--------|----------|---------|
| CRUD | `/api/v1/cover-letters` | Cover letter management |
| GET | `/api/v1/submitted-cover-letter-pdfs/{id}/download` | Download submitted PDF |

Agent tools (via chat): `get_cover_letter`, `approve_cover_letter`, `regenerate_cover_letter`.

### 6.11 Quality Metrics (REQ-010 §10)

| Metric | Target | Alert |
|--------|--------|-------|
| First-draft approval rate | > 60% | < 40% |
| Validation pass rate | > 90% | < 80% |
| Avg regenerations per letter | < 1.5 | > 2.5 |

Outcome tracking: each generation logs `approved` / `regenerated` / `abandoned`.

---

## 7. Application Tracking

**Sources:** REQ-004, REQ-006 §2.6/§5.2

### 7.1 Status Pipeline

| Status | Terminal? | Transitions To |
|--------|-----------|----------------|
| Applied | No | Interviewing, Rejected, Withdrawn |
| Interviewing | No | Offer, Rejected, Withdrawn |
| Offer | No | Accepted, Rejected (rescinded), Withdrawn |
| Accepted | Yes | — |
| Rejected | Yes | — |
| Withdrawn | Yes | — |

Terminal states are **final** — disable status selector.

### 7.2 Application Detail View

Linked entities:

| Entity | Required | Notes |
|--------|----------|-------|
| Job Posting | Yes | Live record (may have changed) |
| Job Snapshot | Yes | Frozen JSONB at application time |
| Job Variant (resume) | Yes | Must be Approved |
| Cover Letter | Optional | If generated |
| Submitted Resume PDF | Optional | Downloadable |
| Submitted Cover Letter PDF | Optional | Downloadable |

Display: status badge, `applied_at`, `status_updated_at`, `current_interview_stage`, notes, offer/rejection details, timeline.

### 7.3 "Mark as Applied" Flow (REQ-004 §7.0-7.1)

"Pending Review" = UI-derived state (approved variant with no linked Application).

1. User downloads Resume PDF → `SubmittedResumePDF` created (`application_id = null`)
2. (Optional) User downloads Cover Letter PDF → `SubmittedCoverLetterPDF` created
3. User applies externally (link to `apply_url`)
4. User clicks "Mark as Applied" → `POST /applications` with IDs from steps 1-2
5. Backend creates Application, links PDFs, captures job snapshot, creates `applied` timeline event

**Edge cases:**
- Abandoned flow: orphan PDFs purged after 7 days; consider reminder
- One application per job per persona (`UNIQUE` constraint)
- Job Variant must be Approved

### 7.4 Interview Stage Tracking (REQ-004 §4.1, §5.1)

`current_interview_stage` on Application: Phone Screen / Onsite / Final Round / null

- Sub-status indicator when status is Interviewing
- Timeline events `interview_scheduled` and `interview_completed` also carry `interview_stage`
- Updatable via PATCH on application

### 7.5 Offer Details Capture (REQ-004 §4.3) — JSONB, all optional

| Field | Type | Notes |
|-------|------|-------|
| `base_salary` | number | |
| `salary_currency` | string | |
| `bonus_percent` | number | |
| `equity_value` | number | |
| `equity_type` | string | RSU / Options |
| `equity_vesting_years` | number | |
| `start_date` | date | |
| `response_deadline` | date | **Deadline countdown** in UI |
| `other_benefits` | string | Free text |
| `notes` | string | |

PII: `base_salary`, `equity_value` encrypted at rest. Agent can compare multiple active offers side-by-side (REQ-004 §8.3).

### 7.6 Rejection Details Capture (REQ-004 §4.4) — JSONB, all optional

| Field | Type | Notes |
|-------|------|-------|
| `stage` | string | Applied / Phone Screen / Onsite / Final Round / Offer |
| `reason` | string | e.g., "Culture fit concerns" |
| `feedback` | string | e.g., "Looking for someone more senior" |
| `rejected_at` | datetime | When rejection communicated |

Agent can pre-populate `stage` from `current_interview_stage`. Pattern analysis: "Your last 3 rejections came at the onsite stage."

### 7.7 Timeline Events (REQ-004 §5)

12 event types, **immutable** once created (append-only):

| Type | Auto/Manual |
|------|-------------|
| `applied` | Auto (on Application creation) |
| `status_changed` | Auto (on status transition) |
| `note_added` | Auto (on note creation) |
| `interview_scheduled` | Manual |
| `interview_completed` | Manual |
| `offer_received` | Auto (status → Offer) |
| `offer_accepted` | Auto (status → Accepted) |
| `rejected` | Auto (status → Rejected) |
| `withdrawn` | Auto (status → Withdrawn) |
| `follow_up_sent` | Manual |
| `response_received` | Manual |
| `custom` | Manual |

**API:**
- `GET /applications/{id}/timeline` — list (chronological)
- `POST /applications/{id}/timeline` — add event

**Display:** Chronological vertical timeline with date, type icon, description, interview stage badge.

### 7.8 Follow-up Suggestions (REQ-004 §8.1)

- Trigger: 5 business days after `interview_completed` with no subsequent event
- Agent message: "It's been 7 days since your phone screen. Want me to draft a follow-up email?"
- Agent-driven (calculated at query time), not schema-driven
- Surfaces in chat interface, no dedicated reminders UI
- `follow_up_sent` event type for recording the action

### 7.9 Job Snapshot (REQ-004 §4.1a)

Frozen JSONB copy at application time:

| Field | Type |
|-------|------|
| `title` | string |
| `company_name` | string |
| `company_url` | string |
| `description` | string |
| `requirements` | string[] |
| `salary_min` / `salary_max` | number |
| `salary_currency` | string |
| `location` | string |
| `work_model` | string |
| `source_url` | string |
| `captured_at` | datetime |

Immutable. Show both: link to live Job Posting + expandable snapshot section.

### 7.10 Pin, Archive, Bulk Operations

| Action | Effect |
|--------|--------|
| Pin | Excludes from auto-archive |
| Archive | Hidden from default views, recoverable |
| Restore | Sets back to visible |
| Hard Delete | Archived items only, with confirmation |

**Bulk:** `POST /applications/bulk-archive` with `{ "ids": [...] }`

**Retention:**

| Status | Auto-Archive | Hard Delete |
|--------|-------------|-------------|
| Applied/Interviewing/Offer | 180 days no activity | 365 days after archive |
| Accepted | 365 days | Never (career milestone) |
| Rejected/Withdrawn | 90 days | 365 days after archive |

### 7.11 Application Notes

- Free-form text field on Application
- Agent-populated from chat, user-editable directly
- Max length: TBD (suggested 10,000 chars)
- PII warning: may contain contact info

### 7.12 Application API

| Method | Endpoint | Purpose |
|--------|----------|---------|
| CRUD | `/api/v1/applications` | Application management |
| CRUD | `/api/v1/applications/{id}/timeline` | Timeline events |
| POST | `/api/v1/applications/bulk-archive` | Bulk archive |

Filtering: `?status=Applied,Interviewing&applied_after=...&applied_before=...`

---

## 8. Settings & Configuration

**Sources:** REQ-003 §4.2b, REQ-006 §6, REQ-007 §11

### 8.1 Job Source Preferences (REQ-003 §4.2b)

**Source registry** (read-only): `GET /api/v1/job-sources`

| Field | Display |
|-------|---------|
| `source_name` | "Adzuna", "Chrome Extension", etc. |
| `source_type` | API / Extension / Manual |
| `description` | Tooltip |
| `is_active` | System-level; grayed out if false |
| `display_order` | Default ordering |

**User preferences** (editable): `GET/PATCH /api/v1/user-source-preferences`

| Field | UI Control |
|-------|------------|
| `is_enabled` | Toggle per source |
| `display_order` | Drag-and-drop reorder |

All sources auto-enabled on persona creation.

### 8.2 Polling Configuration

Via Persona field `polling_frequency`: Daily / Twice Daily / Weekly / Manual Only. See §3.1.11.

### 8.3 Agent Configuration (REQ-007 §11)

**Model routing** (display-only for MVP):

| Task | Model | Rationale |
|------|-------|-----------|
| Skill extraction (Scouter) | Haiku | Fast, cheap |
| Ghost detection | Haiku | Simple classification |
| Scoring (Strategist) | Sonnet | Reasoning needed |
| Cover letter (Ghostwriter) | Sonnet | Writing quality |
| Chat responses | Sonnet | Conversational nuance |
| Onboarding | Sonnet | Interview quality |

Frontend could optionally display which model is processing a task for transparency.

### 8.4 Authentication (REQ-006 §6)

**MVP:** No auth headers needed. `DEFAULT_USER_ID` env var provides user context. Middleware injects automatically.

**Future:** Bearer token in `Authorization` header with `user_id` claim.

---

## 9. Shared Patterns & API Conventions

**Source:** REQ-006

### 9.1 Response Envelope

**Collection:**
```json
{
  "data": [...],
  "meta": { "total": 42, "page": 1, "per_page": 20 }
}
```

**Single resource:**
```json
{ "data": { ... } }
```

### 9.2 Pagination

Offset-based: `?page=1&per_page=20` (max 100).

### 9.3 Error Shape

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable message",
    "details": [...]
  }
}
```

**Error codes:**

| Code | HTTP | Description |
|------|------|-------------|
| `VALIDATION_ERROR` | 400 | Field validation |
| `UNAUTHORIZED` | 401 | Auth required |
| `FORBIDDEN` | 403 | Not your resource |
| `NOT_FOUND` | 404 | Resource not found |
| `DUPLICATE_APPLICATION` | 409 | Already applied |
| `DUPLICATE_JOB` | 409 | URL already exists (ingest) |
| `EXTRACTION_FAILED` | 422 | Could not extract (ingest) |
| `INVALID_STATE_TRANSITION` | 422 | e.g., approving already-approved |
| `TOKEN_EXPIRED` | 410 | Ingest preview expired |
| `INTERNAL_ERROR` | 500 | Unexpected error |

### 9.4 Sorting

`?sort=-fit_score,title` — prefix `-` for descending, comma-separated.

### 9.5 Filtering

`?status=Applied,Interviewing` — comma = OR.

**Resource-specific filters:**

| Resource | Filters |
|----------|---------|
| `job-postings` | `status`, `is_favorite`, `fit_score_min`, `company_name` |
| `applications` | `status`, `applied_after`, `applied_before` |
| `job-variants` | `status`, `base_resume_id` |
| `persona-change-flags` | `status` |

### 9.6 File Storage

All files stored as BYTEA in PostgreSQL. No S3, no filesystem paths.

**Upload:** `POST /resume-files` (`multipart/form-data`, max ~5MB)

**Downloads** (binary with Content-Type/Content-Disposition):

| Endpoint | Returns |
|----------|---------|
| `GET /base-resumes/{id}/download` | Anchor PDF |
| `GET /submitted-resume-pdfs/{id}/download` | Submitted resume |
| `GET /submitted-cover-letter-pdfs/{id}/download` | Submitted cover letter |

### 9.7 Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/ingest` | 10/min |
| `/chat/messages` | 10/min |
| `/embeddings/regenerate` | 5/min |

### 9.8 HTTP Status Conventions

200 GET/PUT/PATCH, 201 POST, 204 DELETE, 400/401/403/404/409/422/500 errors.

---

## 10. Backend Prerequisites (Gaps)

Issues found during the audit that must be resolved before or during frontend implementation.

### 10.1 Missing Application Pin/Archive Columns

**Problem:** REQ-002 §5.4 says Applications can be pinned and archived, but the Application table (REQ-004, REQ-005) has no `is_pinned` or `archived_at` columns. The backend model also lacks these.

**Resolution:** Add `is_pinned: bool` (default false) and `archived_at: timestamp` (nullable) to the `applications` table via migration. Aligns with existing pattern on BaseResume, JobVariant, CoverLetter.

### 10.2 Timeline Event Immutability vs API Stubs

**Problem:** REQ-004 §9 declares timeline events immutable ("cannot be edited or deleted"), but `backend/app/api/v1/applications.py` has PATCH/DELETE stubs for timeline events.

**Resolution:** Frontend treats timeline events as append-only (no edit/delete UI). Backend stubs should be reviewed — either return 405 Method Not Allowed or be removed.

### 10.3 Score Components Not Stored

**Problem:** `FitScoreResult`, `StretchScoreResult`, and `ScoreExplanation` are computed by service-layer dataclasses but only `fit_score`, `stretch_score`, and `ghost_score` are stored as columns on `job_postings`.

**Resolution:** Store components and explanation in a JSONB column (e.g., `score_details`) on `job_postings`, populated at scoring time. This avoids re-computation for every detail view request.

### 10.4 Weight Configuration Deferred

**Problem:** User-configurable score weights listed as "Deferred — Add in v2 if requested" (REQ-008 §12).

**Resolution:** Show weights as read-only in component drill-down. No weight adjustment UI in MVP. Backend already returns weights in result dataclasses.
