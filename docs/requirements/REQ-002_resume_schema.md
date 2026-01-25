# REQ-002: Resume Schema

**Status:** Draft  
**PRD Reference:** §8 Document Management  
**Last Updated:** 2025-01-25

---

## 1. Overview

This document defines the schema for resume-related entities: uploaded files, Base Resumes (master resumes per role type), Job Variants (application-specific tailoring), and Submitted PDFs (immutable snapshots).

**Key Principle:** The Persona (REQ-001) is the source of truth for professional data. Resumes are curated "views" of Persona data, not separate data stores.

---

## 2. Entity Relationships

```
Resume File (uploaded binary)
    │
    └── Extraction ──→ Populates Persona (REQ-001)

Persona (source of truth)
    │
    └── Base Resume (one per role type)
            │
            ├── "Scrum Master" master
            ├── "Product Owner" master
            └── "Agile Coach" master
                    │
                    └── Job Variant (if tailoring needed)
                            │
                            └── Submitted PDF (immutable snapshot)
                                    │
                                    └── Application (REQ-004)
```

---

## 3. Dependencies

### 3.1 This Document Depends On

| Dependency | Type | Fields Used |
|------------|------|-------------|
| REQ-001 Persona Schema | Foreign Key | `persona_id` |
| REQ-001 Persona Schema | References | `work_history[].id`, `work_history[].bullets[].id`, `skills[].id` |

### 3.2 Other Documents Depend On This

| Document | Dependency | Notes |
|----------|------------|-------|
| REQ-001 Persona Schema | `original_resume_file_id` | Links Persona to uploaded file |
| REQ-002b Cover Letter Schema | Pattern | Follows same draft → approved → PDF workflow |
| REQ-004 Application Schema | `job_variant_id`, `submitted_resume_pdf_id` | Application links to Job Variant and Submitted Resume PDF. Bidirectional: Submitted PDF has `application_id`. |
| REQ-005 Database Schema | All field definitions | ERD built from REQ-001 through REQ-004 |

---

## 4. Field Definitions

### 4.1 Resume File

The original uploaded PDF/DOCX. Extraction populates Persona fields directly.

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| id | UUID | ✅ | No | Referenced by `persona.original_resume_file_id` |
| persona_id | UUID | ✅ | No | FK to Persona |
| file_name | String | ✅ | No | Original filename (e.g., "Brian_Resume_2025.pdf") |
| file_type | Enum | ✅ | No | PDF / DOCX |
| file_size_bytes | Integer | ✅ | No | For display/limits |
| file_binary | Binary | ✅ | ✅ | The actual file (may contain PII) |
| uploaded_at | Timestamp | ✅ | No | |
| is_active | Boolean | ✅ | No | True if current upload; false if replaced |

**Notes:**
- Only one active Resume File per Persona at a time
- On new upload: old file marked `is_active = false`, new file becomes active
- Old files retained for history but not used

---

### 4.2 Base Resume

A curated "master" resume for a specific role type. References Persona data.

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| id | UUID | ✅ | No | |
| persona_id | UUID | ✅ | No | FK to Persona |
| name | String | ✅ | No | e.g., "Scrum Master", "Product Owner" |
| role_type | String | ✅ | No | Target role category |
| summary | String | ✅ | No | Role-specific professional summary |
| included_jobs | List of Job IDs | ✅ | No | Which work history entries to include |
| job_bullet_selections | JSONB | ✅ | No | Map of job_id → list of bullet_ids to include |
| job_bullet_order | JSONB | ✅ | No | Map of job_id → ordered list of bullet_ids |
| included_education | List of Education IDs | Optional | No | Which education entries to show (null = show all) |
| included_certifications | List of Certification IDs | Optional | No | Which certs to show (null = show all) |
| skills_emphasis | List of Skill IDs | Optional | No | Which skills to highlight |
| is_primary | Boolean | ✅ | No | If true, default for new applications without clear role match |
| status | Enum | ✅ | No | Active / Archived |
| display_order | Integer | ✅ | No | For ordering multiple Base Resumes in UI |
| created_at | Timestamp | ✅ | No | |
| updated_at | Timestamp | ✅ | No | |
| archived_at | Timestamp | Optional | No | When archived (if applicable) |

