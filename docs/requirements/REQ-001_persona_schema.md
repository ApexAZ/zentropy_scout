# REQ-001: Persona Schema

**Status:** Draft  
**PRD Reference:** §3 Persona Framework  
**Last Updated:** 2025-01-25

---

## 1. Overview

The Persona is the user's complete professional identity — the single source of truth for matching and content generation. It contains everything the system knows about the user: contact info, work history, skills, achievements, preferences, and voice profile.

**Key Principle:** The Persona owns all professional data. Resumes are curated "views" of the Persona, not separate data stores.

---

## 2. Persona Structure

```
Persona
├── Metadata (id, user_id, timestamps, onboarding status)
├── Basic Info (contact, location)
├── Work History[] (complete record, multiple jobs)
│   └── Bullets[] (accomplishments per job)
├── Education[] (multiple degrees supported)
├── Skills[] (hard and soft combined, typed)
├── Certifications[]
├── Achievement Stories[]
├── Voice Profile
├── Non-Negotiables
│   ├── Location
│   ├── Compensation
│   ├── Filters
│   └── Custom[]
├── Growth Targets
├── Original Resume Reference
└── Embeddings (generated for matching)
```

---

## 3. Field Definitions

### 3.0 Persona Metadata

Top-level fields for the Persona record itself.

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| id | UUID | ✅ | No | Primary key |
| user_id | UUID | ✅ | No | Foreign key to User table |
| created_at | Timestamp | ✅ | No | Auto-generated |
| updated_at | Timestamp | ✅ | No | Auto-updated on change |
| onboarding_complete | Boolean | ✅ | No | Default: false |
| onboarding_step | Enum | Optional | No | Current step if incomplete (see §6.1) |
| original_resume_file_id | UUID | Optional | No | Reference to uploaded resume file (see REQ-002) |

---

### 3.1 Basic Info

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| full_name | String | ✅ | ✅ | |
| email | String | ✅ | ✅ | Primary contact |
| phone | String | ✅ | ✅ | |
| linkedin_url | String | Optional | ✅ | |
| portfolio_url | String | Optional | No | Website, GitHub, etc. |
| home_city | String | ✅ | ✅ | e.g., "Gilbert" |
| home_state | String | ✅ | ✅ | e.g., "Arizona" |
| home_country | String | ✅ | No | e.g., "USA" |

### 3.1b Professional Overview

High-level professional identity fields used for display and job matching.

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| professional_summary | String | Optional | No | General career overview (2-4 sentences). Source material for role-specific Base Resume summaries. May be extracted from uploaded resume. |
| years_experience | Integer | Optional | No | Self-reported total years of professional experience. Used for job matching against requirements like "5+ years required". |
| current_role | String | Optional | No | How user identifies professionally — may differ from literal job title in Work History. e.g., "Scrum Master" even if title is "Delivery Lead". |
| current_company | String | Optional | No | Current employer for quick display. May differ from Work History if user has multiple concurrent roles. |

---

### 3.2 Work History

A list of job entries. Ordered by `start_date` descending (most recent first) by default.

#### Job Entry

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| id | UUID | ✅ | No | For referencing in Base Resumes |
| job_title | String | ✅ | No | |
| company_name | String | ✅ | No | |
| company_industry | String | Optional | No | Agent should attempt to gather |
| location | String | ✅ | No | City, State/Country |
| work_model | Enum | ✅ | No | Remote / Hybrid / Onsite |
| start_date | Month/Year | ✅ | No | |
| end_date | Month/Year or "Current" | ✅ | No | |
| description | String | Optional | No | High-level role summary |
| bullets | List of Accomplishment | ✅ | No | At least 1 required |
| display_order | Integer | ✅ | No | For manual reordering |

#### Accomplishment Bullet

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| id | UUID | ✅ | No | For referencing in Base Resumes |
| text | String | ✅ | No | The accomplishment statement |
| skills_demonstrated | List of Skill IDs | Optional | No | Links to skills in §3.4 |
| metrics | String | Optional | No | Quantified results (e.g., "reduced costs by 30%") |
| display_order | Integer | ✅ | No | Order within the job entry |

---

### 3.3 Education

