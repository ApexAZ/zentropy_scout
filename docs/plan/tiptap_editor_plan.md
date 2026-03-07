# Zentropy Scout — TipTap Editor Implementation Plan (REQ-025, REQ-026, REQ-027)

**Created:** 2026-03-05
**Last Updated:** 2026-03-06
**Status:** ✅ Complete

---

## Context

Zentropy Scout's resume system currently stores content as JSONB field selections (checkboxes, bullet reordering) with a plain-text `summary` field. PDF rendering gathers data from these selections and formats it via ReportLab. There is no rich text editing capability.

This plan adds:
1. **TipTap rich text editor** — markdown-based editing surface for resumes (REQ-025)
2. **Resume editing workflow** — LLM-assisted and deterministic generation, auto-save, toggle view (REQ-026)
3. **Job variant collaboration** — LLM tailoring, diff view, approval workflow (REQ-027)

**What changes:** New `markdown_content` fields on `base_resumes` and `job_variants`, new `resume_templates` table, new export pipeline (markdown → PDF/DOCX), TipTap editor component, updated resume detail page (toggle view), new resume creation flow, job variant creation/review UI with diff view.

**What does NOT change:** Existing JSONB selection fields (they become the "persona data picker" — input to generation), existing PDF rendering for legacy resumes, existing variant approval logic (extended, not replaced).

---

## How to Use This Document

1. Find the first 🟡 or ⬜ task — that's where to start
2. Load the REQ section listed in each task via `req-reader` subagent
3. Each task = one commit, sized ≤ 40k tokens of context (TDD + review + fixes included)
4. **Subtask workflow:** Run affected tests → linters → commit (NO push)
5. **Phase-end workflow:** Run full test suite (backend + frontend + E2E) → push → compact
6. After each task: update status (⬜ → ✅), commit, STOP and ask user

**Context management for fresh sessions:** Each subtask is self-contained. A fresh context window needs:
1. This plan (find current task by status icon)
2. The relevant REQ document (via `req-reader` — load the §section listed in the task)
3. The specific files listed in the task description
4. No prior conversation history required

---

## Dependency Chain

```
Phase 1: Database Schema & Models (REQ-025 §4)
    │
    ├── Phase 2: Template System Backend (REQ-025 §6)
    │       │
    │       ├── Phase 3: Export Pipeline Backend (REQ-025 §5)
    │       │
    │       └── Phase 4: Resume Generation Backend (REQ-026 §3-4)
    │
    └── Phase 5: TipTap Editor Component (REQ-025 §3)
            │
            └── Phase 6: Resume Detail Page (REQ-026 §5-6)
                    │
                    └── Phase 7: Resume Creation Flow (REQ-026 §3)
                            │
                            └── Phase 8: Job Variant Backend & UI (REQ-027 §3, §5)
                                    │
                                    └── Phase 9: Diff View & Variant Review (REQ-027 §4, §5)
```

**Ordering rationale:** Schema first (everything depends on it). Backend services before frontend (API must exist for frontend to call). TipTap component before pages that use it. Base resume workflow before variant workflow.

---

## Phase 1: Database Schema & Models (REQ-025 §4)

**Status:** ✅ Complete

