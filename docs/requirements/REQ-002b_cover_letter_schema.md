# REQ-002b: Cover Letter Schema

**Status:** Draft
**PRD Reference:** §8 Document Management, §4.4 Ghostwriter
**Last Updated:** 2025-01-25

---

## 1. Overview

This document defines the schema for cover letter entities: agent-generated drafts, user-approved finals, and immutable PDF snapshots for applications.

**Key Principle:** Cover letters are generated fresh per job application — no templates. The Ghostwriter pulls from Achievement Stories (REQ-001) and writes in the user's Voice Profile to create tailored content for each opportunity.

---

## 2. Entity Relationships

```
Persona (REQ-001)
    │
    ├── Achievement Stories ──→ Referenced by Cover Letter
    │
    └── Voice Profile ──→ Guides writing style

Job Posting (REQ-003)
    │
    └── Cover Letter (generated for this job)
            │
            └── Submitted Cover Letter PDF (immutable snapshot)
                    │
                    └── Application (REQ-004)
```

---

## 3. Dependencies

### 3.1 This Document Depends On

| Dependency | Type | Fields Used |
|------------|------|-------------|
| REQ-001 Persona Schema | References | `achievement_stories[].id`, Voice Profile |
| REQ-002 Resume Schema | Pattern | Follows same draft → approved → PDF pattern |
| REQ-003 Job Posting Schema | Foreign Key | `job_posting_id` |
| REQ-004 Application Schema | Foreign Key | `application_id` |

### 3.2 Other Documents Depend On This

| Document | Dependency | Notes |
|----------|------------|-------|
| REQ-004 Application Schema | `cover_letter_id`, `submitted_cover_letter_pdf_id` | Links Application to cover letter used |
| REQ-005 Database Schema | All field definitions | ERD built from REQ-001 through REQ-004 |

---

## 4. Field Definitions

### 4.1 Cover Letter

The cover letter content — draft and final versions.

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| id | UUID | ✅ | No | |
| persona_id | UUID | ✅ | No | FK to Persona (owner) |
| application_id | UUID | Optional | No | FK to Application (REQ-004) — NULL until application created |
| job_posting_id | UUID | ✅ | No | FK to Job Posting (REQ-003) |
| achievement_stories_used | List of Story IDs | ✅ | No | Which stories from Persona were referenced |
| draft_text | String | ✅ | No | Agent-generated draft content |
| final_text | String | Optional | No | User-approved version (null until approved) |
| status | Enum | ✅ | No | Draft / Approved / Archived |
| agent_reasoning | String | Optional | No | Why agent chose these stories/approach |
| created_at | Timestamp | ✅ | No | |
| updated_at | Timestamp | ✅ | No | |
| approved_at | Timestamp | Optional | No | When user approved |
| archived_at | Timestamp | Optional | No | When archived |

**Notes:**
- `draft_text` is overwritten as user makes edits (no revision history in MVP)
- `final_text` is populated when user approves — becomes immutable
- `achievement_stories_used` enables traceability: "This letter referenced your 'Turned around failing project' story"

### 4.2 Submitted Cover Letter PDF

The exact PDF file submitted with an application. Immutable snapshot.

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| id | UUID | ✅ | No | |
| cover_letter_id | UUID | ✅ | No | FK to Cover Letter |
| application_id | UUID | Optional | No | FK to Application (REQ-004) — NULL until user marks "Applied" |
| file_name | String | ✅ | No | Generated filename |
| file_binary | Binary | ✅ | ✅ | The PDF file (may contain PII from letter content) |
| generated_at | Timestamp | ✅ | No | |

**Notes:**
- One Submitted Cover Letter PDF per Application (once linked)
- Created when user downloads PDF (before Application exists)
- `application_id` is NULL initially, set when user marks "Applied"
- Orphan PDFs (NULL `application_id` older than 7 days) are purged by cleanup job
- Follows Application retention policy once linked

---

## 5. Status Definitions

| Status | Meaning | Transitions To |
|--------|---------|----------------|
| Draft | Agent-generated, awaiting user review/edit | Approved, Archived |
| Approved | User approved, linked to Application | Archived |
| Archived | Hidden from view, follows retention policy | (terminal) |

---

## 6. Retention Policy

Cover letters follow the same retention policy as Job Variants and Submitted PDFs (REQ-002):

