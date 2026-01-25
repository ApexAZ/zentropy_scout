# REQ-004: Application Schema

**Status:** Draft  
**PRD Reference:** §4.4 Application Tracking, §6 Workflow  
**Last Updated:** 2025-01-25

---

## 1. Overview

This document defines the schema for job applications: tracking the user's journey from initial application through final outcome.

**Key Principle:** An Application represents the user's pursuit of a specific job. It links the Job Posting (the opportunity) with the Job Variant (the tailored resume + cover letter). The Application has its own lifecycle independent of the Job Posting.

### 1.1 Problem Context

Job seekers face these pain points that Application tracking addresses:

| Pain Point | How We Address It |
|------------|-------------------|
| **Losing track of where I applied** | Centralized application list with status |
| **Forgetting interview details** | Timeline log captures key events |
| **No record of what I submitted** | Stored PDFs of exact resume/cover letter |
| **Can't compare offers** | Structured offer details |
| **Don't know why I keep getting rejected** | Rejection stage tracking enables pattern analysis |
| **Forgetting to follow up** | Agent can see timeline, suggest follow-ups |

---

## 2. Entity Relationships

```
Job Posting (REQ-003)
    │
    └── Application
            │
            ├── Job Variant (REQ-002) ─── for resume
            │       │
            │       └── Submitted Resume PDF
            │
            ├── Cover Letter (REQ-002b) ─── separate from Job Variant
            │       │
            │       └── Submitted Cover Letter PDF
            │
            ├── Timeline Events
            │       │
            │       └── Chronological activity log
            │
            ├── Offer Details (if status = Offer/Accepted)
            │
            └── Rejection Details (if status = Rejected)
```

**Key insight:** Application is the central "container" that links:
- The Job Posting (the opportunity)
- The Job Variant (the tailored resume)
- The Cover Letter (generated separately, not part of Job Variant)
- The Submitted PDFs (immutable snapshots of what was submitted)

---

## 3. Dependencies

### 3.1 This Document Depends On

| Dependency | Type | Fields Used |
|------------|------|-------------|
| REQ-001 Persona Schema | Foreign Key | `persona_id` (owner) |
| REQ-002 Resume Schema | Foreign Key | `job_variant_id`, `submitted_resume_pdf_id` → Submitted PDF (§4.4) |
| REQ-002b Cover Letter Schema | Foreign Key | `cover_letter_id`, `submitted_cover_letter_pdf_id` → Submitted Cover Letter PDF (§4.2) |
| REQ-003 Job Posting Schema | Foreign Key | `job_posting_id` |

### 3.2 Other Documents Depend On This

| Document | Dependency | Notes |
|----------|------------|-------|
| REQ-002 Resume Schema | `application_id` on Submitted PDF | Bidirectional for referential integrity |
| REQ-002b Cover Letter Schema | `application_id` on Cover Letter and Submitted Cover Letter PDF | Bidirectional for referential integrity |
| REQ-005 Database Schema | All field definitions | ERD built from REQ-001 through REQ-004 |

---

## 4. Field Definitions

### 4.1 Application

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| id | UUID | ✅ | No | |
| persona_id | UUID | ✅ | No | FK to Persona (owner) |
| job_posting_id | UUID | ✅ | No | FK to Job Posting |
| job_variant_id | UUID | ✅ | No | FK to Job Variant (approved) |
| cover_letter_id | UUID | Optional | No | FK to Cover Letter (if one was generated) |
| submitted_resume_pdf_id | UUID | Optional | No | FK to Submitted PDF (REQ-002 §4.4) |
| submitted_cover_letter_pdf_id | UUID | Optional | No | FK to Submitted Cover Letter PDF (REQ-002b §4.2) |
| status | Enum | ✅ | No | Applied / Interviewing / Offer / Accepted / Rejected / Withdrawn |
| current_interview_stage | Enum | Optional | No | Phone Screen / Onsite / Final Round (tracked during Interviewing status) |
| offer_details | JSONB | Optional | No | Populated when offer received (see §4.3) |
| rejection_details | JSONB | Optional | No | Populated when rejected (see §4.4) |
| applied_at | Timestamp | ✅ | No | When user marked as applied |
| status_updated_at | Timestamp | ✅ | No | Last status change |
| notes | Text | Optional | No | Free-form notes, agent-populated from chat |
| created_at | Timestamp | ✅ | No | |
| updated_at | Timestamp | ✅ | No | |

