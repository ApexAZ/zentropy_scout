# REQ-027: Resume Collaboration & AI-Assisted Editing

**Status:** Draft
**Version:** 0.1
**PRD Reference:** §4.4 Ghostwriter, §8 Document Management
**Last Updated:** 2026-03-04

---

## 1. Overview

This document specifies the collaborative editing features for resumes: chat-driven document editing (the LLM modifies the resume through conversation), the job variant diff view (showing what the ghostwriter changed), and the ghostwriter's tailoring workflow for job-specific resumes. These features build on the TipTap editor (REQ-025) and the editing workflow (REQ-026).

**Key Principle:** The user has two editing channels — direct editing in TipTap and conversational editing through chat. Both channels operate on the same markdown document, and changes from either channel appear immediately in the editor.

### 1.1 Scope

| In Scope | Out of Scope |
|----------|--------------|
| Chat-driven document editing (LLM edits via conversation) | TipTap editor component (REQ-025) |
| Job variant creation from master resume | LLM resume generation from scratch (REQ-026) |
| Ghostwriter tailoring for job fit | Manual resume creation flow (REQ-026) |
| Diff view between master and variant | Collaborative multi-user editing |
| Variant review and approval workflow | Cover letter editing (separate feature) |
| Two-channel editing (direct + chat) | Template system (REQ-025) |

### 1.2 Design Principles

| Principle | Description | Enforcement |
|-----------|-------------|-------------|
| **Two Channels, One Document** | Chat edits and direct edits operate on the same markdown | Chat updates push into TipTap; TipTap content sent as context with chat |
| **Transparent Changes** | User always sees what the LLM changed | Diff view for variants; change description for chat edits |
| **Human Approval** | No variant is finalized without user review | Draft → user review → Approve/Reject workflow |
| **Non-Destructive Variants** | Master resume is never modified by variant creation | Variants copy and modify; master remains unchanged |
| **Contextual Chat** | Chat agent has full document context | Current markdown sent with each chat message |

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

## 3. Chat-Driven Document Editing

### 3.1 Concept

The user can modify their resume through natural language commands in the chat interface. The chat agent receives the current resume markdown as context, processes the user's request, and returns updated markdown that replaces the editor content.

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  ┌─────────────────────────────────┬───────────────────────────────┐│
│  │                                 │                               ││
│  │   TipTap Editor                 │   Chat Panel                  ││
│  │                                 │                               ││
│  │   # John Smith                  │   You: Make the summary       ││
│  │                                 │   more concise and emphasize  ││
│  │   ## Professional Summary       │   leadership experience       ││
│  │                                 │                               ││
│  │   Experienced Scrum Master...   │   AI: I've updated your       ││
│  │                                 │   summary to be more concise  ││
│  │   (content updates in           │   and highlight your          ││
│  │    real-time when AI responds)  │   leadership roles. Here's    ││
│  │                                 │   what I changed:             ││
│  │                                 │   - Shortened from 3          ││
│  │                                 │     sentences to 2            ││
│  │                                 │   - Added "Led cross-         ││
│  │                                 │     functional teams of       ││
│  │                                 │     up to 50 engineers"       ││
│  │                                 │                               ││
│  └─────────────────────────────────┴───────────────────────────────┘│
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Chat Edit Flow

```
User types edit request in chat
    │
    ├── Frontend sends message + current editor markdown to backend
    │
    ├── Backend:
    │   ├── Parse user intent (edit scope: section, paragraph, full doc)
    │   ├── Send to LLM with resume markdown + edit instruction
    │   ├── LLM returns updated markdown
    │   └── Validate: modification limits, truthfulness
    │
    ├── Backend responds with:
    │   ├── Updated markdown content
    │   ├── Change description (what was modified and why)
    │   └── Sections affected
    │
    ├── Frontend:
    │   ├── Loads updated markdown into TipTap editor
    │   ├── Shows change description in chat
    │   └── User can undo (Ctrl+Z) to revert
    │
    └── Auto-save triggers for the updated content
```

### 3.3 Chat Edit Request Types

