# REQ-031: Services Layer Reorganization

**Status:** Not Started
**Version:** 0.1
**PRD Reference:** Internal — Code Organization & Maintainability
**Backlog Item:** N/A
**Last Updated:** 2026-03-29

---

## 1. Overview

The `backend/app/services/` directory contains 86 Python modules in a flat structure. At this scale, the flat layout creates three problems:

1. **Navigation overhead.** An LLM or developer opening the directory sees 86 files with no grouping signal. Finding "where does scoring logic live?" requires reading filenames or grep.
2. **Missing coordination context.** 95% of module docstrings document *what* the file does but not *which other files it coordinates with*. A reader cannot reconstruct data flow without reading imports.
3. **Latent duplication.** `embedding_types.py` and `embedding_storage.py` define overlapping enum sets (`PersonaEmbeddingType`, `JobEmbeddingType`) with different type hierarchies and already-drifted values (`"persona_hard_skills"` vs `"hard_skills"`).

### 1.1 Solution

1. **Reorganize** the 86 files into 8 domain subdirectories plus 6 cross-cutting files at the package root. No new business logic, no behavior changes — only file moves and import path updates.
2. **Unify** the duplicate embedding enums into a single canonical definition.
3. **Standardize** module docstrings to include a `Coordinates with:` section and a `Called by:` line, so any reader can answer "what does this do, and how does it connect?" without opening another file.

### 1.2 Scope

| In Scope | Out of Scope |
|----------|-------------|
| Move 80 service files into 8 subdirectories | Test file directory restructuring (tests stay flat) |
| Rename 7 `embedding_*` files to drop redundant prefix | New business logic or behavior changes |
| Unify duplicate embedding enums into one canonical set | Refactoring `pool_scoring.py` ORM imports to protocols |
| Update all import paths (services, routers, repos, tests, scripts) | Database migrations |
| Add `__init__.py` with re-exports for each subdirectory | Frontend changes |
| Standardize all 86 module docstrings | API contract changes |
| Update `services/__init__.py` with package-level docstring | New endpoints or response models |

### 1.3 Relationship to Existing REQs

REQ-031 **amends** the file path references in 10 existing REQ documents. No behavioral specifications are changed — only the filesystem locations of already-implemented service modules.

---

## 2. Dependencies

### 2.1 This Document Depends On

| Dependency | Type | Notes |
|------------|------|-------|
| All service files in `backend/app/services/` | Source | Files being reorganized |
| REQ-016 through REQ-030 | Context | Documents that reference service file paths |

### 2.2 Other Documents Depend On This

| Document | Dependency | Notes |
|----------|------------|-------|
| REQ-016 through REQ-030 | File paths | Errata added to each — see §3 |
| Future REQs | Import conventions | New services should follow subdirectory structure |

---

## 3. Traceability Map

Each REQ below receives a changelog errata entry pointing to this document's §5 mapping table.

| REQ | Version Bump | Affected Files |
|-----|-------------|----------------|
| REQ-016 Scouter | 0.3 → 0.4 | 7 files → `discovery/` |
| REQ-017 Strategist | 0.2 → 0.3 | 8 files → `scoring/` |
| REQ-018 Ghostwriter | 0.3 → 0.4 | 17 files → `generation/` + `rendering/`; §14 Q1 resolved |
| REQ-019 Onboarding | 0.3 → 0.4 | 3 files → `onboarding/` + `rendering/` |
| REQ-020 Metering | 0.3 → 0.4 | 8 files → `billing/` + `discovery/` + `generation/` + `embedding/` |
| REQ-021 Billing | 0.6 → 0.7 | 1 file → `billing/` |
| REQ-022 Admin Pricing | 0.1 → 0.2 | 4 files → `admin/` + `billing/` + `embedding/` |
| REQ-023 USD Billing | 0.3 → 0.4 | 1 file → `admin/` |
| REQ-029 Stripe Checkout | 0.3 → 0.4 | 1 file → `billing/` |
| REQ-030 Billing Hardening | 0.2 → 0.3 | 3 files → `billing/` |

---

## 4. Subdirectory Structure Specification

### 4.1 Directory Layout

