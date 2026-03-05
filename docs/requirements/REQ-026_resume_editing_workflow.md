# REQ-026: Resume Editing Workflow

**Status:** Draft
**Version:** 0.1
**PRD Reference:** §8 Document Management, §4.4 Ghostwriter
**Last Updated:** 2026-03-04

---

## 1. Overview

This document specifies how users create and edit resumes using the TipTap editor (REQ-025). It covers two primary paths: LLM-assisted generation (the system composes a resume from persona data) and manual editing (the user writes directly with persona data as reference). Both paths produce markdown content in TipTap that can be exported to PDF/DOCX.

**Key Principle:** The user is always in control. LLM generates a draft; the user edits, approves, and exports. The system never finalizes content without explicit user action.

### 1.1 Scope

| In Scope | Out of Scope |
|----------|--------------|
| LLM resume generation into TipTap | TipTap editor component itself (REQ-025) |
| Manual resume editing with persona reference panel | Chat-driven editing commands (REQ-027) |
| Page limit control for LLM generation | Job variant diff view (REQ-027) |
| Structured → TipTap conversion flow | Ghostwriter job-specific tailoring (REQ-027) |
| Master resume creation (new + from existing) | Export pipeline details (REQ-025 §5) |
| Content mode transition (structured → markdown) | Template system details (REQ-025 §6) |

### 1.2 Design Principles

| Principle | Description | Enforcement |
|-----------|-------------|-------------|
| **Generate Then Edit** | LLM produces complete draft; user refines | No streaming into editor at MVP; full content loaded when ready |
| **Persona as Source** | All LLM-generated content originates from persona data | Prompt includes persona data; modification limits enforced |
| **Page Awareness** | Users control output length | Page limit parameter sent to LLM; word count shown in editor |
| **Dual Channel** | Both LLM and manual paths produce the same output format | Both result in markdown in TipTap; same export pipeline |
| **Non-Destructive** | Editing never loses the original generation | Previous versions accessible through resume versioning |

---

## 2. Dependencies

### 2.1 This Document Depends On

| Dependency | Type | Notes |
|------------|------|-------|
| REQ-001 Persona Schema v0.8 | Data source | All persona fields used for resume content |
| REQ-002 Resume Schema v0.7 | Entity definitions | BaseResume lifecycle, content fields |
| REQ-025 TipTap Editor v0.1 | Editor component | TipTap editor, markdown storage, export pipeline |
| REQ-010 Content Generation v0.1 | Generation rules | Modification limits, truthfulness constraints |
| REQ-018 Ghostwriter Service v1.0 | Generation service | ContentGenerationService for LLM calls |

### 2.2 Other Documents Depend On This

| Document | Dependency | Notes |
|----------|------------|-------|
| REQ-027 Resume Collaboration | Editing workflow | Chat-driven editing extends the patterns defined here |

---

## 3. Resume Creation Flows

### 3.1 Flow Diagram

```
User clicks [+ New Resume]
    │
    ├── Name, target role, template selection
    │
    ├── Persona data picker (§3.4) — select which jobs, bullets, education,
    │   certifications, skills to include
    │
    ├── Choose creation method:
    │       │
    │       ├── [Generate with AI] ──→ §4 (LLM-Assisted, requires credits)
    │       │
    │       └── [Start from Template] ──→ §3.5 (Deterministic template fill, free)
    │
    └── markdown_content populated → TipTap editor opens → §5 (Manual Editing)
```

### 3.2 New Resume Dialog

