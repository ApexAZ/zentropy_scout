# REQ-025: TipTap Rich Text Editor Foundation

**Status:** Draft
**Version:** 0.1
**PRD Reference:** §8 Document Management
**Last Updated:** 2026-03-04

---

## 1. Overview

This document specifies the foundation for integrating TipTap (a headless ProseMirror-based rich text editor) into Zentropy Scout's resume management system. It covers the editor component, markdown as the canonical storage format, the export pipeline (PDF + DOCX), and the template system.

**Key Principle:** Markdown is the single source of truth for resume content. TipTap renders markdown as rich text for editing. The backend converts markdown to PDF and DOCX for export. LLMs read and write markdown directly.

### 1.1 Scope

| In Scope | Out of Scope |
|----------|--------------|
| TipTap editor component (React) | LLM content generation workflow (REQ-026) |
| Markdown ↔ rich text bidirectional conversion | Chat-driven document editing (REQ-027) |
| PDF export from markdown | Job variant diff view (REQ-027) |
| DOCX export from markdown | Collaborative real-time editing |
| Template system (default + user-uploaded) | Cover letter editing (future) |
| Schema changes for markdown storage | Streaming LLM output into editor |
| Toolbar and formatting controls | Mobile-native editor |

### 1.2 Design Principles

| Principle | Description | Enforcement |
|-----------|-------------|-------------|
| **Markdown-First** | Markdown is canonical; HTML/rich text is a rendering layer | All persistence uses markdown; TipTap converts for display |
| **Lossless Round-Trip** | Markdown → TipTap → markdown must be identical for supported features | `@tiptap/markdown` extension with tested feature subset |
| **Export Fidelity** | PDF and DOCX output should look visually consistent | Shared style definitions inform both export pipelines |
| **Headless & Themed** | TipTap provides no default styles; we style with Tailwind/shadcn | Editor inherits design system tokens |
| **Template Extensibility** | Template system supports adding new templates and user uploads | Templates are markdown files with front-matter metadata |

---

## 2. Dependencies

### 2.1 This Document Depends On

| Dependency | Type | Notes |
|------------|------|-------|
| REQ-001 Persona Schema v0.8 | Data source | Persona fields populate resume content |
| REQ-002 Resume Schema v0.7 | Entity definitions | BaseResume, JobVariant — schema changes in §4 |
| REQ-005 Database Schema v0.10 | Schema | `base_resumes`, `job_variants` tables modified |
| REQ-012 Frontend Application v0.1 | UI framework | Next.js App Router, Tailwind CSS, shadcn/ui |

### 2.2 Other Documents Depend On This

| Document | Dependency | Notes |
|----------|------------|-------|
| REQ-026 Resume Editing Workflow | Editor component | LLM generation and manual editing use the editor |
| REQ-027 Resume Collaboration | Editor component | Chat-driven editing and diff view build on editor |

---

## 3. TipTap Editor Component

### 3.1 Package Selection

| Package | Version | License | Purpose |
|---------|---------|---------|---------|
| `@tiptap/react` | ^2.x | MIT | React integration layer |
| `@tiptap/pm` | ^2.x | MIT | ProseMirror peer dependency |
| `@tiptap/starter-kit` | ^2.x | MIT | Core extensions bundle (bold, italic, headings, lists, etc.) |
| `@tiptap/markdown` | ^3.x | MIT | Official markdown ↔ HTML bidirectional conversion |

**No paid extensions required.** The free/open-source core covers all needed functionality: headings (H1-H4), bold, italic, bullet lists, ordered lists, horizontal rules, links, and blockquotes.

### 3.2 Editor Component Architecture

```
ResumeEditor (client component — "use client")
├── EditorToolbar — formatting buttons (bold, italic, headings, lists, etc.)
├── TipTap Editor — ProseMirror-based editing surface
└── EditorStatusBar — word count, save status, page estimate
```

**Key Implementation Notes:**

| Concern | Approach |
|---------|----------|
| SSR safety | `"use client"` directive; `immediatelyRender: false` in `useEditor()` config |
| Initial content | Pass markdown string; `@tiptap/markdown` parses to ProseMirror document |
| Content extraction | `editor.storage.markdown.getMarkdown()` returns current content as markdown |
| Save trigger | Debounced auto-save (2s after last keystroke) + explicit save button |
| Read-only mode | `editable: false` prop for approved/archived resumes |
| Placeholder text | "Start writing your resume..." when editor is empty |

### 3.3 Supported Formatting Features

The editor supports a deliberate subset of markdown features — enough for professional resumes without introducing round-trip conversion issues.