| Intent | Example | LLM Behavior |
|--------|---------|-------------|
| Section edit | "Make the summary more concise" | Rewrites only the Professional Summary section |
| Bullet edit | "Add a bullet about my Kubernetes migration project" | Adds bullet to relevant work history section |
| Reorder | "Move the SAFe bullet to the top of TechCorp" | Reorders bullets within the specified job |
| Emphasis | "Emphasize leadership over technical skills" | Adjusts language throughout to highlight leadership |
| Tone | "Make it more formal" | Adjusts voice/tone across the document |
| Remove | "Remove the certifications section" | Deletes the specified section |
| Length | "Shorten to fit one page" | Trims content across sections proportionally |
| Add section | "Add a Projects section" | Inserts new heading with placeholder content |

### 3.4 Context Sent to LLM

Each chat edit request sends:

| Context Item | Source | Purpose |
|-------------|--------|---------|
| Current markdown | TipTap editor content | Full document for LLM to modify |
| User's message | Chat input | Edit instruction |
| Persona data summary | Persona API | Available facts for content generation |
| Voice Profile | REQ-001 §3.7 | Maintain consistent tone |
| Modification limits | REQ-010 | Constraints: no fabrication, persona-sourced only |
| Conversation history | Chat session | Previous edit requests for continuity |

### 3.5 Chat Edit API

**Endpoint:** `POST /base-resumes/{id}/chat-edit`

**Request body:**
```json
{
  "message": "Make the summary more concise and emphasize leadership",
  "current_markdown": "# John Smith\n\n## Professional Summary\n\nExperienced...",
  "conversation_id": "uuid"
}
```

**Response:**
```json
{
  "updated_markdown": "# John Smith\n\n## Professional Summary\n\nResults-driven...",
  "change_description": "Shortened summary from 3 sentences to 2. Added emphasis on team leadership and cross-functional collaboration.",
  "sections_affected": ["Professional Summary"],
  "model_used": "gemini-2.0-flash",
  "generation_cost_cents": 0
}
```

### 3.6 Chat Edit Constraints

| Constraint | Enforcement |
|------------|-------------|
| No fabrication | LLM may only use facts from persona data |
| Persona-sourced content | New bullets must reference actual persona work history |
| Voice consistency | Edits maintain the Voice Profile |
| Structural integrity | Output must be valid markdown with proper heading hierarchy |
| Length bounds | Content must stay within markdown max size (50KB) |

### 3.7 Chat Edit Undo

When the chat makes changes, the full document replacement is pushed as a single TipTap transaction. This means:

- **Ctrl+Z** reverts the entire chat edit in one step
- The user can undo, tweak manually, then continue chatting
- Chat and manual edits interleave naturally in the undo stack

---

## 4. Job Variant Creation

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

### 4.5 Variant Edit with Chat

Job variants also support chat-driven editing (§3). The chat context includes the job posting requirements in addition to the standard context:

| Additional Context | Source | Purpose |
|-------------------|--------|---------|
| Job posting summary | REQ-003 | Job requirements, keywords, culture signals |
| Fit score analysis | REQ-008 | Gaps and stretch areas to address |
| Base resume markdown | BaseResume | Reference for diff comparison |

Example chat interactions during variant editing:
- "Emphasize my SAFe experience more"
- "Add a bullet about the CI/CD pipeline I built"
- "Rewrite the summary to match the job's language about 'scaled Agile'"

---

## 5. Diff View

### 5.1 When to Show Diff

The diff view is shown when reviewing an LLM-generated job variant. It compares the base resume's markdown with the variant's markdown.

| Scenario | Show Diff? |
|----------|-----------|
| LLM-generated variant (Draft) | Yes |
| Manually created variant | No (no LLM changes to compare) |
| Approved variant | Yes (compare snapshot against base) |
| Base resume editing | No |

### 5.2 Diff View Layout

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

### 5.3 Diff Highlighting

