/**
 * E2E tests for the Add Job modal two-step ingest flow.
 *
 * REQ-012 §8.7: "Add Job" button in Opportunities toolbar opens a modal.
 * Step 1: Paste raw text + select source → POST /job-postings/ingest.
 * Step 2: Review extracted preview → POST /job-postings/ingest/confirm.
 * All API calls are mocked via Playwright's page.route() — no real backend.
 */

import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import {
	expiredIngestPreviewResponse,
	INGEST_NEW_PERSONA_JOB_ID,
	setupAddJobMocks,
} from "../utils/job-discovery-api-mocks";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Fill the Step 1 ingest form with valid data. */
async function fillIngestForm(page: Page) {
	const modal = page.getByRole("dialog");
	await modal.getByRole("combobox").click();
	await page.getByRole("option", { name: "LinkedIn" }).click();
	await modal
		.getByLabel("Job Posting Text")
		.fill("Senior Software Engineer at WidgetCo. 5+ years TypeScript...");
}

/** Fill form and submit to advance to Step 2 preview. */
async function advanceToPreview(page: Page) {
	await fillIngestForm(page);
	await page.getByRole("button", { name: "Extract & Preview" }).click();
	await expect(
		page.getByRole("heading", { name: "Preview Extracted Data" }),
	).toBeVisible();
}

// ---------------------------------------------------------------------------
// A. Add Job Modal — Form (2 tests)
// ---------------------------------------------------------------------------

test.describe("Add Job Modal — Form", () => {
	test("opens modal with form fields and buttons", async ({ page }) => {
		await setupAddJobMocks(page);
		await page.goto("/");

		// Open modal via toolbar button
		await page.getByTestId("add-job-button").click();

		const modal = page.getByRole("dialog");

		// Modal heading
		await expect(modal.getByRole("heading", { name: "Add Job" })).toBeVisible();

		// Form fields visible
		await expect(modal.getByRole("combobox")).toBeVisible();
		await expect(modal.getByLabel("Source URL")).toBeVisible();
		await expect(modal.getByLabel("Job Posting Text")).toBeVisible();

		// Buttons visible
		await expect(
			modal.getByRole("button", { name: "Extract & Preview" }),
		).toBeVisible();
		await expect(modal.getByRole("button", { name: "Cancel" })).toBeVisible();
	});

	test("validates required fields on empty submit", async ({ page }) => {
		await setupAddJobMocks(page);
		await page.goto("/");
		await page.getByTestId("add-job-button").click();

		// Submit without filling anything
		await page.getByRole("button", { name: "Extract & Preview" }).click();

		// Validation errors should appear
		await expect(page.getByText("Source is required")).toBeVisible();
		await expect(page.getByText("Job posting text is required")).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// B. Add Job Modal — Extract & Preview (2 tests)
// ---------------------------------------------------------------------------

test.describe("Add Job Modal — Extract & Preview", () => {
	test("extract sends POST and shows preview with extracted fields", async ({
		page,
	}) => {
		await setupAddJobMocks(page);
		await page.goto("/");
		await page.getByTestId("add-job-button").click();

		await fillIngestForm(page);

		// Listen for POST
		const postPromise = page.waitForResponse(
			(res) =>
				res.url().includes("/job-postings/ingest") &&
				!res.url().includes("/confirm") &&
				res.request().method() === "POST",
		);

		await page.getByRole("button", { name: "Extract & Preview" }).click();

		const response = await postPromise;
		expect(response.status()).toBe(200);

		// Step 2 heading
		await expect(
			page.getByRole("heading", { name: "Preview Extracted Data" }),
		).toBeVisible();

		// Preview fields populated from mock data
		await expect(page.getByText("Frontend Engineer")).toBeVisible();
		await expect(page.getByText("WidgetCo")).toBeVisible();
		await expect(page.getByText("Austin, TX")).toBeVisible();
		await expect(page.getByText("Full-time")).toBeVisible();

		// Skills badges
		await expect(page.getByText("React")).toBeVisible();
		await expect(page.getByText("TypeScript")).toBeVisible();

		// Step 2 buttons
		await expect(
			page.getByRole("button", { name: "Confirm & Save" }),
		).toBeVisible();
		await expect(page.getByRole("button", { name: "Back" })).toBeVisible();
	});

	test("countdown timer displays remaining time", async ({ page }) => {
		await setupAddJobMocks(page);
		await page.goto("/");
		await page.getByTestId("add-job-button").click();
		await advanceToPreview(page);

		// Countdown timer should show "Expires in" with time
		const timer = page.getByTestId("countdown-timer");
		await expect(timer).toBeVisible();
		await expect(timer).toContainText("Expires in");
	});
});

// ---------------------------------------------------------------------------
// C. Add Job Modal — Confirm & Errors (2 tests)
// ---------------------------------------------------------------------------

test.describe("Add Job Modal — Confirm & Errors", () => {
	test("confirm & save sends POST and navigates to job detail", async ({
		page,
	}) => {
		await setupAddJobMocks(page);
		await page.goto("/");
		await page.getByTestId("add-job-button").click();
		await advanceToPreview(page);

		// Listen for confirm POST
		const confirmPromise = page.waitForResponse(
			(res) =>
				res.url().includes("/job-postings/ingest/confirm") &&
				res.request().method() === "POST",
		);

		await page.getByRole("button", { name: "Confirm & Save" }).click();

		const response = await confirmPromise;
		expect(response.status()).toBe(200);

		// Should navigate to job detail page
		await page.waitForURL(`**/jobs/${INGEST_NEW_PERSONA_JOB_ID}`);
	});

	test("expired preview disables confirm button and shows message", async ({
		page,
	}) => {
		await setupAddJobMocks(page);

		// Override ingest endpoint to return expired preview
		await page.route(/\/job-postings\/ingest$/, async (route) => {
			if (route.request().method() === "POST") {
				await route.fulfill({
					status: 200,
					contentType: "application/json",
					body: JSON.stringify(expiredIngestPreviewResponse()),
				});
			} else {
				await route.fallback();
			}
		});

		await page.goto("/");
		await page.getByTestId("add-job-button").click();
		await advanceToPreview(page);

		// Expired message visible
		await expect(
			page.getByText("Preview expired. Go back and resubmit."),
		).toBeVisible();

		// Confirm button should be disabled
		await expect(
			page.getByRole("button", { name: "Confirm & Save" }),
		).toBeDisabled();
	});
});