```
┌─────────────────────────────────────────────────────────────┐
│ Create New Resume                                            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│ Resume Name:  [Scrum Master Resume          ]                │
│ Target Role:  [Scrum Master                 ]                │
│                                                               │
│ Template:     [Clean & Minimal ▾]                            │
│                                                               │
│ How would you like to start?                                  │
│                                                               │
│ ┌────────────────────────┐  ┌────────────────────────┐       │
│ │                        │  │                        │       │
│ │   Generate with AI     │  │   Start from Template  │       │
│ │                        │  │                        │       │
│ │   AI composes a        │  │   Your selected data   │       │
│ │   polished resume from │  │   filled into template │       │
│ │   your profile data    │  │   — edit from there    │       │
│ │   (requires credits)   │  │   (free)               │       │
│ │                        │  │                        │       │
│ └────────────────────────┘  └────────────────────────┘       │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 Persona Data Picker

Before generation, the user selects which persona data to include. This uses the existing checkbox/drag-and-drop UI (currently the "structured resume" editing surface), reframed as a pre-generation step:

| Selection | UI | Existing Component |
|-----------|----|--------------------|
| Which jobs to include | Checkboxes | `ResumeContentCheckboxes` |
| Which bullets per job | Checkboxes + drag-and-drop reorder | `ReorderableList` |
| Education entries | Checkboxes | `ResumeContentCheckboxes` |
| Certifications | Checkboxes | `ResumeContentCheckboxes` |
| Skills emphasis | Checkboxes | `ResumeContentCheckboxes` |

These selections are saved to the existing JSONB fields on `BaseResume` (`included_jobs`, `job_bullet_selections`, `job_bullet_order`, `included_education`, `included_certifications`, `skills_emphasis`). They inform the generation step — both LLM and deterministic paths read these selections to determine what content goes into the resume.

**Note:** The persona data picker is optional for "Generate with AI" — the LLM can select appropriate content from the full persona. It is required for "Start from Template" since the deterministic fill needs explicit selections.

### 3.4 Deterministic Template Fill (Free Path)

When the user selects "Start from Template" (or has no credits for LLM generation):

| Step | Action | Notes |
|------|--------|-------|
| 1 | Gather selected persona data via `gather_base_resume_content()` | Same logic as current PDF rendering |
| 2 | Mechanically slot data into template sections | No LLM — string concatenation from persona fields |
| 3 | Save result to `markdown_content` | Resume now has a complete first draft |
| 4 | Open TipTap editor with the markdown | User edits and polishes from there |

**API endpoint:** `POST /base-resumes/{id}/generate`

Uses the same endpoint as LLM generation (§4.6) with `"method": "template_fill"`. The backend forks based on the method parameter.

Returns: `{ "markdown_content": "# John Smith\n\n...", "word_count": 342, "method": "template_fill" }`

**What the deterministic fill produces:** A complete, correctly formatted resume document with all selected persona data placed in the appropriate template sections. Contact info in the header, job entries with dates and bullets, education with degrees and dates, skills as a list. Functional and complete — just without the LLM polish (no tailored summary, no rephrased bullets, no strategic emphasis).

---

## 4. LLM-Assisted Resume Generation

### 4.1 Generation Flow

```
User selects [Generate with AI]
    │
    ├── Configure generation options (§4.2)
    │
    ├── Click [Generate]
    │       │
    │       ├── Show loading state in editor ("Generating your resume...")
    │       │
    │       ├── Backend: LLM generates markdown from persona data + template
    │       │
    │       └── Load generated markdown into TipTap
    │
    ├── User reviews and edits in TipTap
    │
    └── User saves (auto-save or explicit)
```

### 4.2 Generation Options Panel

```
┌─────────────────────────────────────────────────────────────┐
│ Generation Options                                           │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│ Page Limit:    [1 page ▾]     (1 page | 2 pages | 3 pages)  │
│                                                               │
│ Emphasis:      [Balanced ▾]   (Technical | Leadership |      │
│                                 Balanced | Industry-specific) │
│                                                               │
│ Include:                                                      │
│   ☑ Professional Summary                                     │
│   ☑ Work Experience                                          │
│   ☑ Education                                                │
│   ☑ Skills                                                   │
│   ☐ Certifications                                           │
│   ☐ Volunteer Experience                                     │
│                                                               │
│ [Generate Resume]                                             │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 Page Limit Control

| Setting | Target Word Count | LLM Instruction |
|---------|-------------------|-----------------|
| 1 page | ~350 words | "Keep the resume to approximately 350 words, fitting on a single page" |
| 2 pages | ~700 words | "Keep the resume to approximately 700 words, fitting on two pages" |
| 3 pages | ~1050 words | "Keep the resume to approximately 1050 words, fitting on three pages" |

The page limit is an instruction to the LLM, not a hard enforcement. The editor status bar shows the actual word count and page estimate so the user can adjust if needed.

### 4.4 LLM Generation Prompt

The generation prompt includes:

| Component | Source | Purpose |
|-----------|--------|---------|
| System prompt | New resume generation system prompt | Role, constraints, output format |
| Template structure | Selected template's markdown skeleton | Section ordering and structure |
| Persona data | All relevant persona fields | Content to draw from |
| Target role | User-specified role type | Focus and emphasis |
| Page limit | User-selected page count | Length constraint |
| Emphasis preference | User-selected emphasis | Technical vs. leadership vs. balanced |
| Section selections | User checkbox choices | Which sections to include |
| Voice Profile | REQ-001 §3.7 | Writing style and tone |

