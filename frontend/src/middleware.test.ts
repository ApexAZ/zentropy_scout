/**
 * Tests for Next.js middleware (auth route protection).
 *
 * REQ-013 §8.6: Server-side route protection — redirects unauthenticated
 * users to /login before any page renders.
 */

import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { config, middleware } from "./middleware";

// ---------------------------------------------------------------------------
// Test constants
// ---------------------------------------------------------------------------

const AUTH_COOKIE_NAME = "zentropy.session-token";
const BASE_URL = "http://localhost:3000";
const LOGIN_URL = `${BASE_URL}/login`;

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

describe("middleware", () => {
	afterEach(() => {
		vi.restoreAllMocks();
	});

	it("redirects to /login when auth cookie is missing", () => {
		const request = createRequest("/dashboard");
		const response = middleware(request);

		expect(response.status).toBe(307);
		expect(response.headers.get("location")).toBe(LOGIN_URL);
	});

	it("passes through when auth cookie is present", () => {
		const request = createRequest("/dashboard", "valid-jwt-token");
		const response = middleware(request);

		// NextResponse.next() returns a response that continues the request
		expect(response.headers.get("location")).toBeNull();
	});

	it("does not redirect /login page (excluded by matcher)", () => {
		// The middleware matcher excludes /login, so middleware won't run.
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
		const response = middleware(request);

		expect(response.status).toBe(307);
		expect(response.headers.get("location")).toBe(LOGIN_URL);
	});

	it("protects nested paths when cookie is missing", () => {
		const request = createRequest("/settings/account");
		const response = middleware(request);

		expect(response.status).toBe(307);
		expect(response.headers.get("location")).toBe(LOGIN_URL);
	});
});
