# Zentropy Scout — REQ-031 Services Layer Reorganization Plan

**Created:** 2026-03-29
**Last Updated:** 2026-03-29
**Status:** ⬜ Not Started
**Branch:** `feat/services-org-llm-support`
**REQ:** REQ-031

---

## Context

`backend/app/services/` contains 86 Python modules in a flat directory. REQ-031 specifies reorganizing them into 8 domain subdirectories, unifying duplicate embedding enums, and standardizing all module docstrings to include coordination context. No business logic changes — only file moves, import path updates, and docstring improvements.

**What gets built:**
- 8 subdirectory packages (`scoring/`, `embedding/`, `generation/`, `rendering/`, `discovery/`, `billing/`, `admin/`, `onboarding/`) with `__init__.py` files
- 80 files moved (73 without rename, 7 embedding files renamed to drop redundant prefix)
- 6 cross-cutting files remain at `services/` root
- Duplicate embedding enums unified into single canonical set
- All 86 module docstrings updated with `Coordinates with:` and `Called by:` sections
- All import paths updated across routers, repositories, providers, tests, and scripts

**What doesn't change:** Business logic, test assertions, API contracts, database schema, frontend code.

---

## How to Use This Document

1. Find the first 🟡 or ⬜ task — that's where to start
2. Load REQ-031 via `req-reader` subagent before each task (load the §sections listed)
3. Each task = one commit, sized ≤ 40k tokens of context
4. **Subtask workflow:** `git mv` files → update imports → run affected tests → linters → commit → STOP and ask user (NO push)
5. **Phase-end workflow:** Run full test suite (backend + frontend) → push → STOP and ask user
6. After each task: update status (⬜ → ✅), commit, STOP and ask user

---

## Dependency Chain

```
Phase 1: Small Domains — billing/, admin/, onboarding/ (8 files)
    │     Low risk, few internal cross-references, validates workflow
    ▼
Phase 2: embedding/ (7 files + enum unification)
    │     Must precede scoring/ — scoring imports embedding utils
    ▼
Phase 3: scoring/ (17 files)
    │     Must precede generation/ — generation reads fit_score thresholds
    ▼
Phase 4: generation/ (24 files)
    │     Largest domain, most internal cross-references
    ▼
Phase 5: rendering/ (8 files)
    │     Called by generation/ — must move after generation imports are stable
    ▼
Phase 6: discovery/ (16 files)
    │     Independent of generation/rendering — can go here or earlier
    ▼
Phase 7: Cross-cutting + Package Docstrings (6 root files + __init__.py updates)
    │     Finalize services/__init__.py, update cross-cutting file docstrings
    ▼
Phase 8: Module Docstring Standardization (all 86 files)
    │     Bulk docstring update — no import changes, low risk
    ▼
Phase 9: Final Verification + Cleanup
```

**Ordering rationale:** Start with the smallest domains (billing, admin, onboarding — 8 files total) to validate the move+import workflow with minimal blast radius. Then embedding (needed by scoring), scoring (needed by generation), generation (largest), rendering, discovery. Docstrings are last because they're pure text changes with zero breakage risk and benefit from all files being in final locations.

---

## Phase 1: Small Domains — billing/, admin/, onboarding/

**Status:** ⬜ Incomplete

*Move the three smallest domains (8 files total) to validate the workflow: git mv, create __init__.py, update all imports, verify tests. Low cross-reference count makes these safe first movers.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-031 §4, §5, §8 |
| 🧪 **Verify** | `pytest -v` after each domain move |
| 🗃️ **Patterns** | `git mv` for history preservation; grep for old import paths |
| ✅ **Verify** | `ruff check .`, `pytest -v` |
| 🔍 **Review** | `code-reviewer` (import consistency) |
| 📝 **Commit** | One commit per domain move |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Security triage gate** — Spawn `security-triage` subagent (general-purpose, opus, foreground). Check remote scanners are clear before implementation begins. | `plan, security` | ✅ |
| 2 | **Move billing/ (4 files)** — Create `services/billing/__init__.py`. `git mv` stripe_service.py, stripe_webhook_service.py, metering_service.py, reservation_sweep.py. Update all imports in: `app/api/auth.py`, `app/api/auth_magic_link.py`, `app/api/auth_oauth.py`, `app/api/credits.py`, `app/api/webhooks.py`, `app/api/deps.py`, `app/providers/metered_provider.py`, `app/main.py`, `app/services/admin_config_service.py` (internal ref from reservation_sweep), and all test files. Verify `pytest -v` passes. REQ-031 §5.1 billing section. | `plan` | ✅ |
| 3 | **Move admin/ (2 files)** — Create `services/admin/__init__.py`. `git mv` admin_config_service.py, admin_management_service.py. Update imports in: `app/api/admin.py`, `app/api/deps.py`, `app/providers/metered_provider.py`, `services/billing/metering_service.py` (just moved), `services/billing/reservation_sweep.py`, and test files. Verify `pytest -v` passes. REQ-031 §5.1 admin section. | `plan` | ⬜ |
| 4 | **Move onboarding/ (2 files)** — Create `services/onboarding/__init__.py`. `git mv` onboarding_workflow.py, onboarding_utils.py. Update imports in: `app/api/onboarding.py` and test files. Verify `pytest -v` passes. REQ-031 §5.1 onboarding section. | `plan` | ⬜ |
| 5 | **Phase gate — full test suite + push** — Run full backend test suite (`pytest tests/ -v`), `ruff check .`. Fix regressions, commit, push. | `plan, commands` | ⬜ |