*Add markdown content columns to base_resumes and job_variants, create resume_templates table with seed data, update SQLAlchemy models and Pydantic schemas.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-025 §4.1–§4.4 (schema changes, migration plan) |
| 🗃️ **Patterns** | Use `zentropy-db` for migrations, `zentropy-tdd` for tests |
| ✅ **Verify** | `cd backend && pytest tests/ -v`, `ruff check .`, `pyright` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` |
| 📝 **Commit** | One commit per subtask |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Alembic migration — add markdown columns + resume_templates table** | | ✅ |
| | **Read:** REQ-025 §4.1 (BaseResume fields), §4.2 (JobVariant fields), §4.3 (resume_templates table), §4.4 (migration plan). | `req-reader, db, plan` | |
| | | | |
| | **Create migration:** Single Alembic revision with 4 steps: | | |
| | 1. Add `markdown_content` (Text, nullable) and `template_id` (UUID, nullable, FK → resume_templates) to `base_resumes` | | |
| | 2. Add `markdown_content` (Text, nullable) and `snapshot_markdown_content` (Text, nullable) to `job_variants` | | |
| | 3. Create `resume_templates` table (id, name, description, markdown_content, is_system, user_id, display_order, created_at, updated_at) | | |
| | 4. Seed one system template: "Clean & Minimal" (REQ-025 §6.1 for content) | | |
| | | | |
| | **Modify models:** `backend/app/models/resume.py` | | |
| | — `BaseResume`: add `markdown_content: Mapped[str | None]`, `template_id: Mapped[uuid.UUID | None]` with FK | | |
| | — `JobVariant`: add `markdown_content: Mapped[str | None]`, `snapshot_markdown_content: Mapped[str | None]` | | |
| | | | |
| | **Create model:** `backend/app/models/resume_template.py` — `ResumeTemplate` with all fields from REQ-025 §4.3 | | |
| | **Update:** `backend/app/models/__init__.py` — export new model | | |
| | | | |
| | **Test migration:** `alembic upgrade head` + `alembic downgrade -1` + `alembic upgrade head` | | |
| | **Run:** `cd backend && pytest tests/ -v` (regression check) | | |
| | **Done when:** Migration applies cleanly, downgrade works, existing tests pass. | | |
| 2 | **Pydantic schemas + ResumeTemplate repository** | | ✅ |
| | **Read:** REQ-025 §4.3 (template table), §6.4 (template API shapes). Existing patterns: `backend/app/schemas/resume.py`, `backend/app/repositories/base_resume_repository.py`. | `req-reader, db, tdd, plan` | |
| | | | |
| | **Update schemas:** `backend/app/schemas/resume.py` | | |
| | — Add `markdown_content` and `template_id` to `BaseResumeResponse`, `CreateBaseResumeRequest`, `UpdateBaseResumeRequest` | | |
| | — Add `markdown_content` and `snapshot_markdown_content` to `JobVariantResponse`, `UpdateJobVariantRequest` | | |
| | | | |
| | **Create schemas:** `backend/app/schemas/resume_template.py` | | |
| | — `ResumeTemplateResponse`, `CreateResumeTemplateRequest`, `UpdateResumeTemplateRequest`, `ResumeTemplateListResponse` | | |
| | | | |
| | **Create repository:** `backend/app/repositories/resume_template_repository.py` | | |
| | — CRUD operations: list (system + user's own), get, create, update, delete | | |
| | — `list_available(user_id)` returns system templates + user's templates, ordered by `display_order` | | |
| | | | |
| | **Tests:** Unit tests for repository CRUD + schema validation | | |
| | **Run:** `cd backend && pytest tests/ -v` | | |
| | **Done when:** Templates can be created/read/updated/deleted. Schemas serialize correctly. All tests pass. | | |
| 3 | **Phase 1 Gate** — Full test suite + push | `phase-gate` | ✅ |
| | Run: `cd backend && pytest tests/ -v`. `cd frontend && npm test -- --run && npm run typecheck && npm run lint`. Push with SSH keep-alive. | | |

#### Phase 1 Notes

**Migration ordering:** The `resume_templates` table must be created before the FK on `base_resumes.template_id` is added. Use a single migration with proper ordering.

**Seed template content:** Use the "Clean & Minimal" template from REQ-025 §6.1. The template contains `{placeholder}` markers that the generation service will replace.

**No data migration needed:** Existing resumes have `markdown_content = NULL`. They continue working via the JSONB path until the user generates or writes markdown content.

---

## Phase 2: Template System Backend (REQ-025 §6)

**Status:** ✅ Complete

*Template service layer and API endpoints for CRUD operations on resume templates.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-025 §6.2–§6.4 (template metadata, picker UI, API endpoints) |
| 🧪 **TDD** | Write tests first — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Use `zentropy-api` for endpoints, `zentropy-tdd` for tests |
| ✅ **Verify** | `cd backend && pytest tests/ -v`, `ruff check .` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` |
| 📝 **Commit** | One commit per subtask |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 4 | **Template service + API endpoints** | | ✅ |
| | **Read:** REQ-025 §6.2–§6.4 (template metadata, API endpoints), §8 (validation rules). Existing patterns: `backend/app/services/persona_service.py`, `backend/app/api/v1/base_resumes.py`. | `req-reader, api, tdd, security, plan` | |
| | | | |
| | **Create service:** `backend/app/services/resume_template_service.py` | | |
| | — `list_templates(user_id)` — system + user's own templates | | |
| | — `get_template(template_id, user_id)` — with ownership check | | |
| | — `create_template(user_id, data)` — validate markdown (must parse, must contain heading) | | |
| | — `update_template(template_id, user_id, data)` — reject if system template | | |
| | — `delete_template(template_id, user_id)` — reject if system template | | |
| | | | |
| | **Create router:** `backend/app/api/v1/resume_templates.py` | | |
| | — `GET /resume-templates` — list available templates | | |
| | — `GET /resume-templates/{id}` — get template details | | |
| | — `POST /resume-templates` — create user template (upload markdown) | | |
| | — `PATCH /resume-templates/{id}` — update user template | | |
| | — `DELETE /resume-templates/{id}` — delete user template | | |
| | | | |
| | **Register router** in `backend/app/api/v1/__init__.py` | | |
| | | | |
| | **Tests:** Service + endpoint tests (CRUD, ownership checks, system template protection, markdown validation) | | |
| | **Run:** `cd backend && pytest tests/ -v` | | |
| | **Done when:** All 5 endpoints work, system templates protected, validation enforced. | | |
| 5 | **Phase 2 Gate** — Full test suite + push | `phase-gate` | ✅ |
| | Run: `cd backend && pytest tests/ -v`. `cd frontend && npm test -- --run && npm run typecheck && npm run lint`. Push with SSH keep-alive. | | |

---

## Phase 3: Export Pipeline Backend (REQ-025 §5)

**Status:** ✅ Complete