**Validation Rules:**
- At least one Base Resume per Persona (created during onboarding)
- Exactly one Base Resume should have `is_primary = true`
- `name` must be unique per Persona

**JSONB Structure Examples:**

`job_bullet_selections`:
```json
{
  "job-uuid-1": ["bullet-uuid-a", "bullet-uuid-b", "bullet-uuid-c"],
  "job-uuid-2": ["bullet-uuid-d", "bullet-uuid-e"]
}
```

`job_bullet_order`:
```json
{
  "job-uuid-1": ["bullet-uuid-b", "bullet-uuid-a", "bullet-uuid-c"],
  "job-uuid-2": ["bullet-uuid-e", "bullet-uuid-d"]
}
```

---

### 4.3 Job Variant

A tailored version of a Base Resume for a specific job application. Created when agent determines tailoring is needed.

**IMPORTANT: Snapshot Behavior**

When a Job Variant is in Draft status, it references the Base Resume for inherited fields. When approved, ALL fields are snapshotted (copied) to the Job Variant to ensure immutability. This prevents changes to the Base Resume from affecting approved Job Variants.

#### 4.3.1 Fields (Draft Status)

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| id | UUID | ✅ | No | |
| base_resume_id | UUID | ✅ | No | FK to Base Resume (source) |
| job_posting_id | UUID | ✅ | No | FK to Job Posting (REQ-003) |
| summary | String | ✅ | No | Job-specific summary (may differ from Base) |
| job_bullet_order | JSONB | ✅ | No | Reordered bullets for this job |
| modifications_description | String | Optional | No | Agent's explanation of changes made |
| status | Enum | ✅ | No | Draft / Approved / Archived |
| created_at | Timestamp | ✅ | No | |
| approved_at | Timestamp | Optional | No | When user approved |
| archived_at | Timestamp | Optional | No | When archived |

During Draft status, these fields are read from `base_resume_id` at render time:
- `included_jobs`
- `job_bullet_selections`
- `included_education`
- `included_certifications`
- `skills_emphasis`

#### 4.3.2 Snapshot Fields (Populated on Approval)

When status changes to Approved, these fields are copied from the Base Resume:

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| snapshot_included_jobs | List of Job IDs | ✅ | No | Copied from Base Resume on approval |
| snapshot_job_bullet_selections | JSONB | ✅ | No | Copied from Base Resume on approval |
| snapshot_included_education | List of Education IDs | Optional | No | Copied from Base Resume on approval |
| snapshot_included_certifications | List of Certification IDs | Optional | No | Copied from Base Resume on approval |
| snapshot_skills_emphasis | List of Skill IDs | Optional | No | Copied from Base Resume on approval |

#### 4.3.3 Rendering Logic

```
If status == Draft:
    Use base_resume_id to fetch inherited fields
    Apply job_bullet_order and summary overrides
    
If status == Approved:
    Use snapshot_* fields (ignore base_resume_id for content)
    Apply job_bullet_order and summary
```

This ensures approved Job Variants are fully self-contained and immutable.

---

### 4.4 Submitted PDF

The exact PDF file submitted with an application. Immutable snapshot.

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| id | UUID | ✅ | No | |
| application_id | UUID | Optional | No | FK to Application (REQ-004) — NULL until user marks "Applied" |
| resume_source_type | Enum | ✅ | No | Base / Variant |
| resume_source_id | UUID | ✅ | No | FK to Base Resume or Job Variant |
| file_name | String | ✅ | No | Generated filename |
| file_binary | Binary | ✅ | ✅ | The PDF file (contains PII) |
| generated_at | Timestamp | ✅ | No | |