#### Notes
- billing/ has the most external callers (auth routers, credits, webhooks, deps, metered_provider, main.py) — good stress test
- admin/ depends on billing/ (metering_service imports admin_config_service) — move admin/ second so we can update the already-moved billing paths
- onboarding/ is the most isolated — fewest external callers

---

## Phase 2: embedding/ (with Enum Unification)

**Status:** ⬜ Incomplete

*Move 7 embedding files with renames. Unify duplicate PersonaEmbeddingType/JobEmbeddingType enums from embedding_types.py + embedding_storage.py into a single canonical set in embedding/types.py. REQ-031 §5.2, §6.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-031 §5.2, §6 |
| 🧪 **Verify** | `pytest -v` after move + unification |
| 🗃️ **Patterns** | `git mv` + rename; grep for all `embedding_types` and `embedding_storage` imports |
| ✅ **Verify** | `ruff check .`, `pytest -v` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` (enum change could affect DB-facing code) |
| 📝 **Commit** | Single commit: move + unify + update imports |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 6 | **Move + rename embedding files (7 files)** — Create `services/embedding/__init__.py`. `git mv` with renames per REQ-031 §5.2: embedding_types→types, embedding_storage→storage, embedding_utils→utils, embedding_cost→cost, embedding_cache→cache, job_embedding_generator→job_generator, persona_embedding_generator→persona_generator. Update all internal cross-references within embedding/ files. Update all external imports in: scoring files (batch_scoring, stretch_score, role_title_match, soft_skills_match), `scripts/reembed_all.py`, and test files. Verify `pytest -v` passes. | `plan` | ⬜ |
| 7 | **Unify embedding enums** — Merge PersonaEmbeddingType and JobEmbeddingType from old embedding_types.py and embedding_storage.py into canonical definitions in `embedding/types.py`. Use `str, Enum` base, unprefixed values. Keep EMBEDDING_CONFIGS and helpers. Move compute_source_hash/is_embedding_fresh to `embedding/storage.py` importing from `embedding/types.py`. Update all consumers. REQ-031 §6. Verify `pytest -v` passes. | `plan` | ⬜ |
| 8 | **Phase gate — full test suite + push** — Run full backend test suite, `ruff check .`. Fix regressions, commit, push. | `plan, commands` | ⬜ |

#### Notes
- Enum unification is the highest-risk task in the entire plan. The values differ (`"persona_hard_skills"` vs `"hard_skills"`). Need to trace which value form is used at runtime/DB boundaries and pick the canonical form.
- `embedding_cache.py` imports from both `embedding_storage` and `persona_embedding_generator` — both are moving simultaneously. Update internal refs within the same commit.

---

## Phase 3: scoring/ (17 files)

**Status:** ⬜ Incomplete

*Move all 17 scoring files. Heavy internal cross-references but no renames. This is the most interconnected domain internally (fit_score is imported by 8+ files within scoring).*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-031 §5.1 scoring section |
| 🧪 **Verify** | `pytest -v` after move |
| 🗃️ **Patterns** | `git mv` all 17 files; grep for `app.services.fit_score`, `app.services.batch_scoring`, etc. |
| ✅ **Verify** | `ruff check .`, `pytest -v` |
| 🔍 **Review** | `code-reviewer` |
| 📝 **Commit** | One commit for all 17 files + import updates |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 9 | **Move scoring/ — core files (9 files)** — Create `services/scoring/__init__.py`. `git mv` the 5 Fit Score components (fit_score, hard_skills_match, soft_skills_match, experience_level, role_title_match, location_logistics) + stretch_score + score_types + score_explanation. Update all internal cross-references (these files heavily import each other via fit_score.FIT_NEUTRAL_SCORE, soft_skills_match.cosine_similarity, etc.). Update external imports in test files. Verify `pytest -v` passes. | `plan` | ⬜ |
| 10 | **Move scoring/ — orchestration + validation files (8 files)** — `git mv` non_negotiables_filter, scoring_flow, batch_scoring, job_scoring_service, pool_scoring, explanation_generation, score_correlation, golden_set. Update internal cross-refs (batch_scoring imports from all component files, job_scoring_service imports batch_scoring + scoring_flow, explanation_generation imports fit_score + stretch_score). Update external imports: `app/services/discovery/job_fetch_service.py` (job_scoring_service), `app/services/discovery/pool_surfacing_service.py` (pool_scoring), `app/services/generation/ghostwriter_triggers.py` (if any), and test files. Verify `pytest -v` passes. | `plan` | ⬜ |
| 11 | **Phase gate — full test suite + push** — Run full backend test suite, `ruff check .`. Fix regressions, commit, push. | `plan, commands` | ⬜ |

#### Notes
- Splitting into two tasks (core + orchestration) keeps each task under context limits
- pool_scoring.py imports ORM models directly — flag in docstring later (Phase 8), not here
- scoring/ files that import from embedding/ are already updated from Phase 2

---

## Phase 4: generation/ (24 files)

**Status:** ⬜ Incomplete

*Largest domain. Heavy internal cross-references. Split into 3 tasks by subgroup: cover letter pipeline, resume pipeline, edge cases + quality.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-031 §5.1 generation section |
| 🧪 **Verify** | `pytest -v` after each task |
| 🗃️ **Patterns** | `git mv`; grep for old import paths |
| ✅ **Verify** | `ruff check .`, `pytest -v` |
| 🔍 **Review** | `code-reviewer` |
| 📝 **Commit** | One commit per sub-batch |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 12 | **Move generation/ — orchestration + resume (10 files)** — Create `services/generation/__init__.py`. `git mv` content_generation_service, resume_generation_service, resume_tailoring_service, ghostwriter_triggers, base_resume_selection, tailoring_decision, bullet_reordering, modification_limits, content_utils, voice_prompt_block. Update internal cross-refs and external imports (routers: base_resumes, job_variants; providers; test files). Verify `pytest -v` passes. | `plan` | ⬜ |
| 13 | **Move generation/ — cover letter pipeline (7 files)** — `git mv` cover_letter_generation, cover_letter_structure, cover_letter_output, cover_letter_validation, voice_validation, story_selection, reasoning_explanation. Update internal cross-refs (cover_letter_output → cover_letter_validation, cover_letter_validation → cover_letter_structure, story_selection → content_utils, content_generation_service refs). Update external imports in test files. Verify `pytest -v` passes. | `plan` | ⬜ |
| 14 | **Move generation/ — edge cases + quality (7 files)** — `git mv` regeneration, data_availability, job_expiry, persona_change, duplicate_story, quality_metrics, generation_outcome. Update internal cross-refs (generation_outcome → regeneration). Update external imports in test files. Verify `pytest -v` passes. | `plan` | ⬜ |
| 15 | **Phase gate — full test suite + push** — Run full backend test suite, `ruff check .`. Fix regressions, commit, push. | `plan, commands` | ⬜ |

#### Notes
- content_generation_service imports from 5+ generation files — move it in the first batch so internal refs within generation/ get fixed early
- cover_letter_output imports cover_letter_validation, which imports cover_letter_structure — these form a chain and must move together
- voice_prompt_block is used by resume_generation_service (same batch) and cover_letter_generation (next batch)

---

## Phase 5: rendering/ (8 files)

**Status:** ⬜ Incomplete

*Move 8 document rendering/parsing files. Called by generation services and API routers.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-031 §5.1 rendering section |
| 🧪 **Verify** | `pytest -v` after move |
| 🗃️ **Patterns** | `git mv`; grep for old import paths |
| ✅ **Verify** | `ruff check .`, `pytest -v` |
| 🔍 **Review** | `code-reviewer` |
| 📝 **Commit** | Single commit for all 8 files |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 16 | **Move rendering/ (8 files)** — Create `services/rendering/__init__.py`. `git mv` pdf_generation, cover_letter_pdf_generation, cover_letter_pdf_storage, cover_letter_editing, markdown_pdf_renderer, markdown_docx_renderer, resume_template_service, resume_parsing_service. Update internal cross-refs (cover_letter_pdf_generation → cover_letter_pdf_storage). Update external imports: `app/api/base_resumes.py`, `app/api/job_variants.py`, `app/api/onboarding.py`, `app/api/resume_templates.py`, `app/services/generation/resume_generation_service.py`, and test files. Verify `pytest -v` passes. | `plan` | ⬜ |
| 17 | **Phase gate — full test suite + push** — Run full backend test suite, `ruff check .`. Fix regressions, commit, push. | `plan, commands` | ⬜ |

---

## Phase 6: discovery/ (16 files)

**Status:** ⬜ Incomplete

*Move 16 job discovery and pool management files. Some depend on scoring/ (pool_scoring uses scoring/fit_score via pool_surfacing_service).*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-031 §5.1 discovery section |
| 🧪 **Verify** | `pytest -v` after each task |
| 🗃️ **Patterns** | `git mv`; grep for old import paths |
| ✅ **Verify** | `ruff check .`, `pytest -v` |
| 🔍 **Review** | `code-reviewer` |
| 📝 **Commit** | One commit per sub-batch |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 18 | **Move discovery/ — core pipeline (8 files)** — Create `services/discovery/__init__.py`. `git mv` discovery_workflow, job_fetch_service, job_extraction, job_enrichment_service, ghost_detection, job_deduplication, global_dedup_service, content_security. Update internal cross-refs (job_fetch_service → job_enrichment_service, scouter_utils, scouter_errors, job_scoring_service; global_dedup_service → content_security, job_deduplication; job_enrichment_service → ghost_detection). Update external imports: `app/api/job_postings.py`, `app/repositories/job_pool_repository.py`, and test files. Verify `pytest -v` passes. | `plan` | ⬜ |
| 19 | **Move discovery/ — status + pool + utilities (8 files)** — `git mv` source_selection, expiration_detection, job_status, user_review, scouter_utils, scouter_errors, pool_surfacing_service, pool_surfacing_worker. Update internal cross-refs (user_review → job_status, pool_surfacing_service → content_security + pool_scoring, pool_surfacing_worker → pool_surfacing_service, discovery_workflow → job_fetch_service + scouter_utils). Update external imports: `app/main.py` (pool_surfacing_worker), and test files. Verify `pytest -v` passes. | `plan` | ⬜ |
| 20 | **Phase gate — full test suite + push** — Run full backend test suite, `ruff check .`. Fix regressions, commit, push. | `plan, commands` | ⬜ |

---

## Phase 7: Cross-Cutting + Package Docstrings

**Status:** ⬜ Incomplete

*Update the 6 cross-cutting files' docstrings with coordination context. Write services/__init__.py package docstring and all subdirectory __init__.py docstrings.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-031 §7, §9 |
| 🧪 **Verify** | `ruff check .` |
| 🔍 **Review** | `code-reviewer` (docstring quality) |
| 📝 **Commit** | Single commit |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 21 | **Update cross-cutting file docstrings (6 files)** — Add `Coordinates with:` and `Called by:` to persona_sync.py, application_workflow.py, agent_message.py, agent_handoff.py, retention_cleanup.py, ingest_token_store.py. Update `services/__init__.py` with package-level docstring describing all 8 domains + cross-cutting files (REQ-031 §4.2 descriptions). Update all 8 subdirectory `__init__.py` files with brief domain docstrings. Verify `ruff check .` passes. | `plan` | ⬜ |
| 22 | **Phase gate — full test suite + push** — Run full backend test suite, `ruff check .`. Fix regressions, commit, push. | `plan, commands` | ⬜ |

---

## Phase 8: Module Docstring Standardization

**Status:** ⬜ Incomplete

*Bulk update all 78 non-passing module docstrings (77 partial + 1 missing) to include `Coordinates with:` and `Called by:` sections per REQ-031 §7. Split into 4 tasks by domain to stay within context limits.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-031 §7 (template + rules) |
| 🧪 **Verify** | `ruff check .` after each batch |
| 🔍 **Review** | `code-reviewer` (docstring completeness) |
| 📝 **Commit** | One commit per batch |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 23 | **Docstrings — scoring/ (17 files)** — Update module docstrings for all 17 scoring files. Add `Coordinates with:` listing internal dependencies and `Called by:` listing external callers. Use new subdirectory-relative names. Preserve existing REQ references. Flag pool_scoring.py ORM import inconsistency per REQ-031 §7.3 rule 6. Verify `ruff check .` passes. | `plan` | ⬜ |
| 24 | **Docstrings — embedding/ (7 files) + generation/ (24 files)** — Update module docstrings for all 31 files. Flag content_generation_service.py placeholder status per REQ-031 §7.3 rule 5. Verify `ruff check .` passes. | `plan` | ⬜ |
| 25 | **Docstrings — rendering/ (8 files) + discovery/ (16 files)** — Update module docstrings for all 24 files. Verify `ruff check .` passes. | `plan` | ⬜ |
| 26 | **Docstrings — billing/ (4 files) + admin/ (2 files) + onboarding/ (2 files)** — Update module docstrings for all 8 files. Verify `ruff check .` passes. | `plan` | ⬜ |
| 27 | **Phase gate — full test suite + push** — Run full backend + frontend test suites, `ruff check .`, linters, typecheck. Fix regressions, commit, push. | `plan, commands` | ⬜ |

#### Notes
- Docstring-only changes have zero breakage risk — no import paths change, no logic changes
- 3 files already pass (cover_letter_pdf_generation, user_review, pool_surfacing_worker) — verify they still pass after file moves, add `Coordinates with:` if needed for new paths
- Batches are sized by total file count to stay within context limits (~30 files per task)

---

## Phase 9: Final Verification + Cleanup

**Status:** ⬜ Incomplete

*Full quality gate across entire codebase. Verify no stale imports, no orphaned files, all tests green.*

#### Workflow
| Step | Action |
|------|--------|
| 🧪 **Verify** | Full test suite + lint + typecheck |
| 🔍 **Review** | `code-reviewer` (final sweep) |
| 📝 **Commit** | Cleanup commit if needed |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 28 | **Verify no stale imports remain** — Grep entire codebase for `from app.services.<old_module>` patterns that should have been updated. Check: `from app.services.fit_score`, `from app.services.embedding_types`, `from app.services.stripe_service`, etc. for all 80 moved files. Fix any stragglers. | `plan` | ⬜ |
| 29 | **Verify no orphaned files** — Confirm old `services/` root has only 7 files: `__init__.py` + 6 cross-cutting. No leftover `.py` files from moves. Confirm all 8 subdirectories have the expected file count. | `plan` | ⬜ |
| 30 | **Final phase gate — full test suite + push** — Run full backend test suite (`pytest tests/ -v -m ""`), frontend tests (`npm run test:run`), `ruff check .`, `npm run lint`, `npm run typecheck`. Fix any regressions. Commit, push. | `plan, commands` | ⬜ |

---

## Task Count Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | 5 | billing/ + admin/ + onboarding/ + security gate + phase gate |
| 2 | 3 | embedding/ move + enum unification + phase gate |
| 3 | 3 | scoring/ core + orchestration + phase gate |
| 4 | 4 | generation/ orchestration + cover letter + edge cases + phase gate |
| 5 | 2 | rendering/ + phase gate |
| 6 | 3 | discovery/ core + utilities + phase gate |
| 7 | 2 | cross-cutting docstrings + phase gate |
| 8 | 5 | 4 docstring batches + phase gate |
| 9 | 3 | stale import check + orphan check + final gate |
| **Total** | **30** | |

---

## Critical Files Reference

| File | Role | Phase |
|------|------|-------|
| `backend/app/services/__init__.py` | Package docstring | Phase 7 |
| `backend/app/services/embedding/types.py` | Canonical embedding enums | Phase 2 |
| `backend/app/main.py` | Worker imports | Phase 1, 6 |
| `backend/app/api/deps.py` | DI imports | Phase 1 |
| `backend/app/providers/metered_provider.py` | Metering imports | Phase 1 |
| `backend/app/repositories/job_pool_repository.py` | Dedup import | Phase 6 |
| `backend/scripts/reembed_all.py` | Embedding script | Phase 2 |

---

## Change Log

| Date | Change |
|------|--------|
| 2026-03-29 | Initial plan creation. 9 phases, 30 tasks. |
