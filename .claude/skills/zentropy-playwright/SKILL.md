---
name: zentropy-playwright
description: |
  Playwright E2E and UI testing strategy for Zentropy Scout. Load this skill when:
  - Writing or discussing Playwright tests
  - Creating E2E or UI component tests
  - Someone mentions "playwright", "e2e", "end-to-end", or "UI testing"
  - Mocking API responses in browser tests
---

## Playwright Strategy for Zentropy

We use Playwright for **End-to-End (E2E)** and **UI Component** testing.

---

## Rules of Engagement

### 1. Mock the AI

NEVER let a Playwright test wait for a real LLM response.

```typescript
// tests/e2e/ghostwriter.spec.ts
import { test, expect } from '@playwright/test';

test('draft generation shows review panel', async ({ page }) => {
  // Mock the AI endpoint BEFORE navigating
  await page.route('**/api/ghostwriter/generate', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        draft: 'Mocked cover letter content...',
        confidence: 0.92
      })
    });
  });

  await page.goto('/applications/123/draft');
  await page.click('[data-testid="generate-draft"]');

  // Test completes instantly, no LLM wait
  await expect(page.locator('[data-testid="review-panel"]')).toBeVisible();
});
```

### 2. Test User Intent, Not Implementation

| ❌ Don't Test | ✅ Do Test |
|---------------|-----------|
| "The div has class 'blue'" | "Error messages appear in red" |
| "Button has onClick handler" | "Clicking 'Submit' shows confirmation" |
| "State variable equals X" | "After login, user sees dashboard" |

```typescript
// ❌ Bad: Testing implementation
expect(await page.locator('.btn-primary').getAttribute('class')).toContain('blue');

// ✅ Good: Testing user-visible behavior
await page.click('[data-testid="submit-application"]');
await expect(page.locator('[data-testid="success-toast"]')).toContainText('Application sent');
```

### 3. Idempotency

Every test must clean up its own data or run in isolation.

```typescript
// tests/e2e/persona.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Persona Management', () => {
  let createdPersonaId: string;

  test.afterEach(async ({ request }) => {
    // Clean up test data
    if (createdPersonaId) {
      await request.delete(`/api/personas/${createdPersonaId}`);
    }
  });

  test('can create a new persona', async ({ page, request }) => {
    await page.goto('/personas/new');
    await page.fill('[data-testid="persona-name"]', 'Test Persona');
    await page.click('[data-testid="save-persona"]');

    // Capture ID for cleanup
    const response = await page.waitForResponse('**/api/personas');
    const data = await response.json();
    createdPersonaId = data.id;

    await expect(page.locator('[data-testid="persona-card"]')).toContainText('Test Persona');
  });
});
```

---

## Test File Structure

```
frontend/tests/
├── e2e/                        # Full user flows
│   ├── auth.spec.ts            # Login, logout, session
│   ├── persona-crud.spec.ts    # Create, edit, delete personas
│   ├── job-application.spec.ts # Full application flow
│   └── ghostwriter.spec.ts     # AI content generation
├── components/                 # Isolated UI components
│   ├── persona-card.spec.ts
│   └── job-match-score.spec.ts
├── fixtures/                   # Reusable test data
│   ├── mock-personas.json
│   └── mock-jobs.json
└── utils/
    ├── auth.ts                 # Login helper
    └── api-mocks.ts            # Common route mocks
```

---

## Selector Strategy

Priority order (most stable → least stable):

1. **`data-testid`** — Explicit, won't break on refactor
2. **`role` + `name`** — Accessible, semantic
3. **`text`** — User-visible, but fragile if copy changes
4. **`class/id`** — Last resort, breaks easily

```typescript
// ✅ Best: data-testid
await page.click('[data-testid="submit-application"]');

// ✅ Good: ARIA role
await page.click(page.getByRole('button', { name: 'Submit Application' }));

// ⚠️ Okay: Text content
await page.click(page.getByText('Submit Application'));

// ❌ Avoid: CSS classes
await page.click('.btn-primary.submit-btn');
```

**Rule:** Add `data-testid` to any element that E2E tests interact with.

---

## Common Mock Patterns

### Mock All AI Endpoints

