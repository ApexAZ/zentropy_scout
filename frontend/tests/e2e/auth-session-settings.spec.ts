/**
 * E2E tests for session management and account settings.
 *
 * REQ-013 §8.3a, §8.6, §8.9: Route protection, session persistence,
 * logout, sign out all devices, name edit, password change/set.
 *
 * All API calls are mocked via Playwright's page.route() — no real backend.
 */

import { expect, test } from "@playwright/test";

import { setupAuthenticatedMocks } from "../utils/auth-api-mocks";

// ---------------------------------------------------------------------------
// Constants — test IDs, selectors, paths
// ---------------------------------------------------------------------------

const TID_ACCOUNT = "account-section";
const TID_PASSWORD_SUBMIT = "password-submit";
const SETTINGS_PATH = "/settings";

// ---------------------------------------------------------------------------
// A. Route Protection (2 tests)
// ---------------------------------------------------------------------------

test.describe("Route Protection", () => {
	test("redirects to /login when session cookie is missing", async ({
		page,
	}) => {
		await page.context().clearCookies();

		await page.goto("/");

		await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
	});

	test("401 API response hides authenticated content", async ({ page }) => {
		const controller = await setupAuthenticatedMocks(page);
		await page.goto(SETTINGS_PATH);

		await expect(page.getByTestId(TID_ACCOUNT)).toBeVisible();

		// Simulate session expiry — next /auth/me returns 401
		controller.state.authenticated = false;
		await page.reload();

		// Account section hidden when session is null
		await expect(page.getByTestId(TID_ACCOUNT)).not.toBeVisible({
			timeout: 10_000,
		});
	});
});

// ---------------------------------------------------------------------------
// B. Session & Logout (2 tests)
// ---------------------------------------------------------------------------

test.describe("Session & Logout", () => {
	test("session persists across page reload", async ({ page }) => {
		await setupAuthenticatedMocks(page);

		await page.goto(SETTINGS_PATH);
		await expect(page.getByTestId(TID_ACCOUNT)).toBeVisible();
		await expect(page.getByText("test@example.com")).toBeVisible();

		await page.reload();

		await expect(page.getByTestId(TID_ACCOUNT)).toBeVisible();
		await expect(page.getByText("test@example.com")).toBeVisible();
	});

	test("sign out calls logout API and redirects to /login", async ({
		page,
	}) => {
		await setupAuthenticatedMocks(page);
		await page.goto(SETTINGS_PATH);
		await expect(page.getByTestId(TID_ACCOUNT)).toBeVisible();

		const logoutPromise = page.waitForResponse(
			(res) =>
				res.url().includes("/auth/logout") && res.request().method() === "POST",
		);

		await page.getByRole("button", { name: "Sign out", exact: true }).click();

		const response = await logoutPromise;
		expect(response.status()).toBe(200);

		await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
	});
});

// ---------------------------------------------------------------------------
// C. Account Settings (5 tests)
// ---------------------------------------------------------------------------

