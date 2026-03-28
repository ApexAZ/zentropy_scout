# Zentropy Scout — Playwright E2E Test Gaps Plan

**Created:** 2026-03-27
**Last Updated:** 2026-03-27
**Status:** ⬜ Incomplete
**Destination:** `docs/plan/playwright_test_gaps_plan.md`

---

## Context

The Playwright E2E test suite has 261 tests across 26 spec files with comprehensive mocking infrastructure — but it has 8 identified gaps: no accessibility audits (axe-core), no visual regression testing, no performance testing, single-browser only (Chromium), untested OAuth callback flow, untested PDF download validation, untested drag-and-drop file upload, and no real backend integration tests.

**What gets built:**
- **Multi-browser:** Firefox + WebKit projects in playwright.config.ts, CI matrix strategy, browser-specific failure fixes
- **Accessibility:** @axe-core/playwright integration, WCAG 2.1 AA scans for 11 key pages
- **Specialized flows:** OAuth callback mock tests, PDF download validation, drag-and-drop upload tests
- **Visual regression:** toHaveScreenshot() baselines for 10 key pages, Docker-based baseline generation for OS consistency
- **Performance:** Web vitals budget assertions for 4 key pages
- **Integration:** Strategy document + smoke test against real backend

**What doesn't change:** Existing 261 tests, mock infrastructure (base-test.ts, fixtures, utils), existing CI workflow structure.

**Key decisions:**
- Fix all browser-specific failures (no skip annotations) — true cross-browser coverage
- Docker-based visual regression baselines for OS consistency (WSL2 local matches Ubuntu CI)
- Web vitals via Playwright native APIs (no playwright-lighthouse dependency)
- Integration tests gated behind `INTEGRATION=true` env var (opt-in, not default)
- Visual regression baselines generated per-browser via snapshotPathTemplate

---

## How to Use This Document

1. Find the first 🟡 or ⬜ task — that's where to start
2. Each task = one commit, sized ≤ 40k tokens of context (TDD + review + fixes included)
3. **Subtask workflow:** Run affected tests → linters → commit → compact (NO push)
4. **Phase-end workflow:** Run full test suite (backend + frontend + E2E) → push → compact
5. After each task: update status (⬜ → ✅), commit, STOP and ask user

| Action | Subtask | Phase Gate |
|--------|---------|------------|
| Tests | Affected files only | Full backend + frontend + E2E |
| Linters | Pre-commit hooks (~25-40s) | Pre-commit + pre-push hooks |
| Git | `git commit` only | `git push` |
| Context | Compact after commit | Compact after push |

**Context management for fresh sessions:** Each subtask is self-contained. A fresh context needs:
1. This plan (find current task by status icon)
2. The specific files listed in the task description
3. No prior conversation history required

---

## Dependency Chain

```
Phase 1: Multi-Browser Configuration
    │
    ▼
Phase 2: Accessibility Audits (axe-core)
    │   (findings may change components → must precede visual baselines)
    ▼
Phase 3: Specialized Flow Testing (OAuth, PDF, Drag-and-Drop)
    │
    ▼
Phase 4: Visual Regression + Performance Testing
    │   (baselines reflect post-accessibility, post-flow-fix state)
    ▼
Phase 5: Real Backend Integration Strategy
```

**Ordering rationale:** Multi-browser first because visual regression baselines are per-browser. Accessibility second because axe-core findings may trigger component changes that would invalidate visual baselines. Specialized flow tests are independent but grouped before visual regression so any UI fixes are captured in baselines. Visual regression + performance come after all UI changes are settled. Integration strategy is last (lowest urgency, highest infrastructure requirement).

---

## Phase 1: Multi-Browser Configuration

**Status:** ⬜ Incomplete

