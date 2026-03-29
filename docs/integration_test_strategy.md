# Integration Test Strategy

**Created:** 2026-03-29
**Last Updated:** 2026-03-29
**Status:** Draft

## Overview

Zentropy Scout uses two tiers of Playwright E2E tests:

1. **Mocked tests** (default) -- Fast, deterministic, run on every PR. All API responses are intercepted by `page.route()` controllers. These tests verify UI behavior in isolation from the backend.

2. **Integration tests** (opt-in) -- Slower, require a running backend + database. These tests hit real API endpoints and verify full-stack behavior end-to-end. Gated behind `INTEGRATION=true`.

This document defines when to use each tier, how to set up infrastructure, and how integration tests fit into CI.

---

## 1. Decision Matrix: Mocked vs Real-Backend Tests

| Scenario | Tier | Why |
|----------|------|-----|
| Auth cookie flow (register, login, session) | **Integration** | Proxy validates cookie presence; backend sets `httpOnly` cookie with real JWT -- mock cookies skip this entirely |
| OAuth callback redirect chain | **Integration** | Multi-hop redirect between provider, backend callback, and frontend -- mock can't simulate cookie-setting redirects |
| PDF generation and download | **Integration** | Backend generates PDF bytes via ReportLab; verifying file content requires a real response |
| File upload (resume import) | **Integration** | Multipart form upload → backend BYTEA storage → retrieval -- mock can't validate the round-trip |
| API response shape validation | **Integration** | Catches schema drift between frontend expectations and actual backend responses |
| Database constraint violations | **Integration** | Unique constraints, foreign keys, and cascade deletes only surface with a real database |
| UI layout and navigation | **Mocked** | No backend dependency; route mocks are sufficient |
| Error state rendering (toast, validation) | **Mocked** | Mock controllers can return arbitrary error shapes on demand |
| Component interaction (click, type, drag) | **Mocked** | Pure frontend behavior; faster with mocked API |
| Loading/skeleton states | **Mocked** | Controlled via delayed route fulfillment |
| Responsive layout | **Mocked** | Viewport-only; no backend needed |
| Visual regression (screenshot comparison) | **Mocked** | Deterministic screenshots require deterministic data |
| Accessibility (axe-core scans) | **Mocked** | WCAG compliance is a frontend concern |
| Performance (Web Vitals budgets) | **Mocked** | Timing metrics should not include backend latency variance |

**Rule of thumb:** If the test would pass with a mock returning the "happy path" response but could fail in production due to backend behavior, it belongs in the integration tier.

---

## 2. Infrastructure Requirements

Integration tests require three services running simultaneously:

| Service | Address | Setup |
|---------|---------|-------|
| PostgreSQL + pgvector | `localhost:5432` | `docker compose up -d` (uses `pgvector/pgvector:pg16`) |
| Backend (FastAPI) | `localhost:8000` | From project root: `source backend/.venv/bin/activate && uvicorn backend.app.main:app --port 8000` |
| Frontend (Next.js) | `localhost:3000` | `cd frontend && npm run dev` |

### Prerequisites

1. **Docker** -- PostgreSQL container must be running and healthy (`docker compose ps`)
2. **Migrations** -- `cd backend && alembic upgrade head` (schema must be current)
3. **Environment** -- `.env` at project root with valid `DATABASE_*` vars, `AUTH_ENABLED=true`, `AUTH_SECRET` set. Note: mocked tests and normal local development use `AUTH_ENABLED=false` (the proxy only checks cookie presence). Only set `AUTH_ENABLED=true` when running integration tests against the real backend.
4. **Backend started from project root** -- `.env` resolves relative to CWD; starting from `backend/` causes missing-env errors

### Environment Variables

Integration tests check for `INTEGRATION=true` at the Playwright config level. When this var is absent, the integration project is excluded entirely:

```typescript
// playwright.config.ts (simplified)
const integrationEnabled = process.env.INTEGRATION === "true";

projects: [
  { name: "chromium", /* ... */ },
  { name: "firefox", /* ... */ },
  { name: "webkit", /* ... */ },
  // Only included when INTEGRATION=true
  ...(integrationEnabled ? [{
    name: "integration",
    testDir: "./tests/integration",
    testMatch: "**/*.spec.ts",
    use: { ...devices["Desktop Chrome"] },
    // No storageState -- real backend validates JWT
  }] : []),
]
```