```
backend/app/services/
├── __init__.py                        # Package docstring describing all domains
│
├── scoring/                           # 17 files
│   ├── __init__.py
│   ├── fit_score.py
│   ├── stretch_score.py
│   ├── hard_skills_match.py
│   ├── soft_skills_match.py
│   ├── experience_level.py
│   ├── role_title_match.py
│   ├── location_logistics.py
│   ├── non_negotiables_filter.py
│   ├── scoring_flow.py
│   ├── batch_scoring.py
│   ├── job_scoring_service.py
│   ├── pool_scoring.py
│   ├── score_types.py
│   ├── score_explanation.py
│   ├── explanation_generation.py
│   ├── score_correlation.py
│   └── golden_set.py
│
├── embedding/                         # 7 files (renamed to drop prefix)
│   ├── __init__.py
│   ├── types.py                       # was embedding_types.py
│   ├── storage.py                     # was embedding_storage.py
│   ├── utils.py                       # was embedding_utils.py
│   ├── cost.py                        # was embedding_cost.py
│   ├── cache.py                       # was embedding_cache.py
│   ├── job_generator.py               # was job_embedding_generator.py
│   └── persona_generator.py           # was persona_embedding_generator.py
│
├── generation/                        # 24 files
│   ├── __init__.py
│   ├── content_generation_service.py
│   ├── resume_generation_service.py
│   ├── resume_tailoring_service.py
│   ├── cover_letter_generation.py
│   ├── story_selection.py
│   ├── base_resume_selection.py
│   ├── tailoring_decision.py
│   ├── bullet_reordering.py
│   ├── reasoning_explanation.py
│   ├── ghostwriter_triggers.py
│   ├── content_utils.py
│   ├── voice_prompt_block.py
│   ├── voice_validation.py
│   ├── cover_letter_structure.py
│   ├── cover_letter_output.py
│   ├── cover_letter_validation.py
│   ├── modification_limits.py
│   ├── regeneration.py
│   ├── data_availability.py
│   ├── job_expiry.py
│   ├── persona_change.py
│   ├── duplicate_story.py
│   ├── quality_metrics.py
│   └── generation_outcome.py
│
├── rendering/                         # 8 files
│   ├── __init__.py
│   ├── pdf_generation.py
│   ├── cover_letter_pdf_generation.py
│   ├── cover_letter_pdf_storage.py
│   ├── cover_letter_editing.py
│   ├── markdown_pdf_renderer.py
│   ├── markdown_docx_renderer.py
│   ├── resume_template_service.py
│   └── resume_parsing_service.py
│
├── discovery/                         # 16 files
│   ├── __init__.py
│   ├── discovery_workflow.py
│   ├── job_fetch_service.py
│   ├── job_extraction.py
│   ├── job_enrichment_service.py
│   ├── ghost_detection.py
│   ├── job_deduplication.py
│   ├── global_dedup_service.py
│   ├── source_selection.py
│   ├── expiration_detection.py
│   ├── job_status.py
│   ├── user_review.py
│   ├── scouter_utils.py
│   ├── scouter_errors.py
│   ├── pool_surfacing_service.py
│   ├── pool_surfacing_worker.py
│   └── content_security.py
│
├── billing/                           # 4 files
│   ├── __init__.py
│   ├── stripe_service.py
│   ├── stripe_webhook_service.py
│   ├── metering_service.py
│   └── reservation_sweep.py
│
├── admin/                             # 2 files
│   ├── __init__.py
│   ├── admin_config_service.py
│   └── admin_management_service.py
│
├── onboarding/                        # 2 files
│   ├── __init__.py
│   ├── onboarding_workflow.py
│   └── onboarding_utils.py
│
│   # Cross-cutting (services/ root) — 6 files
├── persona_sync.py
├── application_workflow.py
├── agent_message.py
├── agent_handoff.py
├── retention_cleanup.py
└── ingest_token_store.py
```

### 4.2 Domain Descriptions

#### `scoring/` — Job-Persona Match Scoring

Owns all logic that answers "how well does this person match this job?" Includes five Fit Score components, three Stretch Score components, non-negotiables pre-filter, batch scoring orchestration, score explanation generation, pool surfacing heuristics, and golden-set validation. Scoring *consumes* embeddings from `embedding/` but never generates them. It *produces* score results consumed by `generation/` and `discovery/`.

#### `embedding/` — Vector Embedding Lifecycle

Owns text-to-vector conversion and vector management. Includes building source text for persona (3 types) and job (2 types) embeddings, calling the embedding provider, hash-based staleness detection, LRU caching, cost estimation, and validation utilities. Pure service provider with no knowledge of scoring or generation logic.

#### `generation/` — Content Generation Pipeline