**Output format:** Raw markdown following the template structure. No placeholders — all content is fully composed.

### 4.5 Generation Constraints (from REQ-010)

| Constraint | Enforcement |
|------------|-------------|
| Truthfulness | LLM may only use facts from persona data |
| No fabrication | No invented metrics, skills, or experiences |
| Voice consistency | Must match user's Voice Profile |
| Template adherence | Output follows selected template section structure |
| Page limit respect | Output respects word count target (±10%) |

### 4.6 Generation API

**Endpoint:** `POST /base-resumes/{id}/generate`

**Request body:**
```json
{
  "page_limit": 1,
  "emphasis": "balanced",
  "include_sections": ["summary", "experience", "education", "skills"],
  "template_id": "uuid-or-null"
}
```

**Response:**
```json
{
  "markdown_content": "# John Smith\n\nExperienced Scrum Master...",
  "word_count": 342,
  "model_used": "gemini-2.0-flash",
  "generation_cost_cents": 0
}
```

The frontend receives the markdown and loads it into the TipTap editor. The user can then edit freely.

### 4.7 Regeneration

If the user is unsatisfied with the generated content:

| Action | Behavior |
|--------|----------|
| [Regenerate] button | Opens generation options panel pre-filled with previous settings |
| User adjusts options | Can change page limit, emphasis, section selections |
| Click [Generate] again | New LLM call; previous content replaced in editor |
| Undo after regeneration | Editor undo stack includes the replacement |

**Note:** Each regeneration is a fresh LLM call using the current persona data, not a refinement of the previous output. For iterative refinement via natural language, see REQ-027 (chat-driven editing).

---

## 5. Manual Editing

### 5.1 Editor Layout with Persona Reference Panel

When editing manually, the user sees a split layout:

```
┌──────────────────────────────────────────────────────────────────────┐
│ Scrum Master Resume                                    [Save] [Export]│
├────────────────────────────┬─────────────────────────────────────────┤
│                            │                                         │
│  Persona Reference Panel   │   TipTap Editor                        │
│                            │                                         │
│  ▸ Contact Info            │   # John Smith                         │
│    John Smith              │                                         │
│    john@email.com          │   john@email.com | (555) 123-4567      │
│    (555) 123-4567          │                                         │
│                            │   ---                                   │
│  ▸ Work History            │                                         │
│    ▾ TechCorp (2020-2024)  │   ## Professional Summary               │
│      • Led team of 12      │                                         │
│      • Reduced cycle time  │   Experienced Scrum Master with 8      │
│      • Implemented SAFe    │   years of experience in...            │
│      • Improved velocity   │                                         │
│                            │   ---                                   │
│    ▸ StartupCo (2018-2020) │                                         │
│                            │   ## Experience                         │
│  ▸ Education               │                                         │
│    BS Computer Science     │   ### Scrum Master — TechCorp          │
│    State University, 2018  │   *2020 – Present*                     │
│                            │                                         │
│  ▸ Skills                  │   - Led team of 12 engineers           │
│    Scrum, SAFe, Jira,      │   - Reduced cycle time by 40%         │
│    Confluence, ...         │                                         │
│                            │                                         │
│  ▸ Certifications          │                                         │
│    CSM, PSM II             │                                         │
│                            │                                         │
└────────────────────────────┴─────────────────────────────────────────┘
```

### 5.2 Reference Panel Behavior

| Feature | Behavior |
|---------|----------|
| Collapsible sections | Each persona category (Work History, Education, Skills, etc.) is expandable/collapsible |
| Copy to editor | Click a bullet, skill, or text snippet to copy it to clipboard for pasting into editor |
| Read-only | Panel is purely reference — editing persona data happens on the Persona page |
| Responsive | Panel collapses to a toggle button on narrow screens |
| Data source | Fetched from existing persona API endpoints |

### 5.3 Manual Editing with Template

When the user selects "Write Manually":

| Step | Action |
|------|--------|
| 1 | Load selected template's markdown into TipTap |
| 2 | Template sections appear as headings with empty content |
| 3 | Persona reference panel opens alongside editor |
| 4 | User writes content, referencing persona data |
| 5 | Auto-save preserves progress |

### 5.4 Editing Features