*Markdown-to-PDF and markdown-to-DOCX export services, plus new API endpoints for exporting resumes with markdown content.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-025 §5.1–§5.5 (export architecture, PDF, DOCX, endpoints, feature mapping) |
| 🧪 **TDD** | Write tests first — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Existing PDF: `backend/app/services/pdf_generation.py`. Use `zentropy-api` for endpoints |
| ✅ **Verify** | `cd backend && pytest tests/ -v`, `ruff check .` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` |
| 📝 **Commit** | One commit per subtask |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 6 | **Install markdown-it-py + python-docx, create MarkdownPdfRenderer** | | ✅ |
| | **Read:** REQ-025 §5.1 (architecture), §5.2 (PDF export), §5.5 (feature mapping). Existing: `backend/app/services/pdf_generation.py` for ReportLab patterns. | `req-reader, tdd, plan` | |
| | | | |
| | **Install:** Add `markdown-it-py>=3.0.0` and `python-docx>=1.0.0` to `backend/pyproject.toml` | | |
| | | | |
| | **Create:** `backend/app/services/markdown_pdf_renderer.py` | | |
| | — Parse markdown via `markdown-it-py` into AST tokens | | |
| | — Map tokens to ReportLab Platypus flowables (Paragraph, ListFlowable, HRFlowable, etc.) | | |
| | — Style definitions matching REQ-025 §5.5 (heading sizes, bold, italic, bullets, etc.) | | |
| | — `render_pdf(markdown_content: str) -> bytes` — returns PDF bytes | | |
| | | | |
| | **Tests:** Unit tests — render each supported markdown feature, verify PDF bytes are valid (check `%PDF` header), test edge cases (empty content, headings only, nested lists) | | |
| | **Run:** `cd backend && pytest tests/ -v` | | |
| | **Done when:** All supported markdown features render to valid PDF. Tests pass. | | |
| 7 | **MarkdownDocxRenderer service** | | ✅ |
| | **Read:** REQ-025 §5.3 (DOCX export), §5.5 (feature mapping). | `req-reader, tdd, plan` | |
| | | | |
| | **Create:** `backend/app/services/markdown_docx_renderer.py` | | |
| | — Parse markdown via `markdown-it-py` (same parser as PDF) | | |
| | — Map tokens to python-docx elements (`add_heading`, `add_paragraph`, bold/italic runs, etc.) | | |
| | — `render_docx(markdown_content: str) -> bytes` — returns DOCX bytes (via BytesIO) | | |
| | | | |
| | **Tests:** Unit tests — render each supported feature, verify DOCX bytes are valid (check PK zip header), test edge cases | | |
| | **Run:** `cd backend && pytest tests/ -v` | | |
| | **Done when:** All supported markdown features render to valid DOCX. Tests pass. | | |
| 8 | **Export API endpoints** | | ✅ |
| | **Read:** REQ-025 §5.4 (export endpoints), §8 (validation: export requires content). Existing: `backend/app/api/v1/base_resumes.py` download endpoint for patterns. | `req-reader, api, tdd, security, plan` | |
| | | | |
| | **Add to** `backend/app/api/v1/base_resumes.py`: | | |
| | — `GET /base-resumes/{id}/export/pdf` — render markdown → PDF, return binary download | | |
| | — `GET /base-resumes/{id}/export/docx` — render markdown → DOCX, return binary download | | |
| | | | |
| | **Add to** `backend/app/api/v1/job_variants.py`: | | |
| | — `GET /job-variants/{id}/export/pdf` — render variant markdown → PDF | | |
| | — `GET /job-variants/{id}/export/docx` — render variant markdown → DOCX | | |
| | | | |
| | **Validation:** Return 422 if `markdown_content` is NULL | | |
| | **Headers:** `Content-Type: application/pdf` or `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `Content-Disposition: attachment; filename=...` | | |
| | | | |
| | **Tests:** Endpoint tests (happy path, missing content → 422, ownership check) | | |
| | **Run:** `cd backend && pytest tests/ -v` | | |
| | **Done when:** All 4 export endpoints return valid files. Validation works. Tests pass. | | |
| 9 | **Phase 3 Gate** — Full test suite + push | `phase-gate` | ✅ |
| | Run: `cd backend && pytest tests/ -v`. `cd frontend && npm test -- --run && npm run typecheck && npm run lint`. Push with SSH keep-alive. | | |

#### Phase 3 Notes

**Coexistence with existing PDF pipeline:** The existing `pdf_generation.py` renders from JSONB selections. The new `markdown_pdf_renderer.py` renders from `markdown_content`. The export endpoints check whether `markdown_content` is populated and use the appropriate renderer. The existing `download` endpoint continues to work for legacy resumes.

**Dependency installation:** Both `markdown-it-py` and `python-docx` are added in §6 since the DOCX renderer also uses `markdown-it-py` for parsing.

---

## Phase 4: Resume Generation Backend (REQ-026 §3-4)

**Status:** ✅ Complete

