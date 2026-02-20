/**
 * E2E tests for login and register pages.
 *
 * REQ-013 §8.2–§8.3: Email/password login, OAuth redirect,
 * forgot password via magic link, registration with password
 * strength indicator, duplicate email handling.
 *
 * All API calls are mocked via Playwright's page.route() — no real backend.
 */

import { expect, test } from "@playwright/test";

import { setupUnauthMocks } from "../utils/auth-api-mocks";

// ---------------------------------------------------------------------------
// Constants — test IDs and selectors
// ---------------------------------------------------------------------------

const TID_LOGIN_SUBMIT = "login-submit";
const TID_REGISTER_SUBMIT = "register-submit";
const TID_SUBMIT_ERROR = "submit-error";
const TID_MAGIC_LINK_SUBMIT = "magic-link-submit";
const DATA_MET = "data-met";

// ---------------------------------------------------------------------------
// A. Login Page (4 tests)
// ---------------------------------------------------------------------------

test.describe("Login Page", () => {
	test("login with email/password submits and redirects to dashboard", async ({
		page,
	}) => {
		const controller = await setupUnauthMocks(page);

		await page.goto("/login");
		await expect(page.getByTestId(TID_LOGIN_SUBMIT)).toBeVisible();

		await page.getByLabel("Email").fill("test@example.com");
		await page.getByLabel("Password").fill("SecurePass123!");

		const verifyPromise = page.waitForResponse(
			(res) =>
				res.url().includes("/auth/verify-password") &&
				res.request().method() === "POST",
		);

		await page.getByTestId(TID_LOGIN_SUBMIT).click();

		const response = await verifyPromise;
		expect(response.status()).toBe(200);
		const body = response.request().postDataJSON();
		expect(body).toMatchObject({
			email: "test@example.com",
			password: "SecurePass123!",
		});

		await expect(page).toHaveURL("/", { timeout: 10_000 });
		expect(controller.state.authenticated).toBe(true);
	});

	test("shows error on invalid credentials", async ({ page }) => {
		const controller = await setupUnauthMocks(page);
		controller.state.verifyPasswordStatus = 401;

		await page.goto("/login");
		await expect(page.getByTestId(TID_LOGIN_SUBMIT)).toBeVisible();

		await page.getByLabel("Email").fill("wrong@example.com");
		await page.getByLabel("Password").fill("BadPassword");
		await page.getByTestId(TID_LOGIN_SUBMIT).click();

		await expect(page.getByTestId(TID_SUBMIT_ERROR)).toBeVisible();
		await expect(page.getByTestId(TID_SUBMIT_ERROR)).toContainText(
			"Invalid email or password",
		);

		await expect(page).toHaveURL("/login");
	});

	test("forgot password flow sends magic link and shows confirmation", async ({
		page,
	}) => {
		await setupUnauthMocks(page);
		await page.goto("/login");

		await page.getByRole("button", { name: "Forgot password?" }).click();

		await expect(page.getByTestId(TID_MAGIC_LINK_SUBMIT)).toBeVisible();
		await expect(
			page.getByText("Enter your email and we'll send a sign-in link"),
		).toBeVisible();

		await page.getByLabel("Email").fill("test@example.com");

		const mlPromise = page.waitForResponse(
			(res) =>
				res.url().includes("/auth/magic-link") &&
				res.request().method() === "POST",
		);

		await page.getByTestId(TID_MAGIC_LINK_SUBMIT).click();

		const response = await mlPromise;
		expect(response.status()).toBe(200);
		const body = response.request().postDataJSON();
		expect(body).toMatchObject({ email: "test@example.com" });

		await expect(
			page.getByText("Check your email for a sign-in link"),
		).toBeVisible();

		await page.getByRole("button", { name: "Back to sign in" }).click();
		await expect(page.getByTestId(TID_LOGIN_SUBMIT)).toBeVisible();
	});

	test("OAuth buttons link to correct provider URLs", async ({ page }) => {
		await setupUnauthMocks(page);
		await page.goto("/login");

		await expect(page.getByTestId(TID_LOGIN_SUBMIT)).toBeVisible();

		const googleLink = page.getByTestId("oauth-google");
		await expect(googleLink).toBeVisible();
		const googleHref = await googleLink.getAttribute("href");
		expect(googleHref).toContain("/auth/providers/google");

		const linkedinLink = page.getByTestId("oauth-linkedin");
		await expect(linkedinLink).toBeVisible();
		const linkedinHref = await linkedinLink.getAttribute("href");
		expect(linkedinHref).toContain("/auth/providers/linkedin");
	});
});

// ---------------------------------------------------------------------------
// B. Register Page (3 tests)
// ---------------------------------------------------------------------------

test.describe("Register Page", () => {
	test("register with email/password shows email confirmation", async ({
		page,
	}) => {
		await setupUnauthMocks(page);
		await page.goto("/register");

		await expect(page.getByTestId(TID_REGISTER_SUBMIT)).toBeVisible();

		await page.getByLabel("Email").fill("new@example.com");
		await page.getByLabel("Password", { exact: true }).fill("StrongPass1!");
		await page.getByLabel("Confirm Password").fill("StrongPass1!");

		const registerPromise = page.waitForResponse(
			(res) =>
				res.url().includes("/auth/register") &&
				res.request().method() === "POST",
		);

		await page.getByTestId(TID_REGISTER_SUBMIT).click();

		const response = await registerPromise;
		expect(response.status()).toBe(201);
		const body = response.request().postDataJSON();
		expect(body).toMatchObject({
			email: "new@example.com",
			password: "StrongPass1!",
		});

		await expect(
			page.getByText("Check your email to verify your account"),
		).toBeVisible();
	});

	test("password strength requirements update dynamically", async ({
		page,
	}) => {
		await setupUnauthMocks(page);
		await page.goto("/register");

		await expect(page.getByTestId(TID_REGISTER_SUBMIT)).toBeVisible();

		const reqIds = ["req-length", "req-letter", "req-number", "req-special"];

		// All requirements start as unmet
		for (const id of reqIds) {
			await expect(page.getByTestId(id)).toHaveAttribute(DATA_MET, "false");
		}

		// Type a password that meets all requirements
		await page.getByLabel("Password", { exact: true }).fill("MyPass1!");

		// All should now be met
		for (const id of reqIds) {
			await expect(page.getByTestId(id)).toHaveAttribute(DATA_MET, "true");
		}
	});

	test("shows error on duplicate email", async ({ page }) => {
		const controller = await setupUnauthMocks(page);
		controller.state.registerStatus = 409;

		await page.goto("/register");
		await expect(page.getByTestId(TID_REGISTER_SUBMIT)).toBeVisible();

		await page.getByLabel("Email").fill("existing@example.com");
		await page.getByLabel("Password", { exact: true }).fill("StrongPass1!");
		await page.getByLabel("Confirm Password").fill("StrongPass1!");
		await page.getByTestId(TID_REGISTER_SUBMIT).click();

		await expect(page.getByTestId(TID_SUBMIT_ERROR)).toBeVisible();
		await expect(page.getByTestId(TID_SUBMIT_ERROR)).toContainText(
			"Email already registered",
		);
	});
});