```typescript
// tests/utils/api-mocks.ts
import { Page } from '@playwright/test';

export async function mockAIEndpoints(page: Page) {
  await page.route('**/api/ghostwriter/**', async (route) => {
    const url = route.request().url();

    if (url.includes('/generate')) {
      await route.fulfill({
        json: { draft: 'Mock generated content', confidence: 0.9 }
      });
    } else if (url.includes('/score')) {
      await route.fulfill({
        json: { score: 85, breakdown: { skills: 90, experience: 80 } }
      });
    }
  });
}

// Usage in test
test('application flow', async ({ page }) => {
  await mockAIEndpoints(page);
  await page.goto('/applications/new');
  // ...
});
```

### Mock Auth State

```typescript
// tests/utils/auth.ts
import { Page } from '@playwright/test';

export async function loginAsTestUser(page: Page) {
  // Set auth cookie/token directly instead of going through UI
  await page.context().addCookies([{
    name: 'session',
    value: 'test-session-token',
    domain: 'localhost',
    path: '/'
  }]);
}
```

---

## Playwright Config

```typescript
// playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  retries: process.env.CI ? 2 : 0,

  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  webServer: {
    command: 'npm run dev',
    port: 3000,
    reuseExistingServer: !process.env.CI,
  },
});
```

---

## Visual Regression Testing (Docker)

Visual regression tests use `toHaveScreenshot()` to compare screenshots against committed baselines. Baselines are generated inside Docker (Ubuntu Noble) so that WSL2 local screenshots match CI (also Ubuntu) — same font rendering, same browser binaries.

### When to Use Docker vs Native Playwright

| Use Case | Tool | Why |
|----------|------|-----|
| **E2E functional tests** | Native Playwright (`npx playwright test`) | Fast, no Docker overhead |
| **Visual regression tests** | Docker (`npm run test:e2e:visual`) | OS-consistent rendering |
| **Updating baselines** | Docker (`npm run test:e2e:visual:update`) | Baselines must match CI |
| **Accessibility tests** | Native Playwright | No screenshot comparison |
| **Performance tests** | Native Playwright (Chromium only) | Browser timing APIs |

### Docker Commands

```bash
cd frontend

# Run visual regression tests (compare against committed baselines)
npm run test:e2e:visual

# Update baselines (after intentional UI changes)
npm run test:e2e:visual:update
```

These commands run Playwright inside a Docker container defined in `frontend/docker/docker-compose.playwright.yml`. The container:
- Uses `frontend/docker/playwright.Dockerfile` (Ubuntu Noble base)
- Bind-mounts `tests/`, `src/`, and `public/` so baselines persist on host
- Starts its own Next.js dev server via Playwright's `webServer` config
- Runs as host user (`UID:GID`) so baselines have correct file ownership

### Baseline Update Workflow

1. Make your UI change
2. Run `cd frontend && npm run test:e2e:visual` — tests fail showing diffs
3. Review the diff screenshots in `frontend/test-results/` to confirm changes are intentional
4. Run `cd frontend && npm run test:e2e:visual:update` — regenerates baselines
5. Commit the updated baselines (`frontend/tests/__screenshots__/`)

### Baseline File Structure

```
frontend/tests/__screenshots__/
└── {projectName}/
    └── e2e/visual-regression.spec.ts/
        ├── landing-desktop.png
        ├── login-desktop.png
        ├── dashboard-desktop.png
        └── ...
```

Baselines are committed to git and MUST be regenerated via Docker after any UI change that affects screenshots. The `maxDiffPixels: 50` threshold allows minor anti-aliasing differences while catching real regressions.

### CI Integration

Visual regression tests run in the `playwright-visual-regression` CI job (`.github/workflows/playwright.yml`), which:
- Runs on push to main and workflow_dispatch only (not PRs)
- Uses `continue-on-error: true` until baselines stabilize
- Uploads screenshot diffs as artifacts on failure, and test reports on all non-cancelled runs

---

## Checklist Before Merging E2E Tests

- [ ] All AI/LLM endpoints are mocked
- [ ] Test uses `data-testid` selectors (added to components if needed)
- [ ] Test cleans up any data it creates
- [ ] Test passes 3x in a row locally
- [ ] Test doesn't depend on other tests' state
- [ ] If UI changed: visual regression baselines updated via Docker