Owns the 8-step pipeline from "user wants content" to "draft ready for review." Includes resume tailoring (base selection, tailoring decision, variant creation, bullet reordering, guardrails), cover letter creation (story selection, LLM generation, validation, output bundling), voice profile enforcement, edge case detection, regeneration handling, and quality tracking. Does NOT persist to database — that bridge is `application_workflow.py` (cross-cutting).

**Note:** `content_generation_service.py` is currently a pipeline skeleton with placeholder steps pending full DB/API wiring (as of 2026-03-29). The orchestration structure and delegation points are real; the private methods pass empty/dummy data to delegated services. The docstring must reflect this status.

#### `rendering/` — Document Format Handling

Owns converting structured data to document formats (PDF, DOCX) and parsing documents back to structured data. Includes ReportLab-based resume/cover letter PDF generation, markdown-to-PDF and markdown-to-DOCX rendering, cover letter storage and editing, resume template CRUD, and PDF resume parsing (pdfplumber + LLM extraction).

#### `discovery/` — Job Discovery & Pool Management

Owns finding, processing, and surfacing jobs to users. Includes discovery orchestration, source adapter coordination, LLM-based extraction, skill/culture enrichment, ghost detection, 4-step deduplication, global pool dedup, content security (injection defense, quarantine), pool surfacing with heuristic scoring, background workers, source prioritization, expiration detection, status state machine, and user review actions.

#### `billing/` — Payments & Usage Metering

Owns Stripe integration, webhook processing, LLM usage metering (reserve/settle/release), and background sweep for stale reservations. Reads pricing configuration from `admin/`. Has no knowledge of what LLM calls are *for*.

#### `admin/` — Admin Configuration & Management

Owns read-side lookups (`admin_config_service.py`) and write-side CRUD (`admin_management_service.py`) for models, pricing, routing, funding packs, system config, and users. Pure configuration provider with no domain logic.

#### `onboarding/` — User Onboarding

Owns atomic persistence of onboarding data and post-onboarding utilities (trigger detection, section routing, embedding impact mapping, prompt templates).

---

## 5. Complete File Mapping

### 5.1 Moves Without Rename

80 files keep their original filename, only the directory changes.