**Cardinality Rules:**
- One Application per Job Posting per Persona (can't apply to same job twice)
- One Job Variant per Application (1:1 — if reapplying to reposted job, create new Job Variant)
- Zero or one Cover Letter per Application (optional — not all jobs need cover letters)
- Job Variant must be in "Approved" status before Application can be created

### 4.1b Reapplication Scenarios

**Scenario 1: Same job, want to apply again**
- Not allowed. One Application per Job Posting.
- If user was rejected, they cannot create a new Application for the same `job_posting_id`.
- Rationale: Prevents spam applications. If company rejected you, applying again to same posting won't help.

**Scenario 2: Job reposts (new Job Posting record)**
- Allowed. Reposted job has different `job_posting_id` (see REQ-003 §8).
- User creates new Job Variant, new Application.
- Agent provides context: "This role was posted before. You applied on Jan 15 and were rejected."
- User decides whether to apply fresh.

**Scenario 3: Same company, different role**
- Allowed. Different `job_posting_id`.
- User may reuse Base Resume, creates new Job Variant tailored to new role.

**Scenario 4: User withdrew, wants to reapply**
- Not allowed for same Job Posting. Withdrawn is terminal.
- If job reposts, user can apply to new posting (Scenario 2).

**Example flow for repost:**
```
Jan 15: User applies to Job Posting A (Scrum Master at Acme)
Feb 1:  User rejected
Feb 15: Job Posting A expires

Mar 1:  Job Posting B created (repost, links to A via previous_posting_ids)
Mar 2:  User sees Job Posting B as new match
        Agent: "This role was posted before. You applied Jan 15, rejected Feb 1."
Mar 3:  User decides to apply → Creates new Job Variant, new Application
```

### 4.2 Submitted Documents

Immutable copies of what was actually submitted.

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| submitted_resume_pdf_id | UUID | Optional | No | FK to Submitted PDF (REQ-002 §4.4) |
| submitted_cover_letter_pdf_id | UUID | Optional | No | FK to Submitted Cover Letter PDF (REQ-002b §4.2) |

**Relationship Clarification:**

The Submitted PDF entities (in REQ-002 and REQ-002b) also have `application_id` pointing back to Application. This bidirectional relationship is intentional:
- Application → Submitted PDF: "What documents did I submit for this application?"
- Submitted PDF → Application: "Which application is this document for?"

**Timing & Linking Flow:**

```
1. User downloads Resume PDF
   → Submitted PDF created (application_id = NULL)
   → PDF ID stored in session/temp state

2. User downloads Cover Letter PDF (optional)
   → Submitted Cover Letter PDF created (application_id = NULL)
   → PDF ID stored in session/temp state

3. User marks "Applied"
   → Application created
   → Application.submitted_resume_pdf_id = PDF ID from step 1
   → Application.submitted_cover_letter_pdf_id = PDF ID from step 2
   → Submitted PDF.application_id = Application.id (backlink set)
   → Submitted Cover Letter PDF.application_id = Application.id (backlink set)
```

**Orphan Cleanup:** PDFs with NULL `application_id` older than 7 days are purged. This handles abandoned flows where user downloaded but never marked Applied.

### 4.3 Offer Details

Captured when status = Offer or Accepted. Stored as JSONB for flexibility.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| offer_details | JSONB | Optional | Populated when offer received |

**JSONB Structure:**

```json
{
  "base_salary": 150000,
  "salary_currency": "USD",
  "bonus_percent": 15,
  "equity_value": 50000,
  "equity_type": "RSU",
  "equity_vesting_years": 4,
  "start_date": "2025-03-01",
  "response_deadline": "2025-02-01",
  "other_benefits": "401k match 6%, unlimited PTO, remote OK",
  "notes": "Negotiated from initial 140k offer"
}
```

All fields optional — user captures what they have.

### 4.4 Rejection Details

Captured when status = Rejected.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| rejection_details | JSONB | Optional | Populated when rejected |

**JSONB Structure:**

```json
{
  "stage": "Onsite",
  "reason": "Culture fit concerns",
  "feedback": "They said team was looking for someone more senior",
  "rejected_at": "2025-01-25T10:00:00Z"
}
```

**Stage values:** Applied (no response), Phone Screen, Onsite, Final Round, Offer (rescinded after negotiation)

**Stage capture:** When user reports rejection, agent asks "At what stage were you rejected?" Agent can pre-populate from `current_interview_stage` or last timeline event with `interview_stage` if available.

---

## 5. Timeline Events

Chronological log of application activity. Displayed in expandable card UI.

### 5.1 Timeline Event Entity

| Field | Type | Required | PII | Notes |
|-------|------|----------|-----|-------|
| id | UUID | ✅ | No | |
| application_id | UUID | ✅ | No | FK to Application |
| event_type | Enum | ✅ | No | See §5.2 |
| event_date | Timestamp | ✅ | No | When event occurred |
| description | String | Optional | No | Details, agent-generated or user-provided |
| interview_stage | Enum | Optional | No | Phone Screen / Onsite / Final Round (for interview events) |
| created_at | Timestamp | ✅ | No | When record was created |

**Note:** `interview_stage` is populated for `interview_scheduled` and `interview_completed` events. This enables rejection analysis: "User was rejected at Onsite stage" even with simple status model.

### 5.2 Event Types

| Event Type | Trigger | Auto/Manual |
|------------|---------|-------------|
| `applied` | Application created | Auto |
| `status_changed` | Status transition | Auto |
| `note_added` | User/agent adds note | Auto |
| `interview_scheduled` | User reports interview | Manual |
| `interview_completed` | User reports completion | Manual |
| `offer_received` | Status → Offer | Auto |
| `offer_accepted` | Status → Accepted | Auto |
| `rejected` | Status → Rejected | Auto |
| `withdrawn` | Status → Withdrawn | Auto |
| `follow_up_sent` | User reports follow-up | Manual |
| `response_received` | User reports response | Manual |
| `custom` | Any other event | Manual |

### 5.3 Example Timeline

```
2025-01-15 — Applied
    Submitted resume v2.3 and cover letter to Acme Corp ATS
    
2025-01-18 — Response received
    Acknowledgment email received, recruiter Jane Smith
    
2025-01-20 — Interview scheduled
    Phone screen with Jane Smith on Jan 22 at 2pm
    
2025-01-22 — Interview completed
    Phone screen went well, discussed team structure and role expectations
    
2025-01-25 — Status changed: Interviewing
    Moving to onsite round
    
2025-01-28 — Interview scheduled
    Onsite on Feb 3, 4-hour panel
    
...
```

---

## 6. Status Lifecycle

### 6.1 Status Definitions

| Status | Meaning | Terminal? |
|--------|---------|-----------|
| Applied | User submitted application, awaiting response | No |
| Interviewing | In active interview process | No |
| Offer | Received offer, considering | No |
| Accepted | User accepted offer | Yes |
| Rejected | Company declined to proceed | Yes |
| Withdrawn | User pulled out of process | Yes |

### 6.2 Status Transitions

```
Applied → Interviewing (company responds positively)
       → Rejected (no response or rejection)
       → Withdrawn (user decides not to pursue)

Interviewing → Offer (company extends offer)
            → Rejected (company declines after interviews)
            → Withdrawn (user pulls out)

Offer → Accepted (user accepts)
     → Rejected (offer rescinded or expires)
     → Withdrawn (user declines offer)
```

### 6.3 Relationship to Job Posting Status

| Scenario | Job Posting Status | Application Status | Notes |
|----------|-------------------|-------------------|-------|
| User applies | Applied | Applied | Both update |
| Job expires during interviews | Expired | Interviewing | Application continues — user may still get hired |
| User gets rejected | (unchanged) | Rejected | Job may still be open for others |
| User accepts offer | (unchanged) | Accepted | Job likely filled but not our concern |

**Key insight:** Job Posting status is about the job's availability. Application status is about the user's journey. They're independent after initial linkage.

---

## 7. Workflow Integration

### 7.1 Application Creation

**Trigger:** Application record is created when user clicks "Mark as Applied" — AFTER external submission.

```
User decides to apply to Job Posting
    │
    ├── Selects or creates Job Variant
    │       │
    │       └── Job Variant must be Approved before proceeding
    │
    ├── (Optional) Cover Letter generated and Approved
    │
    ├── Downloads Resume PDF → Submitted Resume PDF created, stored
    │
    ├── (Optional) Downloads Cover Letter PDF → Submitted Cover Letter PDF created, stored
    │
    ├── Submits externally (outside system — ATS, email, etc.)
    │
    └── Returns to mark "Applied"
            │
            ├── Application record created
            │       ├── Links: Job Posting, Job Variant, Cover Letter (if exists)
            │       ├── Links: Submitted PDFs (created during download step)
            │       ├── Status = Applied
            │       └── applied_at = now
            │
            ├── Job Posting status → Applied
            │
            └── Timeline event: "Applied" (auto)
```

**Why create on "Mark Applied" not earlier?**
- User may abandon flow after downloading PDF
- Don't want phantom Application records for jobs never actually submitted
- Keeps Application list clean — only real applications

**Edge case:** User downloads PDF but forgets to mark Applied. Job Variant and Submitted PDFs exist but no Application. Agent can prompt: "You downloaded materials for Acme Corp 3 days ago. Did you submit the application?"
```

### 7.2 Status Updates

```
User reports status change (via chat or UI)
    │
    ├── Agent updates Application status
    │
    ├── Timeline event created (auto)
    │
    ├── If Offer → Agent prompts for offer details
    │
    ├── If Rejected → Agent prompts for rejection details
    │
    └── status_updated_at = now
```

### 7.3 Notes Population

```
User tells agent about application in chat
    │
    └── Agent extracts relevant info
            │
            ├── Updates notes field
            │
            ├── Creates timeline event if significant
            │
            └── Example: "I had my phone screen today, went well"
                    → Timeline: "Interview completed"
                    → Notes: appended with details
```

---

## 8. Agent Behavior

### 8.1 Follow-up Suggestions

Agent monitors timeline and suggests follow-ups:

> "It's been 7 days since your phone screen with Acme Corp and no response. Would you like me to draft a follow-up email?"

**Logic:** If last event was interview_completed and > 5 business days have passed with no subsequent event.

### 8.2 Pattern Analysis

Agent analyzes rejection data across applications:

> "I've noticed your last 3 rejections came at the onsite stage. Want to practice some interview scenarios?"

**Logic:** Query rejection_details.stage across recent applications, identify patterns.

### 8.3 Offer Comparison

When user has multiple offers:

> "You have 2 active offers. Acme Corp: $150k base, 15% bonus. TechCo: $140k base, $50k equity. Want me to break down the comparison?"

**Logic:** Query applications where status = Offer, present offer_details side by side.

---

## 9. Validation Rules

| Rule | Description |
|------|-------------|
| Job Variant must be approved | Cannot create Application with Draft Job Variant |
| Submitted PDFs required | Resume PDF must exist; Cover Letter optional |
| Valid status transitions | Only transitions defined in §6.2 allowed |
| Terminal status is final | Cannot change status after Accepted/Rejected/Withdrawn |
| Timeline events immutable | Once created, cannot be edited or deleted |

---

## 10. Retention Policy

| Status | Archive Trigger | Delete Trigger |
|--------|-----------------|----------------|
| Applied | 180 days with no activity | 365 days after archive |
| Interviewing | 180 days with no activity | 365 days after archive |
| Offer | 180 days with no activity | 365 days after archive |
| Accepted | 365 days after accepted | Never (career milestone) |
| Rejected | 90 days after rejected | 365 days after archive |
| Withdrawn | 90 days after withdrawn | 365 days after archive |

**Rationale:** 
- Active applications need longer retention (user may return)
- Accepted offers are career milestones — keep indefinitely
- Rejected/Withdrawn are learning data but less valuable over time
- All submitted PDFs retained as long as Application exists

---

## 11. Privacy & Security Notes

### 11.1 PII Fields

| Field | PII? | Notes |
|-------|------|-------|
| offer_details.base_salary | Yes | Sensitive compensation data |
| offer_details.equity_value | Yes | Sensitive compensation data |
| notes | Possibly | User may include contact names, emails |
| timeline descriptions | Possibly | May include interviewer names |

### 11.2 Data Handling

- Offer details encrypted at rest
- Notes field not used for search indexing (may contain PII)
- Submitted PDFs stored securely, not publicly accessible
- Timeline events may be excluded from LLM context if containing PII

---

## 12. Open Questions

| # | Question | Status |
|---|----------|--------|
| 1 | Max length for notes field? | TBD — suggest 10,000 chars |
| 2 | Should timeline events support attachments (screenshots, emails)? | TBD — defer to post-MVP |
| 3 | Notification system for status reminders? | TBD — agent-driven for MVP, may add push notifications later |

---

## 13. Design Decisions & Rationale

This section preserves context for implementation.

### 13.1 Status Lifecycle Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Interview status granularity | Multiple stages (Phone, Onsite, Final) / Single "Interviewing" status | Single "Interviewing" status | Keep it simple for MVP. Timeline events capture stage details. User doesn't need to update status multiple times during interview process. |
| Offer sub-states | Offer + Negotiating + Accepted/Declined / Offer + Accepted only | Offer + Accepted | "Negotiating" is just time spent in Offer state. Declined = Withdrawn. Simpler model. |

### 13.2 Data Capture Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Notes field approach | Structured fields / Free-form text / Hybrid | Free-form text, agent-populated | Maximum flexibility. Agent extracts from conversation, user doesn't fill forms. Can always add structure later if patterns emerge. |
| Offer details structure | Flat fields / JSONB / Separate table | JSONB | Offers vary widely. JSONB allows flexibility without schema changes. Not all fields apply to every offer. |
| Rejection tracking | None / Stage only / Stage + reason | Stage + optional reason/feedback | Enables pattern analysis ("rejected at onsite 4 times") while keeping capture lightweight. |

### 13.3 Timeline Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Timeline storage | Derived from status changes / Explicit event log / Both | Explicit event log | Status changes are just one type of event. User wants to record interviews, follow-ups, responses that don't change status. Richer history. |
| Event mutability | Editable / Immutable / Soft-delete | Immutable | Timeline is a historical record. Editing history is confusing. User can add clarifying events instead. |

### 13.4 Independence Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Application vs Job Posting lifecycle | Tightly coupled / Independent | Independent | Job can expire while user is interviewing. User may get hired from "expired" job. Application tracks user's journey, not job's availability. |

### 13.5 Agent Behavior Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Follow-up reminders | Schema-driven (reminder entity) / Agent-derived / Push notifications | Agent-derived | Agent can calculate from timeline without stored reminders. Simpler schema. Agent suggests, user decides. No notification infrastructure needed for MVP. |

### 13.6 Relationship Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Cover Letter relationship | Part of Job Variant / Linked to Application / Standalone | Linked to Application directly | Cover Letter is not part of resume. They're generated separately, can exist independently. Job Variant is resume-only. Application links both. |
| Job Variant cardinality | 1:many (reuse) / 1:1 (unique per Application) | 1:1 | Each Application gets its own Job Variant. Cleaner audit trail. If reapplying to reposted job, user creates new variant (can copy from old). No confusion about which version was submitted. |
| Submitted PDF bidirectional FK | One direction only / Bidirectional | Bidirectional | Application → Submitted PDF (primary, for querying "what did I submit"). Submitted PDF → Application (for referential integrity, cascading deletes). Both directions useful. |

### 13.7 Creation Trigger Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| When to create Application | On "Start Application" / On PDF download / On "Mark Applied" | On "Mark Applied" | Avoid phantom records from abandoned flows. Keep Application list clean — only real submissions. Agent can prompt if user forgets to mark Applied after downloading. |

### 13.8 Interview Stage Tracking Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Stage tracking mechanism | Separate status values / `current_interview_stage` field / Timeline metadata only | Field + Timeline metadata | Single "Interviewing" status keeps lifecycle simple. `current_interview_stage` field tracks where user is now. Timeline events record stage for each interview. Rejection stage derived from current or last timeline. Best of both worlds. |

### 13.9 Reapplication Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Reapply to same job | Allow unlimited / Allow after cooldown / Block | Block — one Application per Job Posting | Prevents spam. If rejected, reapplying to same posting won't help. User can apply to reposts (new Job Posting ID). Keeps data clean. |
| Reapply to repost | Treat as same job / Treat as new opportunity | New opportunity | Reposts are new Job Posting records (REQ-003 §8). User may have improved skills, company may have different needs. Fresh chance. Agent provides historical context to inform decision. |

### 13.10 PDF Timing Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| When to create Submitted PDF | On "Mark Applied" (with Application) / On PDF download (before Application) | On PDF download | User needs PDF file to submit externally. Can't wait until "Mark Applied" — file would be too late. Create PDF when downloaded, link to Application later. |
| Handling orphan PDFs | Require Application first / Optional `application_id` + cleanup / Delete on browser close | Optional `application_id` + 7-day cleanup job | PDFs exist before Application. Make `application_id` optional, set when user marks Applied. Orphans (downloaded but never applied) cleaned up after 7 days. Simple, handles abandoned flows. |

---

## 14. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2025-01-25 | 0.1 | Initial draft from discovery interview |
| 2025-01-25 | 0.2 | Added: `cover_letter_id` and `current_interview_stage` fields. Added `interview_stage` to Timeline Event. Clarified bidirectional FK relationships. Clarified Application creation trigger (on "Mark Applied"). Added cardinality rules (1:1 for Job Variant). Added reapplication scenarios (§4.1b). Updated dependency cross-references. Added Decision Log entries for relationships, creation trigger, interview stage, and reapplication. |
| 2025-01-25 | 0.3 | Fixed PDF timing issue: `application_id` on Submitted PDFs is Optional (NULL until user marks Applied). Added linking flow diagram (§4.2). Added orphan cleanup note (7-day purge). Added §13.10 PDF Timing Decisions. Cross-updated REQ-002 §4.4 and REQ-002b §4.2 to match. |
| 2025-01-25 | 0.4 | Added missing fields to Application table (§4.1): `offer_details`, `rejection_details`, `submitted_resume_pdf_id`, `submitted_cover_letter_pdf_id`. Fields were documented in subsections but not in main table. |