*Deterministic template fill (free path) and LLM-assisted generation (paid path) services, plus the generation API endpoint.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-026 §3.4 (deterministic fill), §4.1–§4.6 (LLM generation), §8 (validation) |
| 🧪 **TDD** | Write tests first — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Existing prompts: `backend/app/prompts/ghostwriter.py`. Metering: `MeteredLLMProvider`. Use `zentropy-provider` for LLM calls |
| ✅ **Verify** | `cd backend && pytest tests/ -v`, `ruff check .` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` |
| 📝 **Commit** | One commit per subtask |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 10 | **Deterministic template fill service** | | ✅ |
| | **Read:** REQ-026 §3.4 (deterministic fill), §3.3 (persona data picker). Existing: `backend/app/services/pdf_generation.py:gather_base_resume_content()` for data gathering pattern. | `req-reader, tdd, plan` | |
| | | | |
| | **Create:** `backend/app/services/resume_generation_service.py` | | |
| | — `template_fill(resume: BaseResume, template: ResumeTemplate, session: AsyncSession) -> str` | | |
| | — Gather persona data via existing `gather_base_resume_content()` | | |
| | — Replace `{placeholder}` markers in template with gathered data | | |
| | — Return completed markdown string | | |
| | | | |
| | **Tests:** Unit tests with mock persona data — verify all placeholders replaced, empty sections handled gracefully, skills formatted as list | | |
| | **Run:** `cd backend && pytest tests/ -v` | | |
| | **Done when:** Template fill produces complete markdown from persona data. Tests pass. | | |
| 11 | **LLM resume generation prompt + service** | | ✅ |
| | **Read:** REQ-026 §4.2–§4.5 (generation options, page limit, prompt, constraints). REQ-010 for modification limits. Existing prompts: `backend/app/prompts/ghostwriter.py` for pattern. | `req-reader, provider, tdd, security, plan` | |
| | | | |
| | **Create prompt:** `backend/app/prompts/resume_generation.py` | | |
| | — `RESUME_GENERATION_SYSTEM_PROMPT` — role, constraints, output format (raw markdown) | | |
| | — `_RESUME_GENERATION_USER_TEMPLATE` — template structure, persona data, target role, page limit, emphasis, voice profile | | |
| | — `build_resume_generation_prompt(...)` — builder function with sanitization (follow `ghostwriter.py` pattern) | | |
| | | | |
| | **Add to** `backend/app/services/resume_generation_service.py`: | | |
| | — `llm_generate(resume: BaseResume, template: ResumeTemplate, options: GenerateOptions, session: AsyncSession) -> tuple[str, dict]` | | |
| | — Gather persona data, build prompt, call LLM via `MeteredLLMProvider`, return (markdown, metadata) | | |
| | — Uses `TaskType.RESUME_TAILORING` for model routing | | |
| | | | |
| | **Tests:** Unit tests with mocked LLM — verify prompt contains all expected sections, sanitization applied, metering called | | |
| | **Run:** `cd backend && pytest tests/ -v` | | |
| | **Done when:** Prompt builder produces correct prompt. LLM service calls provider correctly. Tests pass. | | |
| 12 | **Generation API endpoint** | | ✅ |
| | **Read:** REQ-026 §4.6 (generation API), §3.4 (template fill endpoint), §8 (validation). | `req-reader, api, tdd, security, plan` | |
| | | | |
| | **Create schema:** Add `GenerateResumeRequest` and `GenerateResumeResponse` to `backend/app/schemas/resume.py` | | |
| | — Request: `method` ("ai" or "template_fill"), `page_limit` (1-3), `emphasis`, `include_sections`, `template_id` | | |
| | — Response: `markdown_content`, `word_count`, `method`, `model_used` (nullable), `generation_cost_cents` | | |
| | | | |
| | **Add to** `backend/app/api/v1/base_resumes.py`: | | |
| | — `POST /base-resumes/{id}/generate` | | |
| | — Fork on `method`: "ai" → `llm_generate()`, "template_fill" → `template_fill()` | | |
| | — "ai" path: check credits (402 if insufficient), use `MeteredLLMProvider` | | |
| | — Save result to `resume.markdown_content`, return response | | |
| | | | |
| | **Tests:** Endpoint tests (both methods, credit check, validation, missing persona data) | | |
| | **Run:** `cd backend && pytest tests/ -v` | | |
| | **Done when:** Both generation paths work via single endpoint. Credit gating works. Tests pass. | | |
| 13 | **Phase 4 Gate** — Full test suite + push | `phase-gate` | ✅ |
| | Run: `cd backend && pytest tests/ -v`. `cd frontend && npm test -- --run && npm run typecheck && npm run lint`. Push with SSH keep-alive. | | |

#### Phase 4 Notes

**TaskType reuse:** `TaskType.RESUME_TAILORING` already has routing entries for Claude (Sonnet) and Gemini (Flash). The admin routing table lets the user swap models without code changes.

**Metering:** The `MeteredLLMProvider` automatically records usage and deducts credits. The generation service just calls `provider.generate()` and the metering wraps it.

**Two-endpoint pattern:** Both "ai" and "template_fill" share `POST /base-resumes/{id}/generate`. The backend forks on the `method` parameter. Same response shape.

---

## Phase 5: TipTap Editor Component (REQ-025 §3)

**Status:** ✅ Complete

*Install TipTap npm packages, create the ResumeEditor component with toolbar, status bar, and markdown round-trip tests.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-025 §3.1–§3.5 (package selection, architecture, features, toolbar, status bar), §7 (round-trip guarantee) |
| 🧪 **TDD** | Write tests first — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Existing component patterns: `frontend/src/components/resume/`. Use Tailwind + shadcn |
| ✅ **Verify** | `cd frontend && npm test -- --run && npm run typecheck && npm run lint` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` + `ui-reviewer` |
| 📝 **Commit** | One commit per subtask |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 14 | **Install TipTap packages + ResumeEditor component** | | ✅ |
| | **Read:** REQ-025 §3.1 (packages), §3.2 (architecture), §3.3 (supported features), §3.4 (toolbar). | `req-reader, tdd, ui, plan` | |
| | | | |
| | **Install:** `npm install @tiptap/react @tiptap/pm @tiptap/starter-kit @tiptap/markdown @tiptap/extension-link` | | |
| | | | |
| | **Create:** `frontend/src/components/editor/resume-editor.tsx` | | |
| | — `"use client"` directive | | |
| | — `useEditor()` with: StarterKit, Link, Markdown extensions | | |
| | — `immediatelyRender: false` for SSR safety | | |
| | — Props: `initialContent` (markdown string), `editable`, `onChange` callback, `placeholder` | | |
| | — Content extraction: `editor.storage.markdown.getMarkdown()` | | |
| | | | |
| | **Create:** `frontend/src/components/editor/editor-toolbar.tsx` | | |
| | — Button groups: Bold, Italic | H1-H4 | Bullet, Ordered | HR, Link | Undo, Redo | | |
| | — Active state highlighting when cursor in formatted block | | |
| | — `data-testid` attributes per REQ-025 §3.4 | | |
| | | | |
| | **Tests:** Unit tests — editor renders, toolbar buttons toggle formatting, markdown round-trip (§7.2 test categories: headings, inline, lists, links, HR, mixed content, edge cases) | | |
| | **Run:** `cd frontend && npm test -- --run && npm run typecheck` | | |
| | **Done when:** Editor renders markdown, toolbar works, round-trip preserves content. Tests pass. | | |
| 15 | **EditorStatusBar + auto-save hook** | | ✅ |
| | **Read:** REQ-025 §3.5 (status bar). REQ-026 §7.1–§7.2 (save strategy, status indicator). | `req-reader, tdd, ui, plan` | |
| | | | |
| | **Create:** `frontend/src/components/editor/editor-status-bar.tsx` | | |
| | — Word count (from editor text), page estimate (words / 350), save status indicator | | |
| | — Status states: "Saved", "Saving...", "Unsaved changes", "Save failed — retry" | | |
| | | | |
| | **Create:** `frontend/src/hooks/use-auto-save.ts` | | |
| | — Debounced save (2s after last keystroke) | | |
| | — `PATCH /base-resumes/{id}` with `{ markdown_content: "..." }` | | |
| | — Optimistic concurrency: send `updated_at`, handle 409 Conflict | | |
| | — Returns save status for status bar | | |
| | — `beforeunload` warning if unsaved changes | | |
| | | | |
| | **Tests:** StatusBar unit tests (word count, page estimate, status states). Auto-save hook tests (debounce, save call, conflict handling). | | |
| | **Run:** `cd frontend && npm test -- --run && npm run typecheck` | | |
| | **Done when:** Status bar shows live stats. Auto-save debounces and persists. Conflict detection works. Tests pass. | | |
| 16 | **Phase 5 Gate** — Full test suite + push | `phase-gate` | ✅ |
| | Run: `cd backend && pytest tests/ -v`. `cd frontend && npm test -- --run && npm run typecheck && npm run lint`. Push with SSH keep-alive. | | |