| Current Path | New Path |
|-------------|----------|
| **scoring/ (17 files)** | |
| `services/fit_score.py` | `services/scoring/fit_score.py` |
| `services/stretch_score.py` | `services/scoring/stretch_score.py` |
| `services/hard_skills_match.py` | `services/scoring/hard_skills_match.py` |
| `services/soft_skills_match.py` | `services/scoring/soft_skills_match.py` |
| `services/experience_level.py` | `services/scoring/experience_level.py` |
| `services/role_title_match.py` | `services/scoring/role_title_match.py` |
| `services/location_logistics.py` | `services/scoring/location_logistics.py` |
| `services/non_negotiables_filter.py` | `services/scoring/non_negotiables_filter.py` |
| `services/scoring_flow.py` | `services/scoring/scoring_flow.py` |
| `services/batch_scoring.py` | `services/scoring/batch_scoring.py` |
| `services/job_scoring_service.py` | `services/scoring/job_scoring_service.py` |
| `services/pool_scoring.py` | `services/scoring/pool_scoring.py` |
| `services/score_types.py` | `services/scoring/score_types.py` |
| `services/score_explanation.py` | `services/scoring/score_explanation.py` |
| `services/explanation_generation.py` | `services/scoring/explanation_generation.py` |
| `services/score_correlation.py` | `services/scoring/score_correlation.py` |
| `services/golden_set.py` | `services/scoring/golden_set.py` |
| **generation/ (24 files)** | |
| `services/content_generation_service.py` | `services/generation/content_generation_service.py` |
| `services/resume_generation_service.py` | `services/generation/resume_generation_service.py` |
| `services/resume_tailoring_service.py` | `services/generation/resume_tailoring_service.py` |
| `services/cover_letter_generation.py` | `services/generation/cover_letter_generation.py` |
| `services/story_selection.py` | `services/generation/story_selection.py` |
| `services/base_resume_selection.py` | `services/generation/base_resume_selection.py` |
| `services/tailoring_decision.py` | `services/generation/tailoring_decision.py` |
| `services/bullet_reordering.py` | `services/generation/bullet_reordering.py` |
| `services/reasoning_explanation.py` | `services/generation/reasoning_explanation.py` |
| `services/ghostwriter_triggers.py` | `services/generation/ghostwriter_triggers.py` |
| `services/content_utils.py` | `services/generation/content_utils.py` |
| `services/voice_prompt_block.py` | `services/generation/voice_prompt_block.py` |
| `services/voice_validation.py` | `services/generation/voice_validation.py` |
| `services/cover_letter_structure.py` | `services/generation/cover_letter_structure.py` |
| `services/cover_letter_output.py` | `services/generation/cover_letter_output.py` |
| `services/cover_letter_validation.py` | `services/generation/cover_letter_validation.py` |
| `services/modification_limits.py` | `services/generation/modification_limits.py` |
| `services/regeneration.py` | `services/generation/regeneration.py` |
| `services/data_availability.py` | `services/generation/data_availability.py` |
| `services/job_expiry.py` | `services/generation/job_expiry.py` |
| `services/persona_change.py` | `services/generation/persona_change.py` |
| `services/duplicate_story.py` | `services/generation/duplicate_story.py` |
| `services/quality_metrics.py` | `services/generation/quality_metrics.py` |
| `services/generation_outcome.py` | `services/generation/generation_outcome.py` |
| **rendering/ (8 files)** | |
| `services/pdf_generation.py` | `services/rendering/pdf_generation.py` |
| `services/cover_letter_pdf_generation.py` | `services/rendering/cover_letter_pdf_generation.py` |
| `services/cover_letter_pdf_storage.py` | `services/rendering/cover_letter_pdf_storage.py` |
| `services/cover_letter_editing.py` | `services/rendering/cover_letter_editing.py` |
| `services/markdown_pdf_renderer.py` | `services/rendering/markdown_pdf_renderer.py` |
| `services/markdown_docx_renderer.py` | `services/rendering/markdown_docx_renderer.py` |
| `services/resume_template_service.py` | `services/rendering/resume_template_service.py` |
| `services/resume_parsing_service.py` | `services/rendering/resume_parsing_service.py` |
| **discovery/ (16 files)** | |
| `services/discovery_workflow.py` | `services/discovery/discovery_workflow.py` |
| `services/job_fetch_service.py` | `services/discovery/job_fetch_service.py` |
| `services/job_extraction.py` | `services/discovery/job_extraction.py` |
| `services/job_enrichment_service.py` | `services/discovery/job_enrichment_service.py` |
| `services/ghost_detection.py` | `services/discovery/ghost_detection.py` |
| `services/job_deduplication.py` | `services/discovery/job_deduplication.py` |
| `services/global_dedup_service.py` | `services/discovery/global_dedup_service.py` |
| `services/source_selection.py` | `services/discovery/source_selection.py` |
| `services/expiration_detection.py` | `services/discovery/expiration_detection.py` |
| `services/job_status.py` | `services/discovery/job_status.py` |
| `services/user_review.py` | `services/discovery/user_review.py` |
| `services/scouter_utils.py` | `services/discovery/scouter_utils.py` |
| `services/scouter_errors.py` | `services/discovery/scouter_errors.py` |
| `services/pool_surfacing_service.py` | `services/discovery/pool_surfacing_service.py` |
| `services/pool_surfacing_worker.py` | `services/discovery/pool_surfacing_worker.py` |
| `services/content_security.py` | `services/discovery/content_security.py` |
| **billing/ (4 files)** | |
| `services/stripe_service.py` | `services/billing/stripe_service.py` |
| `services/stripe_webhook_service.py` | `services/billing/stripe_webhook_service.py` |
| `services/metering_service.py` | `services/billing/metering_service.py` |
| `services/reservation_sweep.py` | `services/billing/reservation_sweep.py` |
| **admin/ (2 files)** | |
| `services/admin_config_service.py` | `services/admin/admin_config_service.py` |
| `services/admin_management_service.py` | `services/admin/admin_management_service.py` |
| **onboarding/ (2 files)** | |
| `services/onboarding_workflow.py` | `services/onboarding/onboarding_workflow.py` |
| `services/onboarding_utils.py` | `services/onboarding/onboarding_utils.py` |

### 5.2 Moves With Rename (embedding/)

7 files are renamed to drop the redundant `embedding_` prefix when moving into the `embedding/` subdirectory.

