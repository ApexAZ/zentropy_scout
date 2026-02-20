import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
	testDir: "./tests",
	timeout: 30_000,
	retries: process.env.CI ? 2 : 0,
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
			use: { ...devices["Desktop Chrome"] },
		},
	],
	webServer: {
		command: "npm run dev",
		port: 3000,
		reuseExistingServer: !process.env.CI,
	},
});
