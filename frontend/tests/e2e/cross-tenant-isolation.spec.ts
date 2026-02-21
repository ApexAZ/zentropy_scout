/**
 * E2E tests for cross-tenant data isolation in the frontend.
 *
 * REQ-014 §5.1: Backend returns 404 (not 403) for cross-tenant resource
 * access. These tests verify the frontend renders appropriate error states
 * when API responses indicate the resource doesn't exist (or belongs to
 * another user).
 *
 * Strategy: Mock detail endpoints to return 404 and verify the UI shows
 * NotFoundState or FailedState — never the resource's actual data.
 */

import { expect, test } from "@playwright/test";

import {
	CROSS_TENANT_ID,
	mock404ForRoute,
	mockEmptyList,
	setupCrossTenantBaseMocks,
} from "../utils/cross-tenant-api-mocks";

// ---------------------------------------------------------------------------
// A. Application Detail — Cross-Tenant 404 (2 tests)
// ---------------------------------------------------------------------------

test.describe("Application Detail — Cross-Tenant 404", () => {
	test("shows not-found state when accessing another user's application", async ({
		page,
	}) => {
		await setupCrossTenantBaseMocks(page);
		await mock404ForRoute(page, /\/api\/v1\/applications\//);

		await page.goto(`/applications/${CROSS_TENANT_ID}`);

		// NotFoundState renders role="alert" with "doesn't exist" message
		const alert = page.locator('[data-slot="not-found-state"]');
		await expect(alert).toBeVisible();
		await expect(page.getByText(/doesn.*t exist/)).toBeVisible();

		// "Go back" button navigates to applications list
		await expect(page.getByRole("button", { name: "Go back" })).toBeVisible();
	});

	test("Go back button navigates to applications list", async ({ page }) => {
		await setupCrossTenantBaseMocks(page);
		await mock404ForRoute(page, /\/api\/v1\/applications\//);

		await page.goto(`/applications/${CROSS_TENANT_ID}`);

		await expect(page.locator('[data-slot="not-found-state"]')).toBeVisible();

		await page.getByRole("button", { name: "Go back" }).click();
		await expect(page).toHaveURL("/applications");
	});
});

// ---------------------------------------------------------------------------
// B. Job Detail — Cross-Tenant 404 (1 test)
// ---------------------------------------------------------------------------

test.describe("Job Detail — Cross-Tenant 404", () => {
	test("shows not-found state when accessing another user's job posting", async ({
		page,
	}) => {
		await setupCrossTenantBaseMocks(page);
		await mock404ForRoute(page, /\/api\/v1\/job-postings\//);

		await page.goto(`/jobs/${CROSS_TENANT_ID}`);

		// NotFoundState renders with "doesn't exist" message
		const alert = page.locator('[data-slot="not-found-state"]');
		await expect(alert).toBeVisible();
		await expect(page.getByText(/doesn.*t exist/)).toBeVisible();

		// "Go back" button should be visible and navigate to dashboard
		const goBack = page.getByRole("button", { name: "Go back" });
		await expect(goBack).toBeVisible();
		await goBack.click();
		await expect(page).toHaveURL("/");
	});
});

// ---------------------------------------------------------------------------
// C. Resume Detail — Cross-Tenant 404 (1 test)
// ---------------------------------------------------------------------------

test.describe("Resume Detail — Cross-Tenant 404", () => {
	test("shows error state when accessing another user's resume", async ({
		page,
	}) => {
		await setupCrossTenantBaseMocks(page);
		await mock404ForRoute(page, /\/api\/v1\/base-resumes\//);

		await page.goto(`/resumes/${CROSS_TENANT_ID}`);

		// ResumeDetail shows FailedState (generic error, not 404-specific)
		const alert = page.locator('[data-slot="failed-state"]');
		await expect(alert).toBeVisible();
		await expect(page.getByText("Failed to load.")).toBeVisible();

		// Retry button is visible (would re-fetch, still get 404)
		await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// D. Variant Review — Cross-Tenant 404 (1 test)
// ---------------------------------------------------------------------------

test.describe("Variant Review — Cross-Tenant 404", () => {
	test("shows error state when accessing another user's variant", async ({
		page,
	}) => {
		await setupCrossTenantBaseMocks(page);

		// Mock both variant and base-resume endpoints to return 404
		await mock404ForRoute(page, /\/api\/v1\/job-variants\//);
		await mock404ForRoute(page, /\/api\/v1\/base-resumes\//);

		const resumeId = CROSS_TENANT_ID;
		const variantId = "00000000-0000-4000-b000-000000000098";
		await page.goto(`/resumes/${resumeId}/variants/${variantId}/review`);

		// VariantReview shows FailedState on any fetch error
		const alert = page.locator('[data-slot="failed-state"]');
		await expect(alert).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// E. Ghostwriter Review — Cross-Tenant Empty State (1 test)
// ---------------------------------------------------------------------------

test.describe("Ghostwriter Review — Cross-Tenant Empty State", () => {
	test("shows no materials when accessing another user's job review page", async ({
		page,
	}) => {
		await setupCrossTenantBaseMocks(page);

		// Mock variants and cover-letters lists to return empty (ownership filter)
		await mockEmptyList(page, /\/api\/v1\/variants/);
		await mockEmptyList(page, /\/api\/v1\/cover-letters/);

		await page.goto(`/jobs/${CROSS_TENANT_ID}/review`);

		// GhostwriterReviewPage shows "No materials found" when lists are empty
		await expect(page.getByTestId("review-page-no-materials")).toBeVisible();
		await expect(page.getByText("No materials found")).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// F. Dashboard — Empty List (No Data Leakage) (1 test)
// ---------------------------------------------------------------------------

test.describe("Dashboard — Empty List (No Data Leakage)", () => {
	test("dashboard shows empty state when user has no job postings", async ({
		page,
	}) => {
		await setupCrossTenantBaseMocks(page);

		// Mock job postings list to return empty (user has no jobs)
		await mockEmptyList(page, /\/api\/v1\/job-postings/);
		// Mock applications list to return empty
		await mockEmptyList(page, /\/api\/v1\/applications/);

		await page.goto("/");

		// Dashboard should be visible with no data — empty state shown
		await expect(page.getByTestId("dashboard-tabs")).toBeVisible();

		// Opportunities tab should show empty state (no jobs from other users)
		await expect(page.getByTestId("tab-content-opportunities")).toBeVisible();

		// Verify no job data is visible — empty state message instead
		await expect(page.getByText("No opportunities found.")).toBeVisible();
	});
});