| Current Path | New Path | Rationale |
|-------------|----------|-----------|
| `services/embedding_types.py` | `services/embedding/types.py` | `embedding/embedding_types.py` stutters |
| `services/embedding_storage.py` | `services/embedding/storage.py` | Same |
| `services/embedding_utils.py` | `services/embedding/utils.py` | Same |
| `services/embedding_cost.py` | `services/embedding/cost.py` | Same |
| `services/embedding_cache.py` | `services/embedding/cache.py` | Same |
| `services/job_embedding_generator.py` | `services/embedding/job_generator.py` | Drop `embedding_` infix |
| `services/persona_embedding_generator.py` | `services/embedding/persona_generator.py` | Drop `embedding_` infix |

### 5.3 No Move (cross-cutting)

6 files remain at `services/` root. See §9 for rationale.

| File | Reason |
|------|--------|
| `persona_sync.py` | Bridges persona changes to base resumes across domains |
| `application_workflow.py` | Bridges generation output to database persistence |
| `agent_message.py` | Agent-to-user messaging — used by any orchestrator |
| `agent_handoff.py` | Agent-to-agent handoff — used by any orchestrator |
| `retention_cleanup.py` | Runs 4 independent cleanup policies spanning all domains |
| `ingest_token_store.py` | Ephemeral token management — unique, small, API-only |

---

## 6. Embedding Enum Unification

### 6.1 Problem

Two files define overlapping enums with **different type hierarchies and already-drifted values**:

| Aspect | `embedding_types.py` | `embedding_storage.py` |
|--------|---------------------|----------------------|
| `PersonaEmbeddingType` base | `Enum` (plain) | `str, Enum` (string-valued) |
| `JobEmbeddingType` base | `Enum` (plain) | `str, Enum` (string-valued) |
| `EmbeddingType` | `Enum` (combined, 5 members) | Union alias (`Persona \| Job`) |
| Values | Prefixed: `"persona_hard_skills"` | Unprefixed: `"hard_skills"` |
| Extra content | `EMBEDDING_CONFIGS` dict, helper functions | `compute_source_hash()`, `is_embedding_fresh()` |

### 6.2 Resolution

Merge into a single `embedding/types.py`:

1. **Canonical enums** use `str, Enum` base (from `embedding_storage.py`) for JSON serialization.
2. **Values** use the **unprefixed** form (`"hard_skills"`, `"soft_skills"`, etc.) — these are the values used in the `embedding_storage.py` path, which is the DB-facing side.
3. **`EmbeddingType`** becomes a `Union` alias (cleaner than a combined enum).
4. **`EMBEDDING_CONFIGS`** dict and helper functions from `embedding_types.py` are preserved in `types.py`.
5. **`compute_source_hash()`** and **`is_embedding_fresh()`** move to `embedding/storage.py` and import enums from `embedding/types.py`.
6. All consumers are updated to import from the canonical location.

### 6.3 Consumer Impact

Search all imports of `embedding_types` and `embedding_storage` enum names. Update to import from `app.services.embedding.types`. Grep patterns:

```
from app.services.embedding_types import
from app.services.embedding_storage import PersonaEmbeddingType
from app.services.embedding_storage import JobEmbeddingType
from app.services.embedding_storage import EmbeddingType
```

---

## 7. Module Docstring Standard

### 7.1 Requirement

Every `.py` file in `services/` (including subdirectories) must have a module-level docstring that answers three questions without needing to read code or open other files:

1. **WHAT** — What does this file do?
2. **WHERE** — Where does it sit in the larger pipeline?
3. **WITH** — What other files does it coordinate with?

### 7.2 Template

```python
"""<One-line summary>.

<REQ reference>: <2-3 sentence description of what the file does>.

<Optional: Additional context, constraints, or warnings.>

Coordinates with:
  - <file.py> -- <what it provides to or receives from this file>
  - <file.py> -- <what it provides to or receives from this file>

Called by: <file(s) that import from this module>.
"""
```

### 7.3 Rules

1. **`Coordinates with:` is mandatory** for files that import from or are imported by other service files. Files with no service-layer dependencies may omit it.
2. **`Called by:` is mandatory** for all files. Lists the primary external callers (routers, orchestrators, other services).
3. **Use new subdirectory-relative names** (e.g., `scoring/fit_score.py`, not `fit_score.py`).
4. **Existing REQ references** in docstrings should be preserved.
5. **`content_generation_service.py`** docstring must note that the pipeline is a skeleton with placeholder steps pending DB/API wiring.
6. **`pool_scoring.py`** docstring must note the known inconsistency: imports ORM models directly while other scoring files use TypedDict/Protocol inputs. The functions are pure (no DB access) but do not follow the protocol pattern.

