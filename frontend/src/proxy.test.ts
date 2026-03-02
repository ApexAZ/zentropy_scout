/**
 * Tests for Next.js proxy (auth route protection).
 *
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
const LOGIN_URL = `${BASE_URL}/login`;
const HOME_URL = `${BASE_URL}/`;

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
		const request = createRequest("/dashboard", "valid-jwt-token");
		const response = proxy(request);

		// NextResponse.next() returns a response that continues the request
		expect(response.headers.get("location")).toBeNull();
	});

	it("does not redirect /login page (excluded by matcher)", () => {
		// The proxy matcher excludes /login, so proxy won't run.
		// We verify the config matcher pattern excludes /login.
		const matcherPattern = config.matcher[0];
		const loginRegex = new RegExp(matcherPattern);
		expect(loginRegex.test("/login")).toBe(false);
	});

	it("does not redirect /register page (excluded by matcher)", () => {
		const matcherPattern = config.matcher[0];
		const registerRegex = new RegExp(matcherPattern);
		expect(registerRegex.test("/register")).toBe(false);
	});

	it("protects the root path when cookie is missing", () => {
		const request = createRequest("/");
		const response = proxy(request);

		expect(response.status).toBe(307);
		expect(response.headers.get("location")).toBe(LOGIN_URL);
	});

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
		const token = fakeJwt({ sub: "user-1", adm: true });
		const request = createRequest("/admin/config", token);
		const response = proxy(request);

		expect(response.headers.get("location")).toBeNull();
	});

	it("redirects /admin/config to / when JWT lacks adm claim", () => {
		const token = fakeJwt({ sub: "user-1" });
		const request = createRequest("/admin/config", token);
		const response = proxy(request);

		expect(response.status).toBe(307);
		expect(response.headers.get("location")).toBe(HOME_URL);
	});

	it("redirects /admin/config to / when adm claim is false", () => {
		const token = fakeJwt({ sub: "user-1", adm: false });
		const request = createRequest("/admin/config", token);
		const response = proxy(request);

		expect(response.status).toBe(307);
		expect(response.headers.get("location")).toBe(HOME_URL);
	});

	it("redirects /admin to / when JWT payload is malformed", () => {
		const request = createRequest("/admin/config", "not-a-jwt");
		const response = proxy(request);

		expect(response.status).toBe(307);
		expect(response.headers.get("location")).toBe(HOME_URL);
	});

	it("does not apply admin guard to non-admin paths", () => {
		const token = fakeJwt({ sub: "user-1" });
		const request = createRequest("/settings", token);
		const response = proxy(request);

		expect(response.headers.get("location")).toBeNull();
	});
});