A list of education entries. Users may have multiple degrees. **Education is optional** — not everyone has formal education.

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| id | UUID | ✅ | No | |
| degree | String | ✅ | No | e.g., "Bachelor of Science" |
| field_of_study | String | ✅ | No | e.g., "Computer Science" |
| institution | String | ✅ | No | e.g., "Arizona State University" |
| graduation_year | Year | ✅ | No | |
| gpa | Decimal | Optional | No | More relevant for new grads |
| honors | String | Optional | No | e.g., "Summa Cum Laude" |
| display_order | Integer | ✅ | No | For manual reordering |

---

### 3.4 Skills

A single list containing both Hard Skills and Soft Skills, distinguished by `skill_type`.

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| id | UUID | ✅ | No | For referencing |
| skill_name | String | ✅ | No | e.g., "Python", "Conflict Resolution" |
| skill_type | Enum | ✅ | No | Hard / Soft |
| category | String | ✅ | No | Predefined + custom allowed |
| proficiency | Enum (1-4) | ✅ | No | Learning / Familiar / Proficient / Expert |
| years_used | Integer | ✅ | No | |
| last_used | "Current" or Year | ✅ | No | |
| display_order | Integer | ✅ | No | For manual reordering within type |

#### Proficiency Scale

| Level | Label | Definition |
|-------|-------|------------|
| 1 | Learning | Currently studying, no professional use yet |
| 2 | Familiar | Have used professionally, would need ramp-up time |
| 3 | Proficient | Can work independently, solid experience |
| 4 | Expert | Deep expertise, could teach others, go-to person |

#### Hard Skill Categories (Defaults)

- Programming Language
- Framework / Library
- Tool / Software
- Platform / Infrastructure
- Methodology
- Domain Knowledge
- (Custom allowed)

#### Soft Skill Categories (Defaults)

- Leadership & Management
- Communication
- Collaboration
- Problem Solving
- Adaptability
- (Custom allowed)

---

### 3.5 Certifications

A list of professional certifications.

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| id | UUID | ✅ | No | |
| certification_name | String | ✅ | No | e.g., "AWS Solutions Architect" |
| issuing_organization | String | ✅ | No | e.g., "Amazon Web Services" |
| date_obtained | Date | ✅ | No | |
| expiration_date | Date or "No Expiration" | ✅ | No | |
| credential_id | String | Optional | No | |
| verification_url | URL | Optional | No | |
| display_order | Integer | ✅ | No | For manual reordering |

---

### 3.6 Achievement Stories

Structured narratives for behavioral interview content and cover letter generation.

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| id | UUID | ✅ | No | |
| title | String | ✅ | No | Short identifier (e.g., "Turned around failing project") |
| context | String | ✅ | No | 1-2 sentences: what was the situation? |
| action | String | ✅ | No | What did you do? |
| outcome | String | ✅ | No | What was the result? Quantify if possible. |
| skills_demonstrated | List of Skill IDs | Optional | No | Links to relevant skills |
| related_job_id | Job ID | Optional | No | Links to work history entry |
| display_order | Integer | ✅ | No | For manual reordering |

**Count:** Unlimited. Agent encourages 3-5 minimum during onboarding.

---

### 3.7 Voice Profile

Guides the Ghostwriter to write in the user's authentic tone. All fields are derived from interview + writing samples, then user can edit.

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| tone | String | ✅ | No | e.g., "Direct, confident, avoids buzzwords" |
| sentence_style | String | ✅ | No | e.g., "Short sentences, active voice" |
| vocabulary_level | String | ✅ | No | e.g., "Technical when relevant, otherwise plain English" |
| personality_markers | String | Optional | No | e.g., "Occasional dry humor, never self-deprecating" |
| sample_phrases | List of String | Optional | No | e.g., "I led...", "I built...", "The result was..." |
| things_to_avoid | List of String | Optional | No | e.g., "Passionate", "Synergy", "Think outside the box" |
| writing_sample_text | String | Optional | No | Raw text user provided for voice derivation |

**How captured:** Derived from interview conversation + optional writing samples. User can edit.

---

### 3.8 Non-Negotiables

Hard filters that exclude jobs from consideration.

#### 3.8.1 Location

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| commutable_cities | List of String | ✅ | No | Cities user is willing to commute to |
| max_commute_minutes | Integer | Optional | No | |
| remote_preference | Enum | ✅ | No | Remote Only / Hybrid OK / Onsite OK / No Preference |
| relocation_open | Boolean | ✅ | No | |
| relocation_cities | List of String | Optional | No | If relocation_open = true |