| Change Type | Visual Treatment | Description |
|-------------|-----------------|-------------|
| Addition | Green background | Text added that wasn't in master |
| Removal | Red strikethrough | Text removed from master |
| Modification | Yellow background | Text that was rephrased |
| Reorder | Blue background + position indicator | Bullets/sections that moved |

### 5.4 Diff Implementation

**Approach:** Word-level diff between the master's markdown and the variant's markdown.

| Step | Implementation |
|------|---------------|
| 1 | Split both documents into words |
| 2 | Compute word-level diff (longest common subsequence) |
| 3 | Group consecutive changes into change spans |
| 4 | Render both documents with change highlighting |

**Library consideration:** Use a JavaScript diff library (e.g., `diff` npm package) for client-side computation. The diff is purely for display — the canonical content is the variant's markdown.

### 5.5 Diff View Actions

| Action | Behavior | Available When |
|--------|----------|---------------|
| Approve | Sets variant status to Approved; snapshots all fields | Draft status |
| Regenerate | Opens generation options; creates new variant draft | Draft status |
| Edit | Switches to full TipTap editor (no split view) | Draft status |
| Archive | Archives the variant | Draft or Approved |
| Export PDF | Exports variant markdown to PDF | Any status |
| Export DOCX | Exports variant markdown to DOCX | Any status |

---

## 6. Variant Review and Approval

### 6.1 Approval Flow