| Feature | Markdown Syntax | TipTap Extension | Resume Use Case |
|---------|----------------|-------------------|-----------------|
| Headings (H1-H4) | `# ` to `#### ` | `Heading` (starter-kit) | Section titles (Experience, Education, Skills) |
| Bold | `**text**` | `Bold` (starter-kit) | Emphasis, company/role names |
| Italic | `*text*` | `Italic` (starter-kit) | Subtle emphasis, titles |
| Bullet list | `- item` | `BulletList` (starter-kit) | Accomplishment bullets |
| Ordered list | `1. item` | `OrderedList` (starter-kit) | Numbered steps, rankings |
| Horizontal rule | `---` | `HorizontalRule` (starter-kit) | Section separators |
| Links | `[text](url)` | `Link` (separate extension) | Portfolio, LinkedIn |
| Blockquote | `> text` | `Blockquote` (starter-kit) | Optional: professional summary callout |

**Explicitly NOT supported** (to avoid conversion issues): tables, images, code blocks, footnotes, task lists, nested blockquotes.

### 3.4 Toolbar Specification

```
┌──────────────────────────────────────────────────────────────────┐
│ B  I  │ H1 H2 H3 H4  │ • ─ 1. ─  │ ― Link  │ Undo Redo       │
└──────────────────────────────────────────────────────────────────┘
```

| Group | Buttons | Behavior |
|-------|---------|----------|
| Text style | Bold, Italic | Toggle on selection |
| Headings | H1, H2, H3, H4 | Dropdown or individual buttons; toggle on current block |
| Lists | Bullet, Ordered | Toggle list type on current block |
| Insert | Horizontal Rule, Link | Insert at cursor; link opens URL dialog |
| History | Undo, Redo | Standard undo/redo stack |

Buttons show active state when the cursor is inside a formatted block (e.g., Bold button highlighted when cursor is in bold text).

### 3.5 Editor Status Bar

```
┌──────────────────────────────────────────────────────────────────┐
│ 342 words  │  ~1 page  │  Saved ✓                               │
└──────────────────────────────────────────────────────────────────┘
```

| Field | Source | Notes |
|-------|--------|-------|
| Word count | Count words in editor text content | Update on every change |
| Page estimate | `words / 350` rounded up | Approximate — PDF rendering may differ |
| Save status | "Saved", "Saving...", "Unsaved changes" | Reflects auto-save state |

---

## 4. Schema Changes

### 4.1 BaseResume — New Fields

Add markdown content storage alongside existing JSONB selection fields. The JSONB selection fields serve as the **persona data picker** — the user selects which jobs, bullets, education, certifications, and skills to include. The `markdown_content` field is always the actual resume document. Every resume is a markdown document; the JSONB fields are input to generation, not an alternative content mode.

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `markdown_content` | Text | Optional | NULL | Markdown resume document (always the source of truth when populated) |
| `template_id` | UUID | Optional | NULL | FK to resume_templates (NULL = default template) |

**Content Pipeline:**

```
JSONB selection fields (persona data picker)
    → Generation (LLM-assisted or deterministic template fill)
        → markdown_content (the actual resume document)
            → TipTap editor (viewing and editing)
            → PDF/DOCX export
```

**Two generation paths:**
- **LLM-assisted (paid):** Selected persona data + template → LLM generates polished, tailored markdown. Requires credits.
- **Deterministic template fill (free):** Selected persona data + template → system mechanically slots data into template sections. No LLM, no credits. Produces a functional but unpolished starting point.

Both paths produce `markdown_content` that the user edits in TipTap.

### 4.2 JobVariant — New Fields

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `markdown_content` | Text | Optional | NULL | Markdown source for job-specific tailoring |
| `snapshot_markdown_content` | Text | Optional | NULL | Frozen copy on approval (like other snapshot fields) |

**Draft JobVariants** inherit the base resume's markdown if their own `markdown_content` is NULL. When edited (by user or LLM), `markdown_content` is populated with the modified version.

**Approval snapshot:** When a variant is approved, `snapshot_markdown_content` is set to the current `markdown_content` value, freezing the content for immutability.

### 4.3 New Table: `resume_templates`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `id` | UUID | Yes | PK |
| `name` | String(100) | Yes | Display name (e.g., "Clean & Minimal") |
| `description` | Text | Optional | Brief description for template picker |
| `markdown_content` | Text | Yes | Template skeleton with placeholder sections |
| `is_system` | Boolean | Yes | `true` for built-in templates; `false` for user-uploaded |
| `user_id` | UUID | Optional | NULL for system templates; FK to Users for user templates |
| `display_order` | Integer | Yes | Ordering in template picker |
| `created_at` | Timestamp | Yes | |
| `updated_at` | Timestamp | Yes | |

