/**
 * E2E tests for persona sub-entity CRUD editors.
 *
 * REQ-012 §7.2: Post-onboarding editors for work history, education, and
 * certifications with add/delete support. Each editor uses the
 * delete-with-references flow (reference check → DELETE).
 * All API calls are mocked via Playwright's page.route() — no real backend.
 */

import { expect, test } from "@playwright/test";

import {
	CERT_ID,
	EDUCATION_ID,
	PERSONA_ID,
	setupPersonaEditorCrudMocks,
	WORK_HISTORY_IDS,
} from "../utils/persona-update-api-mocks";

// ---------------------------------------------------------------------------
// A. Work History Editor (3 tests)
// ---------------------------------------------------------------------------

test.describe("Work History Editor", () => {
	test("displays work history entries", async ({ page }) => {
		await setupPersonaEditorCrudMocks(page);
		await page.goto("/persona/work-history");

		// Both entries from mock data should be visible
		await expect(page.getByText("Senior Engineer")).toBeVisible();
		await expect(page.getByText("Acme Corp")).toBeVisible();
		await expect(page.getByText("Software Engineer")).toBeVisible();
		await expect(page.getByText("Beta Inc")).toBeVisible();
	});

	test("add a new job entry via form", async ({ page }) => {
		await setupPersonaEditorCrudMocks(page);
		await page.goto("/persona/work-history");

		await page.getByRole("button", { name: "Add a job" }).click();
		await expect(page.getByTestId("work-history-form")).toBeVisible();

		// Fill required fields
		await page.getByLabel("Job Title").fill("Staff Engineer");
		await page.getByLabel("Company Name").fill("NewCorp");
		await page.getByLabel("Location").fill("Austin, TX");
		await page.getByLabel("Work Model").selectOption("Remote");
		await page.getByLabel("Start Date").fill("2024-01");
		await page.getByLabel("This is my current role").check();

		// Listen for POST
		const postPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/personas/${PERSONA_ID}/work-history`) &&
				!res.url().includes("/references") &&
				res.request().method() === "POST",
		);

		await page.getByRole("button", { name: "Save" }).click();

		const response = await postPromise;
		expect(response.status()).toBe(201);

		// Form should disappear, returning to list view
		await expect(page.getByTestId("work-history-form")).not.toBeVisible();
	});

	test("delete a job entry", async ({ page }) => {
		await setupPersonaEditorCrudMocks(page);
		await page.goto("/persona/work-history");

		// Verify entry exists
		await expect(page.getByText("Senior Engineer")).toBeVisible();

		// Listen for DELETE (fires after automatic reference check)
		const deletePromise = page.waitForResponse(
			(res) =>
				res
					.url()
					.includes(
						`/personas/${PERSONA_ID}/work-history/${WORK_HISTORY_IDS[0]}`,
					) &&
				!res.url().includes("/references") &&
				res.request().method() === "DELETE",
		);

		await page.getByRole("button", { name: "Delete Senior Engineer" }).click();

		const response = await deletePromise;
		expect(response.status()).toBe(204);

		// Card's delete button should be gone (more specific than text which
		// also appears in the toast and the "Deleting..." dialog)
		await expect(
			page.getByRole("button", { name: "Delete Senior Engineer" }),
		).not.toBeAttached();
	});
});

// ---------------------------------------------------------------------------
// B. Education Editor (3 tests)
// ---------------------------------------------------------------------------

test.describe("Education Editor", () => {
	test("displays education entries", async ({ page }) => {
		await setupPersonaEditorCrudMocks(page);
		await page.goto("/persona/education");

		// Mock data: BS in Computer Science at UC Berkeley
		await expect(page.getByText("UC Berkeley")).toBeVisible();
		await expect(page.getByText("BS")).toBeVisible();
		await expect(page.getByText("Computer Science")).toBeVisible();
	});

	test("add a new education entry via form", async ({ page }) => {
		await setupPersonaEditorCrudMocks(page);
		await page.goto("/persona/education");

		await page.getByRole("button", { name: "Add education" }).click();
		await expect(page.getByTestId("education-form")).toBeVisible();

		// Fill required fields
		await page.getByLabel("Institution").fill("MIT");
		await page.getByLabel("Degree").fill("MS");
		await page.getByLabel("Field of Study").fill("Artificial Intelligence");
		await page.getByLabel("Graduation Year").fill("2020");

		// Listen for POST
		const postPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/personas/${PERSONA_ID}/education`) &&
				!res.url().includes("/references") &&
				res.request().method() === "POST",
		);

		await page.getByRole("button", { name: "Save" }).click();

		const response = await postPromise;
		expect(response.status()).toBe(201);

		// Form should disappear
		await expect(page.getByTestId("education-form")).not.toBeVisible();
	});

	test("delete an education entry", async ({ page }) => {
		await setupPersonaEditorCrudMocks(page);
		await page.goto("/persona/education");

		// Verify entry exists
		await expect(page.getByText("UC Berkeley")).toBeVisible();

		// Listen for DELETE
		const deletePromise = page.waitForResponse(
			(res) =>
				res
					.url()
					.includes(`/personas/${PERSONA_ID}/education/${EDUCATION_ID}`) &&
				!res.url().includes("/references") &&
				res.request().method() === "DELETE",
		);

		// aria-label is "Delete ${entry.degree}"
		await page.getByRole("button", { name: "Delete BS" }).click();

		const response = await deletePromise;
		expect(response.status()).toBe(204);

		// Card's delete button should be gone
		await expect(
			page.getByRole("button", { name: "Delete BS" }),
		).not.toBeAttached();
	});
});

