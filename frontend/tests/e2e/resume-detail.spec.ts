/**
 * E2E tests for the resume detail editor page.
 *
 * REQ-012 §9.2: Base resume editor — summary textarea, content selection
 * checkboxes, save via PATCH, render PDF, PDF preview, variants list.
 * All API calls are mocked via Playwright's page.route() — no real backend.
 */

import { expect, test } from "@playwright/test";

import {
	BASE_RESUME_IDS,
	setupResumeListMocks,
} from "../utils/resume-api-mocks";

// ---------------------------------------------------------------------------
// A. Resume Detail — Display (2 tests)
// ---------------------------------------------------------------------------

test.describe("Resume Detail — Display", () => {
	test("displays header, summary, and PDF preview for rendered resume", async ({
		page,
	}) => {
		await setupResumeListMocks(page);
		await page.goto(`/resumes/${BASE_RESUME_IDS[0]}`);

		await expect(page.getByTestId("resume-detail")).toBeVisible();

		// Header shows name, role type, and status badge
		await expect(
			page.getByRole("heading", { name: "Scrum Master" }),
		).toBeVisible();
		await expect(page.getByText("Scrum Master / Agile Coach")).toBeVisible();
		await expect(page.getByLabel("Status: Active")).toBeVisible();

		// Summary textarea pre-filled
		const summary = page.getByLabel("Summary");
		await expect(summary).toHaveValue(
			"Experienced Scrum Master with strong facilitation skills",
		);

		// PDF preview visible (rendered_at is set for Scrum Master)
		await expect(page.getByText("PDF Preview")).toBeVisible();

		// Variants list visible
		await expect(page.getByTestId("variants-list")).toBeVisible();
	});

	test("shows Render PDF button for un-rendered resume", async ({ page }) => {
		await setupResumeListMocks(page);
		await page.goto(`/resumes/${BASE_RESUME_IDS[1]}`);

		await expect(page.getByTestId("resume-detail")).toBeVisible();

		// Product Owner has no rendered_at — Render PDF button visible
		await expect(
			page.getByRole("button", { name: "Render PDF" }),
		).toBeVisible();

		// No PDF preview section
		await expect(page.getByText("PDF Preview")).not.toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// B. Resume Detail — Save & Render (2 tests)
// ---------------------------------------------------------------------------

test.describe("Resume Detail — Save & Render", () => {
	test("Save button sends PATCH with updated summary", async ({ page }) => {
		await setupResumeListMocks(page);
		await page.goto(`/resumes/${BASE_RESUME_IDS[0]}`);

		await expect(page.getByTestId("resume-detail")).toBeVisible();

		// Edit summary
		const summary = page.getByLabel("Summary");
		await summary.clear();
		await summary.fill("Updated Scrum Master summary with new focus areas");

		// Set up PATCH listener
		const patchPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/base-resumes/${BASE_RESUME_IDS[0]}`) &&
				res.request().method() === "PATCH",
		);

		// Click Save
		await page.getByRole("button", { name: "Save" }).click();

		// Verify PATCH sent with updated summary
		const response = await patchPromise;
		expect(response.status()).toBe(200);
		const body = response.request().postDataJSON();
		expect(body.summary).toBe(
			"Updated Scrum Master summary with new focus areas",
		);

		// After save, Re-render PDF button should appear
		// (updated_at > rendered_at due to PATCH mock setting later timestamp)
		await expect(
			page.getByRole("button", { name: "Re-render PDF" }),
		).toBeVisible();
	});

	test("Render PDF button sends POST and updates preview", async ({ page }) => {
		await setupResumeListMocks(page);
		await page.goto(`/resumes/${BASE_RESUME_IDS[1]}`);

		await expect(page.getByTestId("resume-detail")).toBeVisible();

		// Set up POST listener for render
		const renderPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/base-resumes/${BASE_RESUME_IDS[1]}/render`) &&
				res.request().method() === "POST",
		);

		// Click Render PDF
		await page.getByRole("button", { name: "Render PDF" }).click();

		// Verify POST sent
		const response = await renderPromise;
		expect(response.status()).toBe(200);

		// After render, PDF preview should appear (rendered_at now set)
		await expect(page.getByText("PDF Preview")).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// C. Resume Detail — Variants List (1 test)
// ---------------------------------------------------------------------------

test.describe("Resume Detail — Variants List", () => {
	test("shows variant cards with status badges and correct actions", async ({
		page,
	}) => {
		await setupResumeListMocks(page);
		await page.goto(`/resumes/${BASE_RESUME_IDS[0]}`);

		await expect(page.getByTestId("variants-list")).toBeVisible();

		// 2 variant cards (both belong to base resume 1)
		const cards = page.getByTestId("variant-card");
		await expect(cards).toHaveCount(2);

		// Draft variant: "Frontend Engineer at AlphaTech" — Review & Approve + Archive
		const draftCard = cards.nth(0);
		await expect(draftCard).toContainText("Frontend Engineer at AlphaTech");
		await expect(draftCard.getByLabel("Status: Draft")).toBeVisible();
		await expect(
			draftCard.getByRole("button", {
				name: /Review & Approve/i,
			}),
		).toBeVisible();
		await expect(
			draftCard.getByRole("button", { name: /Archive/i }),
		).toBeVisible();

		// Approved variant: "Backend Engineer at BetaWorks" — View only
		const approvedCard = cards.nth(1);
		await expect(approvedCard).toContainText("Backend Engineer at BetaWorks");
		await expect(approvedCard.getByLabel("Status: Approved")).toBeVisible();
		await expect(
			approvedCard.getByRole("button", { name: /View/i }),
		).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// D. Resume Detail — Navigation (1 test)
// ---------------------------------------------------------------------------

test.describe("Resume Detail — Navigation", () => {
	test("back link navigates to resume list", async ({ page }) => {
		await setupResumeListMocks(page);
		await page.goto(`/resumes/${BASE_RESUME_IDS[0]}`);

		await expect(page.getByTestId("resume-detail")).toBeVisible();

		await page.getByRole("link", { name: "Back to Resumes" }).click();
		await expect(page).toHaveURL("/resumes");
	});
});