**Seed data:** One default system template ("Clean & Minimal") is seeded via migration.

### 4.4 Migration Plan

| Step | Action | Reversible |
|------|--------|------------|
| 1 | Add `markdown_content`, `template_id` to `base_resumes` | Yes (drop columns) |
| 2 | Add `markdown_content`, `snapshot_markdown_content` to `job_variants` | Yes (drop columns) |
| 3 | Create `resume_templates` table | Yes (drop table) |
| 4 | Seed default "Clean & Minimal" template | Yes (delete row) |

**No data migration required.** Existing resumes have `markdown_content = NULL`. When a resume is generated (LLM or template fill), `markdown_content` is populated.

---

## 5. Export Pipeline

### 5.1 Architecture

```
Markdown (canonical) ──┬──→ PDF  (backend: markdown-it → ReportLab)
                       └──→ DOCX (backend: markdown-it → python-docx)
```

Both export paths receive markdown as input and produce binary output stored as BYTEA.

### 5.2 PDF Export

**Approach:** Parse markdown into an intermediate structure, then render via existing ReportLab/Platypus pipeline.

| Step | Implementation | Notes |
|------|---------------|-------|
| 1. Parse markdown | `markdown-it-py` (Python) | Parse markdown to AST tokens |
| 2. Map to Platypus flowables | New `MarkdownPdfRenderer` service | Map headings → `Paragraph` with heading style, lists → bullet `Paragraph`, etc. |
| 3. Apply template styles | Template-specific `ParagraphStyle` definitions | Font, size, spacing, margins from template |
| 4. Render PDF | `SimpleDocTemplate.build()` | Returns PDF bytes |

**Relationship to existing `pdf_generation.py`:** The existing service gathers persona data from JSONB selections and renders it. The new `MarkdownPdfRenderer` takes pre-composed markdown instead. Both produce PDF bytes via ReportLab. They coexist — whether a resume has `markdown_content` determines which path is used.

### 5.3 DOCX Export

**New dependency:** `python-docx` (pip)

| Step | Implementation | Notes |
|------|---------------|-------|
| 1. Parse markdown | `markdown-it-py` (Python) | Same parser as PDF path |
| 2. Map to DOCX elements | New `MarkdownDocxRenderer` service | Map headings → `add_heading()`, paragraphs → `add_paragraph()`, etc. |
| 3. Apply template styles | Template-specific `Document` styles | Font, size, spacing from template |
| 4. Return DOCX bytes | `document.save(BytesIO)` | Returns DOCX bytes |

### 5.4 Export API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/base-resumes/{id}/export/pdf` | Export base resume as PDF |
| `GET` | `/base-resumes/{id}/export/docx` | Export base resume as DOCX |
| `GET` | `/job-variants/{id}/export/pdf` | Export job variant as PDF |
| `GET` | `/job-variants/{id}/export/docx` | Export job variant as DOCX |

**Response:** Binary file download with appropriate `Content-Type` and `Content-Disposition` headers.

**Note:** Existing download endpoints (`/base-resumes/{id}/download`, `/submitted-resume-pdfs/{id}/download`) continue to work for legacy resumes without `markdown_content`. The new export endpoints handle resumes with `markdown_content` and add DOCX support.

### 5.5 Markdown Feature → Export Mapping

| Markdown Feature | PDF Rendering | DOCX Rendering |
|-----------------|---------------|----------------|
| `# Heading 1` | 16pt bold, centered | `add_heading(level=1)` |
| `## Heading 2` | 13pt bold, left | `add_heading(level=2)` |
| `### Heading 3` | 11pt bold, left | `add_heading(level=3)` |
| `#### Heading 4` | 10pt bold, left | `add_heading(level=4)` |
| `**bold**` | Bold font weight | Bold run |
| `*italic*` | Italic font style | Italic run |
| `- bullet` | Bullet character + indent | Bullet paragraph style |
| `1. ordered` | Number + indent | Numbered list style |
| `---` | Horizontal line flowable | Horizontal line paragraph border |
| `[text](url)` | Blue underlined text | Hyperlink |
| `> blockquote` | Indented with left border | Indented paragraph |

---

## 6. Template System

### 6.1 Default Template: "Clean & Minimal"

```markdown
# {full_name}

{email} | {phone} | {location} | {linkedin_url}

---

## Professional Summary

{summary}

---

## Experience

### {job_title} — {company_name}
*{start_date} – {end_date}*

- {bullet_1}
- {bullet_2}

---

## Education

### {degree} — {institution}
*{graduation_date}*

---

## Skills

{skills_list}

---

## Certifications

- {certification_1}
- {certification_2}
```