---

## 3. Database Seeding

Integration tests do **not** use pre-seeded fixture data. Instead:

### Per-Test User Registration

Each test registers its own user via the real `POST /api/v1/auth/register` endpoint. This guarantees:

- **Isolation** -- No shared state between tests
- **Idempotency** -- Tests can run in any order, concurrently
- **Realistic flow** -- The registration endpoint is itself under test

```typescript
// Example: register a unique test user
const timestamp = Date.now();
const email = `integration-${timestamp}@test.example.com`;
const password = "TestPassword123!";

// RegisterRequest accepts only email + password (extra="forbid")
const registerResponse = await request.post("/api/v1/auth/register", {
  data: { email, password },
});
expect(registerResponse.status()).toBe(201);
```

### Database Schema

Alembic migrations must be applied before tests run. The integration test setup script (or CI job) runs:

```bash
cd backend && alembic upgrade head
```

No seed scripts, no shared fixtures, no test database snapshots. The register endpoint creates all necessary data.

### Cleanup

Test users accumulate in the database. For local development this is harmless (the dev database is ephemeral -- `docker compose down -v` resets it). In CI, each run starts with a fresh PostgreSQL container.

---

## 4. CI Approach

Integration tests run in a **separate CI job** that provisions its own PostgreSQL service container.

### Workflow Design

```yaml
# .github/workflows/playwright.yml (integration job -- future addition)
playwright-integration:
  if: github.event_name == 'push' && github.ref == 'refs/heads/main'
  runs-on: ubuntu-latest
  timeout-minutes: 20
  permissions:
    contents: read
  services:
    postgres:
      image: pgvector/pgvector@sha256:a208a03832da123d45ec6049b4d5c9d49fcacfbffd7d6e3cb537bffdf62e769e  # pg16
      env:
        POSTGRES_USER: zentropy_user
        POSTGRES_PASSWORD: ${{ secrets.DB_PASSWORD }}
        POSTGRES_DB: zentropy_scout
      ports:
        - 5432:5432
      options: >-
        --health-cmd "pg_isready -U zentropy_user -d zentropy_scout"
        --health-interval 10s
        --health-timeout 5s
        --health-retries 5
  steps:
    - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6
    - uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405  # v6
      with: { python-version: "3.11" }
    - uses: actions/setup-node@6044e13b5dc448c55e2357c09f80417699197238  # v6.2.0
      with: { node-version: "20" }
    # Backend setup
    - run: pip install -e "./backend[dev]"
    - name: Run migrations
      run: cd backend && alembic upgrade head
      env:
        DATABASE_PASSWORD: ${{ secrets.DB_PASSWORD }}
    - name: Start FastAPI server
      run: |
        cd backend
        python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
        for i in $(seq 1 30); do
          if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
            echo "Server is ready"
            break
          fi
          echo "Waiting for server... ($i/30)"
          sleep 2
        done
        if ! curl -sf http://localhost:8000/health > /dev/null 2>&1; then
          echo "::error::Server failed to start within 60 seconds"
          exit 1
        fi
      env:
        DATABASE_PASSWORD: ${{ secrets.DB_PASSWORD }}
        AUTH_ENABLED: "true"
        AUTH_SECRET: ${{ secrets.AUTH_SECRET }}
        RATE_LIMIT_ENABLED: "false"
    # Frontend setup
    - run: npm ci
      working-directory: frontend
    - run: npx playwright install chromium
      working-directory: frontend
    # Run integration tests (Playwright's webServer config handles frontend startup)
    - run: INTEGRATION=true npx playwright test --project=integration
      working-directory: frontend
```

**CI Secrets Required:** The integration job needs these GitHub Secrets configured:
- `DB_PASSWORD` -- PostgreSQL password (matches existing CI jobs)
- `AUTH_SECRET` -- JWT signing key for real auth flows

### Trigger Rules

| Trigger | Runs Integration? | Why |
|---------|-------------------|-----|
| Push to `main` | Yes | Full validation after merge |
| Pull request | No | Too slow for PR feedback; mocked tests catch UI regressions |
| `workflow_dispatch` | Yes | Manual trigger for debugging |