// ---------------------------------------------------------------------------
// C. Certification Editor (3 tests)
// ---------------------------------------------------------------------------

test.describe("Certification Editor", () => {
	test("displays certification entries", async ({ page }) => {
		await setupPersonaEditorCrudMocks(page);
		await page.goto("/persona/certifications");

		// Mock data: AWS Solutions Architect from Amazon Web Services
		await expect(page.getByText("AWS Solutions Architect")).toBeVisible();
		await expect(page.getByText("Amazon Web Services")).toBeVisible();
	});

	test("add a new certification entry via form", async ({ page }) => {
		await setupPersonaEditorCrudMocks(page);
		await page.goto("/persona/certifications");

		await page.getByRole("button", { name: "Add certification" }).click();
		await expect(page.getByTestId("certification-form")).toBeVisible();

		// Fill required fields
		await page.getByLabel("Certification Name").fill("CKA");
		await page
			.getByLabel("Issuing Organization")
			.fill("Cloud Native Computing Foundation");
		await page.getByLabel("Date Obtained").fill("2024-06-15");

		// Listen for POST
		const postPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/personas/${PERSONA_ID}/certifications`) &&
				!res.url().includes("/references") &&
				res.request().method() === "POST",
		);

		await page.getByRole("button", { name: "Save" }).click();

		const response = await postPromise;
		expect(response.status()).toBe(201);

		// Form should disappear
		await expect(page.getByTestId("certification-form")).not.toBeVisible();
	});

	test("delete a certification entry", async ({ page }) => {
		await setupPersonaEditorCrudMocks(page);
		await page.goto("/persona/certifications");

		// Verify entry exists
		await expect(page.getByText("AWS Solutions Architect")).toBeVisible();

		// Listen for DELETE
		const deletePromise = page.waitForResponse(
			(res) =>
				res
					.url()
					.includes(`/personas/${PERSONA_ID}/certifications/${CERT_ID}`) &&
				!res.url().includes("/references") &&
				res.request().method() === "DELETE",
		);

		// aria-label is "Delete ${entry.certification_name}"
		await page
			.getByRole("button", { name: "Delete AWS Solutions Architect" })
			.click();

		const response = await deletePromise;
		expect(response.status()).toBe(204);

		// Card's delete button should be gone
		await expect(
			page.getByRole("button", { name: "Delete AWS Solutions Architect" }),
		).not.toBeAttached();
	});
});