**Notes:**
- One Submitted PDF per Application (once linked)
- Created when user downloads PDF (before Application exists)
- `application_id` is NULL initially, set when user marks "Applied"
- Orphan PDFs (NULL `application_id` older than 7 days) are purged by cleanup job
- Follows Application retention policy once linked

---

### 4.5 Persona Change Flag

Tracks changes to Persona data that may need to be reflected in Base Resumes. Enables the "flag for review" sync mechanism.

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| id | UUID | ✅ | No | |
| persona_id | UUID | ✅ | No | FK to Persona |
| change_type | Enum | ✅ | No | job_added / bullet_added / skill_added / education_added / certification_added |
| item_id | UUID | ✅ | No | ID of the new Persona item |
| item_description | String | ✅ | No | Human-readable summary for display |
| status | Enum | ✅ | No | Pending / Resolved |
| created_at | Timestamp | ✅ | No | When the change occurred |
| resolved_at | Timestamp | Optional | No | When user addressed the flag |
| resolution | Enum | Optional | No | added_to_all / added_to_some / skipped |

**Notes:**
- Created automatically when user adds items to Persona
- Flags are displayed in UI and/or surfaced by agent during conversation
- Resolved when user decides what to do with the new item
- Old resolved flags can be purged after 30 days (housekeeping)

---

## 5. Retention Policy

### 5.1 Retention Rules

| Entity | Archive Trigger | Delete Trigger | Manual Override |
|--------|-----------------|----------------|-----------------|
| **Resume File** | On new upload (old file archived) | Never (history preserved) | User can hard delete old uploads |
| **Base Resume** | User action only | Never (archive only) | User can restore from archive |
| **Job Variant** | 60 days after Application terminal state, OR immediate on Dismiss | 180 days after archive | User can pin to prevent |
| **Submitted PDF** | Follows Job Variant / Application | Follows Job Variant / Application | Follows Job Variant / Application |

### 5.2 Terminal States (from REQ-004)

| State | Archive Trigger |
|-------|-----------------|
| Offer | 60 days after state entered |
| Rejected | 60 days after state entered |
| Withdrawn | 60 days after state entered |
| Dismissed | Immediate |

### 5.3 Status Enum Values

| Status | Meaning |
|--------|---------|
| Active | Normal state, visible in UI |
| Archived | Hidden from default views, recoverable |
| (Deleted) | Hard deleted, not recoverable — no record remains |

### 5.4 User Actions

| Action | Allowed On | Effect |
|--------|------------|--------|
| Archive | Base Resume, Job Variant, Application | Sets status = Archived, hidden from UI |
| Restore | Archived items (before hard delete) | Sets status = Active |
| Pin | Job Variant, Application | Excludes from auto-archive/delete |
| Hard Delete | Archived items | Permanently removes record (with confirmation) |

---

## 6. Workflow Integration

### 6.1 Onboarding Flow

1. User uploads resume (optional) → Resume File created
2. System extracts data → Persona populated (REQ-001)
3. Agent conducts interview → Persona enriched
4. Agent asks: "What role are you targeting?" → First Base Resume created
5. Agent asks: "Any other roles you're considering?" → Additional Base Resumes (optional)
6. First Base Resume marked `is_primary = true`

**If no upload:** Base Resume still created from Persona data gathered via interview.

### 6.2 Application Flow (with Auto-Draft)

```
Job discovered (≥90% match)
    │
    ├── Agent selects appropriate Base Resume (by role match)
    │
    ├── Agent drafts Cover Letter (REQ-002b)
    │
    ├── Agent evaluates: "Does Base Resume need tailoring?"
    │       │
    │       ├── No  → Use Base Resume directly
    │       │
    │       └── Yes → Job Variant created (Draft status)
    │                 Agent explains modifications
    │                 User reviews/approves → Job Variant status = Approved
    │                                         Snapshot fields populated
    │
    ├── User clicks "Download Resume PDF"
    │       │
    │       └── Submitted PDF generated and stored
    │           (from Base Resume or approved Job Variant)
    │
    └── User applies externally, then marks as "Applied"
            │
            └── Application status updated (PDF already exists)
```