```
Variant created (Draft)
    │
    ├── User reviews in diff view (§5)
    │
    ├── User optionally edits (direct or chat)
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

### 6.2 Post-Approval Behavior

| Action | Allowed? | Notes |
|--------|----------|-------|
| View | Yes | Read-only in TipTap or diff view |
| Export PDF/DOCX | Yes | From `snapshot_markdown_content` |
| Edit | No | Approved variants are immutable |
| Create new variant | Yes | Archives old variant, creates new Draft |
| Archive | Yes | Removes from active view |

### 6.3 Variant State Machine

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

## 7. Integration with Existing Ghostwriter

### 7.1 ContentGenerationService Changes

The existing `ContentGenerationService` (REQ-018) needs updates to support markdown-mode resumes:

| Step in Pipeline | Current Behavior | Updated Behavior |
|-----------------|------------------|------------------|
| 2. Select base resume | Selects by role_type match | Same; also checks `content_mode` |
| 4. Create job variant | Reorders JSONB bullet selections | If `content_mode = 'markdown'`: LLM receives master's markdown, returns tailored markdown |
| 6. Generate cover letter | Unchanged | Unchanged |
| 8. Build review response | Returns JSONB modifications description | Also returns tailored markdown + diff summary |

### 7.2 LLM Tailoring Prompt (Markdown Mode)

When the base resume is in `content_mode = 'markdown'`, the tailoring prompt changes:

| Component | Content |
|-----------|---------|
| System prompt | "You are a resume tailoring expert. Modify the resume to better match the job requirements while preserving the user's voice and factual accuracy." |
| Input: resume markdown | Base resume's `markdown_content` |
| Input: job requirements | Job posting title, description, key skills, keywords |
| Input: tailoring analysis | Keyword gaps, bullet relevance scores from `tailoring_decision.py` |
| Input: modification limits | Allowed: reorder, rephrase emphasis, adjust keywords. Forbidden: add new content, fabricate, remove sections. |
| Output format | Complete tailored markdown document |

### 7.3 Backwards Compatibility

| Resume Mode | Tailoring Behavior |
|------------|-------------------|
| `content_mode = 'structured'` | Existing behavior — JSONB bullet reordering, summary adjustment |
| `content_mode = 'markdown'` | New behavior — markdown tailoring via LLM |

Both paths produce a JobVariant. The variant inherits the base resume's `content_mode`. Structured variants use JSONB snapshot fields; markdown variants use `snapshot_markdown_content`.

---

## 8. Validation Rules

| Rule | Description |
|------|-------------|
| Chat edit requires active resume | Cannot chat-edit an archived or approved resume |
| Chat edit size limit | Single chat edit cannot increase content by more than 5KB |
| Variant requires job posting | JobVariant must reference a valid, non-archived job posting |
| Variant requires base resume | JobVariant must reference a valid, non-archived base resume |
| Approval requires content | Cannot approve variant with empty `markdown_content` |
| Diff requires both documents | Diff view needs both master and variant markdown to be non-NULL |
| Modification limits apply to LLM edits | Chat and variant tailoring both enforce REQ-010 constraints |

---

## 9. Error Handling

| Scenario | User Experience |
|----------|-----------------|
| Chat edit LLM fails | Toast: "Edit failed. Your document is unchanged." Chat shows error message. |
| Chat edit returns invalid markdown | Backend validates and rejects; toast: "Edit produced invalid content. Try rephrasing." |
| Variant tailoring LLM fails | Toast: "Could not tailor resume. Try again or edit manually." Variant stays as copy of master. |
| Diff computation fails | Fallback: show variant without diff highlighting. Toast: "Diff unavailable." |
| Approval fails (server error) | Toast: "Approval failed. Please try again." Variant stays in Draft. |
| Concurrent edit conflict | 409 Conflict — "Resume was modified. Reload to see latest changes." |

---

## 10. Open Questions

| # | Question | Status |
|---|----------|--------|
| 1 | Should chat edits show a preview diff before applying? | TBD — adds complexity but increases trust. Consider for post-MVP. |
| 2 | Should the diff view support inline editing (edit directly in the diff)? | **DECIDED: No** — diff is for review. Click [Edit] to switch to full editor. Keeps diff view simple. |
| 3 | Should variant chat have access to the base resume for context? | **DECIDED: Yes** — the base resume markdown is included in chat context so the LLM can reference what was changed and why. |
| 4 | Rate limit on chat edits? | TBD — consider per-minute limit to prevent accidental rapid-fire LLM calls |
| 5 | Should chat-driven editing work for cover letters too? | Deferred — scoped to resumes for now. Cover letter chat editing as separate feature. |

---

## 11. Design Decisions & Rationale

### 11.1 Chat Edit Architecture

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Edit granularity | Section-level replacement / Full document replacement | Full document replacement | LLM returns the complete updated document. This is simpler than tracking which sections changed, handles cross-section edits naturally, and the full document replacement is a single TipTap transaction (atomic undo). Section-level would require parsing and merging. |
| Edit application | Immediate / Preview-then-apply | Immediate with undo | Preview adds an extra confirmation step that slows the conversational flow. Undo (Ctrl+Z) provides a safety net. If users want to compare, they can undo and redo. Preview mode as post-MVP enhancement. |

### 11.2 Diff View

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Diff algorithm | Line-level / Word-level / Character-level | Word-level | Line-level is too coarse for resume content (misses rephrased sentences). Character-level is too noisy (highlights every small change). Word-level shows meaningful changes clearly. |
| Diff computation | Server-side / Client-side | Client-side | Diff is a display concern. Client-side avoids a round-trip. Resume documents are small (<50KB) — diff computation is instant. Library: `diff` npm package. |
| Diff and edit | Side-by-side with inline edit / Separate modes | Separate modes | Editing inside a diff view is complex (need to re-diff on every keystroke). Cleaner UX: review in diff view, click [Edit] for full editor. Mode switching is one click. |

### 11.3 Variant Tailoring

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Tailoring for markdown mode | JSONB-based (current) / Full markdown rewrite / Hybrid | Full markdown rewrite | JSONB-based tailoring (reorder bullets, adjust summary) doesn't apply to free-form markdown. The LLM needs the full document to tailor effectively — adjusting keywords throughout, rephrasing for emphasis, reordering sections. The modification limits still constrain what the LLM can change. |
| Variant content source | Always inherit master / Copy on creation | Copy on creation | Variants get their own `markdown_content` at creation time. This decouples them from the master — master edits don't affect existing variants. Aligns with the existing snapshot-on-approval pattern but extends it to creation for markdown mode. |

---

## 12. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-04 | 0.1 | Initial draft. Chat-driven editing, job variant workflow, diff view, ghostwriter integration. |
