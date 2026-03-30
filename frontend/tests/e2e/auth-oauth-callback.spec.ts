/**
 * E2E tests for OAuth callback flows.
 *
 * REQ-013 §4.1, §4.2: OAuth redirect-callback sequence for Google
 * and LinkedIn providers. Tests the full OAuth flow from button click
 * through simulated provider callback to authenticated dashboard.
 *
 * A. Happy Path — OAuth button click, simulated callback, authenticated dashboard.
 * B. Error Cases — provider errors and backend callback failures via
 *    redirect chain interception.
 *
 * Note: Playwright's route.fulfill() supports single-hop redirects but
 * chained cross-origin redirects (initiation → callback → frontend) fail
 * in Chromium with chrome-error://chromewebdata/. Happy path tests
 * simulate the callback result directly; error tests use single-hop
 * redirect to the callback endpoint.
 */

import { expect, test, type Page } from "./base-test";

import { authMeResponse } from "../fixtures/auth-mock-data";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LOGIN_PATH = "/login";
const REGISTER_PATH = "/register";
const DASHBOARD_PATH = "/dashboard";
const DASHBOARD_PATTERN = /\/dashboard/;

/** WebKit fix: wait for AuthProvider /auth/me to settle before interaction. */
const GOTO_OPTS = { waitUntil: "networkidle" } as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Mutable auth state shared between route handlers. The `authenticated`
 * flag is flipped during the simulated callback so the auth/me handler
 * returns the correct response for the current authentication state.
 */
interface OAuthMockState {
	authenticated: boolean;
}

/**
 * Set up a stateful auth/me handler (401 → 200) for OAuth flow tests.
 * LIFO priority over the base-test handler.
 */
async function setupStatefulAuthMe(
	page: Page,
	state: OAuthMockState,
): Promise<void> {
	await page.route(/\/api\/v1\/auth\/me/, async (route) => {
		if (state.authenticated) {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify(authMeResponse()),
			});
		} else {
			await route.fulfill({ status: 401, body: "Unauthorized" });
		}
	});
}

/**
 * Simulate the end result of a successful OAuth callback:
 * set the session cookie and flip the auth state to authenticated.
 *
 * In production, the backend callback sets the session cookie and
 * redirects to the frontend. We simulate this by directly setting
 * the cookie and updating the auth state.
 */
async function simulateOAuthCallback(
	page: Page,
	state: OAuthMockState,
): Promise<void> {
	state.authenticated = true;
	await page.context().addCookies([
		{
			name: "zentropy.session-token",
			value: "mock-oauth-session-token",
			domain: "localhost",
			path: "/",
		},
	]);
}

/**
 * Set up route mocks for OAuth error scenarios.
 *
 * Auth/me always returns 401. Initiation redirects to callback.
 * Callback returns the specified error response (single-hop redirect
 * chain that works reliably in Playwright).
 */
async function setupOAuthErrorMocks(
	page: Page,
	options: {
		/** Query params for the callback URL (e.g., code/state or error). */
		callbackParams: string;
		/** HTTP status code the callback returns. */
		callbackStatus: number;
		/** Error response body from the callback. */
		callbackBody: { error: { code: string; message: string } };
	},
): Promise<void> {
	// Auth/me always 401 — error flow prevents authentication
	await page.route(/\/api\/v1\/auth\/me/, async (route) => {
		await route.fulfill({ status: 401, body: "Unauthorized" });
	});

	// Mock initiation: redirect to callback with specified params.
	// Uses HTML meta refresh instead of HTTP 307 because WebKit's
	// Playwright driver does not support route.fulfill() with redirect
	// status codes.
	await page.route(/\/api\/v1\/auth\/providers\/google/, async (route) => {
		const url = new URL(route.request().url());
		const callbackUrl = `${url.origin}/api/v1/auth/callback/google?${options.callbackParams}`;
		await route.fulfill({
			status: 200,
			contentType: "text/html",
			body: `<!DOCTYPE html><html><head><meta http-equiv="refresh" content="0;url=${callbackUrl}"></head><body></body></html>`,
		});
	});

	// Mock callback: return error response
	await page.route(/\/api\/v1\/auth\/callback\/google/, async (route) => {
		await route.fulfill({
			status: options.callbackStatus,
			contentType: "application/json",
			body: JSON.stringify(options.callbackBody),
		});
	});
}

// ---------------------------------------------------------------------------
// Cookie cleanup — clear auth cookie so proxy allows /login and /register
// ---------------------------------------------------------------------------

test.beforeEach(async ({ page }) => {
	await page.context().clearCookies();
});

