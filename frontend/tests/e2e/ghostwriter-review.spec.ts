/**
 * E2E tests for the unified ghostwriter review page.
 *
 * REQ-012 §10.7: Combined review of resume variant + cover letter
 * with tabbed navigation and unified approve actions.
 * All API calls are mocked via Playwright's page.route() — no real backend.
 */

import { expect, test } from "@playwright/test";

import {
	COVER_LETTER_ID,
	JOB_POSTING_ID,
	setupGhostwriterReviewMocks,
	setupGuardrailErrorMocks,
	setupNoMaterialsMocks,
	VARIANT_ID,
} from "../utils/ghostwriter-api-mocks";

// ---------------------------------------------------------------------------
// Button name constants (used across multiple tests)
// ---------------------------------------------------------------------------

const APPROVE_BOTH = "Approve Both";
const APPROVE_RESUME_ONLY = "Approve Resume Only";
const APPROVE_LETTER_ONLY = "Approve Letter Only";

// ---------------------------------------------------------------------------
// A. Full render — header, tabs, variant content, approve buttons (1 test)
// ---------------------------------------------------------------------------

test.describe("Ghostwriter Review — Full Render", () => {
	test("shows header, tabs, variant content, and approve buttons", async ({
		page,
	}) => {
		await setupGhostwriterReviewMocks(page);
		await page.goto(`/jobs/${JOB_POSTING_ID}/review`);

		await expect(page.getByTestId("ghostwriter-review")).toBeVisible();

		// Header with job title and company
		await expect(
			page.getByText("Materials for: Frontend Engineer at AlphaTech"),
		).toBeVisible();

		// Tab triggers
		await expect(
			page.getByRole("tab", { name: "Resume Variant" }),
		).toBeVisible();
		await expect(page.getByRole("tab", { name: "Cover Letter" })).toBeVisible();

		// Default tab: variant review with side-by-side panels
		await expect(page.getByTestId("variant-review")).toBeVisible();
		await expect(page.getByTestId("base-panel")).toBeVisible();
		await expect(page.getByTestId("variant-panel")).toBeVisible();

		// Unified approve actions
		await expect(
			page.getByRole("button", { name: APPROVE_BOTH }),
		).toBeVisible();
		await expect(
			page.getByRole("button", { name: APPROVE_RESUME_ONLY }),
		).toBeVisible();
		await expect(
			page.getByRole("button", { name: APPROVE_LETTER_ONLY }),
		).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// B. Tab switching — cover letter content visible after click (1 test)
// ---------------------------------------------------------------------------

test.describe("Ghostwriter Review — Tab Switching", () => {
	test("clicking Cover Letter tab shows cover letter review", async ({
		page,
	}) => {
		await setupGhostwriterReviewMocks(page);
		await page.goto(`/jobs/${JOB_POSTING_ID}/review`);

		await expect(page.getByTestId("ghostwriter-review")).toBeVisible();

		// Click Cover Letter tab
		await page.getByRole("tab", { name: "Cover Letter" }).click();

		// Cover letter review should be visible
		await expect(page.getByTestId("cover-letter-review")).toBeVisible();

		// Variant review should be hidden (inactive tab)
		await expect(page.getByTestId("variant-review")).not.toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// C. Approve Both — sends POST + PATCH, buttons hidden (1 test)
// ---------------------------------------------------------------------------

test.describe("Ghostwriter Review — Approve Both", () => {
	test("approve both sends POST variant + PATCH cover letter and hides buttons", async ({
		page,
	}) => {
		await setupGhostwriterReviewMocks(page);
		await page.goto(`/jobs/${JOB_POSTING_ID}/review`);

		await expect(page.getByTestId("ghostwriter-review")).toBeVisible();

		// Set up listeners for both approval requests
		const approveVariantPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/job-variants/${VARIANT_ID}/approve`) &&
				res.request().method() === "POST",
		);
		const approveCoverLetterPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/cover-letters/${COVER_LETTER_ID}`) &&
				res.request().method() === "PATCH",
		);

		// Click Approve Both
		await page.getByRole("button", { name: APPROVE_BOTH }).click();

		// Verify both requests sent
		const variantResponse = await approveVariantPromise;
		const coverLetterResponse = await approveCoverLetterPromise;
		expect(variantResponse.status()).toBe(200);
		expect(coverLetterResponse.status()).toBe(200);

		const patchBody = coverLetterResponse.request().postDataJSON();
		expect(patchBody).toMatchObject({ status: "Approved" });

		// After both approved, all approve buttons should be hidden
		await expect(
			page.getByRole("button", { name: APPROVE_BOTH }),
		).not.toBeVisible();
		await expect(
			page.getByRole("button", { name: APPROVE_RESUME_ONLY }),
		).not.toBeVisible();
		await expect(
			page.getByRole("button", { name: APPROVE_LETTER_ONLY }),
		).not.toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// D. Approve Resume Only — partial approval (1 test)
// ---------------------------------------------------------------------------

test.describe("Ghostwriter Review — Approve Resume Only", () => {
	test("approving resume only keeps cover letter approve button visible", async ({
		page,
	}) => {
		await setupGhostwriterReviewMocks(page);
		await page.goto(`/jobs/${JOB_POSTING_ID}/review`);

		await expect(page.getByTestId("ghostwriter-review")).toBeVisible();

		const approveVariantPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/job-variants/${VARIANT_ID}/approve`) &&
				res.request().method() === "POST",
		);

		await page.getByRole("button", { name: "Approve Resume Only" }).click();

		const response = await approveVariantPromise;
		expect(response.status()).toBe(200);

		// "Approve Both" gone (variant no longer Draft)
		await expect(
			page.getByRole("button", { name: APPROVE_BOTH }),
		).not.toBeVisible();
		// "Approve Resume Only" gone
		await expect(
			page.getByRole("button", { name: APPROVE_RESUME_ONLY }),
		).not.toBeVisible();
		// "Approve Letter Only" still visible (cover letter still Draft)
		await expect(
			page.getByRole("button", { name: APPROVE_LETTER_ONLY }),
		).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// E. Error blocking — guardrail errors disable approve (1 test)
// ---------------------------------------------------------------------------

test.describe("Ghostwriter Review — Error Blocking", () => {
	test("guardrail errors disable Approve Both and Approve Resume Only", async ({
		page,
	}) => {
		await setupGuardrailErrorMocks(page);
		await page.goto(`/jobs/${JOB_POSTING_ID}/review`);

		await expect(page.getByTestId("ghostwriter-review")).toBeVisible();

		// "Approve Both" disabled (guardrail errors on variant)
		await expect(
			page.getByRole("button", { name: APPROVE_BOTH }),
		).toBeDisabled();
		// "Approve Resume Only" disabled
		await expect(
			page.getByRole("button", { name: APPROVE_RESUME_ONLY }),
		).toBeDisabled();
		// "Approve Letter Only" still enabled (no cover letter validation errors)
		await expect(
			page.getByRole("button", { name: APPROVE_LETTER_ONLY }),
		).toBeEnabled();
	});
});

// ---------------------------------------------------------------------------
// F. No materials — empty state (1 test)
// ---------------------------------------------------------------------------

test.describe("Ghostwriter Review — No Materials", () => {
	test("shows empty state when no materials found for job", async ({
		page,
	}) => {
		await setupNoMaterialsMocks(page);
		await page.goto(`/jobs/${JOB_POSTING_ID}/review`);

		await expect(page.getByTestId("review-page-no-materials")).toBeVisible();
		await expect(
			page.getByText("No materials found for this job"),
		).toBeVisible();
	});
});