**Key timing:** PDF is generated when user downloads, NOT when they mark as "Applied". This allows user to download the PDF, submit it to the job portal, then return to mark the application status.

### 6.3 Persona → Base Resume Sync

When user adds new items to Persona, Base Resumes need to stay current.

**Sync Mechanism: Flag for Review**

| Persona Change | System Behavior |
|----------------|-----------------|
| New job added | Flag: "New job added. Include in Base Resumes?" |
| New bullet added to existing job | Flag: "New accomplishment added to [Job]. Add to Base Resumes?" |
| New skill added | Flag: "New skill added. Emphasize in Base Resumes?" |
| New education added | Flag: "New education added. Include in Base Resumes?" |
| New certification added | Flag: "New certification added. Include in Base Resumes?" |

**Agent Behavior:**

When flag is raised, agent prompts user:
> "I see you added a new accomplishment to your Product Manager role. Would you like me to add it to your Scrum Master resume, Product Owner resume, or both?"

User confirms per Base Resume. Agent updates `job_bullet_selections` accordingly.

**Flag Storage:** See §4.5 Persona Change Flag for entity definition.

### 6.4 PDF Generation

**Trigger:** User clicks "Download Resume PDF" for an application.

**Process:**
1. Determine source: Base Resume (if no tailoring) or approved Job Variant
2. If Job Variant and status = Draft, prompt user to approve first
3. Generate PDF from source
4. Store as Submitted PDF (copied, not linked)
5. Link Submitted PDF to Application record
6. Return PDF to user for download

**Subsequent downloads:** If Submitted PDF already exists for this Application, return the stored version (ensures consistency).

**Regeneration:** User can request "Regenerate PDF" if they edited the Job Variant while still in Draft status. Once Job Variant is Approved and PDF is generated, no regeneration is allowed.

---

## 7. Agent Behavior

### 7.1 Base Resume Selection

When a job is discovered, agent selects Base Resume by:
1. Match role_type to job title/category
2. If no clear match, use `is_primary = true` Base Resume
3. If multiple matches, agent asks user to confirm

### 7.2 Tailoring Decision