*Add Firefox and WebKit projects to playwright.config.ts, update CI to run all three browsers, and fix any browser-specific failures in the existing 261 tests. This must precede visual regression baselines since they are per-browser.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read `playwright.config.ts`, `.github/workflows/playwright.yml` |
| 🧪 **TDD** | Run existing tests against new browsers, fix failures |
| 🗃️ **Patterns** | Use `zentropy-playwright` for config conventions |
| ✅ **Verify** | `npx playwright test --list` confirms 3 projects; all tests pass on all browsers |
| 🔍 **Review** | Use `code-reviewer` + `security-reviewer` agents |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Security triage gate** — Spawn `security-triage` subagent (general-purpose, opus, foreground). Verdicts: CLEAR → proceed, VULNERABLE → fix, FALSE POSITIVE → full prosecution, NEEDS INVESTIGATION → escalate. | `plan, security` | ✅ |
| 2 | **Add Firefox and WebKit projects to playwright.config.ts** — Add two new project entries: `{ name: "firefox", use: { ...devices["Desktop Firefox"] } }` and `{ name: "webkit", use: { ...devices["Desktop Safari"] } }`. Keep Chromium first. Verify with `npx playwright test --list` that all 3 projects appear. Install browsers: `npx playwright install --with-deps firefox webkit`. | `plan, playwright, e2e` | ✅ |
| 3 | **Update CI workflow for multi-browser matrix** — Modify `.github/workflows/playwright.yml`: (a) change browser install to `npx playwright install --with-deps` (all configured browsers), (b) add matrix strategy `browser: [chromium, firefox, webkit]` passing `--project=${{ matrix.browser }}`, (c) gate Firefox/WebKit to `push` events only (not `pull_request`) via matrix conditional, (d) update artifact upload to include browser name, (e) increase `timeout-minutes` to 20. | `plan, playwright, commands` | ✅ |
| 4 | **Add cross-browser npm scripts and run Firefox tests** — Add to `package.json`: `"test:e2e:firefox": "playwright test --project=firefox"`, `"test:e2e:webkit": "playwright test --project=webkit"`, `"test:e2e:all": "playwright test"`. Run all 261 tests against Firefox. Document and fix all failures. This may involve fixing CSS/JS browser-specific issues, adjusting selectors, or adding small waits for rendering differences. | `plan, playwright, e2e, tdd` | ✅ |
| 5 | **Run WebKit tests and fix remaining failures** — Run all 261 tests against WebKit. Fix all browser-specific failures. WebKit has stricter CSS handling and different event timing — expect different failures than Firefox. After fixing, run all 3 browsers together to confirm no regressions. | `plan, playwright, e2e, tdd` | ⬜ |
| 6 | **Phase gate — full test suite + push** — Run test-runner in Full mode (pytest + Vitest + Playwright all browsers + lint + typecheck). Fix regressions, commit, push. | `plan, commands` | ⬜ |

#### Notes
- Split browser fixes into separate tasks (§4 Firefox, §5 WebKit) because each may surface different issues and could be substantial
- Firefox and WebKit tests run on `push` to main only in CI (not PRs) to avoid tripling CI time on every PR

---

## Phase 2: Accessibility Audits with axe-core

**Status:** ⬜ Incomplete

