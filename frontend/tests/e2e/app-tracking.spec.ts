/**
 * E2E tests for the application tracking flow.
 *
 * REQ-012 §11: Dashboard In Progress / History tabs, application detail,
 * status transitions, offer/rejection capture, timeline, notes, pin, archive.
 * All API calls are mocked via Playwright's page.route() — no real backend.
 */

import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import {
	APP_IDS,
	setupAppDetailMocks,
	setupInProgressTabMocks,
	setupOfferAppMocks,
	setupRejectedAppMocks,
	setupTimelineAppMocks,
} from "../utils/app-tracking-api-mocks";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Remove React Query DevTools overlay (fixed-positioned, blocks clicks on lower elements). */
async function removeDevToolsOverlay(page: Page): Promise<void> {
	await page.evaluate(() => {
		document.querySelector(".tsqd-parent-container")?.remove();
	});
}

// ---------------------------------------------------------------------------
// Shared constants
// ---------------------------------------------------------------------------

const APP_001_ID = APP_IDS[0]; // Applied
const APP_002_ID = APP_IDS[1]; // Interviewing, pinned, has notes
const APP_003_ID = APP_IDS[2]; // Offer
const APP_005_ID = APP_IDS[4]; // Rejected

// ---------------------------------------------------------------------------
// A. In Progress Tab (3 tests)
// ---------------------------------------------------------------------------