**Placeholders** (`{field_name}`) are replaced with persona data during LLM generation (REQ-026). When a user creates a resume manually, the template provides the section structure with empty content.

### 6.2 Template Metadata

Templates are stored in the `resume_templates` table (§4.3). The `markdown_content` field contains the template skeleton. System templates are seeded via migration; user templates are created via API.

### 6.3 Template Picker UI

When creating a new resume, the user selects a template:

```
┌─────────────────────────────────────────────────────────────┐
│ Choose a Resume Template                                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│ ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│ │              │  │              │  │              │        │
│ │  Clean &     │  │   (More      │  │  + Upload    │        │
│ │  Minimal     │  │   Coming     │  │    Your Own  │        │
│ │  ★ Default   │  │    Soon)     │  │              │        │
│ │              │  │              │  │              │        │
│ └──────────────┘  └──────────────┘  └──────────────┘        │
│                                                               │
│ [Select Template]                                             │
└─────────────────────────────────────────────────────────────┘
```

**"Upload Your Own"** allows users to upload a markdown file as a custom template. The file is validated (must parse as valid markdown, must contain at least one heading) and stored in `resume_templates` with `is_system = false` and the user's `user_id`.

### 6.4 Template API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/resume-templates` | List available templates (system + user's own) |
| `GET` | `/resume-templates/{id}` | Get template details |
| `POST` | `/resume-templates` | Create user template (upload markdown) |
| `PATCH` | `/resume-templates/{id}` | Update user template (system templates cannot be modified) |
| `DELETE` | `/resume-templates/{id}` | Delete user template (system templates cannot be deleted) |

---

## 7. Markdown Round-Trip Guarantee

### 7.1 Lossless Conversion Requirement

For the supported feature subset (§3.3), converting markdown → TipTap → markdown must produce semantically equivalent output. Minor formatting differences are acceptable (e.g., trailing whitespace, blank line count), but structural changes are not.

### 7.2 Testing Strategy

| Test Category | What to Verify |
|---------------|----------------|
| Headings | All levels (H1-H4) preserve after round-trip |
| Inline formatting | Bold, italic, bold+italic combinations |
| Lists | Bullet and ordered lists with multi-level nesting |
| Links | URL and display text preserved |
| Horizontal rules | Preserved as `---` |
| Mixed content | Heading → paragraph → list → paragraph sequences |
| Edge cases | Empty documents, single-line content, consecutive headings |

### 7.3 Unsupported Feature Handling

If markdown content contains unsupported features (e.g., tables from a user-uploaded template), TipTap will render them as plain text. The export pipeline should handle unknown tokens gracefully (render as plain text, log a warning).

---

## 8. Validation Rules

| Rule | Description |
|------|-------------|
| Template name unique per scope | System templates: globally unique. User templates: unique per user. |
| Template markdown valid | Must parse without errors; must contain at least one heading |
| Export requires content | Cannot export PDF/DOCX if `markdown_content` is NULL |
| Variant snapshot complete | On approval, `snapshot_markdown_content` must be set if variant has `markdown_content` |

---

## 9. Privacy & Security Notes

### 9.1 PII Fields

| Entity | PII Fields | Notes |
|--------|------------|-------|
| BaseResume | `markdown_content` | Contains full resume text with contact info, work history |
| JobVariant | `markdown_content`, `snapshot_markdown_content` | Contains tailored resume text |
| resume_templates | `markdown_content` (user templates only) | May contain personal info if user uploads filled template |

### 9.2 Input Sanitization

- User-uploaded templates are validated as markdown (no embedded HTML/scripts)
- Markdown content is sanitized before export to prevent injection in PDF/DOCX renderers
- `@tiptap/markdown` strips any raw HTML from editor output

---

## 10. New Dependencies

### 10.1 Frontend (npm)

| Package | Version | License | Size | Purpose |
|---------|---------|---------|------|---------|
| `@tiptap/react` | ^2.x | MIT | ~50KB | React integration |
| `@tiptap/pm` | ^2.x | MIT | ~200KB | ProseMirror core (peer dep) |
| `@tiptap/starter-kit` | ^2.x | MIT | ~30KB | Core extensions bundle |
| `@tiptap/markdown` | ^3.x | MIT | ~15KB | Markdown ↔ HTML conversion |
| `@tiptap/extension-link` | ^2.x | MIT | ~5KB | Link support |