#### 3.8.2 Compensation

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| minimum_base_salary | Integer | Optional | ✅ | Annual, in user's currency |
| currency | String | Optional | No | Default: USD |

#### 3.8.3 Other Filters

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| visa_sponsorship_required | Boolean | ✅ | No | |
| industry_exclusions | List of String | Optional | No | e.g., "Defense", "Gambling", "Tobacco" |
| company_size_preference | Enum | Optional | No | Startup / Mid-size / Enterprise / No Preference |
| max_travel_percent | Enum | Optional | No | None / <25% / <50% / Any |

#### 3.8.4 Custom Non-Negotiables

Users can define additional filters beyond the defaults.

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| id | UUID | ✅ | No | |
| filter_name | String | ✅ | No | e.g., "No Amazon subsidiaries" |
| filter_type | Enum | ✅ | No | Exclude / Require |
| filter_value | String | ✅ | No | The value to match against |
| filter_field | String | ✅ | No | Which job field to check (e.g., "company_name", "description") |

**Example custom filter:**
- filter_name: "No Amazon subsidiaries"
- filter_type: Exclude
- filter_value: "Amazon, AWS, Whole Foods, Ring, Twitch"
- filter_field: "company_name"

---

### 3.9 Growth Targets

Skills and roles the user wants to develop toward.

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| target_roles | List of String | Optional | No | e.g., "Engineering Manager", "Staff Engineer" |
| target_skills | List of String | Optional | No | e.g., "Kubernetes", "People Management" |
| stretch_appetite | Enum | ✅ | No | Low / Medium / High |

**Matching impact:** Used to calculate Stretch Score alongside Fit Score (see PRD §4.3).

---

### 3.10 Discovery Preferences

User settings that control how jobs are discovered and presented.

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| minimum_fit_threshold | Integer | ✅ | 50 | Jobs below this Fit Score not shown by default (0-100) |
| polling_frequency | Enum | ✅ | Daily | Daily / Twice Daily / Weekly / Manual Only |
| auto_draft_threshold | Integer | ✅ | 90 | Fit Score threshold for auto-drafting cover letter |

**Behavior:**
- Jobs below `minimum_fit_threshold` are discovered but not surfaced unless user opts to "Show all"
- Jobs at or above `auto_draft_threshold` trigger automatic cover letter drafting
- User can always manually trigger discovery regardless of `polling_frequency`

---

## 4. Embeddings

Generated from Persona data for semantic matching. Stored separately but linked to Persona.

### 4.1 Embedding Records

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | UUID | ✅ | |
| persona_id | UUID | ✅ | Foreign key to Persona |
| embedding_type | Enum | ✅ | hard_skills / soft_skills / logistics |
| vector | Float[] | ✅ | The embedding vector |
| model_name | String | ✅ | e.g., "text-embedding-3-small" |
| model_version | String | ✅ | e.g., "2024-01" |
| source_hash | String | ✅ | Hash of source data (to detect staleness) |
| created_at | Timestamp | ✅ | |

### 4.2 Embedding Sources

| Embedding Type | Source Fields |
|----------------|---------------|
| hard_skills | Skills where skill_type = Hard (names, proficiency, years) |
| soft_skills | Skills where skill_type = Soft (names, proficiency, years) |
| logistics | Non-Negotiables, Growth Targets |

### 4.3 Regeneration Rules

Embeddings are regenerated when:
- Source fields are updated (detected via source_hash comparison)
- Embedding model is upgraded (model_version changes)

Old embeddings are deleted after new ones are generated successfully.

**Model:** TBD during implementation (OpenAI text-embedding-3-small, Cohere embed-v3, or equivalent)

---

## 5. Relationship to Resumes

```
Persona (source of truth)
    │
    ├── original_resume_file_id ──→ Uploaded file (PDF/DOCX binary)
    │
    └── Base Resume (curated view for a role type)
            │
            └── Job Variant (tailored for specific application)
```

| Entity | Contains | Purpose |
|--------|----------|---------|
| Persona | Complete work history, all skills, all accomplishments | Matching, full context for agents |
| Base Resume | Selection of jobs/bullets, custom ordering, role-specific summary | Defines a "lens" (Scrum Master, PM, etc.) |
| Job Variant | Snapshot tailored to one job posting | Linked to Application record |