| Entity | Archive Trigger | Delete Trigger | Manual Override |
|--------|-----------------|----------------|-----------------|
| **Cover Letter** | 60 days after Application terminal state, OR immediate on Dismiss | 180 days after archive | User can pin to prevent |
| **Submitted Cover Letter PDF** | Follows Cover Letter / Application | Follows Cover Letter / Application | Follows Cover Letter / Application |

**Terminal states:** Offer, Rejected, Withdrawn (60 days to archive), Dismissed (immediate archive)

---

## 7. Workflow Integration

### 7.1 Generation Flow (with Auto-Draft)

```
Job discovered (≥90% match)
    │
    ├── Agent selects appropriate Base Resume (REQ-002)
    │
    ├── Agent analyzes job posting
    │       │
    │       └── Identifies key requirements, culture signals, keywords
    │
    ├── Agent selects Achievement Stories
    │       │
    │       └── Matches stories to job requirements
    │
    ├── Agent generates Cover Letter draft
    │       │
    │       ├── Uses Voice Profile for tone/style
    │       ├── References selected Achievement Stories
    │       └── Aligns with job posting keywords
    │
    └── Cover Letter created (status: Draft)
            │
            └── User reviews/edits → Approves
                    │
                    ├── Cover Letter status = Approved
                    │   final_text = draft_text (locked)
                    │
                    └── User clicks "Download Cover Letter PDF"
                            │
                            └── Submitted Cover Letter PDF generated and stored
                                    │
                                    └── User applies externally, marks as "Applied"
```

**Key timing:** PDF is generated when user downloads, NOT when they mark as "Applied". This matches the resume PDF workflow (REQ-002) and allows user to download, submit externally, then return to update status.

### 7.2 Agent Story Selection

The Ghostwriter selects Achievement Stories based on:

| Factor | How Used |
|--------|----------|
| **Skills match** | Story demonstrates skills required by job |
| **Recency** | Prefer recent stories (if `related_job_id` links to recent position) |
| **Impact** | Prefer stories with quantified outcomes |
| **Variety** | Avoid using same story repeatedly if user has many |

Agent reasoning is stored in `agent_reasoning` field:
> "Selected 'Turned around failing project' because it demonstrates leadership under pressure and aligns with the job's emphasis on 'driving results in ambiguous situations'. Also referenced 'Scaled Agile adoption' to highlight SAFe experience mentioned in requirements."

### 7.3 User Editing

When user edits the draft:
1. `draft_text` is updated (overwrites previous)
2. `updated_at` is refreshed
3. Status remains "Draft" until approved

User can request agent to regenerate:
> "Can you try a different approach? Focus more on my technical skills."

Agent generates new `draft_text`, preserving edit history is out of scope for MVP.

### 7.4 Approval & PDF Generation

**Approval:**
1. `final_text` = current `draft_text`
2. `status` = "Approved"
3. `approved_at` = now
4. Cover letter becomes immutable (no further edits)

**PDF Generation:**

Trigger: User clicks "Download Cover Letter PDF" for an application.

Process:
1. Check Cover Letter status — must be Approved
2. If still Draft, prompt user to approve first
3. Generate PDF from `final_text`
4. Store as Submitted Cover Letter PDF
5. Link to Application record
6. Return PDF to user for download

**Subsequent downloads:** If Submitted Cover Letter PDF already exists, return stored version.

**Regeneration:** Not allowed after approval — cover letter is locked.

---

## 8. Agent Behavior

### 8.1 Cover Letter Structure

Agent generates cover letters following this general structure:

| Section | Content |
|---------|---------|
| **Opening** | Hook + why this company/role specifically |
| **Body 1** | Achievement Story demonstrating key qualification |
| **Body 2** | Additional relevant experience/skills (optional) |
| **Closing** | Call to action, enthusiasm, availability |

Structure may vary based on job requirements and Voice Profile.

### 8.2 Voice Profile Application

Agent applies Voice Profile (REQ-001 §3.7) to all generated content:

| Voice Field | How Applied |
|-------------|-------------|
| `tone` | Overall letter tone (e.g., confident but not arrogant) |
| `sentence_style` | Sentence length and structure |
| `vocabulary_level` | Technical vs. accessible language |
| `personality_markers` | Subtle personality elements |
| `sample_phrases` | Preferred phrasings |
| `things_to_avoid` | Words/phrases never used |

