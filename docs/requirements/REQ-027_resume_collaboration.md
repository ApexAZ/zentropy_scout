# REQ-027: Resume Collaboration & AI-Assisted Editing

**Status:** Draft
**Version:** 0.1
**PRD Reference:** §4.4 Ghostwriter, §8 Document Management
**Last Updated:** 2026-03-04

---

## 1. Overview

This document specifies the job variant workflow for resumes: job variant creation (LLM-tailored and manual), the diff view (showing what the ghostwriter changed), the variant review and approval workflow, and the ghostwriter's tailoring integration for markdown resumes. These features build on the TipTap editor (REQ-025) and the editing workflow (REQ-026).

**Key Principle:** The user always reviews what the LLM changed before approving. Variants are drafts until explicitly approved.

**Deferred to Chat Agent PBI:** Chat-driven document editing (§3 in v0.1) — where the user modifies resumes through natural language conversation — is deferred to the broader chat agent implementation (backlog item #11). The chat agent will have tool access to resume editing as one of its capabilities, alongside access to personas, jobs, applications, and other system features. This avoids building chat infrastructure twice.

### 1.1 Scope

| In Scope | Out of Scope |
|----------|--------------|
| Job variant creation from master resume | TipTap editor component (REQ-025) |
| Ghostwriter tailoring for job fit | LLM resume generation from scratch (REQ-026) |
| Diff view between master and variant | Chat-driven document editing (deferred to Chat Agent PBI) |
| Variant review and approval workflow | Collaborative multi-user editing |
| Variant editing in TipTap | Cover letter editing (separate feature) |
| Job requirements reference panel | Template system (REQ-025) |

### 1.2 Design Principles

| Principle | Description | Enforcement |
|-----------|-------------|-------------|
| **Transparent Changes** | User always sees what the LLM changed | Diff view for variants shows additions, removals, modifications |
| **Human Approval** | No variant is finalized without user review | Draft → user review → Approve/Reject workflow |
| **Non-Destructive Variants** | Master resume is never modified by variant creation | Variants copy and modify; master remains unchanged |

---

## 2. Dependencies

### 2.1 This Document Depends On

| Dependency | Type | Notes |
|------------|------|-------|
| REQ-001 Persona Schema v0.8 | Data source | Persona data for content constraints |
| REQ-002 Resume Schema v0.7 | Entity definitions | BaseResume, JobVariant, snapshot behavior |
| REQ-003 Job Posting Schema v0.4 | Entity definitions | Job requirements for tailoring |
| REQ-025 TipTap Editor v0.1 | Editor component | Editor, markdown storage, export |
| REQ-026 Resume Editing Workflow v0.1 | Editing patterns | Generation, auto-save, reference panel |
| REQ-010 Content Generation v0.1 | Generation rules | Modification limits, truthfulness constraints |
| REQ-018 Ghostwriter Service v1.0 | Service layer | ContentGenerationService for tailoring |

### 2.2 Other Documents Depend On This

| Document | Dependency | Notes |
|----------|------------|-------|
| (None currently) | — | — |

---

## 3. Job Variant Creation

### 4.1 Two Paths to Job Variant

| Path | Trigger | Process |
|------|---------|---------|
| **With LLM** | User clicks "Draft Resume" on job detail page (or ghostwriter auto-triggers above threshold) | Ghostwriter picks best master, tailors for job, loads into TipTap with diff |
| **Without LLM** | User clicks "Create Variant" on job detail page and selects a master resume | Master resume's markdown loaded into TipTap; user edits manually for fit |

### 4.2 LLM Variant Creation Flow

```
User clicks [Draft Resume] on job detail page
    │
    ├── Backend: ContentGenerationService.generate()
    │   ├── Select best-matching base resume (role_type + scoring)
    │   ├── Evaluate tailoring need (keyword gaps, bullet relevance)
    │   ├── If tailoring needed:
    │   │   ├── LLM generates tailored markdown from master's markdown_content
    │   │   ├── Validate against modification limits
    │   │   └── Save as JobVariant (Draft) with markdown_content
    │   └── If no tailoring: create variant with master's markdown_content unchanged
    │
    ├── Navigate to variant review page
    │   ├── Show diff view (§5)
    │   ├── Show agent reasoning
    │   └── TipTap editor (editable in Draft status)
    │
    └── User reviews → edits → approves
```

### 4.3 Manual Variant Creation Flow

```
User clicks [Create Variant] on job detail page
    │
    ├── Select which master resume to base it on
    │
    ├── JobVariant created (Draft) with markdown_content = master's markdown_content
    │
    ├── Navigate to variant editor
    │   ├── TipTap editor with variant's markdown
    │   ├── Persona reference panel (same as REQ-026 §5)
    │   ├── Job posting requirements panel (§4.4)
    │   └── No diff view (no LLM changes to show)
    │
    └── User edits for job fit → approves
```

### 4.4 Job Requirements Panel

When editing a job variant (LLM or manual), a panel shows the job posting's key requirements:

```
┌────────────────────────────────┐
│ Job Requirements               │
│                                │
│ Scrum Master at Acme Corp      │
│                                │
│ Key Skills:                    │
│ • SAFe certification           │
│ • Scaled Agile experience      │
│ • CI/CD pipeline knowledge     │
│ • Team leadership (10+ ppl)    │
│                                │
│ Keywords to Include:           │
│ • "scaled Agile" (3x in post)  │
│ • "cross-functional" (2x)      │
│ • "stakeholder management"     │
│                                │
│ Fit Score: 87% (Strong)        │
│                                │
└────────────────────────────────┘
```

This panel helps the user (manual path) or the LLM (assisted path) understand what the job emphasizes.

### 3.5 Variant Editing

Job variants in Draft status can be edited directly in TipTap (same toggle view pattern as base resumes — REQ-026 §6.1). The variant editor includes the Job Requirements Panel (§3.4) alongside the Persona Reference Panel (REQ-026 §5).

**Chat-driven variant editing** (e.g., "Emphasize my SAFe experience more", "Rewrite the summary to match the job's language") is **deferred to the Chat Agent PBI**. The chat agent will have job posting context available when editing variants, enabling job-aware conversational editing.

---

## 4. Diff View

### 4.1 When to Show Diff

The diff view is shown when reviewing an LLM-generated job variant. It compares the base resume's markdown with the variant's markdown.

| Scenario | Show Diff? |
|----------|-----------|
| LLM-generated variant (Draft) | Yes |
| Manually created variant | No (no LLM changes to compare) |
| Approved variant | Yes (compare snapshot against base) |
| Base resume editing | No |

### 4.2 Diff View Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│ Resume Variant: Scrum Master at Acme Corp              Draft ⏳     │
├─────────────────────────────┬────────────────────────────────────────┤
│ Master Resume               │ Tailored Variant                       │
│ (read-only)                 │ (editable in TipTap)                  │
├─────────────────────────────┼────────────────────────────────────────┤
│                             │                                        │
│ ## Professional Summary     │ ## Professional Summary                │
│                             │                                        │
│ Experienced Scrum Master    │ Experienced Scrum Master with 8       │
│ with 8 years of             │ years in [scaled Agile]               │
│ experience in Agile         │ environments, specializing in          │
│ environments...             │ [SAFe implementation]...               │
│                             │    ↑ additions highlighted green       │
│                             │                                        │
│ ### TechCorp                │ ### TechCorp                           │
│ - Led team of 12            │ - [Implemented SAFe across 3 teams]   │
│ - Reduced cycle time        │    ↑ moved up, highlighted blue       │
│ - Improved velocity by 25%  │ - Led team of 12 engineers            │
│ - Implemented SAFe          │ - Reduced cycle time by 40%           │
│                             │ - Improved velocity by 25%            │
│                             │                                        │
└─────────────────────────────┴────────────────────────────────────────┘

Agent Reasoning:
"The job posting mentions 'SAFe' 3 times and 'scaled Agile' 2 times.
I moved your SAFe implementation bullet to position 1 and added
'scaled Agile' to the summary to improve keyword alignment."

[Approve]  [Regenerate]  [Edit]  [Archive]
```

### 4.3 Diff Highlighting

| Change Type | Visual Treatment | Description |
|-------------|-----------------|-------------|
| Addition | Green background | Text added that wasn't in master |
| Removal | Red strikethrough | Text removed from master |
| Modification | Yellow background | Text that was rephrased |
| Reorder | Blue background + position indicator | Bullets/sections that moved |

### 4.4 Diff Implementation

**Approach:** Word-level diff between the master's markdown and the variant's markdown.

| Step | Implementation |
|------|---------------|
| 1 | Split both documents into words |
| 2 | Compute word-level diff (longest common subsequence) |
| 3 | Group consecutive changes into change spans |
| 4 | Render both documents with change highlighting |

**Library consideration:** Use a JavaScript diff library (e.g., `diff` npm package) for client-side computation. The diff is purely for display — the canonical content is the variant's markdown.

### 4.5 Diff View Actions

| Action | Behavior | Available When |
|--------|----------|---------------|
| Approve | Sets variant status to Approved; snapshots all fields | Draft status |
| Regenerate | Opens generation options; creates new variant draft | Draft status |
| Edit | Switches to full TipTap editor (no split view) | Draft status |
| Archive | Archives the variant | Draft or Approved |
| Export PDF | Exports variant markdown to PDF | Any status |
| Export DOCX | Exports variant markdown to DOCX | Any status |

---

## 5. Variant Review and Approval

### 5.1 Approval Flow

```
Variant created (Draft)
    │
    ├── User reviews in diff view (§4)
    │
    ├── User optionally edits directly in TipTap
    │
    ├── User clicks [Approve]
    │       │
    │       ├── Confirmation dialog: "Approve this variant? It will be
    │       │    locked for editing."
    │       │
    │       ├── Backend:
    │       │   ├── Set status = 'Approved'
    │       │   ├── Set approved_at = now()
    │       │   ├── Snapshot markdown_content → snapshot_markdown_content
    │       │   ├── Snapshot all JSONB fields (existing behavior)
    │       │   └── Variant becomes read-only
    │       │
    │       └── Frontend:
    │           ├── Editor switches to read-only mode
    │           ├── Status badge: "Approved"
    │           └── Export buttons remain active
    │
    └── Approved variant linked to job for application
```

### 5.2 Post-Approval Behavior

| Action | Allowed? | Notes |
|--------|----------|-------|
| View | Yes | Read-only in TipTap or diff view |
| Export PDF/DOCX | Yes | From `snapshot_markdown_content` |
| Edit | No | Approved variants are immutable |
| Create new variant | Yes | Archives old variant, creates new Draft |
| Archive | Yes | Removes from active view |

### 5.3 Variant State Machine

```
           ┌─────────────────────────┐
           │                         │
  Create ──→  Draft                  │
           │  (editable,             │
           │   diff view available)  │
           │                         │
           └─────┬────────┬──────────┘
                 │        │
          Approve│        │Archive
                 │        │
                 ▼        ▼
           ┌──────────┐  ┌──────────┐
           │ Approved  │  │ Archived │
           │ (locked,  │  │ (hidden) │
           │  export)  │  │          │
           └─────┬─────┘  └──────────┘
                 │
                 │Archive
                 ▼
           ┌──────────┐
           │ Archived │
           └──────────┘
```

---

## 6. Integration with Existing Ghostwriter

### 6.1 ContentGenerationService Changes

The existing `ContentGenerationService` (REQ-018) needs updates to support markdown resumes:

| Step in Pipeline | Current Behavior | Updated Behavior |
|-----------------|------------------|------------------|
| 2. Select base resume | Selects by role_type match | Same; checks for `markdown_content` |
| 4. Create job variant | Reorders JSONB bullet selections | If base has `markdown_content`: LLM receives master's markdown, returns tailored markdown. If no markdown (legacy): falls back to JSONB reordering. |
| 6. Generate cover letter | Unchanged | Unchanged |
| 8. Build review response | Returns JSONB modifications description | Also returns tailored markdown + diff summary |

### 6.2 LLM Tailoring Prompt (Markdown Resumes)

When the base resume has `markdown_content`, the tailoring prompt:

| Component | Content |
|-----------|---------|
| System prompt | "You are a resume tailoring expert. Modify the resume to better match the job requirements while preserving the user's voice and factual accuracy." |
| Input: resume markdown | Base resume's `markdown_content` |
| Input: job requirements | Job posting title, description, key skills, keywords |
| Input: tailoring analysis | Keyword gaps, bullet relevance scores from `tailoring_decision.py` |
| Input: modification limits | Allowed: reorder, rephrase emphasis, adjust keywords. Forbidden: add new content, fabricate, remove sections. |
| Output format | Complete tailored markdown document |

### 6.3 Backwards Compatibility

| Resume State | Tailoring Behavior |
|------------|-------------------|
| Has `markdown_content` | New behavior — LLM receives full markdown, returns tailored markdown |
| No `markdown_content` (legacy) | Existing behavior — JSONB bullet reordering, summary adjustment |

Both paths produce a JobVariant. Markdown variants use `snapshot_markdown_content` on approval. Legacy variants use JSONB snapshot fields.

---

## 7. Validation Rules

| Rule | Description |
|------|-------------|
| Variant requires job posting | JobVariant must reference a valid, non-archived job posting |
| Variant requires base resume | JobVariant must reference a valid, non-archived base resume |
| Approval requires content | Cannot approve variant with empty `markdown_content` |
| Diff requires both documents | Diff view needs both master and variant markdown to be non-NULL |
| Modification limits apply to LLM tailoring | Variant tailoring enforces REQ-010 constraints |
| LLM tailoring requires credits | If insufficient balance, return 402. Offer manual variant creation as fallback. |

---

## 8. Error Handling

| Scenario | User Experience |
|----------|-----------------|
| Variant tailoring LLM fails | Toast: "Could not tailor resume. Try again or edit manually." Variant stays as copy of master. |
| Diff computation fails | Fallback: show variant without diff highlighting. Toast: "Diff unavailable." |
| Approval fails (server error) | Toast: "Approval failed. Please try again." Variant stays in Draft. |
| Concurrent edit conflict | 409 Conflict — "Resume was modified. Reload to see latest changes." |

---

## 9. Open Questions

| # | Question | Status |
|---|----------|--------|
| 1 | Should the diff view support inline editing (edit directly in the diff)? | **DECIDED: No** — diff is for review. Click [Edit] to switch to full editor. Keeps diff view simple. |
| 2 | Chat-driven editing scope and architecture? | **Deferred to Chat Agent PBI** — backlog item #11. Chat agent will have tool access to resume editing alongside other system features. |

---

## 10. Design Decisions & Rationale

### 10.1 Diff View

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Diff algorithm | Line-level / Word-level / Character-level | Word-level | Line-level is too coarse for resume content (misses rephrased sentences). Character-level is too noisy (highlights every small change). Word-level shows meaningful changes clearly. |
| Diff computation | Server-side / Client-side | Client-side | Diff is a display concern. Client-side avoids a round-trip. Resume documents are small (<50KB) — diff computation is instant. Library: `diff` npm package. |
| Diff and edit | Side-by-side with inline edit / Separate modes | Separate modes | Editing inside a diff view is complex (need to re-diff on every keystroke). Cleaner UX: review in diff view, click [Edit] for full editor. Mode switching is one click. |

### 10.2 Variant Tailoring

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Tailoring for markdown resumes | JSONB-based (current) / Full markdown rewrite / Hybrid | Full markdown rewrite | JSONB-based tailoring (reorder bullets, adjust summary) doesn't apply to free-form markdown. The LLM needs the full document to tailor effectively — adjusting keywords throughout, rephrasing for emphasis, reordering sections. The modification limits still constrain what the LLM can change. |
| Variant content source | Always inherit master / Copy on creation | Copy on creation | Variants get their own `markdown_content` at creation time. This decouples them from the master — master edits don't affect existing variants. Aligns with the existing snapshot-on-approval pattern but extends it to creation. |

---

## 11. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-04 | 0.1 | Initial draft. Chat-driven editing, job variant workflow, diff view, ghostwriter integration. |
| 2026-03-05 | 0.2 | Audit review: Deferred chat-driven editing (§3 in v0.1) to Chat Agent PBI (backlog #11). Removed `content_mode` references — resumes with `markdown_content` use markdown path, legacy resumes use JSONB path. Renumbered sections. Added credit gating for LLM tailoring. |