Base Resume and Job Variant schemas are defined in [REQ-002 Resume Schema](./REQ-002_resume_schema.md).

---

## 6. Data Collection

### 6.1 Onboarding Interview Flow

The Onboarding Agent gathers Persona data in this order:

| Step | Name | Fields Captured |
|------|------|-----------------|
| 1 | resume_upload | original_resume_file_id, extracted work history/skills/education |
| 2 | basic_info | full_name, email, phone, location fields |
| 3 | work_history | Confirm/expand extracted jobs, add missing bullets |
| 4 | education | Confirm/add education entries (optional) |
| 5 | skills | Confirm extracted skills, add proficiency/years, add missing skills |
| 6 | certifications | Ask if any professional certifications |
| 7 | achievement_stories | Guided conversation to capture 3-5 stories |
| 8 | non_negotiables | Location preferences, salary, filters |
| 9 | growth_targets | Target roles, skills to develop, stretch appetite |
| 10 | voice_profile | Derived from conversation + optional writing sample |
| 11 | review | User reviews complete Persona, makes edits |

The `onboarding_step` field tracks which step the user is on if they exit early. They can resume where they left off.

### 6.2 Agent Behavior

- Agent should attempt to gather all optional fields
- If user gives incomplete answers, agent presses for specifics
- Agent derives soft skills from Achievement Stories, asks user to confirm/rate
- Agent presents Voice Profile summary for user approval
- Agent can infer `company_industry` from company name if user doesn't know
- Agent should ask about certifications even if none on resume

### 6.3 Post-Onboarding Updates

Users can update their Persona at any time via:
- Direct editing in the UI
- Conversation with the agent ("I got a new certification")
- Re-running parts of the onboarding interview

---

## 7. Validation Rules

| Rule | Description |
|------|-------------|
| At least 1 job in Work History | Cannot complete onboarding with empty work history |
| At least 1 bullet per job | Every job needs at least one accomplishment |
| Skills require all fields | name + type + category + proficiency + years + last_used (no partial entries) |
| Non-Negotiables location required | Must specify commutable_cities OR remote_preference = "Remote Only" |
| Stretch Appetite required | Must select Low / Medium / High |
| Education is optional | Users without formal education can skip |
| Certifications are optional | Users without certifications can skip |

---

## 7b. Deletion Handling

When user deletes Persona items that are referenced by other entities (Base Resumes, Cover Letters), the system uses a "flag for review" pattern.

### 7b.1 Reference Check on Delete

Before deleting a Persona item, system checks for references:

| Deleted Item | Check For References In |
|--------------|-------------------------|
| Job (work history) | Base Resume `included_jobs` |
| Bullet | Base Resume `job_bullet_selections`, `job_bullet_order` |
| Skill | Base Resume `skills_emphasis` |
| Education | Base Resume `included_education` |
| Certification | Base Resume `included_certifications` |
| Achievement Story | Cover Letter `achievement_stories_used` (approved letters are immutable — only check draft letters) |

### 7b.2 Deletion Flow

```
User requests delete
    │
    ├── No references found → Delete immediately
    │
    └── References found → Flag for review
            │
            ├── Show user: "This item is used in [X] Base Resumes"
            │
            └── User chooses:
                    ├── "Remove from all and delete" → Cascade remove, then delete
                    ├── "Cancel" → No action
                    └── "Review each" → Show list, user decides per item
```

### 7b.3 Immutable Entity Protection

**Cannot delete if referenced by immutable entities:**

| Immutable Entity | Behavior |
|------------------|----------|
| Approved Job Variant | Block delete — user must archive the Application first |
| Approved Cover Letter | Block delete — user must archive the Application first |
| Submitted PDF | N/A — PDFs are snapshots, don't hold live references |

Agent should explain: "This bullet is part of an application you submitted to Acme Corp. You can archive that application first if you want to delete this bullet."

---

## 8. Privacy & Security Notes

### 8.1 PII Fields

The following fields contain Personally Identifiable Information and should be:
- Encrypted at rest
- Excluded from logs
- Included in data export/delete requests

| Section | PII Fields |
|---------|------------|
| Basic Info | full_name, email, phone, linkedin_url, home_city, home_state |
| Compensation | minimum_base_salary |

### 8.2 Data Residency

