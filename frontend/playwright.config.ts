import { defineConfig, devices } from "@playwright/test";

const integrationEnabled = process.env.INTEGRATION === "true";

// ---------------------------------------------------------------------------
// Visual regression baseline workflow (Docker-based)
//
// Baselines are generated inside a Docker container to ensure consistent
// font rendering and browser binaries across WSL2 local dev and Ubuntu CI.
//
//   Generate/update baselines:
//     cd frontend && npm run test:e2e:visual:update
//
//   Run visual regression tests (compare against baselines):
//     cd frontend && npm run test:e2e:visual
//
// Both commands use docker/docker-compose.playwright.yml which builds from
// docker/playwright.Dockerfile (mcr.microsoft.com/playwright:v1.58.2-noble).
// Tests and __screenshots__ are bind-mounted so baselines persist on host.
//
// Baselines live in tests/e2e/__screenshots__/{projectName}/... and MUST be
// committed to git. Regenerate after any UI change that affects screenshots.
// ---------------------------------------------------------------------------

export default defineConfig({
	testDir: "./tests",
	// Visual regression tests run only via Docker (npm run test:e2e:visual).
	// Exclude from default npx playwright test to avoid font-rendering mismatches.
	testIgnore: /visual-regression/,
	timeout: 30_000,
	expect: {
		timeout: 10_000,
		toHaveScreenshot: {
			maxDiffPixels: 50,
			threshold: 0.2,
		},
	},
	snapshotPathTemplate:
		"{testDir}/__screenshots__/{projectName}/{testFilePath}/{arg}{ext}",
	workers: process.env.CI ? undefined : 4,
	retries: process.env.CI ? 2 : 1,
	use: {
		baseURL: "http://localhost:3000",
		trace: "on-first-retry",
		screenshot: "only-on-failure",
		// Auth cookie for proxy bypass — proxy checks PRESENCE only
		// (not JWT validity), so any non-empty value works.
		storageState: {
			cookies: [
				{
					name: "zentropy.session-token",
					value: "mock-e2e-session",
					domain: "localhost",
					path: "/",
					expires: -1,
					httpOnly: false,
					secure: false,
					sameSite: "Lax",
				},
			],
			origins: [],
		},
	},
	projects: [
		{
			name: "chromium",
			testMatch: "e2e/**/*.spec.ts",
			use: { ...devices["Desktop Chrome"] },
		},
		{
			name: "firefox",
			testMatch: "e2e/**/*.spec.ts",
			use: { ...devices["Desktop Firefox"] },
		},
		{
			name: "webkit",
			testMatch: "e2e/**/*.spec.ts",
			use: { ...devices["Desktop Safari"] },
		},
		// Integration tests: real backend + DB, no mock storageState.
		// Only included when INTEGRATION=true (opt-in).
		...(integrationEnabled
			? [
					{
						name: "integration",
						testDir: "./tests/integration",
						testMatch: "**/*.spec.ts",
						use: {
							...devices["Desktop Chrome"],
							// Override global storageState — real backend validates JWT,
							// so tests must authenticate via API (no mock cookie).
							storageState: undefined,
						},
					},
				]
			: []),
	],
	webServer: {
		command: "npm run dev",
		port: 3000,
		reuseExistingServer: !process.env.CI,
	},
});