*Install @axe-core/playwright, create a reusable audit helper, and scan 11 key pages for WCAG 2.1 AA violations. This runs before visual regression because findings may trigger component changes that would invalidate baselines.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read existing `accessibility.spec.ts`, review component structure for a11y patterns |
| �� **TDD** | Write axe-core scan tests, fix violations to make them pass |
| 🗃️ **Patterns** | Use `zentropy-playwright` for test structure, `zentropy-tdd` for TDD cycle |
| ✅ **Verify** | `npx playwright test tests/e2e/accessibility.spec.ts -v` |
| 🔍 **Review** | Use `code-reviewer` + `security-reviewer` + `ui-reviewer` agents |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 7 | **Security triage gate** — Spawn `security-triage` subagent. | `plan, security` | ⬜ |
| 8 | **Install @axe-core/playwright and create audit helper** — Run `npm install -D @axe-core/playwright` in frontend. Create `frontend/tests/utils/axe-helper.ts` exporting `runAxeAudit(page, options?)` wrapping `AxeBuilder`. Default to WCAG 2.1 AA tags (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`). Accept optional `disableRules` array and `exclude` selectors. Return `AxeResults`. Include JSDoc with usage example. | `plan, playwright, e2e, tdd` | ⬜ |
| 9 | **Axe audits for public pages (landing, login, register)** — Expand `accessibility.spec.ts` with a new `test.describe("WCAG 2.1 AA — Public Pages")` block. Add axe-core scans for: `/` (landing, unauthenticated — clear cookies), `/login`, `/register`. Each test: navigate with appropriate mocks, wait for `networkidle`, run `runAxeAudit(page)`, assert `violations.length === 0`. Fix any WCAG violations in-line (TDD: test fails → fix component → test passes). Existing reduced-motion test stays unchanged. | `plan, playwright, e2e, tdd, ui` | ⬜ |
| 10 | **Axe audits for authenticated pages (dashboard, persona, resumes, applications, settings)** — Add `test.describe("WCAG 2.1 AA — Authenticated Pages")` block. Scan 5 pages: `/dashboard`, `/persona/basic-info`, `/resumes`, `/applications`, `/settings`. Use appropriate mock controllers from existing utils. Fix WCAG violations in-line. | `plan, playwright, e2e, tdd, ui` | ⬜ |
| 11 | **Axe audits for complex pages (onboarding, ghostwriter review, chat)** — Add `test.describe("WCAG 2.1 AA — Complex Pages")` block. Scan 3 pages: `/onboarding` (step 1 idle), `/jobs/{id}/review` (ghostwriter review with mocked variant + cover letter), dashboard with chat panel open. These have the most interactive widgets — highest a11y risk. Fix violations in-line. | `plan, playwright, e2e, tdd, ui` | ⬜ |
| 12 | **Phase gate — full test suite + push** — Run test-runner in Full mode. Fix regressions, commit, push. | `plan, commands` | ⬜ |

#### Notes
- Expect common violations: missing aria-labels on icon buttons, color contrast issues, heading hierarchy gaps, form label associations
- Fix violations in the components themselves, not with axe rule exclusions — exclusions are a last resort for third-party widgets

---

## Phase 3: Specialized Flow Testing (OAuth, PDF, Drag-and-Drop)

**Status:** ⬜ Incomplete

*Test three untested interaction patterns: OAuth callback mocking, PDF download response validation, and native drag-and-drop file upload. All tests use mocked APIs.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read `auth-login-register.spec.ts`, `resume-detail.spec.ts`, `onboarding.spec.ts`, and corresponding mock controllers |
| 🧪 **TDD** | Write failing tests first for each flow |
| 🗃️ **Patterns** | Use `zentropy-playwright` for mock patterns, `zentropy-api` for endpoint understanding |
| ✅ **Verify** | Run each new spec file individually, then full e2e suite |
| 🔍 **Review** | Use `code-reviewer` + `security-reviewer` agents |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 13 | **Security triage gate** — Spawn `security-triage` subagent. | `plan, security` | ⬜ |
| 14 | **OAuth callback flow tests** — Create `frontend/tests/e2e/auth-oauth-callback.spec.ts`. The existing tests only verify OAuth buttons have correct `href` attributes. New spec mocks the full redirect-callback sequence: (a) intercept `GET /api/v1/auth/providers/google` to return 302 to fake Google URL with `oauth_state` cookie set, (b) simulate callback by navigating to mocked `/api/v1/auth/callback/google?code=mock_code&state=mock_state` that sets session cookie and returns 302 to `/dashboard`, (c) verify user lands on dashboard in authenticated state. Repeat for LinkedIn. Test error cases: invalid state (CSRF), expired code, provider error (`error=access_denied`). Use `AuthMockController` pattern. ~6 tests. **Files:** `auth-api-mocks.ts`, `auth-mock-data.ts`, `auth-login-register.spec.ts` (reference only). | `plan, playwright, e2e, tdd, security` | ⬜ |
| 15 | **PDF download and export validation tests** — Create `frontend/tests/e2e/pdf-download.spec.ts`. Test: (a) clicking "Download PDF" on resume detail triggers download with correct `Content-Type: application/pdf` and `Content-Disposition: attachment` headers — use `page.waitForEvent('download')`, (b) export PDF button works (mock the `/export/pdf` endpoint to return a PDF buffer), (c) export DOCX button works similarly, (d) cover letter PDF download from ghostwriter review page. Mock endpoints return small valid PDF buffers (`%PDF-1.4` header). ~4-5 tests. **Files:** `resume-api-mocks.ts`, `resume-mock-data.ts`, `ghostwriter-api-mocks.ts`. | `plan, playwright, e2e, tdd` | ⬜ |
| 16 | **Drag-and-drop file upload tests** — Create `frontend/tests/e2e/file-upload-dnd.spec.ts`. The existing onboarding tests use `setInputFiles()` on the hidden input but never test the drag-and-drop path. New tests: (a) simulate drag-and-drop via `page.evaluate()` dispatching synthetic `DragEvent` with mock `DataTransfer` + `FileList` containing a PDF, verify drop zone shows active state during dragover, verify upload progress appears, verify auto-advance to step 2 after mock success. (b) Invalid file type (`.docx`) → error message. (c) Oversized file (>10MB) → error message. ~3-4 tests. **Files:** `onboarding-api-mocks.ts`, `onboarding-mock-data.ts`, `resume-upload-step.tsx` (reference). | `plan, playwright, e2e, tdd` | ⬜ |
| 17 | **Phase gate — full test suite + push** — Run test-runner in Full mode. Fix regressions, commit, push. | `plan, commands` | ⬜ |

#### Notes
- OAuth callback tests mock the entire server-side flow — no real OAuth providers involved
- PDF download tests use `page.waitForEvent('download')` which works across all 3 browsers
- Drag-and-drop via synthetic events is the proven Playwright pattern (native DnD API not supported)

---

## Phase 4: Visual Regression + Performance Testing

**Status:** ⬜ Incomplete

*Add toHaveScreenshot() baselines for 10 key pages using Docker for OS-consistent rendering, and web vitals budget assertions for 4 key pages. Visual baselines depend on Phase 1 (multi-browser) and Phase 2 (accessibility fixes that may have changed components).*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read `playwright.config.ts` for current snapshot/screenshot config, confirm multi-browser projects are in place |
| ��� **TDD** | Write screenshot tests, generate baselines with `--update-snapshots` |
| 🗃️ **Patterns** | Use `zentropy-playwright` for test structure |
| ✅ **Verify** | Run visual regression tests twice — second run must pass without `--update-snapshots` |
| 🔍 **Review** | Use `code-reviewer` + `ui-reviewer` agents |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 18 | **Security triage gate** — Spawn `security-triage` subagent. | `plan, security` | ⬜ |
| 19 | **Set up Docker-based visual regression infrastructure** — Create `frontend/docker/playwright.Dockerfile` using the official `mcr.microsoft.com/playwright` image matching the installed Playwright version. Create `frontend/docker-compose.playwright.yml` that mounts the frontend directory and runs Playwright tests inside the container. Add npm scripts: `"test:e2e:visual": "docker compose -f docker/docker-compose.playwright.yml run --rm playwright npx playwright test tests/e2e/visual-regression.spec.ts"`, `"test:e2e:visual:update": "... --update-snapshots"`. Update `playwright.config.ts` to add `expect.toHaveScreenshot` settings: `maxDiffPixels: 50`, `threshold: 0.2`. Add `snapshotPathTemplate: "{testDir}/__screenshots__/{projectName}/{testFilePath}/{arg}{ext}"`. Document the Docker-based baseline workflow in a comment block in `playwright.config.ts`. | `plan, playwright, e2e, commands` | ⬜ |
| 20 | **Visual regression tests for public pages** — Create `frontend/tests/e2e/visual-regression.spec.ts`. Add `toHaveScreenshot()` tests for 3 public pages: landing (unauthenticated), login, register. Each test: set viewport to 1280×720 (desktop), navigate with appropriate mocks, wait for `networkidle`, call `expect(page).toHaveScreenshot('landing-desktop.png')`. Generate initial baselines inside Docker with `--update-snapshots`. Verify second run passes. | `plan, playwright, e2e, tdd, ui` | ⬜ |
| 21 | **Visual regression tests for authenticated pages** — Add to `visual-regression.spec.ts`: 7 authenticated pages — `/dashboard`, `/persona/basic-info`, `/resumes`, `/resumes/{id}` (detail), `/applications`, `/settings`, `/jobs/{id}/review` (ghostwriter). Use appropriate mock controllers. Generate baselines inside Docker. Total: 10 pages × 3 browsers = 30 baseline images. | `plan, playwright, e2e, tdd, ui` | ⬜ |
| 22 | **Update CI for visual regression** — Update `.github/workflows/playwright.yml` to: (a) run visual regression tests using the same Docker image (or the matching official Playwright image in CI), (b) upload screenshot diff artifacts on failure for review, (c) initially use `continue-on-error: true` for visual regression job until baselines stabilize. Add step to upload `__screenshots__` directory as artifact when tests fail. | `plan, playwright, commands` | ⬜ |
| 23 | **Performance budget tests with web vitals** — Create `frontend/tests/e2e/performance.spec.ts`. Measure web vitals for 4 key pages: landing, dashboard, resume detail, onboarding step 1. Extract `PerformanceNavigationTiming` via `page.evaluate()`: (a) TTFB (`responseStart - requestStart` < 800ms), (b) DOM Content Loaded (`domContentLoadedEventEnd - navigationStart` < 3000ms), (c) Load (`loadEventEnd - navigationStart` < 5000ms). Extract LCP via `PerformanceObserver` where supported. All thresholds are generous for mocked-API pages — value is catching regressions. Run on Chromium only (`test.skip` for Firefox/WebKit). ~4-5 tests. | `plan, playwright, e2e, tdd` | ⬜ |
| 24 | **Update Claude Code configuration for Docker visual regression** — Update all `.claude/` files and `CLAUDE.md` that reference Playwright to document the Docker-based visual regression workflow. Files to update: (a) `.claude/skills/zentropy-playwright/SKILL.md` — add Docker commands (`npm run test:e2e:visual`, `npm run test:e2e:visual:update`), document when to use Docker vs native Playwright, baseline update workflow, (b) `.claude/agents/test-runner.md` — add visual regression Docker commands to the "Full mode" test suite, (c) `.claude/agents/qa-reviewer.md` — add visual regression as a test type to recommend when UI changes are detected, (d) `CLAUDE.md` Testing section — add visual regression Docker workflow to the "When to Run Tests" table and note about baseline generation, (e) `.claude/skills/zentropy-commands/SKILL.md` — add Docker Playwright commands if not already present. | `plan, playwright, e2e` | ⬜ |
| 25 | **Phase gate — full test suite + push** — Run test-runner in Full mode. Fix regressions, commit, push. | `plan, commands` | ⬜ |

#### Notes
- Docker ensures WSL2 baselines match CI (Ubuntu) — same font rendering, same browser binaries
- The `maxDiffPixels: 50` allows minor anti-aliasing differences while catching real regressions
- Performance thresholds are intentionally generous — mocked pages should easily pass, failures indicate real regressions
- Visual regression runs inside Docker locally but can use the native CI runner (same Ubuntu base)

---

## Phase 5: Real Backend Integration Strategy

**Status:** ⬜ Incomplete

*Document the real-backend integration test strategy and implement a single smoke test against the real API. This is a foundation for future expansion, not a full integration suite.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read `docker-compose.yml`, backend startup patterns, existing pytest integration setup |
| 🧪 **TDD** | Write smoke test first, configure infrastructure to make it pass |
| 🗃️ **Patterns** | Use `zentropy-commands` for Docker operations, `zentropy-playwright` for test structure |
| ✅ **Verify** | Docker up → backend started → migration applied → smoke test passes |
| 🔍 **Review** | Use `code-reviewer` + `security-reviewer` agents |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 26 | **Security triage gate** — Spawn `security-triage` subagent. | `plan, security` | ⬜ |
| 27 | **Write integration test strategy document** — Create `docs/integration_test_strategy.md`. Document: (a) when to use real-backend tests vs mocked tests (decision matrix: auth flows, file I/O, PDF gen → real; UI layout, navigation, error states → mocked), (b) infrastructure requirements (Docker PostgreSQL + pgvector, backend on :8000, frontend on :3000), (c) database seeding (Alembic migrations + register endpoint for per-test user), (d) CI approach (separate workflow with `services: postgres`, push-to-main only), (e) test isolation (each test registers its own user, no shared state), (f) environment variable gating (`INTEGRATION=true`). | `plan, e2e` | ⬜ |
| 28 | **Create integration Playwright project and smoke test** — Add new project to `playwright.config.ts`: `{ name: "integration", use: { ...devices["Desktop Chrome"] }, testDir: "./tests/integration", testMatch: "**/*.spec.ts" }`. The integration project must NOT use the mock `storageState` (real backend validates JWT). Create `frontend/tests/integration/smoke.spec.ts`: (a) import from `@playwright/test` directly (NOT `base-test.ts` — no mocked routes), (b) hit `GET /api/v1/auth/me` → verify 401, (c) register test user via `POST /api/v1/auth/register`, (d) login via `POST /api/v1/auth/verify-password` → verify session cookie set, (e) `GET /api/v1/auth/me` → verify 200, (f) navigate to `/dashboard` → verify it loads. Gate behind `INTEGRATION=true` env var. Add `"test:e2e:integration": "INTEGRATION=true playwright test --project=integration"` to package.json. Document prerequisites in JSDoc (Docker running, backend started, migrations applied). | `plan, playwright, e2e, tdd, security` | ⬜ |
| 29 | **Phase gate — full test suite + push** ��� Run test-runner in Full mode (standard mocked tests only — integration is opt-in). Fix regressions, commit, push. | `plan, commands` | ⬜ |

#### Notes
- Integration tests are opt-in (`INTEGRATION=true`) — they never run in the default `npx playwright test` invocation
- Each test registers its own user (no shared fixtures) for complete isolation
- Real backend integration catches: auth cookie flow bugs, API response shape changes, database constraint violations
- Future expansion: add PDF download, file upload, and onboarding flows as integration tests

---

## Task Count Summary

| Phase | Feature Tasks | Gate Tasks | Total |
|-------|--------------|------------|-------|
| 1. Multi-Browser | 4 | 2 | 6 |
| 2. Accessibility | 4 | 2 | 6 |
| 3. Specialized Flows | 3 | 2 | 5 |
| 4. Visual + Perf + Config | 6 | 2 | 8 |
| 5. Integration | 2 | 2 | 4 |
| **Total** | **19** | **10** | **29** |

**Estimated new tests:** ~42-48 (11 axe scans + 13-15 flow tests + 10 screenshots + 4-5 perf + 1 integration smoke)
**Estimated post-plan state:** ~305+ tests across ~32 spec files, 3 browsers, WCAG 2.1 AA compliance, visual baselines, performance budgets

---

## Critical Files Reference

| File | Role |
|------|------|
| `frontend/playwright.config.ts` | Central config — multi-browser projects, snapshot settings, integration project |
| `.github/workflows/playwright.yml` | CI — matrix strategy, multi-browser install, visual regression |
| `frontend/tests/e2e/base-test.ts` | Shared test fixture — LIFO route priority (unchanged, reference only) |
| `frontend/tests/e2e/accessibility.spec.ts` | Existing a11y test — expanded with axe-core |
| `frontend/tests/utils/axe-helper.ts` | NEW — reusable axe-core audit wrapper |
| `frontend/tests/e2e/auth-oauth-callback.spec.ts` | NEW — OAuth callback flow tests |
| `frontend/tests/e2e/pdf-download.spec.ts` | NEW — PDF download/export tests |
| `frontend/tests/e2e/file-upload-dnd.spec.ts` | NEW — Drag-and-drop upload tests |
| `frontend/tests/e2e/visual-regression.spec.ts` | NEW — Visual regression baselines |
| `frontend/tests/e2e/performance.spec.ts` | NEW — Web vitals budget tests |
| `frontend/docker/playwright.Dockerfile` | NEW — Docker image for consistent baselines |
| `frontend/docker/docker-compose.playwright.yml` | NEW — Docker Compose for visual regression |
| `.claude/skills/zentropy-playwright/SKILL.md` | UPDATE — Add Docker visual regression commands and workflow |
| `.claude/agents/test-runner.md` | UPDATE — Add visual regression Docker commands to Full mode |
| `.claude/agents/qa-reviewer.md` | UPDATE — Add visual regression as recommenable test type |
| `.claude/skills/zentropy-commands/SKILL.md` | UPDATE — Add Docker Playwright commands |
| `frontend/tests/integration/smoke.spec.ts` | NEW — Real backend smoke test |
| `docs/integration_test_strategy.md` | NEW — Integration test strategy document |

---

## Change Log

| Date | Change |
|------|--------|
| 2026-03-27 | Initial plan created |