MVP: All data stored locally in PostgreSQL container on user's machine. No data leaves machine except:
- LLM API calls (prompts contain persona data — user accepts this)
- Embedding API calls (skill/job text sent for vectorization)

---

## 9. Open Questions

| # | Question | Status |
|---|----------|--------|
| 1 | How do we handle skill synonyms? (e.g., "JS" vs "JavaScript") | TBD — may need normalization table |
| 2 | Should certifications affect matching score, or just be displayed? | TBD — leaning toward matching |
| 3 | Max length for text fields? (for database column sizing) | TBD — defer to REQ-005 |
| 4 | Should we support multiple languages for international users? | TBD — out of scope for MVP |

---

## 10. Dependencies

### 10.1 This Document Depends On

| Dependency | Type | Notes |
|------------|------|-------|
| None | — | REQ-001 is foundational |

### 10.2 Other Documents Depend On This

| Document | Dependency | Notes |
|----------|------------|-------|
| REQ-002 Resume Schema | `persona_id`, `job.id`, `bullet.id`, `skill.id`, `education.id`, `certification.id` | Base Resume references Persona fields |
| REQ-002b Cover Letter Schema | `persona_id`, `achievement_stories[].id`, Voice Profile | Cover letters use stories and voice |
| REQ-003 Job Posting Schema | `persona_id`, Skills, Non-Negotiables, Growth Targets, Discovery Preferences | Matching and filtering jobs |
| REQ-004 Application Schema | `persona_id` | Links applications to user |
| REQ-005 Database Schema | All field definitions | ERD built from REQ-001 through REQ-004 |

---

## 11. Design Decisions & Rationale

This section preserves context for implementation.

### 11.1 Data Ownership Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Where professional data lives | Resume stores data / Persona stores data / Both | Persona is source of truth | Resume is a "view" of Persona. Avoids duplication. User updates one place. Base Resumes select/order from Persona data. |

### 11.2 Skill Structure Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Skill proficiency scale | 1-10 / 1-5 / 4-level named | 4-level: Learning, Familiar, Proficient, Expert | Named levels are more meaningful than arbitrary numbers. 4 levels provides enough granularity without false precision. |
| Hard vs Soft skills | Separate lists / Single list with type | Single list with `skill_type` enum | Same structure, easier to query, agent can filter by type when needed. |

### 11.3 Achievement Story Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Story structure | Freeform text / Structured (Context, Action, Outcome) | Structured | Easier for agents to parse and use for content generation. Ensures completeness. User still writes in their own words. |

### 11.4 Voice Profile Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Voice capture method | Direct questions / Derived from conversation / Writing samples | Combination: derived + optional samples | Direct questions feel awkward. Deriving from natural conversation is more authentic. Writing samples add richness if user has them. Agent extracts traits, user reviews. |

### 11.5 Sync & Deletion Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| When Persona changes, update Base Resumes? | Auto-add / Flag for review / Manual only | Flag for review | Auto-add could clutter resumes with irrelevant items. Manual is easy to forget. Flag lets user decide per-resume with agent assistance. |
| Deletion handling | Block if referenced / Cascade delete / Flag for review | Flag for review + block for immutable | Consistent pattern with additions. But can't delete items referenced by approved Job Variants (immutable snapshots). |

### 11.6 Retention Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Retention thresholds | 30/90 days / 60/180 days / User-configurable | 60 days to archive, 180 days to delete | 60 days gives user time to revisit. 180 days is long enough to not lose important history but short enough to manage storage. |

---

## 12. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2025-01-25 | 0.1 | Initial draft from discovery interview |
| 2025-01-25 | 0.2 | Added: Persona metadata, PII flags, display_order fields, custom non-negotiables structure, embedding versioning, onboarding steps enum, education as list, writing_sample_text field |
| 2025-01-25 | 0.3 | Added: §7b Deletion Handling — reference check on delete, flag for review pattern, immutable entity protection |
| 2025-01-25 | 0.4 | Added: §3.10 Discovery Preferences (minimum_fit_threshold, polling_frequency, auto_draft_threshold). Added: §11 Design Decisions & Rationale for context preservation. |
| 2025-01-25 | 0.5 | Added: §3.1b Professional Overview — `professional_summary`, `years_experience`, `current_role`, `current_company`. These support job matching and display without requiring computation from Work History. |