Agent evaluates if tailoring is needed based on:
- Keyword gaps (job requires terms not prominent in Base Resume)
- Bullet relevance (some bullets more relevant than current order)
- Summary alignment (summary doesn't emphasize what job values)

Agent should explain reasoning:
> "I recommend tailoring your Scrum Master resume for this role because the job emphasizes 'scaled Agile' and 'SAFe', which aren't highlighted in your current summary. I'll reorder your bullets to emphasize your SAFe experience."

### 7.3 Modification Limits

When creating Job Variant, agent may:
- Reorder bullets within jobs
- Adjust summary wording
- Emphasize different skills

Agent may NOT:
- Add content not in Persona
- Remove jobs entirely
- Fabricate metrics or experiences

---

## 8. Validation Rules

| Rule | Description |
|------|-------------|
| At least one Base Resume | Cannot complete onboarding without creating at least one |
| Exactly one is_primary | One Base Resume must be marked primary |
| Unique names | Base Resume names must be unique per Persona |
| Valid job references | `included_jobs` must reference valid Persona work history IDs |
| Valid bullet references | All bullet IDs in selections/order must exist in Persona |
| Valid education references | `included_education` IDs must reference valid Persona education entries |
| Valid certification references | `included_certifications` IDs must reference valid Persona certification entries |
| Valid skill references | `skills_emphasis` must reference valid Persona skill IDs |
| Immutable after approval | Job Variant cannot be edited after `status = Approved` |
| Immutable Submitted PDF | Submitted PDF cannot be modified after creation |

---

## 9. Privacy & Security Notes

### 9.1 PII Fields

| Entity | PII Fields | Notes |
|--------|------------|-------|
| Resume File | `file_binary` | Contains full resume with contact info |
| Submitted PDF | `file_binary` | Contains full resume with contact info |

### 9.2 Data Residency

- All files stored locally in PostgreSQL (binary columns) for MVP
- Future: Consider object storage (S3-compatible) for files if scaling needed
- Files included in data export requests
- Files deleted on hard delete (cascades from Application)

---

## 10. Open Questions

| # | Question | Status |
|---|----------|--------|
| 1 | Max file size for uploads? | TBD — suggest 10MB |
| 2 | PDF generation library? | TBD — WeasyPrint, ReportLab, or similar |
| 3 | Should we support other export formats (DOCX)? | TBD — PDF only for MVP |
| 4 | Template system for PDF styling? | TBD — defer to implementation |

---

## 11. Design Decisions & Rationale

This section preserves context for implementation.

### 11.1 Resume Architecture Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Resume data ownership | Resume stores all data / Resume references Persona | Resume references Persona | Persona is source of truth. Base Resume selects which items to include. Avoids duplication, ensures consistency. |
| Base Resume vs Job Variant | Single resume type / Two-tier system | Two-tier: Base Resume → Job Variant | Base Resume captures role-type targeting (PM resume, Scrum Master resume). Job Variant tailors for specific job. Clean separation of concerns. |

### 11.2 Inheritance & Immutability Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Job Variant inheritance | Always inherit from Base Resume / Snapshot on creation / Snapshot on approval | Snapshot on approval | Drafts should reflect Base Resume edits (user iterating). Approved variants must be immutable (legal/audit trail). Snapshot captures state at moment of commitment. |
| What gets snapshotted | Everything / Only overrides / Inherited fields only | All inherited fields + overrides | Approved Job Variant must be fully self-contained. Cannot depend on Base Resume state. User might edit Base Resume after approval. |

### 11.3 PDF Generation Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| When to generate PDF | On approval / On "Applied" status / On download | On download | User needs PDF before submitting externally. They download, submit to ATS, then return to mark "Applied." Can't generate on status change — too late. |
| PDF regeneration | Always regenerate / Store and reuse / Version tracking | Store first generation, block regeneration after approval | Approved resume = legal document. Must preserve exact version submitted. Draft can regenerate freely. |

### 11.4 Sync Mechanism Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| When Persona changes | Auto-update Base Resumes / Flag for review / Ignore | Flag for review | New skill might be relevant to some resumes, not others. Agent prompts user: "You added Kubernetes to your skills. Add it to your PM resume?" User decides. |
| Sync flag lifecycle | Keep forever / Auto-resolve / TTL | 30-day TTL, purge resolved | Keeps table clean. User has time to act. Old resolved flags have no value. |

---

## 12. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2025-01-25 | 0.1 | Initial draft from discovery interview |
| 2025-01-25 | 0.2 | Added: `included_education`, `included_certifications`, `display_order` to Base Resume. Added Persona → Base Resume sync mechanism (§6.3). Clarified Job Variant inheritance. Added REQ-002b dependency. |
| 2025-01-25 | 0.3 | CRITICAL FIX: Job Variant now snapshots all fields on approval (§4.3.1–4.3.3) to ensure immutability. Clarified PDF generation timing — triggered on download, not on "Applied" status (§6.4). Promoted Persona Change Flag to proper entity (§4.5). |
| 2025-01-25 | 0.4 | Added: §11 Design Decisions & Rationale for context preservation. |
| 2025-01-25 | 0.5 | Fixed Submitted PDF timing: `application_id` is now Optional (§4.4). PDF created on download with NULL `application_id`, linked when user marks "Applied". Added orphan cleanup note (7-day purge). |