### 8.3 Modification Limits

Agent may:
- Select which Achievement Stories to reference
- Adapt story framing to match job requirements
- Adjust language to match job posting keywords
- Vary structure based on job/company

Agent may NOT:
- Fabricate experiences not in Persona
- Claim skills user doesn't have
- Misrepresent job history or education
- Use Achievement Stories with embellished outcomes

---

## 9. Validation Rules

| Rule | Description |
|------|-------------|
| One Cover Letter per Application | Each Application has exactly one Cover Letter |
| Valid story references | `achievement_stories_used` must reference valid Persona story IDs |
| Draft text required | Cannot create Cover Letter without `draft_text` |
| Final text on approval | `final_text` must be set when status = Approved |
| Immutable after approval | Cover Letter cannot be edited after `status = Approved` |
| Immutable Submitted PDF | Submitted Cover Letter PDF cannot be modified after creation |
| PDF requires approval | Submitted PDF can only be generated from Approved cover letter |

---

## 10. Privacy & Security Notes

### 10.1 PII Fields

| Entity | PII Fields | Notes |
|--------|------------|-------|
| Cover Letter | `draft_text`, `final_text` | May contain personal details from stories |
| Submitted Cover Letter PDF | `file_binary` | Contains full letter content |

### 10.2 Data Residency

- All content stored locally in PostgreSQL for MVP
- Text fields may be sent to LLM API for generation
- PDF files stored as binary columns
- Files included in data export requests
- Files deleted on hard delete (cascades from Application)

---

## 11. Open Questions

| # | Question | Status |
|---|----------|--------|
| 1 | Max length for cover letters? | TBD — suggest 4000 chars (~1 page) |
| 2 | Should agent warn if letter exceeds typical length? | TBD — probably yes |
| 3 | PDF formatting/styling options? | TBD — defer to implementation, match resume style |
| 4 | Support for different letter formats (email body vs. formal letter)? | TBD — out of scope for MVP |

---

## 12. Design Decisions & Rationale

This section preserves context for implementation.

### 12.1 Template Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Cover letter templates | Templates per role / Templates per company type / No templates | No templates | Achievement stories provide reusable content. Fresh generation ensures tailoring to specific job. Templates encourage lazy, generic letters. Agent + stories = better quality than templates. |

### 12.2 Generation Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Auto-draft trigger | All matches / High matches only / Manual only | High matches (≥90% Fit Score) | Low matches probably won't apply. High matches are worth the compute. User can always manually trigger for any job. Configurable threshold in Persona preferences. |
| Generation approach | Full generation / Section-by-section / User writes + agent edits | Agent drafts full letter, user edits | Faster for user. Agent has context from Persona, job, stories. User reviews and tweaks voice/emphasis. |

### 12.3 Content Source Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Story selection | User picks stories / Agent picks stories / Hybrid | Agent suggests, user approves | Agent can match stories to job requirements. User knows which stories resonate best. Hybrid respects both. |
| Voice consistency | Formal template voice / User's natural voice / Configurable | User's voice from Voice Profile | Cover letter should sound like user, not generic corporate speak. Voice Profile captures user's actual communication style. Authenticity matters. |

### 12.4 Workflow Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Cover letter lifecycle | Standalone / Tied to Job Variant / Tied to Application | Tied to Job Variant | Cover letter and resume submitted together. Makes sense to link at that level. Application links to both via Job Variant. |
| PDF generation timing | On approval / On "Applied" status / On download | On download | Same rationale as resume: user needs PDF before external submission. They download, submit to ATS, then mark status. |

---

## 13. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2025-01-25 | 0.1 | Initial draft from discovery interview |
| 2025-01-25 | 0.2 | Clarified PDF generation timing — triggered on download, not on "Applied" status (§7.1, §7.4). Aligned with REQ-002 workflow. |
| 2025-01-25 | 0.3 | Added: §12 Design Decisions & Rationale for context preservation. |
| 2025-01-25 | 0.4 | Fixed Submitted Cover Letter PDF timing: `application_id` is now Optional (§4.2). PDF created on download with NULL `application_id`, linked when user marks "Applied". Added orphan cleanup note (7-day purge). |
| 2025-01-25 | 0.5 | Fixed CoverLetter `application_id` to Optional (§4.1) — cover letters can be auto-drafted before Application exists. |