### Why Not on PRs?

Integration tests require:
- PostgreSQL service container startup (~15s)
- Backend installation + migration (~30s)
- Backend server startup (~5s)
- Full auth flow per test (~2-5s each)

This overhead is acceptable on push-to-main but would slow PR feedback loops. Mocked Playwright tests (running on every PR) catch the vast majority of UI regressions without this cost.

---

## 5. Test Isolation

### Principles

1. **Each test registers its own user** -- No shared user accounts, no shared session state
2. **No test depends on another test's data** -- Tests can run in any order or in parallel
3. **No database truncation between tests** -- Registration with unique emails provides natural isolation
4. **No shared cookies or storage state** -- Each test authenticates independently via the API

### Implementation Pattern

```typescript
import { test, expect } from "@playwright/test";

test.describe("Integration: Feature X", () => {
  let testEmail: string;
  const testPassword = "TestPass123!";

  test.beforeEach(async ({ page }) => {
    // Register a unique user for this test
    testEmail = `integ-${Date.now()}-${Math.random().toString(36).slice(2)}@test.example.com`;

    // Use page.request (shares browser cookie jar) instead of standalone request context
    await page.request.post("/api/v1/auth/register", {
      data: { email: testEmail, password: testPassword },
    });

    // Login -- backend sets httpOnly cookie on the browser context directly
    const loginResponse = await page.request.post("/api/v1/auth/verify-password", {
      data: { email: testEmail, password: testPassword },
    });
    expect(loginResponse.ok()).toBeTruthy();
    // Cookie is now set on the page's browser context (httpOnly, set by backend)
  });

  test("does something with real backend", async ({ page }) => {
    await page.goto("/dashboard");
    // ... assertions against real backend data
  });
});
```

**Note:** Use `page.request` (not the standalone `request` fixture) so that cookies set by the backend's `Set-Cookie` response header are applied to the browser context. The standalone `request` fixture has its own cookie jar that is not shared with `page`.

### What This Catches (That Mocks Miss)

| Issue | Mocked Test Result | Integration Test Result |
|-------|-------------------|----------------------|
| Backend returns different JSON shape than frontend expects | Passes (mock matches frontend expectation) | **Fails** (real response doesn't match) |
| Auth cookie `httpOnly`/`Secure` flags misconfigured | Passes (mock cookie has no flags) | **Fails** (browser can't read cookie, or cookie not sent) |
| Database unique constraint on email | Passes (no real DB) | **Fails** (duplicate registration rejected) |
| CORS misconfiguration | Passes (no cross-origin requests) | **Fails** (browser blocks API call) |

---

## 6. Environment Variable Gating

### The `INTEGRATION` Variable

Integration tests are completely opt-in. The gating mechanism:

| Layer | Behavior When `INTEGRATION` is Absent | Behavior When `INTEGRATION=true` |
|-------|---------------------------------------|-----------------------------------|
| `playwright.config.ts` | Integration project not included in `projects[]` | Integration project added to `projects[]` |
| `npx playwright test` | Runs only mocked test projects (chromium, firefox, webkit) | Runs mocked + integration projects |
| CI (PR) | Skipped entirely | N/A (not triggered on PRs) |
| CI (push to main) | N/A | Set by the integration job |

### NPM Script

```json
{
  "scripts": {
    "test:e2e:integration": "INTEGRATION=true playwright test --project=integration"
  }
}
```

### Local Development

```bash
# Run ONLY mocked tests (default -- no backend needed)
cd frontend && npx playwright test

# Run ONLY integration tests (requires running backend + DB)
cd frontend && npm run test:e2e:integration

# Run everything (mocked + integration)
cd frontend && INTEGRATION=true npx playwright test
```

Note: `npx` is needed in terminal commands but not in npm scripts (npm resolves `node_modules/.bin` automatically).

### Guard Rails

- The integration test directory (`frontend/tests/integration/`) is separate from mocked tests (`frontend/tests/e2e/`)
- Integration specs import from `@playwright/test` directly, NOT from `base-test.ts` (no mock infrastructure)
- The integration Playwright project has no `storageState` -- the real backend issues cookies
- If `INTEGRATION=true` is set but the backend isn't running, tests fail fast with connection errors (not silent passes)