| Feature | Description |
|---------|-------------|
| Auto-save | Debounced save (2s after last keystroke) — saves `markdown_content` to backend |
| Manual save | Explicit [Save] button for immediate persistence |
| Undo/Redo | TipTap's built-in history (Ctrl+Z / Ctrl+Shift+Z) |
| Word count | Live word count in status bar |
| Page estimate | Approximate page count based on word count |
| Read-only mode | Approved resumes displayed with `editable: false` |
| Keyboard shortcuts | Standard formatting shortcuts (Ctrl+B bold, Ctrl+I italic, etc.) |

---

## 6. Resume Detail Page (Updated)

### 6.1 Updated Layout — Toggle View

The resume detail page (`/resumes/[id]`) supports two views toggled within the same page. The user never navigates away — they switch between Preview and Edit mode via a toggle control.

```
┌─────────────────────────────────────────────────────────────┐
│ Scrum Master Resume            [Preview] [Edit]   ★ Primary │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│ PREVIEW MODE (default):                                       │
│ ┌─────────────────────────────────────────────────────────┐  │
│ │   Resume content preview (read-only TipTap)             │  │
│ │   # John Smith                                         │  │
│ │   john@email.com | (555) 123-4567                      │  │
│ │   ...                                                  │  │
│ └─────────────────────────────────────────────────────────┘  │
│ [Edit]  [Generate with AI]  [Export PDF ▾]  [Edit Selections]│
│                                                               │
│ EDIT MODE (toggled):                                          │
│ ┌──────────────────────┬──────────────────────────────────┐  │
│ │ Persona Reference    │ TipTap Editor (editable)         │  │
│ │ Panel (§5)           │ with toolbar + status bar        │  │
│ └──────────────────────┴──────────────────────────────────┘  │
│ [Done Editing]  [Export PDF ▾]                                │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│ ── Job Variants ──────────────────────────────────────────── │
│ (variant list — same as REQ-012 §9.2)                        │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Action Buttons

| Button | Behavior |
|--------|----------|
| Edit | Toggles to Edit mode (TipTap editor with persona reference panel) |
| Done Editing | Toggles back to Preview mode |
| Generate with AI | Opens generation options (§4.2). If `markdown_content` exists, warns: replaces current content. Requires credits. |
| Export PDF | Exports `markdown_content` → PDF (REQ-025 §5.2) |
| Export DOCX | Exports `markdown_content` → DOCX (REQ-025 §5.3) |
| Edit Selections | Opens persona data picker (§3.3) to change which data is included |

**No content state:** If `markdown_content` is NULL (resume just created, not yet generated), Preview mode shows a prompt: "Generate your resume or start from a template to get started." with [Generate with AI] and [Start from Template] buttons.

### 6.3 Content Preview

The preview shows rendered markdown content via read-only TipTap (`editable: false`). This provides a WYSIWYG view of the resume as the user would see it in the editor, without the toolbar or editing capabilities.

---

## 7. Auto-Save Specification

### 7.1 Save Strategy

| Trigger | Behavior |
|---------|----------|
| Keystroke | Start 2-second debounce timer |
| Timer expires | `PATCH /base-resumes/{id}` with `{ "markdown_content": "..." }` |
| Explicit save ([Save] button) | Immediate `PATCH` call; reset debounce timer |
| Navigate away | Save if unsaved changes exist; show "Unsaved changes" warning if save fails |
| Browser close | `beforeunload` event if unsaved changes |

### 7.2 Save Status Indicator

| State | Display | Trigger |
|-------|---------|---------|
| Saved | "Saved" with check icon | Successful PATCH response |
| Saving | "Saving..." with spinner | PATCH request in flight |
| Unsaved | "Unsaved changes" with warning dot | Content changed since last save |
| Error | "Save failed — retry" with error icon | PATCH request failed |

### 7.3 Conflict Prevention

At MVP, no concurrent editing support. The `updated_at` field on the base resume serves as an optimistic concurrency guard:

| Step | Action |
|------|--------|
| 1 | Editor loads resume and stores `updated_at` |
| 2 | On save, send `updated_at` in request |
| 3 | Backend compares with current `updated_at` |
| 4 | If mismatch, return 409 Conflict |
| 5 | Frontend shows "Resume was modified elsewhere. Reload?" |

---

## 8. Validation Rules

| Rule | Description |
|------|-------------|
| Resume name required | Cannot be empty; max 100 characters |
| Role type required | Cannot be empty; max 255 characters |
| Markdown content max size | 50KB (ample for multi-page resumes) |
| Page limit range | 1-3 pages for LLM generation |
| Template required for new resume | Must select a template (default pre-selected) |
| LLM generation requires credits | If insufficient balance, endpoint returns 402. Frontend falls back to offering template fill. |
| Template fill requires selections | At least one job with bullets selected in persona data picker |
| LLM generation requires persona data | At least one work history entry and summary must exist in persona |

---

## 9. Error Handling

| Scenario | User Experience |
|----------|-----------------|
| LLM generation fails | Toast: "Resume generation failed. Please try again." Editor stays empty or retains previous content. |
| LLM returns content exceeding page limit | Content loaded normally; page estimate in status bar shows actual count. User can edit down. |
| Auto-save fails | Status bar shows "Save failed — retry". Retry on next keystroke. Unsaved content remains in editor. |
| Template load fails | Toast: "Could not load template." Resume created with empty content. |
| Export fails | Toast: "Export failed. Please try again." |
| Persona data insufficient | Generation options panel shows warning: "Add work experience to your profile to generate a resume." |

---

## 10. Open Questions

| # | Question | Status |
|---|----------|--------|
| 1 | Should regeneration preserve user edits and only update LLM-generated sections? | **DECIDED: No** — regeneration replaces all content. For targeted edits, use chat-driven editing (REQ-027). |
| 2 | Should the reference panel show all persona data or only data relevant to the target role? | TBD — start with all data; filter by role type as enhancement |
| 3 | Should we track generation history (each LLM output) for comparison? | Deferred — not MVP. Users have undo in the editor. |
| 4 | Keyboard shortcut for switching between editor and reference panel? | TBD — consider Tab or Ctrl+\ |

---

## 11. Design Decisions & Rationale

### 11.1 Generation Approach

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| LLM output loading | Streaming into editor / Generate-then-load | Generate-then-load | Streaming requires batching TipTap transactions at sentence boundaries to avoid jitter. Generate-then-load is simpler, provides complete undo, and the generation time (~3-5s) is acceptable with a loading indicator. Streaming deferred to post-MVP. |
| Generation scope | Full resume / Section-by-section | Full resume | Section-by-section adds complexity (multiple LLM calls, partial state management). Full resume generation gives the LLM context across sections for better coherence. User can edit individual sections after generation. |

### 11.2 Generation Tiers (Free vs Paid)

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Free tier experience | Block resume creation / Empty template only / Deterministic template fill | Deterministic template fill | Blocking is too restrictive — users need to create resumes to see value. Empty template means retyping data the system already has (15-30 min of busywork). Template fill mechanically slots selected persona data into the template — functional, complete, and instant. User edits from there. LLM generation adds polish for paying users. |
| Generation endpoint | Separate endpoints for LLM vs template fill / Single endpoint with method parameter | Single endpoint | `POST /base-resumes/{id}/generate` with `method: "ai" | "template_fill"`. Backend forks on the parameter. Same response shape. Frontend doesn't need to know which backend path ran. |

### 11.3 Resume Detail Page — View Toggle

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Editor location | Separate route (`/resumes/[id]/edit`) / Modal overlay / Toggle within detail page | Toggle within detail page | Separate route causes disorientation — user navigates away from their resume context. Modal is too constrained for a full editor with toolbar, status bar, and side panel. Toggle keeps the user on the same page, switching between Preview and Edit views. Back button returns to the resume list, not to a previous view state. |

### 11.4 Reference Panel

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Panel position | Left sidebar / Right sidebar / Bottom drawer | Left sidebar | Left-to-right: reference → compose. Natural reading flow. Editor gets the wider right pane. Consistent with document editor UX patterns (e.g., Google Docs sidebar). |
| Panel interaction | Copy-paste only / Drag-and-drop into editor / Click-to-insert | Copy to clipboard on click | Drag-and-drop into ProseMirror is complex to implement. Click-to-insert would need cursor position tracking. Copy-to-clipboard is simple, universal, and lets the user choose where to paste. |

---

## 12. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-04 | 0.1 | Initial draft. LLM generation, manual editing, reference panel, page limit control. |
| 2026-03-05 | 0.2 | Audit review: Eliminated `content_mode` — all resumes are markdown. Added persona data picker as pre-generation step (§3.3). Added deterministic template fill as free-tier path (§3.4). Replaced dual-mode action buttons with single set. Updated detail page to toggle between Preview/Edit views within same page (§6.1). Added free/paid generation tier decision. |