### 7.4 Audit Baseline

| Verdict | Count | Notes |
|---------|-------|-------|
| Pass (all 3) | 3 | `cover_letter_pdf_generation`, `user_review`, `pool_surfacing_worker` |
| Partial (missing WITH) | 77 | Systemic gap — WHAT and WHERE are present |
| Fail (missing entirely) | 1 | `__init__.py` |

All 78 non-passing files require docstring updates.

---

## 8. Import Path Migration Rules

### 8.1 Pattern

All imports follow the absolute path convention: `from app.services.<domain>.<module> import <name>`.

Old:
```python
from app.services.fit_score import calculate_fit_score
```

New:
```python
from app.services.scoring.fit_score import calculate_fit_score
```

### 8.2 Files Requiring Import Updates

Based on the dependency analysis, imports exist in these locations:

| Location | Import Pattern | Example |
|----------|---------------|---------|
| `backend/app/api/*.py` | Routers importing services | `auth.py` → `stripe_service` |
| `backend/app/api/deps.py` | Dependency injection | `admin_config_service`, `metering_service` |
| `backend/app/providers/metered_provider.py` | Metered wrapper | `admin_config_service`, `metering_service` |
| `backend/app/repositories/job_pool_repository.py` | Pool repo | `global_dedup_service` |
| `backend/app/main.py` | Worker startup | `pool_surfacing_worker`, `reservation_sweep` |
| `backend/app/services/**/*.py` | Cross-service imports | ~60 internal references |
| `backend/tests/**/*.py` | Test imports | 100+ test files |
| `backend/scripts/reembed_all.py` | Migration script | `job_embedding_generator`, `persona_embedding_generator` |

### 8.3 Subdirectory `__init__.py` Files

Each subdirectory gets an `__init__.py` that:
1. Contains a brief docstring describing the domain.
2. Does **NOT** re-export all module contents. Consumers import directly from the module file, not from `__init__`.

This keeps `__init__.py` lightweight and avoids circular import issues.

---

## 9. Cross-Cutting Files Rationale

| File | Why Not in a Domain |
|------|---------------------|
| `persona_sync.py` | Touches persona models AND resume models. Called by persona API routers after edits. Doesn't belong to scoring, generation, or any single pipeline. |
| `application_workflow.py` | Bridges generation output (drafts) to database persistence (JobVariant, CoverLetter, Application). Spans the generation → storage boundary. |
| `agent_message.py` | Defines 6 semantic message types usable by any agent orchestrator. Pure data definitions with no domain logic. |
| `agent_handoff.py` | Defines 3 inter-agent communication patterns. Same reasoning as `agent_message.py`. |
| `retention_cleanup.py` | Runs 4 independent cleanup policies (orphan PDFs, change flags, archived records, expired jobs) spanning all domains. |
| `ingest_token_store.py` | In-memory ephemeral token management for ingest preview. Used only by `job_postings` router. Too small and unique to justify its own subdirectory. |

---

## 10. Implementation Constraints

1. **No behavior changes.** Every test must pass with identical assertions before and after. The only expected test changes are import path updates.
2. **Atomic per-domain moves.** Move one domain at a time (e.g., all 17 scoring files together), update all imports for that domain, verify tests pass, commit. Do not interleave domains.
3. **Git `mv` for history.** Use `git mv` so file history is preserved in `git log --follow`.
4. **No circular imports.** The proposed structure has no circular dependencies between domains. If a circular import is discovered during implementation, it indicates a misplaced file — resolve by moving the file, not by adding lazy imports.
5. **Embedding enum unification happens with the embedding/ domain move** — not as a separate step. This prevents a state where the old enum files exist at the old path but consumers are partially migrated.

---

## 11. Testing Requirements

1. **Full backend test suite must pass** after each domain move (`pytest tests/ -v`).
2. **Full frontend test suite must pass** after all moves (`npm test` in `frontend/`).
3. **Linting must pass** (`ruff check .` from `backend/`, `npm run lint` from `frontend/`).
4. **Type checking must pass** (`pyright` from `backend/`, `npm run typecheck` from `frontend/`).
5. **No test file moves.** Test files remain in their current flat structure (`tests/unit/test_*.py`). Only their import paths change.

---

## 12. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-29 | 0.1 | Initial draft. Specifies reorganization of 86 service files into 8 domain subdirectories, embedding enum unification, and module docstring standardization. Amends file path references in REQ-016 through REQ-030. |