### 10.2 Backend (pip)

| Package | Version | License | Purpose |
|---------|---------|---------|---------|
| `python-docx` | ^1.x | MIT | DOCX generation |
| `markdown-it-py` | ^3.x | MIT | Markdown → AST parsing for export |

---

## 11. Open Questions

| # | Question | Status |
|---|----------|--------|
| 1 | Should template switching after content exists attempt content migration or warn-and-replace? | **DECIDED: Warn-and-replace** — template defines structure; migrating content between structures is fragile and error-prone. User sees confirmation dialog. |
| 2 | Should we store HTML alongside markdown for faster rendering? | **DECIDED: No** — TipTap converts on load; caching adds complexity without meaningful performance benefit for resume-length documents. |
| 3 | Max markdown content size? | **DECIDED: 50KB** — ample for multi-page resumes. Referenced in REQ-026 §8 and REQ-027 §3.6. |

---

## 12. Design Decisions & Rationale

### 12.1 Editor Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Editor library | TipTap / Slate / Draft.js / Lexical | TipTap | Headless (style with Tailwind), ProseMirror-based (mature), official markdown extension, MIT license, active maintenance. Slate has steeper learning curve. Draft.js is Facebook-deprecated. Lexical is newer with less ecosystem. |
| Markdown as storage | Markdown / HTML / ProseMirror JSON | Markdown | LLMs read/write markdown natively. Portable across systems. Human-readable in database. HTML is verbose and fragile. ProseMirror JSON is editor-specific. |
| Bidirectional conversion | Custom parser / `@tiptap/markdown` / community `tiptap-markdown` | `@tiptap/markdown` (official) | Official package (v3.20.0), actively maintained by TipTap team. Community `tiptap-markdown` is deprecated. Custom parser adds maintenance burden. |

### 12.2 Export Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| PDF from markdown | markdown → HTML → wkhtmltopdf / markdown → ReportLab / markdown → weasyprint | markdown → ReportLab | ReportLab already in stack. No system dependencies (wkhtmltopdf, weasyprint need system libs). Consistent with existing PDF pipeline. |
| DOCX generation | python-docx / docx-template / pandoc | python-docx | Pure Python, no system dependencies. Simple API for document creation. docx-template needs template files. Pandoc is a system dependency. |
| Markdown parser (backend) | markdown-it-py / mistune / commonmark | markdown-it-py | CommonMark compliant, extensible, well-maintained. Mistune is fast but less standard-compliant. |

### 12.3 Template Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Template count at launch | Multiple templates / One default + extensible | One default + extensible | Reduces scope. One well-designed template is better than several mediocre ones. Architecture supports adding more. Users can upload their own. |
| Template storage | Filesystem / Database / Embedded in code | Database (`resume_templates` table) | Queryable, supports user-uploaded templates, follows existing BYTEA-in-DB pattern. Filesystem requires file management. Embedded limits extensibility. |
| Template format | Markdown with placeholders / HTML template / JSON schema | Markdown with placeholders | Natural fit — templates ARE resume structures. Placeholders guide LLM generation. Users can write templates in any markdown editor. |

### 12.4 Schema Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Content architecture | Dual content modes (structured vs markdown) / Markdown-only with JSONB as input | Markdown-only | All resumes are markdown documents. The JSONB selection fields are a persona data picker that informs generation — not an alternative editing mode. This eliminates dual pipelines, dual export paths, and `content_mode` branching throughout the stack. The existing checkbox/drag-and-drop UI is reframed as "select what goes into this resume" rather than "this IS the resume." |
| Generation tiers | LLM-only / Deterministic-only / Both | Both (paid + free) | LLM generation (paid) produces polished, tailored content. Deterministic template fill (free) mechanically slots persona data into template sections — functional but unpolished. Both produce markdown for TipTap editing. Free tier ensures every user can create a real document without credits. |
| Template ownership | Scope to persona_id / Scope to user_id | user_id | Templates are a user asset, not persona content. Using `user_id` is consistent with the multitenancy isolation pattern used throughout the codebase and prevents orphaned templates if a persona is recreated. |

---

## 13. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-04 | 0.1 | Initial draft. TipTap editor component, markdown storage, PDF + DOCX export, template system. |
| 2026-03-05 | 0.2 | Audit review: Eliminated `content_mode` dual pipeline — all resumes are markdown documents, JSONB fields are persona data picker input. Changed `resume_templates` ownership from `persona_id` to `user_id` for multitenancy consistency. Added `PATCH` endpoint for template updates. Added deterministic template fill (free tier) alongside LLM generation (paid). Resolved max content size as 50KB. |