#### Phase 5 Notes

**SSR safety:** TipTap is a client-side library. The `"use client"` directive + `immediatelyRender: false` prevents SSR hydration issues in Next.js.

**Markdown extension:** `@tiptap/markdown` (v3.x) is the official package. It replaces the community `tiptap-markdown` which is deprecated. Configuration: `storage: true` to enable `editor.storage.markdown.getMarkdown()`.

**Round-trip testing:** Tests in §14 verify that markdown → TipTap → markdown produces semantically equivalent output for all supported features (REQ-025 §7.2). Minor formatting differences (trailing whitespace, blank line count) are acceptable.

---

## Phase 6: Resume Detail Page Update (REQ-026 §5-6)

**Status:** ✅ Complete

*Update the resume detail page with toggle view (Preview/Edit), integrate TipTap editor in edit mode with persona reference panel.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-026 §5.1–§5.4 (editor layout, reference panel, editing features), §6.1–§6.3 (toggle view, action buttons, content preview) |
| 🧪 **TDD** | Write tests first — follow `zentropy-tdd` |
| ✅ **Verify** | `cd frontend && npm test -- --run && npm run typecheck && npm run lint` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` + `ui-reviewer` |
| 📝 **Commit** | One commit per subtask |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 17 | **Resume detail page — toggle view (Preview/Edit)** | | ✅ |
| | **Read:** REQ-026 §6.1 (toggle view layout), §6.2 (action buttons), §6.3 (content preview). Existing: `frontend/src/components/resume/resume-detail.tsx`. | `req-reader, tdd, ui, plan` | |
| | | | |
| | **Modify:** `frontend/src/components/resume/resume-detail.tsx` (or create wrapper) | | |
| | — Add view toggle state: Preview (default) | Edit | | |
| | — Preview mode: read-only TipTap rendering of `markdown_content` | | |
| | — Edit mode: full TipTap editor with toolbar + status bar + auto-save | | |
| | — "No content" state: prompt with [Generate with AI] and [Start from Template] buttons when `markdown_content` is NULL | | |
| | — Action buttons: Edit, Done Editing, Generate with AI, Export PDF/DOCX, Edit Selections | | |
| | | | |
| | **Update TypeScript types:** `frontend/src/types/resume.ts` — add `markdown_content`, `template_id` to BaseResume interface | | |
| | | | |
| | **Tests:** Toggle between Preview/Edit, no-content state renders prompt, action buttons shown per mode | | |
| | **Run:** `cd frontend && npm test -- --run && npm run typecheck` | | |
| | **Done when:** Resume detail page toggles between Preview and Edit. Read-only TipTap renders markdown. Tests pass. | | |
| 18 | **Persona reference panel** | | ✅ 2026-03-06 |
| | **Read:** REQ-026 §5.1–§5.2 (panel layout, behavior). Existing persona API: `frontend/src/lib/api/personas.ts`. | `req-reader, tdd, ui, plan` | |
| | | | |
| | **Create:** `frontend/src/components/editor/persona-reference-panel.tsx` | | |
| | — Collapsible sections: Contact Info, Work History, Education, Skills, Certifications | | |
| | — Work History: expandable per job with bullet list | | |
| | — Click-to-copy: click any item to copy text to clipboard (toast confirmation) | | |
| | — Read-only: no editing in panel | | |
| | — Responsive: collapses to toggle button on narrow screens | | |
| | — Data fetched from existing persona API endpoints | | |
| | | | |
| | **Wire into edit mode:** Show panel alongside TipTap editor in Edit mode (left panel, editor right) | | |
| | | | |
| | **Tests:** Panel renders persona data, sections expand/collapse, click-to-copy works, responsive collapse | | |
| | **Run:** `cd frontend && npm test -- --run && npm run typecheck` | | |
| | **Done when:** Reference panel shows persona data alongside editor. Copy works. Tests pass. | | |
| 19 | **Phase 6 Gate** — Full test suite + push | `phase-gate` | ✅ 2026-03-06 |
| | Run: `cd backend && pytest tests/ -v`. `cd frontend && npm test -- --run && npm run typecheck && npm run lint`. `npx playwright test`. Push with SSH keep-alive. | | |

---

## Phase 7: Resume Creation Flow (REQ-026 §3)

**Status:** ✅ Complete

*Update the new resume wizard with template picker, generation options, and wire the creation flow through to the TipTap editor.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-026 §3.1–§3.4 (creation flows, dialog, persona data picker, deterministic fill), §4.2 (generation options) |
| 🧪 **TDD** | Write tests first — follow `zentropy-tdd` |
| ✅ **Verify** | `cd frontend && npm test -- --run && npm run typecheck && npm run lint` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` + `ui-reviewer` |
| 📝 **Commit** | One commit per subtask |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 20 | **Template picker + new resume dialog update** | | ✅ 2026-03-06 |
| | **Read:** REQ-025 §6.3 (template picker UI), REQ-026 §3.2 (new resume dialog). Existing: `frontend/src/components/resume/new-resume-wizard.tsx`. | `req-reader, tdd, ui, plan` | |
| | | | |
| | **Create:** `frontend/src/components/editor/template-picker.tsx` | | |
| | — Grid of template cards (system + user's own) | | |
| | — Fetch from `GET /resume-templates` | | |
| | — Selected state with visual highlight | | |
| | — Default template pre-selected | | |
| | | | |
| | **Modify:** `frontend/src/components/resume/new-resume-wizard.tsx` | | |
| | — Add template selection step | | |
| | — Add creation method choice: "Generate with AI" vs "Start from Template" | | |
| | — Wire template selection to resume creation API | | |
| | | | |
| | **Tests:** Template picker renders templates, selection works, dialog shows both creation paths | | |
| | **Run:** `cd frontend && npm test -- --run && npm run typecheck` | | |
| | **Done when:** Template picker works. New resume dialog offers both paths. Tests pass. | | |
| 21 | **Generation options panel + wire creation flow** | | ✅ |
| | **Read:** REQ-026 §4.2 (generation options panel), §4.3 (page limit), §4.7 (regeneration). | `req-reader, tdd, ui, plan` | |
| | | | |
| | **Create:** `frontend/src/components/editor/generation-options-panel.tsx` | | |
| | — Page limit dropdown (1/2/3 pages) | | |
| | — Emphasis dropdown (Technical/Leadership/Balanced/Industry-specific) | | |
| | — Section checkboxes (Summary, Experience, Education, Skills, Certifications, Volunteer) | | |
| | — [Generate Resume] button | | |
| | | | |
| | **Wire frontend → backend flow:** | | |
| | — "Generate with AI" → show options panel → call `POST /base-resumes/{id}/generate` with `method: "ai"` → load result into TipTap | | |
| | — "Start from Template" → call `POST /base-resumes/{id}/generate` with `method: "template_fill"` → load result into TipTap | | |
| | — Loading state in editor: "Generating your resume..." | | |
| | — Credit check: if insufficient, show toast and offer template fill as fallback | | |
| | — Regeneration: [Regenerate] button reopens options panel | | |
| | | | |
| | **Tests:** Options panel renders, generation flow calls API, loading state, credit fallback | | |
| | **Run:** `cd frontend && npm test -- --run && npm run typecheck` | | |
| | **Done when:** Both creation paths work end-to-end (frontend → API → editor). Tests pass. | | |
| 22 | **Phase 7 Gate** — Full test suite + E2E + push | `phase-gate` | ✅ |
| | Run: `cd backend && pytest tests/ -v`. `cd frontend && npm test -- --run && npm run typecheck && npm run lint`. `npx playwright test`. Push with SSH keep-alive. | | |

#### Phase 7 Notes

**Persona data picker reframe:** The existing checkbox/drag-and-drop UI (`ResumeContentCheckboxes`, `ReorderableList`) already works for selecting which jobs/bullets/education/etc. to include. It stays as-is but is now positioned as a pre-generation step rather than the resume editing surface itself. This reframe is primarily a UX/label change, not a code rewrite.

**Credit fallback:** If the user clicks "Generate with AI" but has insufficient credits, the frontend should show a toast ("Insufficient credits") and offer "Start from Template" as a free alternative.

---

## Phase 8: Job Variant Backend & UI (REQ-027 §3, §5)

**Status:** ✅ Complete

*Backend endpoints for variant creation (manual + LLM tailoring) and frontend variant creation UI. Extends existing job variant infrastructure.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-027 §3 (variant creation flows), §5 (approval flow), §6 (ghostwriter integration), §7 (validation) |
| 🧪 **TDD** | Write tests first — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Existing: `backend/app/api/v1/job_variants.py`, `backend/app/services/content_generation/` |
| ✅ **Verify** | `cd backend && pytest tests/ -v`, `cd frontend && npm test -- --run` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` + `ui-reviewer` (for §24) |
| 📝 **Commit** | One commit per subtask |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 23 | **Variant creation endpoints — manual + LLM tailoring** | | ✅ |
| | **Read:** REQ-027 §3 (variant creation, §4.1 two paths, §4.2 LLM flow, §4.3 manual flow), §6 (ghostwriter integration, §6.1–§6.3). Existing: `backend/app/api/v1/job_variants.py`, `backend/app/prompts/ghostwriter.py`. | `req-reader, api, provider, tdd, security, plan` | |
| | | | |
| | **Create prompt:** Add to `backend/app/prompts/ghostwriter.py` (or new file `resume_tailoring.py`): | | |
| | — `RESUME_TAILORING_SYSTEM_PROMPT` — tailoring expert, modify markdown for job fit, preserve voice | | |
| | — `build_resume_tailoring_prompt(...)` — base resume markdown, job requirements, tailoring analysis, modification limits | | |
| | | | |
| | **Add to** `backend/app/api/v1/job_variants.py` or create service: | | |
| | — `POST /job-variants/create-for-job` (or extend existing `POST /job-variants`): | | |
| | — `method: "manual"` → copy base resume's `markdown_content` to variant | | |
| | — `method: "ai"` → LLM tailors base resume's markdown for job → save as variant `markdown_content` | | |
| | — LLM path: check credits (402 if insufficient), use `MeteredLLMProvider` with `TaskType.RESUME_TAILORING` | | |
| | | | |
| | **Update variant approval** in existing approve endpoint: | | |
| | — On approval, snapshot `markdown_content` → `snapshot_markdown_content` (alongside existing JSONB snapshots) | | |
| | | | |
| | **Tests:** Both creation paths, credit gating, approval snapshots markdown, validation (requires job posting + base resume) | | |
| | **Run:** `cd backend && pytest tests/ -v` | | |
| | **Done when:** Both variant creation paths work. Approval snapshots markdown. Tests pass. | | |
| 24 | **Variant creation UI + job requirements panel** | | ✅ |
| | **Read:** REQ-027 §3 (§4.3 manual flow, §4.4 job requirements panel, §3.5 variant editing). Existing variant UI: `frontend/src/components/resume/variants-list.tsx`. | `req-reader, tdd, ui, plan` | |
| | | | |
| | **Create:** `frontend/src/components/editor/job-requirements-panel.tsx` | | |
| | — Shows job posting key skills, keywords, fit score | | |
| | — Data from job posting API | | |
| | | | |
| | **Update:** Variant creation flow in frontend | | |
| | — "Draft Resume" button (LLM path) on job detail page | | |
| | — "Create Variant" button (manual path) with base resume selection | | |
| | — Navigate to variant editor with TipTap + job requirements panel | | |
| | | | |
| | **Update TypeScript types:** Add `markdown_content`, `snapshot_markdown_content` to JobVariant interface | | |
| | | | |
| | **Tests:** Variant creation UI, job requirements panel renders, both creation paths trigger correct API calls | | |
| | **Run:** `cd frontend && npm test -- --run && npm run typecheck` | | |
| | **Done when:** Users can create variants via both paths. Job requirements panel shows. Tests pass. | | |
| 25 | **Phase 8 Gate** — Full test suite + push | `phase-gate` | ✅ |
| | Run: `cd backend && pytest tests/ -v`. `cd frontend && npm test -- --run && npm run typecheck && npm run lint`. `npx playwright test`. Push with SSH keep-alive. | | |

---

## Phase 9: Diff View & Variant Review (REQ-027 §4, §5)

**Status:** ✅ Complete

*Word-level diff component comparing master and variant markdown, variant review page with approval actions, and final regression gate.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-027 §4 (diff view), §5 (variant review and approval) |
| 🧪 **TDD** | Write tests first — follow `zentropy-tdd` |
| ✅ **Verify** | `cd frontend && npm test -- --run && npm run typecheck && npm run lint` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` + `ui-reviewer` |
| 📝 **Commit** | One commit per subtask |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 26 | **Install diff package + DiffView component** | | ✅ 2026-03-06 |
| | **Read:** REQ-027 §4.1–§4.4 (when to show diff, layout, highlighting, implementation). | `req-reader, tdd, ui, plan` | |
| | | | |
| | **Install:** `npm install diff` (by kpdecker, standard word-level diff library) | | |
| | | | |
| | **Create:** `frontend/src/components/editor/diff-view.tsx` | | |
| | — Props: `masterMarkdown`, `variantMarkdown` | | |
| | — Word-level diff using `diffWords()` from `diff` package | | |
| | — Side-by-side layout: master (read-only, left) | variant (right) | | |
| | — Highlighting: green (additions), red (removals), yellow (modifications) | | |
| | — Fallback: if diff fails, show variant without highlighting (REQ-027 §8) | | |
| | | | |
| | **Tests:** Diff highlights additions/removals/modifications, handles empty docs, fallback on error | | |
| | **Run:** `cd frontend && npm test -- --run && npm run typecheck` | | |
| | **Done when:** DiffView renders word-level diff with color highlighting. Tests pass. | | |
| 27 | **Variant review page + approval actions** | | ✅ |
| | **Read:** REQ-027 §4.5 (diff actions), §5.1–§5.3 (approval flow, post-approval, state machine). Existing: `frontend/src/app/(main)/resumes/[id]/variants/[variantId]/review/page.tsx`. | `req-reader, tdd, ui, plan` | |
| | | | |
| | **Create/update:** Variant review page | | |
| | — DiffView showing master vs variant (for LLM-generated variants) | | |
| | — Agent reasoning display (from LLM response) | | |
| | — TipTap editor (editable in Draft status, read-only in Approved) | | |
| | — Action buttons: [Approve], [Regenerate], [Edit], [Archive], [Export PDF/DOCX] | | |
| | — Approval flow: confirmation dialog → `POST /job-variants/{id}/approve` → read-only mode | | |
| | — Status badge: Draft / Approved / Archived | | |
| | | | |
| | **Tests:** Review page renders diff (LLM variants), no diff for manual variants, approval flow, read-only after approval, action buttons per status | | |
| | **Run:** `cd frontend && npm test -- --run && npm run typecheck` | | |
| | **Done when:** Full variant review workflow works. Diff shows for LLM variants. Approval locks variant. Tests pass. | | |
| 28 | **Phase 9 Gate (Final)** — Full regression + push | `phase-gate` | ✅ |
| | Run full suite: `cd backend && pytest tests/ -v`. `cd frontend && npm test -- --run && npm run typecheck && npm run lint`. `npx playwright test`. Push with SSH keep-alive. Update this plan status to ✅ Complete. Update `CLAUDE.md` Current Status section. Update backlog PBI #24 status. | | |

#### Phase 9 Notes

**Diff library:** `diff` by kpdecker is the standard choice (REQ-027 §10.1 design decision). `diffWords()` provides word-level granularity — coarser than character-level (too noisy) but finer than line-level (too coarse for resume content).

**Diff is display-only:** The canonical content is always the variant's `markdown_content`. The diff view is purely for helping the user understand what changed. If diff computation fails, the variant is still fully usable.

**State machine:** Draft → Approved (via approve), Draft → Archived (via archive), Approved → Archived (via archive). Already partially implemented in existing `job_variants.py` approval endpoint — extend to handle `markdown_content` snapshots.

---

## Task Count Summary

| Phase | Subtasks | Gates | Total |
|-------|----------|-------|-------|
| 1: Database Schema & Models | 2 | 1 | 3 |
| 2: Template System Backend | 1 | 1 | 2 |
| 3: Export Pipeline Backend | 3 | 1 | 4 |
| 4: Resume Generation Backend | 3 | 1 | 4 |
| 5: TipTap Editor Component | 2 | 1 | 3 |
| 6: Resume Detail Page | 2 | 1 | 3 |
| 7: Resume Creation Flow | 2 | 1 | 3 |
| 8: Job Variant Backend & UI | 2 | 1 | 3 |
| 9: Diff View & Variant Review | 2 | 1 | 3 |
| **Total** | **19 subtasks** | **9 gates** | **28 items** |

---

## Critical Files Reference

### Backend — Modified

| File | Phase | Changes |
|------|-------|---------|
| `backend/app/models/resume.py` | §1 | Add markdown fields to BaseResume + JobVariant |
| `backend/app/models/__init__.py` | §1 | Export ResumeTemplate |
| `backend/app/schemas/resume.py` | §2, §12 | Add markdown fields + generation request/response |
| `backend/app/api/v1/base_resumes.py` | §8, §12 | Export endpoints + generation endpoint |
| `backend/app/api/v1/job_variants.py` | §8, §23 | Export endpoints + variant creation with markdown |
| `backend/app/api/v1/__init__.py` | §4 | Register resume_templates router |
| `backend/pyproject.toml` | §6 | Add markdown-it-py, python-docx |

### Backend — New

| File | Phase | Purpose |
|------|-------|---------|
| `backend/app/models/resume_template.py` | §1 | ResumeTemplate model |
| `backend/app/schemas/resume_template.py` | §2 | Template Pydantic schemas |
| `backend/app/repositories/resume_template_repository.py` | §2 | Template CRUD repository |
| `backend/app/services/resume_template_service.py` | §4 | Template business logic |
| `backend/app/api/v1/resume_templates.py` | §4 | Template API endpoints |
| `backend/app/services/markdown_pdf_renderer.py` | §6 | Markdown → PDF via ReportLab |
| `backend/app/services/markdown_docx_renderer.py` | §7 | Markdown → DOCX via python-docx |
| `backend/app/services/resume_generation_service.py` | §10–§11 | Template fill + LLM generation |
| `backend/app/prompts/resume_generation.py` | §11 | Resume generation prompts |
| Alembic migration file | §1 | Schema changes |

### Frontend — Modified

| File | Phase | Changes |
|------|-------|---------|
| `frontend/src/types/resume.ts` | §17, §24 | Add markdown fields to interfaces |
| `frontend/src/components/resume/resume-detail.tsx` | §17 | Toggle view (Preview/Edit) |
| `frontend/src/components/resume/new-resume-wizard.tsx` | §20 | Template picker + creation paths |
| `frontend/src/components/resume/variants-list.tsx` | §24 | Variant creation buttons |
| `frontend/package.json` | §14, §26 | TipTap + diff packages |

### Frontend — New

| File | Phase | Purpose |
|------|-------|---------|
| `frontend/src/components/editor/resume-editor.tsx` | §14 | TipTap editor component |
| `frontend/src/components/editor/editor-toolbar.tsx` | §14 | Formatting toolbar |
| `frontend/src/components/editor/editor-status-bar.tsx` | §15 | Word count, page estimate, save status |
| `frontend/src/components/editor/persona-reference-panel.tsx` | §18 | Persona data reference |
| `frontend/src/components/editor/template-picker.tsx` | §20 | Template selection grid |
| `frontend/src/components/editor/generation-options-panel.tsx` | §21 | Page limit, emphasis, sections |
| `frontend/src/components/editor/job-requirements-panel.tsx` | §24 | Job posting requirements |
| `frontend/src/components/editor/diff-view.tsx` | §26 | Word-level diff component |
| `frontend/src/hooks/use-auto-save.ts` | §15 | Debounced auto-save hook |

---

## New Dependencies

### Frontend (npm)

| Package | Purpose | Added In |
|---------|---------|----------|
| `@tiptap/react` | React integration | §14 |
| `@tiptap/pm` | ProseMirror peer dep | §14 |
| `@tiptap/starter-kit` | Core extensions bundle | §14 |
| `@tiptap/markdown` | Markdown ↔ HTML conversion | §14 |
| `@tiptap/extension-link` | Link support | §14 |
| `diff` | Word-level diff for variant review | §26 |

### Backend (pip)

| Package | Purpose | Added In |
|---------|---------|----------|
| `markdown-it-py` >=3.0.0 | Markdown → AST parsing for export | §6 |
| `python-docx` >=1.0.0 | DOCX generation | §6 |

---

## Change Log

| Date | Changes |
|------|---------|
| 2026-03-05 | Initial plan. 9 phases, 28 items (19 subtasks + 9 gates). Covers REQ-025, REQ-026, REQ-027. |
