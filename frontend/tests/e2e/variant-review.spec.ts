/**
 * E2E tests for the variant review page (side-by-side diff).
 *
 * REQ-012 §9.3: Side-by-side comparison of base resume vs tailored variant
 * with diff highlighting, bullet move indicators, Approve/Archive actions.
 * REQ-012 §9.4: Guardrail violations with blocking behaviour.
 * All API calls are mocked via Playwright's page.route() — no real backend.
 */

import { expect, test } from "@playwright/test";

import {
	BASE_RESUME_IDS,
	GUARDRAIL_ERROR,
	GUARDRAIL_WARNING,
	JOB_VARIANT_IDS,
	setupResumeListMocks,
	setupVariantReviewMocks,
} from "../utils/resume-api-mocks";

const REVIEW_URL = `/resumes/${BASE_RESUME_IDS[0]}/variants/${JOB_VARIANT_IDS[0]}/review`;

// ---------------------------------------------------------------------------
// A. Variant Review — Display (2 tests)
// ---------------------------------------------------------------------------

test.describe("Variant Review — Display", () => {
	test("shows side-by-side panels with header title", async ({ page }) => {
		await setupResumeListMocks(page);
		await page.goto(REVIEW_URL);

		await expect(page.getByTestId("variant-review")).toBeVisible();

		// Header shows job title + company from job posting lookup
		await expect(
			page.getByRole("heading", {
				name: "Frontend Engineer at AlphaTech",
			}),
		).toBeVisible();

		// Both panels visible
		await expect(page.getByTestId("base-panel")).toBeVisible();
		await expect(page.getByTestId("variant-panel")).toBeVisible();

		// Panel headings
		await expect(
			page.getByRole("heading", { name: "Base Resume" }),
		).toBeVisible();
		await expect(
			page.getByRole("heading", { name: "Tailored Variant" }),
		).toBeVisible();
	});

	test("shows bullet move indicators in variant panel", async ({ page }) => {
		await setupResumeListMocks(page);
		await page.goto(REVIEW_URL);

		await expect(page.getByTestId("variant-review")).toBeVisible();

		// The Draft variant has reversed bullet order for wh-001:
		// base = [b-001, b-002], variant = [b-002, b-001]
		// So b-001 (position 1 in base) moves to position 2 → shows "from #1"
		const variantPanel = page.getByTestId("variant-panel");
		await expect(variantPanel.getByText("from #1")).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// B. Variant Review — Agent Reasoning (1 test)
// ---------------------------------------------------------------------------

test.describe("Variant Review — Agent Reasoning", () => {
	test("displays collapsible agent reasoning section", async ({ page }) => {
		await setupResumeListMocks(page);
		await page.goto(REVIEW_URL);

		await expect(page.getByTestId("variant-review")).toBeVisible();

		// Agent reasoning section visible (Draft variant has reasoning text)
		await expect(page.getByTestId("agent-reasoning")).toBeVisible();

		// Toggle button exists — starts expanded by default
		const toggle = page.getByTestId("agent-reasoning-toggle");
		await expect(toggle).toBeVisible();
		await expect(toggle).toHaveAttribute("aria-expanded", "true");
		await expect(
			page.getByText("Reordered bullets to highlight mentoring"),
		).toBeVisible();

		// Collapse reasoning
		await toggle.click();
		await expect(toggle).toHaveAttribute("aria-expanded", "false");
	});
});

// ---------------------------------------------------------------------------
// C. Variant Review — Approve & Archive Actions (2 tests)
// ---------------------------------------------------------------------------

test.describe("Variant Review — Actions", () => {
	test("Approve button sends POST and navigates back", async ({ page }) => {
		await setupResumeListMocks(page);
		await page.goto(REVIEW_URL);

		await expect(page.getByTestId("variant-review")).toBeVisible();

		// Set up POST listener for approve
		const approvePromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/job-variants/${JOB_VARIANT_IDS[0]}/approve`) &&
				res.request().method() === "POST",
		);

		// Click Approve
		await page.getByRole("button", { name: "Approve" }).click();

		// Verify POST sent
		const response = await approvePromise;
		expect(response.status()).toBe(200);

		// Navigates back to resume detail
		await expect(page).toHaveURL(`/resumes/${BASE_RESUME_IDS[0]}`);
	});

	test("Archive button sends DELETE after confirmation", async ({ page }) => {
		await setupResumeListMocks(page);
		await page.goto(REVIEW_URL);

		await expect(page.getByTestId("variant-review")).toBeVisible();

		// Set up DELETE listener
		const deletePromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/job-variants/${JOB_VARIANT_IDS[0]}`) &&
				res.request().method() === "DELETE",
		);

		// Click Archive → opens confirmation dialog
		await page.getByRole("button", { name: "Archive" }).click();

		// Confirm the dialog (scoped to dialog footer to avoid ambiguity)
		await expect(page.getByText("Archive Variant")).toBeVisible();
		await page
			.locator("[data-slot='confirmation-dialog-footer']")
			.getByRole("button", { name: "Archive" })
			.click();

		// Verify DELETE sent
		const response = await deletePromise;
		expect(response.status()).toBe(204);

		// Navigates back to resume detail
		await expect(page).toHaveURL(`/resumes/${BASE_RESUME_IDS[0]}`);
	});
});

// ---------------------------------------------------------------------------
// D. Variant Review — Guardrail Violations (2 tests)
// ---------------------------------------------------------------------------

test.describe("Variant Review — Guardrails", () => {
	test("error-severity guardrail blocks Approve and shows banner", async ({
		page,
	}) => {
		await setupVariantReviewMocks(page, {
			variantId: JOB_VARIANT_IDS[0],
			guardrailResult: GUARDRAIL_ERROR,
		});
		await page.goto(REVIEW_URL);

		await expect(page.getByTestId("variant-review")).toBeVisible();

		// Guardrail violation banner visible
		await expect(page.getByTestId("guardrail-violations")).toBeVisible();
		await expect(
			page.getByText("Resume contains fabricated accomplishments"),
		).toBeVisible();

		// Approve button disabled
		await expect(page.getByRole("button", { name: "Approve" })).toBeDisabled();

		// Regenerate button enabled (only active when errors present)
		await expect(
			page.getByRole("button", { name: "Regenerate" }),
		).toBeEnabled();

		// "Go to Persona" link present
		await expect(page.getByTestId("go-to-persona-link")).toBeVisible();
	});

	test("warning-severity guardrail does NOT block Approve", async ({
		page,
	}) => {
		await setupVariantReviewMocks(page, {
			variantId: JOB_VARIANT_IDS[0],
			guardrailResult: GUARDRAIL_WARNING,
		});
		await page.goto(REVIEW_URL);

		await expect(page.getByTestId("variant-review")).toBeVisible();

		// Guardrail banner visible (warnings still show)
		await expect(page.getByTestId("guardrail-violations")).toBeVisible();
		await expect(
			page.getByText("Missing 2 of 5 required skills"),
		).toBeVisible();

		// Approve button still enabled (warnings don't block)
		await expect(page.getByRole("button", { name: "Approve" })).toBeEnabled();

		// Regenerate disabled (no errors)
		await expect(
			page.getByRole("button", { name: "Regenerate" }),
		).toBeDisabled();
	});
});

// ---------------------------------------------------------------------------
// E. Variant Review — Navigation (1 test)
// ---------------------------------------------------------------------------

test.describe("Variant Review — Navigation", () => {
	test("back link navigates to resume detail", async ({ page }) => {
		await setupResumeListMocks(page);
		await page.goto(REVIEW_URL);

		await expect(page.getByTestId("variant-review")).toBeVisible();

		await page.getByRole("link", { name: "Back to resume detail" }).click();
		await expect(page).toHaveURL(`/resumes/${BASE_RESUME_IDS[0]}`);
	});
});
