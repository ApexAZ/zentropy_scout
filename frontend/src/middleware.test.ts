/**
 * Tests for Next.js middleware (auth-based routing).
 *
 * REQ-024 §5.2: Cookie-presence routing for landing page, dashboard,
 * login, and register routes.
 */

import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { config, middleware } from "./middleware";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const AUTH_COOKIE_NAME = "zentropy.session-token";
const BASE_URL = "http://localhost:3000";
const DASHBOARD_URL = `${BASE_URL}/dashboard`;
const LOGIN_URL = `${BASE_URL}/login`;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Create a NextRequest for the given path, optionally with an auth cookie. */
function createRequest(path: string, withCookie = false): NextRequest {
	const req = new NextRequest(new URL(path, BASE_URL));
	if (withCookie) {
		// nosemgrep: cookies-default-koa — test-only: sets cookie on mock NextRequest
		req.cookies.set(AUTH_COOKIE_NAME, "test-session-token");
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

	describe("GET / (landing page vs dashboard redirect)", () => {
		it("redirects authenticated user from / to /dashboard", () => {
			const request = createRequest("/", true);
			const response = middleware(request);

			expect(response.status).toBe(307);
			expect(response.headers.get("location")).toBe(DASHBOARD_URL);
		});

		it("allows unauthenticated user to see landing page at /", () => {
			const request = createRequest("/");
			const response = middleware(request);

			expect(response.headers.get("location")).toBeNull();
		});
	});

	describe("GET /dashboard (auth guard)", () => {
		it("redirects unauthenticated user from /dashboard to /login", () => {
			const request = createRequest("/dashboard");
			const response = middleware(request);

			expect(response.status).toBe(307);
			expect(response.headers.get("location")).toBe(LOGIN_URL);
		});

		it("allows authenticated user to access /dashboard", () => {
			const request = createRequest("/dashboard", true);
			const response = middleware(request);

			expect(response.headers.get("location")).toBeNull();
		});
	});

	describe("GET /login (already-authenticated redirect)", () => {
		it("redirects authenticated user from /login to /dashboard", () => {
			const request = createRequest("/login", true);
			const response = middleware(request);

			expect(response.status).toBe(307);
			expect(response.headers.get("location")).toBe(DASHBOARD_URL);
		});

		it("allows unauthenticated user to access /login", () => {
			const request = createRequest("/login");
			const response = middleware(request);

			expect(response.headers.get("location")).toBeNull();
		});
	});

	describe("GET /register (already-authenticated redirect)", () => {
		it("redirects authenticated user from /register to /dashboard", () => {
			const request = createRequest("/register", true);
			const response = middleware(request);

			expect(response.status).toBe(307);
			expect(response.headers.get("location")).toBe(DASHBOARD_URL);
		});

		it("allows unauthenticated user to access /register", () => {
			const request = createRequest("/register");
			const response = middleware(request);

			expect(response.headers.get("location")).toBeNull();
		});
	});

	describe("config.matcher", () => {
		it("includes all routed paths", () => {
			expect(config.matcher).toContain("/");
			expect(config.matcher).toContain("/dashboard");
			expect(config.matcher).toContain("/login");
			expect(config.matcher).toContain("/register");
		});
	});
});