test.describe("Account Settings", () => {
	test("name inline edit saves via PATCH /auth/profile", async ({ page }) => {
		await setupAuthenticatedMocks(page);
		await page.goto(SETTINGS_PATH);
		await expect(page.getByTestId(TID_ACCOUNT)).toBeVisible();

		await expect(page.getByText("Test User")).toBeVisible();

		await page.getByRole("button", { name: "Edit name" }).click();

		const nameInput = page.getByLabel("Name");
		await expect(nameInput).toBeVisible();

		await nameInput.clear();
		await nameInput.fill("Jane Doe");

		const patchPromise = page.waitForResponse(
			(res) =>
				res.url().includes("/auth/profile") &&
				res.request().method() === "PATCH",
		);

		await page.getByRole("button", { name: "Save" }).click();

		const response = await patchPromise;
		expect(response.status()).toBe(200);
		const body = response.request().postDataJSON();
		expect(body).toMatchObject({ name: "Jane Doe" });

		await expect(page.getByText("Jane Doe")).toBeVisible();
	});

	test("password change flow with current password", async ({ page }) => {
		await setupAuthenticatedMocks(page);
		await page.goto(SETTINGS_PATH);
		await expect(page.getByTestId(TID_ACCOUNT)).toBeVisible();

		await page.getByRole("button", { name: "Change password" }).click();

		await expect(page.getByLabel("Current password")).toBeVisible();
		await expect(
			page.getByLabel("New password", { exact: true }),
		).toBeVisible();
		await expect(page.getByLabel("Confirm new password")).toBeVisible();

		await page.getByLabel("Current password").fill("OldPass123!");
		await page.getByLabel("New password", { exact: true }).fill("NewPass456!");
		await page.getByLabel("Confirm new password").fill("NewPass456!");

		const changePromise = page.waitForResponse(
			(res) =>
				res.url().includes("/auth/change-password") &&
				res.request().method() === "POST",
		);

		await page.getByTestId(TID_PASSWORD_SUBMIT).click();

		const response = await changePromise;
		expect(response.status()).toBe(200);
		const body = response.request().postDataJSON();
		expect(body).toMatchObject({
			current_password: "OldPass123!",
			new_password: "NewPass456!",
		});

		await expect(page.getByLabel("Current password")).not.toBeVisible();
	});

	test("OAuth-only user sees 'Set a password' without current password field", async ({
		page,
	}) => {
		await setupAuthenticatedMocks(page, { hasPassword: false });
		await page.goto(SETTINGS_PATH);
		await expect(page.getByTestId(TID_ACCOUNT)).toBeVisible();

		await expect(
			page.getByRole("button", { name: "Set a password" }),
		).toBeVisible();

		await page.getByRole("button", { name: "Set a password" }).click();

		await expect(page.getByLabel("Current password")).not.toBeVisible();
		await expect(
			page.getByLabel("New password", { exact: true }),
		).toBeVisible();
		await expect(page.getByLabel("Confirm new password")).toBeVisible();

		await page.getByLabel("New password", { exact: true }).fill("FirstPass1!");
		await page.getByLabel("Confirm new password").fill("FirstPass1!");

		const changePromise = page.waitForResponse(
			(res) =>
				res.url().includes("/auth/change-password") &&
				res.request().method() === "POST",
		);

		await page.getByTestId(TID_PASSWORD_SUBMIT).click();

		const response = await changePromise;
		expect(response.status()).toBe(200);
		const body = response.request().postDataJSON();
		expect(body.current_password).toBeNull();
		expect(body.new_password).toBe("FirstPass1!");
	});

	test("password mismatch shows client-side error", async ({ page }) => {
		await setupAuthenticatedMocks(page);
		await page.goto(SETTINGS_PATH);
		await expect(page.getByTestId(TID_ACCOUNT)).toBeVisible();

		await page.getByRole("button", { name: "Change password" }).click();

		await page.getByLabel("Current password").fill("OldPass123!");
		await page.getByLabel("New password", { exact: true }).fill("NewPass456!");
		await page.getByLabel("Confirm new password").fill("DifferentPass789!");

		await page.getByTestId(TID_PASSWORD_SUBMIT).click();

		await expect(page.getByText("Passwords do not match")).toBeVisible();
	});

	test("sign out all devices shows confirmation and calls API", async ({
		page,
	}) => {
		await setupAuthenticatedMocks(page);
		await page.goto(SETTINGS_PATH);
		await expect(page.getByTestId(TID_ACCOUNT)).toBeVisible();

		await page.getByRole("button", { name: "Sign out of all devices" }).click();

		await expect(
			page.getByText(
				"This will sign you out everywhere, including other browsers and devices",
			),
		).toBeVisible();

		const invalidatePromise = page.waitForResponse(
			(res) =>
				res.url().includes("/auth/invalidate-sessions") &&
				res.request().method() === "POST",
		);

		await page.getByRole("button", { name: "Confirm" }).click();

		const response = await invalidatePromise;
		expect(response.status()).toBe(200);

		await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
	});
});
