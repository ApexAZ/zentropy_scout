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
    ├── Select template (REQ-025 §6.3)
    │
    ├── Choose creation method:
    │       │
    │       ├── [Generate with AI] ──→ §4 (LLM-Assisted)
    │       │
    │       └── [Write Manually]   ──→ §5 (Manual Editing)
    │
    └── Resume created with content_mode = 'markdown'
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
│ │   Generate with AI     │  │   Write Manually       │       │
│ │                        │  │                        │       │
│ │   AI composes a resume │  │   Start with template  │       │
│ │   from your profile    │  │   and write your own   │       │
│ │   data                 │  │   content              │       │
│ │                        │  │                        │       │
│ └────────────────────────┘  └────────────────────────┘       │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 Structured Resume Conversion

When a user opens an existing structured resume (`content_mode = 'structured'`) and clicks "Edit in TipTap":

| Step | Action | Notes |
|------|--------|-------|
| 1 | Show confirmation dialog | "Converting to rich text editor. This cannot be undone. Continue?" |
| 2 | Gather persona data using existing `gather_base_resume_content()` | Same logic as current PDF rendering |
| 3 | Compose markdown from gathered content + selected template | Backend endpoint returns markdown string |
| 4 | Save `markdown_content` and set `content_mode = 'markdown'` | One-way conversion |
| 5 | Load TipTap editor with the markdown | User can now edit freely |

**API endpoint:** `POST /base-resumes/{id}/convert-to-markdown`

Returns: `{ "markdown_content": "# John Smith\n\n..." }`

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

### 6.1 Updated Layout

The existing resume detail page (REQ-012 §9.2) is updated to accommodate both content modes:

```
┌─────────────────────────────────────────────────────────────┐
│ Scrum Master Resume                       Active  ★ Primary │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│ [Edit in TipTap]  [Generate with AI]  [Export PDF ▾]         │
│                                                               │
│ ┌─────────────────────────────────────────────────────────┐  │
│ │                                                         │  │
│ │   Resume content preview (rendered markdown)            │  │
│ │                                                         │  │
│ │   # John Smith                                         │  │
│ │   john@email.com | (555) 123-4567                      │  │
│ │   ...                                                  │  │
│ │                                                         │  │
│ └─────────────────────────────────────────────────────────┘  │
│                                                               │
│ ── Job Variants ──────────────────────────────────────────── │
│                                                               │
│ (variant list — same as REQ-012 §9.2)                        │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Action Buttons by Content Mode

| Button | `content_mode = 'structured'` | `content_mode = 'markdown'` |
|--------|-------------------------------|----------------------------|
| Edit in TipTap | Shows conversion dialog (§3.3) | Opens TipTap editor |
| Generate with AI | Opens generation options (§4.2) | Opens generation options (warns: replaces current content) |
| Export PDF | Existing download (ReportLab from selections) | New export (markdown → PDF) |
| Export DOCX | Not available | New export (markdown → DOCX) |
| Edit Selections | Opens existing checkbox/drag-drop UI | Not available (markdown mode) |

### 6.3 Content Preview

For `content_mode = 'markdown'` resumes, the detail page shows a rendered preview of the markdown content (read-only TipTap with `editable: false`). This replaces the "summary + bullet selections" view used for structured resumes.

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
| Content mode immutable after conversion | Cannot revert from 'markdown' to 'structured' |
| Generation requires persona data | At least one work history entry and summary must exist in persona |

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

### 11.2 Content Mode Transition

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Transition direction | Bidirectional / One-way (structured → markdown) | One-way | Markdown → structured requires re-mapping free text back to persona bullet IDs, which is lossy and unreliable. Users who prefer structured mode keep it. Users who upgrade to TipTap get the full editing experience. |
| Transition trigger | Automatic / User-initiated | User-initiated with confirmation | Irreversible change should be explicit. Users see a confirmation dialog explaining the change. Prevents accidental conversion. |

### 11.3 Reference Panel

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Panel position | Left sidebar / Right sidebar / Bottom drawer | Left sidebar | Left-to-right: reference → compose. Natural reading flow. Editor gets the wider right pane. Consistent with document editor UX patterns (e.g., Google Docs sidebar). |
| Panel interaction | Copy-paste only / Drag-and-drop into editor / Click-to-insert | Copy to clipboard on click | Drag-and-drop into ProseMirror is complex to implement. Click-to-insert would need cursor position tracking. Copy-to-clipboard is simple, universal, and lets the user choose where to paste. |

---

## 12. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-04 | 0.1 | Initial draft. LLM generation, manual editing, reference panel, page limit control. |