// ---------------------------------------------------------------------------
// A. Happy Path (3 tests)
// ---------------------------------------------------------------------------

test.describe("OAuth Callback — Happy Path", () => {
	test("Google OAuth: button click → callback → authenticated dashboard", async ({
		page,
	}) => {
		const state: OAuthMockState = { authenticated: false };
		await setupStatefulAuthMe(page, state);

		await page.goto(LOGIN_PATH, GOTO_OPTS);

		// Verify OAuth button links to correct initiation endpoint
		const href = await page.getByTestId("oauth-google").getAttribute("href");
		expect(href).toContain("/api/v1/auth/providers/google");

		// Simulate successful OAuth callback (cookie + auth state)
		await simulateOAuthCallback(page, state);

		// Navigate to dashboard as the backend callback would redirect
		await page.goto(DASHBOARD_PATH, GOTO_OPTS);

		// Verify authenticated dashboard rendered (not redirected to /login)
		await expect(page).toHaveURL(DASHBOARD_PATTERN);
		expect(state.authenticated).toBe(true);
	});

	test("LinkedIn OAuth: button click → callback → authenticated dashboard", async ({
		page,
	}) => {
		const state: OAuthMockState = { authenticated: false };
		await setupStatefulAuthMe(page, state);

		await page.goto(LOGIN_PATH, GOTO_OPTS);

		// Verify OAuth button links to correct initiation endpoint
		const href = await page.getByTestId("oauth-linkedin").getAttribute("href");
		expect(href).toContain("/api/v1/auth/providers/linkedin");

		// Simulate successful OAuth callback
		await simulateOAuthCallback(page, state);

		await page.goto(DASHBOARD_PATH, GOTO_OPTS);

		await expect(page).toHaveURL(DASHBOARD_PATTERN);
		expect(state.authenticated).toBe(true);
	});

	test("Google OAuth from register page works", async ({ page }) => {
		const state: OAuthMockState = { authenticated: false };
		await setupStatefulAuthMe(page, state);

		await page.goto(REGISTER_PATH, GOTO_OPTS);

		// Verify OAuth button on register page also links correctly
		const href = await page.getByTestId("oauth-google").getAttribute("href");
		expect(href).toContain("/api/v1/auth/providers/google");

		// Simulate successful OAuth callback
		await simulateOAuthCallback(page, state);

		await page.goto(DASHBOARD_PATH, GOTO_OPTS);

		await expect(page).toHaveURL(DASHBOARD_PATTERN);
		expect(state.authenticated).toBe(true);
	});
});

// ---------------------------------------------------------------------------
// B. Error Cases (3 tests)
// ---------------------------------------------------------------------------

test.describe("OAuth Callback — Error Cases", () => {
	test("provider error (access_denied) prevents authentication", async ({
		page,
	}) => {
		await setupOAuthErrorMocks(page, {
			callbackParams:
				"error=access_denied&error_description=User+denied+access",
			callbackStatus: 400,
			callbackBody: {
				error: {
					code: "VALIDATION_ERROR",
					message: "Missing authorization code",
				},
			},
		});

		await page.goto(LOGIN_PATH, GOTO_OPTS);
		await page.getByTestId("oauth-google").click();

		// User should NOT reach the authenticated dashboard
		await page.waitForLoadState("networkidle");
		await expect(page).not.toHaveURL(DASHBOARD_PATTERN);
	});

	test("callback server error (500) prevents authentication", async ({
		page,
	}) => {
		await setupOAuthErrorMocks(page, {
			callbackParams: "code=mock_code&state=mock_state",
			callbackStatus: 500,
			callbackBody: {
				error: {
					code: "INTERNAL_ERROR",
					message: "OAuth authentication failed",
				},
			},
		});

		await page.goto(LOGIN_PATH, GOTO_OPTS);
		await page.getByTestId("oauth-google").click();

		await page.waitForLoadState("networkidle");
		await expect(page).not.toHaveURL(DASHBOARD_PATTERN);
	});

	test("invalid OAuth state (CSRF) prevents authentication", async ({
		page,
	}) => {
		await setupOAuthErrorMocks(page, {
			callbackParams: "code=mock_code&state=invalid_state",
			callbackStatus: 400,
			callbackBody: {
				error: {
					code: "VALIDATION_ERROR",
					message: "Invalid or expired OAuth state",
				},
			},
		});

		await page.goto(LOGIN_PATH, GOTO_OPTS);
		await page.getByTestId("oauth-google").click();

		await page.waitForLoadState("networkidle");
		await expect(page).not.toHaveURL(DASHBOARD_PATTERN);
	});
});
