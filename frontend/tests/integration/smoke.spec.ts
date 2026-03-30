/**
 * Integration smoke test — verifies the auth API contract against a real backend.
 *
 * Prerequisites:
 *   1. Docker PostgreSQL running: `docker compose up -d`
 *   2. Migrations applied: `cd backend && alembic upgrade head`
 *   3. Backend started FROM PROJECT ROOT (so .env is found):
 *      `source backend/.venv/bin/activate && uvicorn backend.app.main:app --port 8000`
 *      Environment must include: AUTH_ENABLED=true, AUTH_SECRET=<secret>,
 *      RATE_LIMIT_ENABLED=false (register has 3/hour limit)
 *   4. Frontend started: `cd frontend && npm run dev`
 *
 * Run: `cd frontend && npm run test:e2e:integration`
 *   or: `cd frontend && INTEGRATION=true npx playwright test --project=integration`
 *
 * This test imports from @playwright/test directly (NOT base-test.ts) —
 * no mocked routes, no mock storageState. The real backend validates JWTs.
 *
 * Note: Full auth-through-dashboard flow (register → verify email → login →
 * navigate) requires email verification infrastructure (test-only verify
 * endpoint or email interception). For now, the smoke test validates the
 * real API contracts: 401 without auth, successful registration, and the
 * email verification security gate (403 for unverified users).
 */
import { test, expect } from "@playwright/test";

test.describe("Integration: Auth smoke test", () => {
	test("unauthenticated request to /auth/me returns 401", async ({ page }) => {
		const response = await page.request.get("/api/v1/auth/me");
		expect(response.status()).toBe(401);
	});

	test("register creates a new user", async ({ page }) => {
		const timestamp = Date.now();
		const random = Math.random().toString(36).slice(2, 8);
		const testEmail = `integ-${timestamp}-${random}@test.example.com`;

		const response = await page.request.post("/api/v1/auth/register", {
			data: { email: testEmail, password: "TestPassword123!" },
		});
		expect(response.status()).toBe(201);

		const data = await response.json();
		expect(data.data.email).toBe(testEmail);
		expect(data.data.id).toBeTruthy();
	});

	test("login blocked for unverified email (security gate)", async ({
		page,
	}) => {
		const timestamp = Date.now();
		const random = Math.random().toString(36).slice(2, 8);
		const testEmail = `integ-${timestamp}-${random}@test.example.com`;

		// Register a user (email_verified remains null)
		const registerResponse = await page.request.post("/api/v1/auth/register", {
			data: { email: testEmail, password: "TestPassword123!" },
		});
		expect(registerResponse.status()).toBe(201);

		// Attempt login — backend should reject with 403 (EMAIL_NOT_VERIFIED)
		const loginResponse = await page.request.post(
			"/api/v1/auth/verify-password",
			{
				data: { email: testEmail, password: "TestPassword123!" },
			},
		);
		expect(loginResponse.status()).toBe(403);

		const errorData = await loginResponse.json();
		expect(errorData.error.code).toBe("EMAIL_NOT_VERIFIED");
	});

	test("duplicate registration returns 409", async ({ page }) => {
		const timestamp = Date.now();
		const random = Math.random().toString(36).slice(2, 8);
		const testEmail = `integ-${timestamp}-${random}@test.example.com`;

		// First registration succeeds
		const first = await page.request.post("/api/v1/auth/register", {
			data: { email: testEmail, password: "TestPassword123!" },
		});
		expect(first.status()).toBe(201);

		// Duplicate registration returns conflict
		const second = await page.request.post("/api/v1/auth/register", {
			data: { email: testEmail, password: "TestPassword123!" },
		});
		expect(second.status()).toBe(409);

		const errorData = await second.json();
		expect(errorData.error.code).toBe("EMAIL_ALREADY_EXISTS");
	});
});
