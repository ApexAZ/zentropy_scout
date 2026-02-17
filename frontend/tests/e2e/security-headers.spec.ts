/**
 * E2E tests for HTTP security response headers.
 *
 * Phase 13 (Security Audit): Validates that Next.js security headers
 * configured in next.config.ts are served on all page responses.
 *
 * CORS validation lives in the backend test suite
 * (backend/tests/unit/test_api_main.py::TestCORSMiddleware) because
 * Playwright mocks API routes via page.route() and cannot observe
 * actual backend CORS headers.
 */
import { expect, test } from "@playwright/test";

test.describe("Security Headers", () => {
	let headers: Record<string, string>;

	test.beforeEach(async ({ page }) => {
		const response = await page.goto("/");
		expect(response).not.toBeNull();
		headers = response!.headers();
	});

	test("includes X-Frame-Options DENY", () => {
		expect(headers["x-frame-options"]).toBe("DENY");
	});

	test("includes X-Content-Type-Options nosniff", () => {
		expect(headers["x-content-type-options"]).toBe("nosniff");
	});

	test("includes Referrer-Policy", () => {
		expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");
	});

	test("includes Permissions-Policy restricting sensitive APIs", () => {
		const policy = headers["permissions-policy"];
		expect(policy).toContain("camera=()");
		expect(policy).toContain("microphone=()");
		expect(policy).toContain("geolocation=()");
	});

	test("disables X-XSS-Protection when CSP is present", () => {
		expect(headers["x-xss-protection"]).toBe("0");
	});

	test("includes Strict-Transport-Security", () => {
		const hsts = headers["strict-transport-security"];
		expect(hsts).toContain("max-age=31536000");
		expect(hsts).toContain("includeSubDomains");
	});

	test("includes Content-Security-Policy with all required directives", () => {
		const csp = headers["content-security-policy"];
		expect(csp).toBeDefined();
		expect(csp).toContain("default-src 'self'");
		expect(csp).toContain("script-src 'self'");
		expect(csp).toContain("style-src 'self'");
		expect(csp).toContain("img-src 'self'");
		expect(csp).toContain("font-src 'self'");
		expect(csp).toContain("frame-ancestors 'none'");
		expect(csp).toContain("base-uri 'self'");
		expect(csp).toContain("form-action 'self'");
		expect(csp).toContain("object-src 'none'");
	});

	test("CSP does not contain wildcard or overly permissive sources", () => {
		const csp = headers["content-security-policy"];
		expect(csp).not.toContain("default-src *");
		expect(csp).not.toContain("script-src *");
		expect(csp).not.toContain("connect-src *");
	});

	test("does not expose X-Powered-By header", () => {
		expect(headers["x-powered-by"]).toBeUndefined();
	});
});
