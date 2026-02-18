/**
 * E2E tests for the resume list and new resume wizard flow.
 *
 * REQ-012 §9.1: Card-based resume list with primary badge, status, variant
 * count, actions (View & Edit, Download PDF, Archive).
 * REQ-012 §9.2: New resume wizard form with content selection checkboxes.
 * All API calls are mocked via Playwright's page.route() — no real backend.
 */

import { expect, test } from "@playwright/test";

import {
	BASE_RESUME_IDS,
	PERSONA_ID,
	setupEmptyResumeListMocks,
	setupResumeListMocks,
} from "../utils/resume-api-mocks";

// ---------------------------------------------------------------------------
// A. Resume List — Cards & Display (3 tests)
// ---------------------------------------------------------------------------

test.describe("Resume List — Cards & Display", () => {
	test("displays active resume cards with primary badge and variant count", async ({
		page,
	}) => {
		await setupResumeListMocks(page);
		await page.goto("/resumes");

		await expect(page.getByTestId("resume-list")).toBeVisible();

		// 2 active resume cards (archived hidden by default)
		const cards = page.getByTestId("resume-card");
		await expect(cards).toHaveCount(2);

		// First resume: Scrum Master — primary, rendered, has variants
		const firstCard = cards.nth(0);
		await expect(firstCard).toContainText("Scrum Master");
		await expect(firstCard).toContainText("Primary");
		await expect(firstCard).toContainText("Scrum Master / Agile Coach");
		await expect(firstCard).toContainText("2 variants");
		await expect(firstCard).toContainText("1 pending review");

		// Download PDF button visible (rendered_at is set)
		await expect(
			firstCard.getByRole("link", { name: "Download PDF" }),
		).toBeVisible();

		// Second resume: Product Owner — not primary, no variants, not rendered
		const secondCard = cards.nth(1);
		await expect(secondCard).toContainText("Product Owner");
		await expect(
			secondCard.getByRole("link", { name: "Download PDF" }),
		).not.toBeAttached();
	});

	test("show archived checkbox reveals archived resumes", async ({ page }) => {
		await setupResumeListMocks(page);
		await page.goto("/resumes");

		await expect(page.getByTestId("resume-list")).toBeVisible();

		// Initially 2 cards
		await expect(page.getByTestId("resume-card")).toHaveCount(2);
		await expect(page.getByText("Tech Lead (Archived)")).not.toBeVisible();

		// Check "Show archived"
		await page.getByLabel("Show archived").check();

		// Now 3 cards (including archived)
		await expect(page.getByTestId("resume-card")).toHaveCount(3);
		await expect(page.getByText("Tech Lead (Archived)")).toBeVisible();
	});

	test("empty state shows create prompt", async ({ page }) => {
		await setupEmptyResumeListMocks(page);
		await page.goto("/resumes");

		await expect(page.getByTestId("resume-list")).toBeVisible();

		// Empty state message
		await expect(page.getByText("No resumes yet")).toBeVisible();
		await expect(
			page.getByText("Create your first base resume to get started."),
		).toBeVisible();

		// Empty state action button (inside the status output element)
		await expect(
			page.getByRole("status").getByRole("button", { name: "New Resume" }),
		).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// B. Resume List — Archive Action (1 test)
// ---------------------------------------------------------------------------

test.describe("Resume List — Archive Action", () => {
	test("archive button sends DELETE and removes card", async ({ page }) => {
		await setupResumeListMocks(page);
		await page.goto("/resumes");

		await expect(page.getByTestId("resume-list")).toBeVisible();
		await expect(page.getByTestId("resume-card")).toHaveCount(2);

		// Set up DELETE listener for the second resume (Product Owner)
		const deletePromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/base-resumes/${BASE_RESUME_IDS[1]}`) &&
				res.request().method() === "DELETE",
		);

		// Click Archive on the second card (Product Owner)
		const secondCard = page.getByTestId("resume-card").nth(1);
		await secondCard.getByRole("button", { name: "Archive" }).click();

		// Verify DELETE sent
		const response = await deletePromise;
		expect(response.status()).toBe(204);

		// After refetch, card should be removed
		await expect(page.getByTestId("resume-card")).toHaveCount(1);
		await expect(page.getByText("Product Owner")).not.toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// C. Resume List — Navigation (2 tests)
// ---------------------------------------------------------------------------

test.describe("Resume List — Navigation", () => {
	test("New Resume button navigates to wizard", async ({ page }) => {
		await setupResumeListMocks(page);
		await page.goto("/resumes");

		await expect(page.getByTestId("resume-list")).toBeVisible();

		await page.getByRole("button", { name: "New Resume" }).first().click();
		await expect(page).toHaveURL("/resumes/new");
	});

	test("View & Edit link navigates to resume detail", async ({ page }) => {
		await setupResumeListMocks(page);
		await page.goto("/resumes");

		await expect(page.getByTestId("resume-list")).toBeVisible();

		// Click View & Edit on the first card
		const firstCard = page.getByTestId("resume-card").nth(0);
		await firstCard.getByRole("link", { name: "View & Edit" }).click();

		await expect(page).toHaveURL(`/resumes/${BASE_RESUME_IDS[0]}`);
	});
});

// ---------------------------------------------------------------------------
// D. New Resume Wizard (2 tests)
// ---------------------------------------------------------------------------

test.describe("New Resume Wizard", () => {
	test("create resume form submits POST and redirects to detail", async ({
		page,
	}) => {
		await setupResumeListMocks(page);
		await page.goto("/resumes/new");

		await expect(page.getByTestId("new-resume-wizard")).toBeVisible();

		// Fill form fields
		await page.getByLabel("Name").fill("DevOps Engineer");
		await page.getByLabel("Role Type").fill("DevOps / SRE roles");
		await page
			.getByLabel("Summary")
			.fill("Infrastructure specialist with cloud expertise");

		// Set up POST listener
		const postPromise = page.waitForResponse(
			(res) =>
				res.url().includes("/base-resumes") &&
				res.request().method() === "POST",
		);

		// Click Create Resume
		await page.getByRole("button", { name: "Create Resume" }).click();

		// Verify POST sent with form data
		const response = await postPromise;
		expect(response.status()).toBe(201);
		const body = response.request().postDataJSON();
		expect(body.name).toBe("DevOps Engineer");
		expect(body.role_type).toBe("DevOps / SRE roles");
		expect(body.summary).toBe("Infrastructure specialist with cloud expertise");
		expect(body.persona_id).toBe(PERSONA_ID);

		// Should redirect to the new resume's detail page
		await expect(page).toHaveURL(/\/resumes\/br-e2e-new-001/);
	});

	test("back link navigates to resume list", async ({ page }) => {
		await setupResumeListMocks(page);
		await page.goto("/resumes/new");

		await expect(page.getByTestId("new-resume-wizard")).toBeVisible();

		await page.getByRole("link", { name: "Back to Resumes" }).click();
		await expect(page).toHaveURL("/resumes");
	});
});