test.describe("In Progress Tab", () => {
	test("displays active applications", async ({ page }) => {
		await setupInProgressTabMocks(page);
		await page.goto("/?tab=in-progress");

		await expect(page.getByTestId("applications-table")).toBeVisible();

		// Applied, Interviewing, Offer apps should be visible
		await expect(page.getByText("Frontend Engineer")).toBeVisible();
		await expect(page.getByText("AlphaTech")).toBeVisible();
		await expect(page.getByText("Full Stack Developer")).toBeVisible();
		await expect(page.getByText("BetaWorks")).toBeVisible();
		await expect(page.getByText("Senior Platform Engineer")).toBeVisible();
		await expect(page.getByText("GammaCorp")).toBeVisible();

		// Terminal status apps should NOT be visible
		await expect(page.getByText("DeltaSoft")).not.toBeVisible();
		await expect(page.getByText("EpsilonIO")).not.toBeVisible();
		await expect(page.getByText("ZetaCloud")).not.toBeVisible();
	});

	test("status filter narrows results", async ({ page }) => {
		await setupInProgressTabMocks(page);
		await page.goto("/?tab=in-progress");

		await expect(page.getByTestId("applications-table")).toBeVisible();

		// Select "Interviewing" from status filter
		await page.getByLabel("Status filter").click();
		await page.getByRole("option", { name: "Interviewing" }).click();

		// Only the Interviewing app should be visible
		await expect(page.getByText("Full Stack Developer")).toBeVisible();
		await expect(page.getByText("Frontend Engineer")).not.toBeVisible();
		await expect(page.getByText("Senior Platform Engineer")).not.toBeVisible();
	});

	test("clicking row navigates to detail", async ({ page }) => {
		await setupInProgressTabMocks(page);
		await page.goto("/?tab=in-progress");

		await expect(page.getByTestId("applications-table")).toBeVisible();

		// Click the row containing the Interviewing app's job title
		await page.getByText("Full Stack Developer").click();
		await expect(page).toHaveURL(`/applications/${APP_002_ID}`);
		await expect(page.getByTestId("application-detail")).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// B. History Tab (2 tests)
// ---------------------------------------------------------------------------

test.describe("History Tab", () => {
	test("displays terminal applications", async ({ page }) => {
		await setupInProgressTabMocks(page);
		await page.goto("/?tab=history");

		await expect(page.getByTestId("applications-table")).toBeVisible();

		// Terminal status apps should be visible (except archived by default)
		await expect(page.getByText("Staff Engineer")).toBeVisible();
		await expect(page.getByText("DeltaSoft")).toBeVisible();
		await expect(page.getByText("Backend Engineer")).toBeVisible();
		await expect(page.getByText("EpsilonIO")).toBeVisible();

		// Archived app (track-app-006) should NOT be visible by default
		await expect(page.getByText("DevOps Engineer")).not.toBeVisible();
	});

	test("show archived toggle reveals archived application", async ({
		page,
	}) => {
		await setupInProgressTabMocks(page);
		await page.goto("/?tab=history");

		await expect(page.getByTestId("applications-table")).toBeVisible();

		// Archived app not visible yet
		await expect(page.getByText("DevOps Engineer")).not.toBeVisible();

		// Check "Show archived" checkbox
		await page.getByLabel("Show archived").check();

		// Now the archived app should be visible
		await expect(page.getByText("DevOps Engineer")).toBeVisible();
		await expect(page.getByText("ZetaCloud")).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// C. Application Detail — Metadata & Documents (2 tests)
// ---------------------------------------------------------------------------

test.describe("Application Detail — Metadata & Documents", () => {
	test("displays header with status and interview stage", async ({ page }) => {
		await setupAppDetailMocks(page);
		await page.goto(`/applications/${APP_002_ID}`);

		await expect(page.getByTestId("application-detail")).toBeVisible();

		// Job title and company
		await expect(
			page.getByRole("heading", { name: "Full Stack Developer" }),
		).toBeVisible();
		await expect(page.getByText("BetaWorks")).toBeVisible();

		// Status badge: Interviewing (use aria-label to avoid matching timeline text)
		await expect(page.getByLabel("Status: Interviewing")).toBeVisible();

		// Interview stage badge: Phone Screen (scope to header to avoid timeline matches)
		await expect(
			page.getByTestId("application-header").getByText("Phone Screen"),
		).toBeVisible();

		// Status transition trigger should be visible
		await expect(page.getByTestId("status-transition-trigger")).toBeVisible();
	});

	test("documents panel and expandable job snapshot", async ({ page }) => {
		await setupAppDetailMocks(page);
		await page.goto(`/applications/${APP_002_ID}`);

		await expect(page.getByTestId("documents-panel")).toBeVisible();
		await expect(page.getByTestId("job-snapshot-section")).toBeVisible();

		// Click to expand snapshot
		await page.getByTestId("snapshot-toggle").click();

		// Verify expanded details
		await expect(page.getByTestId("snapshot-details")).toBeVisible();
		await expect(page.getByTestId("snapshot-description")).toBeVisible();
		await expect(page.getByTestId("snapshot-requirements")).toBeVisible();
		await expect(page.getByTestId("snapshot-salary")).toBeVisible();
		await expect(page.getByTestId("snapshot-location")).toBeVisible();
		await expect(page.getByTestId("snapshot-work-model")).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// D. Status Transitions (4 tests)
// ---------------------------------------------------------------------------

test.describe("Status Transitions", () => {
	test("Applied → Interviewing with interview stage selection", async ({
		page,
	}) => {
		await setupAppDetailMocks(page);
		await page.goto(`/applications/${APP_001_ID}`);

		await expect(page.getByTestId("application-detail")).toBeVisible();

		// Open status transition dropdown and select Interviewing
		const patchPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/applications/${APP_001_ID}`) &&
				res.request().method() === "PATCH",
		);

		await page.getByTestId("status-transition-trigger").click();
		await page.getByRole("option", { name: "Interviewing" }).click();

		// Interview stage dialog should appear
		await expect(page.getByText("Select Interview Stage")).toBeVisible();

		// Select Phone Screen radio
		await page.locator("#stage-Phone\\ Screen").click();

		// Confirm
		await page.getByRole("button", { name: "Confirm" }).click();

		// Verify PATCH was sent
		const response = await patchPromise;
		expect(response.status()).toBe(200);
		const body = response.request().postDataJSON();
		expect(body).toMatchObject({
			status: "Interviewing",
			current_interview_stage: "Phone Screen",
		});
	});

	test("Interviewing → Offer with offer details", async ({ page }) => {
		await setupAppDetailMocks(page);
		await page.goto(`/applications/${APP_002_ID}`);

		await expect(page.getByTestId("application-detail")).toBeVisible();

		const patchPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/applications/${APP_002_ID}`) &&
				res.request().method() === "PATCH",
		);

		await page.getByTestId("status-transition-trigger").click();
		await page.getByRole("option", { name: "Offer" }).click();

		// Offer details dialog should appear (use heading role for specificity)
		await expect(
			page.getByRole("heading", { name: "Offer Details" }),
		).toBeVisible();

		// Fill base salary
		await page.locator("#offer-base-salary").fill("185000");

		// Click save
		await page.getByRole("button", { name: "Save" }).click();

		// Verify PATCH
		const response = await patchPromise;
		expect(response.status()).toBe(200);
		const body = response.request().postDataJSON();
		expect(body.status).toBe("Offer");
		expect(body.offer_details).toBeDefined();
		expect(body.offer_details.base_salary).toBe(185000);
	});

	test("Offer → Accepted with confirmation", async ({ page }) => {
		await setupOfferAppMocks(page);
		await page.goto(`/applications/${APP_003_ID}`);

		await expect(page.getByTestId("application-detail")).toBeVisible();

		const patchPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/applications/${APP_003_ID}`) &&
				res.request().method() === "PATCH",
		);

		await page.getByTestId("status-transition-trigger").click();
		await page.getByRole("option", { name: "Accepted" }).click();

		// Confirmation dialog should appear
		await expect(page.getByText("Mark as Accepted")).toBeVisible();

		// Confirm
		await page.getByRole("button", { name: "Confirm" }).click();

		// Verify PATCH
		const response = await patchPromise;
		expect(response.status()).toBe(200);
		const body = response.request().postDataJSON();
		expect(body).toMatchObject({ status: "Accepted" });
	});

	test("Applied → Rejected with rejection details", async ({ page }) => {
		await setupAppDetailMocks(page);
		await page.goto(`/applications/${APP_001_ID}`);

		await expect(page.getByTestId("application-detail")).toBeVisible();

		const patchPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/applications/${APP_001_ID}`) &&
				res.request().method() === "PATCH",
		);

		await page.getByTestId("status-transition-trigger").click();
		await page.getByRole("option", { name: "Rejected" }).click();

		// Rejection details dialog should appear (use heading role for specificity)
		await expect(
			page.getByRole("heading", { name: "Rejection Details" }),
		).toBeVisible();

		// Fill reason
		await page.locator("#rejection-reason").fill("Position filled");

		// Click save
		await page.getByRole("button", { name: "Save" }).click();

		// Verify PATCH
		const response = await patchPromise;
		expect(response.status()).toBe(200);
		const body = response.request().postDataJSON();
		expect(body.status).toBe("Rejected");
		expect(body.rejection_details).toBeDefined();
		expect(body.rejection_details.reason).toBe("Position filled");
	});
});

// ---------------------------------------------------------------------------
// E. Offer & Rejection Details (2 tests)
// ---------------------------------------------------------------------------

test.describe("Offer & Rejection Details", () => {
	test("offer card displays all fields", async ({ page }) => {
		await setupOfferAppMocks(page);
		await page.goto(`/applications/${APP_003_ID}`);

		await expect(page.getByTestId("application-detail")).toBeVisible();

		// Offer card and all rows
		await expect(page.getByTestId("offer-details-card")).toBeVisible();
		await expect(page.getByTestId("offer-salary-row")).toBeVisible();
		await expect(page.getByTestId("offer-bonus-row")).toBeVisible();
		await expect(page.getByTestId("offer-equity-row")).toBeVisible();
		await expect(page.getByTestId("offer-start-date-row")).toBeVisible();
		await expect(page.getByTestId("offer-deadline-row")).toBeVisible();
		await expect(page.getByTestId("offer-benefits-row")).toBeVisible();
		await expect(page.getByTestId("offer-notes-row")).toBeVisible();
	});

	test("rejection card displays all fields", async ({ page }) => {
		await setupRejectedAppMocks(page);
		await page.goto(`/applications/${APP_005_ID}`);

		await expect(page.getByTestId("application-detail")).toBeVisible();

		// Rejection card and all rows
		await expect(page.getByTestId("rejection-details-card")).toBeVisible();
		await expect(page.getByTestId("rejection-stage-row")).toBeVisible();
		await expect(page.getByTestId("rejection-reason-row")).toBeVisible();
		await expect(page.getByTestId("rejection-feedback-row")).toBeVisible();
		await expect(page.getByTestId("rejection-date-row")).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// F. Timeline (3 tests)
// ---------------------------------------------------------------------------

test.describe("Timeline", () => {
	test("displays events with icons and descriptions", async ({ page }) => {
		await setupTimelineAppMocks(page);
		await page.goto(`/applications/${APP_002_ID}`);

		await expect(page.getByTestId("application-detail")).toBeVisible();
		await expect(page.getByTestId("application-timeline")).toBeVisible();

		// 4 timeline event items
		const items = page.getByTestId("timeline-event-item");
		await expect(items).toHaveCount(4);

		// Check type-specific icons
		await expect(page.getByTestId("timeline-icon-applied")).toBeVisible();
		await expect(
			page.getByTestId("timeline-icon-interview_scheduled"),
		).toBeVisible();

		// Interview stage badge on the scheduled event
		await expect(page.getByTestId("timeline-event-stage")).toBeVisible();
		await expect(page.getByTestId("timeline-event-stage")).toContainText(
			"Phone Screen",
		);

		// Description on the follow-up event
		const descriptions = page.getByTestId("timeline-event-description");
		await expect(
			descriptions.filter({ hasText: "Thank you email sent" }),
		).toBeVisible();
	});

	test("add manual event sends POST", async ({ page }) => {
		await setupTimelineAppMocks(page);
		await page.goto(`/applications/${APP_002_ID}`);

		await expect(page.getByTestId("application-timeline")).toBeVisible();

		// Initially 4 events
		await expect(page.getByTestId("timeline-event-item")).toHaveCount(4);

		// Click Add Event button
		await page.getByRole("button", { name: "Add Event" }).click();

		// Dialog should appear
		await expect(page.getByText("Add Timeline Event")).toBeVisible();

		// Select event type: Follow-up Sent
		await page.getByTestId("event-type-select").click();
		await page.getByRole("option", { name: "Follow-up Sent" }).click();

		// Fill event date
		await page.locator("#event-date").fill("2026-02-12T10:00");

		// Fill description
		await page.locator("#event-description").fill("Sent thank-you note");

		// Set up POST response listener
		const postPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/applications/${APP_002_ID}/timeline`) &&
				res.request().method() === "POST",
		);

		// Click Save
		await page.getByRole("button", { name: "Save" }).click();

		// Verify POST sent
		const response = await postPromise;
		expect(response.status()).toBe(201);

		// After refetch, should now have 5 events
		await expect(page.getByTestId("timeline-event-item")).toHaveCount(5);
	});

	test("empty timeline shows empty state", async ({ page }) => {
		// track-app-001 has no timeline events in the mock controller
		// (timeline events Map only has entries for APP_IDS[1])
		await setupAppDetailMocks(page);
		await page.goto(`/applications/${APP_001_ID}`);

		await expect(page.getByTestId("application-detail")).toBeVisible();
		await expect(page.getByTestId("timeline-empty")).toBeVisible();
		await expect(page.getByTestId("timeline-empty")).toContainText(
			"No events yet.",
		);
	});
});

// ---------------------------------------------------------------------------
// G. Notes (2 tests)
// ---------------------------------------------------------------------------

test.describe("Notes", () => {
	test("edit and save notes sends PATCH", async ({ page }) => {
		await setupAppDetailMocks(page);
		await page.goto(`/applications/${APP_001_ID}`);

		await expect(page.getByTestId("application-detail")).toBeVisible();

		// App-001 has no notes — should show placeholder
		await expect(page.getByText("No notes yet.")).toBeVisible();

		await removeDevToolsOverlay(page);

		// Click edit
		await page.getByTestId("notes-edit-button").click();

		// Textarea and char count should appear
		await expect(page.getByTestId("notes-textarea")).toBeVisible();
		await expect(page.getByTestId("notes-char-count")).toBeVisible();

		// Type notes
		await page.getByTestId("notes-textarea").fill("Follow up next week");

		// Set up PATCH listener
		const patchPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/applications/${APP_001_ID}`) &&
				res.request().method() === "PATCH",
		);

		// Click save
		await page.getByTestId("notes-save-button").click();

		// Verify PATCH sent
		const response = await patchPromise;
		expect(response.status()).toBe(200);
		const body = response.request().postDataJSON();
		expect(body).toMatchObject({ notes: "Follow up next week" });
	});

	test("cancel editing discards changes", async ({ page }) => {
		await setupAppDetailMocks(page);
		await page.goto(`/applications/${APP_002_ID}`);

		await expect(page.getByTestId("application-detail")).toBeVisible();

		// App-002 has notes: "Went well"
		await expect(page.getByText("Went well")).toBeVisible();

		await removeDevToolsOverlay(page);

		// Click edit
		await page.getByTestId("notes-edit-button").click();
		await expect(page.getByTestId("notes-textarea")).toBeVisible();

		// Type something else
		await page.getByTestId("notes-textarea").fill("Changed");

		// Click cancel
		await page.getByTestId("notes-cancel-button").click();

		// Original notes should still show, textarea should be gone
		await expect(page.getByText("Went well")).toBeVisible();
		await expect(page.getByTestId("notes-textarea")).not.toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// H. Pin & Archive (2 tests)
// ---------------------------------------------------------------------------

test.describe("Pin & Archive", () => {
	test("pin toggle sends PATCH", async ({ page }) => {
		await setupAppDetailMocks(page);
		await page.goto(`/applications/${APP_001_ID}`);

		await expect(page.getByTestId("application-detail")).toBeVisible();

		// App-001 is not pinned
		const patchPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/applications/${APP_001_ID}`) &&
				res.request().method() === "PATCH",
		);

		await page.getByTestId("pin-toggle").click();

		const response = await patchPromise;
		expect(response.status()).toBe(200);
		const body = response.request().postDataJSON();
		expect(body).toMatchObject({ is_pinned: true });
	});

	test("archive sends DELETE and redirects", async ({ page }) => {
		await setupAppDetailMocks(page);
		await page.goto(`/applications/${APP_001_ID}`);

		await expect(page.getByTestId("application-detail")).toBeVisible();

		const deletePromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/applications/${APP_001_ID}`) &&
				res.request().method() === "DELETE",
		);

		await page.getByTestId("archive-button").click();

		const response = await deletePromise;
		expect(response.status()).toBe(204);

		// Should redirect to applications list
		await expect(page).toHaveURL("/applications");
	});
});

// ---------------------------------------------------------------------------
// I. Navigation (1 test)
// ---------------------------------------------------------------------------

test.describe("Navigation", () => {
	test("back link navigates from detail to applications list", async ({
		page,
	}) => {
		await setupAppDetailMocks(page);
		await page.goto(`/applications/${APP_002_ID}`);

		await expect(page.getByTestId("application-detail")).toBeVisible();
		await expect(page.getByTestId("back-to-applications")).toBeVisible();

		await page.getByTestId("back-to-applications").click();
		await expect(page).toHaveURL("/applications");
	});
});
