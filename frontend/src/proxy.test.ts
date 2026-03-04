/**
 * Tests for Next.js proxy (auth-based routing and route protection).
 *
 * REQ-024 §5.2: Cookie-presence routing — authenticated users on public
 * routes redirect to /dashboard; unauthenticated users see landing/auth pages.
 * REQ-013 §8.6: Server-side route protection — redirects unauthenticated
 * users to /login before any page renders.
 * REQ-022 §5.4: Admin route guard — redirects non-admin users away from
 * /admin/* routes based on JWT `adm` claim.
 */

import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { config, proxy } from "./proxy";

// ---------------------------------------------------------------------------
// Test constants
// ---------------------------------------------------------------------------

const AUTH_COOKIE_NAME = "zentropy.session-token";
const BASE_URL = "http://localhost:3000";
const DASHBOARD_URL = `${BASE_URL}/dashboard`;
const LOGIN_URL = `${BASE_URL}/login`;
const HOME_URL = `${BASE_URL}/`;
const VALID_TOKEN = "valid-jwt-token";
const TEST_USER_SUB = "user-1";
const ADMIN_CONFIG_PATH = "/admin/config";
const MATCHER_REGEX = config.matcher[2];

/** Build a fake JWT with a given payload. Not cryptographically valid. */
function fakeJwt(payload: Record<string, unknown>): string {
	const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
	const body = btoa(JSON.stringify(payload));
	return `${header}.${body}.fake-signature`;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Create a NextRequest for the given path, optionally with an auth cookie. */
function createRequest(path: string, cookie?: string): NextRequest {
	const req = new NextRequest(new URL(path, BASE_URL));
	if (cookie) {
		// nosemgrep: cookies-default-koa — test-only: sets cookie on mock NextRequest, not a browser response
		req.cookies.set(AUTH_COOKIE_NAME, cookie);
	}
	return req;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("proxy", () => {
	afterEach(() => {
		vi.restoreAllMocks();
	});

	it("redirects to /login when auth cookie is missing", () => {
		const request = createRequest("/dashboard");
		const response = proxy(request);

		expect(response.status).toBe(307);
		expect(response.headers.get("location")).toBe(LOGIN_URL);
	});

	it("passes through when auth cookie is present", () => {
		const request = createRequest("/dashboard", VALID_TOKEN);
		const response = proxy(request);

		// NextResponse.next() returns a response that continues the request
		expect(response.headers.get("location")).toBeNull();
	});

	it("matcher regex excludes /login (handled by explicit entry)", () => {
		const regexPattern = MATCHER_REGEX;
		const loginRegex = new RegExp(regexPattern);
		expect(loginRegex.test("/login")).toBe(false);
	});

	it("matcher regex excludes /register (handled by explicit entry)", () => {
		const regexPattern = MATCHER_REGEX;
		const registerRegex = new RegExp(regexPattern);
		expect(registerRegex.test("/register")).toBe(false);
	});

	it.each([
		"/zentropy_logo.png",
		"/favicon.ico",
		"/robots.txt",
		"/next.svg",
		"/some-image.jpg",
		"/photo.jpeg",
		"/icon.gif",
		"/hero.webp",
		"/sitemap.xml",
	])("does not redirect static file %s (excluded by matcher)", (path) => {
		const regexPattern = MATCHER_REGEX;
		const regex = new RegExp(regexPattern);
		expect(regex.test(path)).toBe(false);
	});

	// -------------------------------------------------------------------
	// Public route handling — REQ-024 §5.2
	// -------------------------------------------------------------------

	it("allows / without cookie (landing page)", () => {
		const request = createRequest("/");
		const response = proxy(request);

		expect(response.headers.get("location")).toBeNull();
	});

	it("redirects / to /dashboard when cookie is present", () => {
		const request = createRequest("/", VALID_TOKEN);
		const response = proxy(request);

		expect(response.status).toBe(307);
		expect(response.headers.get("location")).toBe(DASHBOARD_URL);
	});

	it("allows /login without cookie", () => {
		const request = createRequest("/login");
		const response = proxy(request);

		expect(response.headers.get("location")).toBeNull();
	});

	it("redirects /login to /dashboard when cookie is present", () => {
		const request = createRequest("/login", VALID_TOKEN);
		const response = proxy(request);

		expect(response.status).toBe(307);
		expect(response.headers.get("location")).toBe(DASHBOARD_URL);
	});

	it("allows /register without cookie", () => {
		const request = createRequest("/register");
		const response = proxy(request);

		expect(response.headers.get("location")).toBeNull();
	});

	it("redirects /register to /dashboard when cookie is present", () => {
		const request = createRequest("/register", VALID_TOKEN);
		const response = proxy(request);

		expect(response.status).toBe(307);
		expect(response.headers.get("location")).toBe(DASHBOARD_URL);
	});

	// -------------------------------------------------------------------
	// Protected route handling — REQ-013 §8.6
	// -------------------------------------------------------------------

	it("protects nested paths when cookie is missing", () => {
		const request = createRequest("/settings/account");
		const response = proxy(request);

		expect(response.status).toBe(307);
		expect(response.headers.get("location")).toBe(LOGIN_URL);
	});

	// -------------------------------------------------------------------
	// Admin route guard (REQ-022 §5.4)
	// -------------------------------------------------------------------

	it("passes through /admin/config when JWT has adm claim", () => {
		const token = fakeJwt({ sub: TEST_USER_SUB, adm: true });
		const request = createRequest(ADMIN_CONFIG_PATH, token);
		const response = proxy(request);

		expect(response.headers.get("location")).toBeNull();
	});

	it("redirects /admin/config to / when JWT lacks adm claim", () => {
		const token = fakeJwt({ sub: TEST_USER_SUB });
		const request = createRequest(ADMIN_CONFIG_PATH, token);
		const response = proxy(request);

		expect(response.status).toBe(307);
		expect(response.headers.get("location")).toBe(HOME_URL);
	});

	it("redirects /admin/config to / when adm claim is false", () => {
		const token = fakeJwt({ sub: TEST_USER_SUB, adm: false });
		const request = createRequest(ADMIN_CONFIG_PATH, token);
		const response = proxy(request);

		expect(response.status).toBe(307);
		expect(response.headers.get("location")).toBe(HOME_URL);
	});

	it("redirects /admin to / when JWT payload is malformed", () => {
		const request = createRequest(ADMIN_CONFIG_PATH, "not-a-jwt");
		const response = proxy(request);

		expect(response.status).toBe(307);
		expect(response.headers.get("location")).toBe(HOME_URL);
	});

	it("does not apply admin guard to non-admin paths", () => {
		const token = fakeJwt({ sub: TEST_USER_SUB });
		const request = createRequest("/settings", token);
		const response = proxy(request);

		expect(response.headers.get("location")).toBeNull();
	});
});
