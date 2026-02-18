/**
 * E2E tests for the persona update flow.
 *
 * REQ-012 §7: Persona overview, section editors (basic info, growth targets,
 * skills), change flag banner, and change flag resolution.
 * All API calls are mocked via Playwright's page.route() — no real backend.
 */

import { expect, test } from "@playwright/test";

import {
	CHANGE_FLAG_IDS,
	PERSONA_ID,
	setupBasicInfoEditorMocks,
	setupChangeFlagsResolverMocks,
	setupGrowthTargetsEditorMocks,
	setupPersonaOverviewMocks,
	setupPersonaOverviewWithFlagsMocks,
	setupSkillsEditorMocks,
} from "../utils/persona-update-api-mocks";

// ---------------------------------------------------------------------------
// A. Persona Overview (3 tests)
// ---------------------------------------------------------------------------

test.describe("Persona Overview", () => {
	test("displays persona header with identity and professional info", async ({
		page,
	}) => {
		await setupPersonaOverviewMocks(page);
		await page.goto("/persona");

		await expect(page.getByTestId("persona-header")).toBeVisible();

		// Identity column
		await expect(page.getByText("Jane Doe")).toBeVisible();
		await expect(page.getByText("jane@example.com")).toBeVisible();

		// Professional column
		await expect(page.getByText("Senior Engineer")).toBeVisible();
		await expect(page.getByText("Acme Corp")).toBeVisible();
		await expect(page.getByText("8 years")).toBeVisible();
		await expect(page.getByText("San Francisco, CA, USA")).toBeVisible();
	});

	test("shows 8 section cards with counts", async ({ page }) => {
		await setupPersonaOverviewMocks(page);
		await page.goto("/persona");

		await expect(page.getByTestId("persona-overview")).toBeVisible();

		// Work History: 2 entries
		await expect(page.getByTestId("section-card-work-history")).toContainText(
			"2 positions",
		);

		// Skills: 2 Hard + 1 Soft
		await expect(page.getByTestId("section-card-skills")).toContainText(
			"2 Hard, 1 Soft",
		);

		// Education: 1 entry
		await expect(page.getByTestId("section-card-education")).toContainText(
			"1 entry",
		);

		// Certifications: 1 cert
		await expect(page.getByTestId("section-card-certifications")).toContainText(
			"1 certification",
		);

		// Achievement Stories: 3 stories
		await expect(
			page.getByTestId("section-card-achievement-stories"),
		).toContainText("3 stories");

		// Voice Profile
		await expect(page.getByTestId("section-card-voice")).toContainText(
			"Configured",
		);

		// Growth Targets
		await expect(page.getByTestId("section-card-growth")).toContainText(
			"2 target roles, 2 target skills",
		);

		// Non-Negotiables
		await expect(
			page.getByTestId("section-card-non-negotiables"),
		).toContainText("2 custom filters");
	});

	test("discovery preferences block shows thresholds and polling", async ({
		page,
	}) => {
		await setupPersonaOverviewMocks(page);
		await page.goto("/persona");

		const prefs = page.getByTestId("discovery-preferences");
		await expect(prefs).toBeVisible();

		await expect(prefs).toContainText("60");
		await expect(prefs).toContainText("80");
		await expect(prefs).toContainText("Daily");
	});
});

// ---------------------------------------------------------------------------
// B. Basic Info Editor (2 tests)
// ---------------------------------------------------------------------------

test.describe("Basic Info Editor", () => {
	test("edit and save basic info", async ({ page }) => {
		await setupBasicInfoEditorMocks(page);
		await page.goto("/persona/basic-info");

		await expect(page.getByTestId("basic-info-editor-form")).toBeVisible();

		// Verify pre-filled
		await expect(page.getByLabel("Full Name")).toHaveValue("Jane Doe");

		// Clear and type new name
		await page.getByLabel("Full Name").clear();
		await page.getByLabel("Full Name").fill("Jane Smith");

		// Set up PATCH listener
		const patchPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/personas/${PERSONA_ID}`) &&
				res.request().method() === "PATCH",
		);

		// Click Save
		await page.getByRole("button", { name: "Save" }).click();

		// Verify PATCH sent with new name
		const response = await patchPromise;
		expect(response.status()).toBe(200);
		const body = response.request().postDataJSON();
		expect(body.full_name).toBe("Jane Smith");

		// Verify navigation back to persona overview
		await expect(page).toHaveURL("/persona");
	});

	test("back link navigates to overview", async ({ page }) => {
		await setupBasicInfoEditorMocks(page);
		await page.goto("/persona/basic-info");

		await expect(page.getByTestId("basic-info-editor-form")).toBeVisible();

		await page.getByText("Back to Profile").click();
		await expect(page).toHaveURL("/persona");
	});
});

// ---------------------------------------------------------------------------
// C. Growth Targets Editor (2 tests)
// ---------------------------------------------------------------------------

test.describe("Growth Targets Editor", () => {
	test("save growth targets with updated stretch appetite", async ({
		page,
	}) => {
		await setupGrowthTargetsEditorMocks(page);
		await page.goto("/persona/growth");

		await expect(page.getByTestId("growth-targets-editor-form")).toBeVisible();

		// Verify Medium is currently checked
		const mediumRadio = page.getByRole("radio", { name: "Medium" });
		await expect(mediumRadio).toBeChecked();

		// Click High radio
		await page.getByRole("radio", { name: "High" }).click();

		// Set up PATCH listener
		const patchPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/personas/${PERSONA_ID}`) &&
				res.request().method() === "PATCH",
		);

		// Click Save
		await page.getByRole("button", { name: "Save" }).click();

		// Verify PATCH sent with updated stretch_appetite
		const response = await patchPromise;
		expect(response.status()).toBe(200);
		const body = response.request().postDataJSON();
		expect(body.stretch_appetite).toBe("High");

		// Verify success message (stays on page, no navigation)
		await expect(page.getByTestId("save-success")).toContainText(
			"Growth targets saved.",
		);
	});

	test("pre-fills tag fields with existing values", async ({ page }) => {
		await setupGrowthTargetsEditorMocks(page);
		await page.goto("/persona/growth");

		await expect(page.getByTestId("growth-targets-editor-form")).toBeVisible();

		// Verify target roles tags
		await expect(page.getByText("Staff Engineer")).toBeVisible();
		await expect(page.getByText("Engineering Manager")).toBeVisible();

		// Verify target skills tags
		await expect(page.getByText("Kubernetes")).toBeVisible();
		await expect(page.getByText("People Management")).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// D. Skills Editor (3 tests)
// ---------------------------------------------------------------------------

test.describe("Skills Editor", () => {
	test("displays skills in Hard and Soft tabs", async ({ page }) => {
		await setupSkillsEditorMocks(page);
		await page.goto("/persona/skills");

		// Hard Skills tab should be active by default
		await expect(
			page.getByRole("tab", { name: /Hard Skills \(2\)/ }),
		).toBeVisible();
		await expect(
			page.getByRole("tab", { name: /Soft Skills \(1\)/ }),
		).toBeVisible();

		// Hard skills content visible
		await expect(page.getByText("TypeScript")).toBeVisible();
		await expect(page.getByText("Python")).toBeVisible();

		// Click Soft Skills tab
		await page.getByRole("tab", { name: /Soft Skills/ }).click();
		await expect(page.getByText("Leadership")).toBeVisible();
	});

	test("add new skill via form", async ({ page }) => {
		await setupSkillsEditorMocks(page);
		await page.goto("/persona/skills");

		// Click Add skill button
		await page.getByRole("button", { name: "Add skill" }).click();

		// Skills form should appear
		await expect(page.getByTestId("skills-form")).toBeVisible();

		// Fill form
		await page.getByLabel("Skill Name").fill("Docker");
		await page
			.getByRole("radiogroup", { name: "Skill Type" })
			.getByText("Hard")
			.click();
		await page.getByLabel("Category").selectOption("Tool / Software");
		await page
			.getByRole("radiogroup", { name: "Proficiency" })
			.getByText("Proficient")
			.click();
		await page.getByLabel("Years Used").fill("3");
		await page.getByLabel("Last Used").fill("Current");

		// Set up POST listener
		const postPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/personas/${PERSONA_ID}/skills`) &&
				res.request().method() === "POST",
		);

		// Click Save
		await page.getByRole("button", { name: "Save" }).click();

		// Verify POST sent
		const response = await postPromise;
		expect(response.status()).toBe(201);

		// Form should disappear, tab count updates
		await expect(page.getByTestId("skills-form")).not.toBeVisible();
		await expect(
			page.getByRole("tab", { name: /Hard Skills \(3\)/ }),
		).toBeVisible();
	});

	test("cancel add skill returns to list", async ({ page }) => {
		await setupSkillsEditorMocks(page);
		await page.goto("/persona/skills");

		// Click Add skill
		await page.getByRole("button", { name: "Add skill" }).click();
		await expect(page.getByTestId("skills-form")).toBeVisible();

		// Click Cancel
		await page.getByRole("button", { name: "Cancel" }).click();

		// Form should be gone, tab count unchanged
		await expect(page.getByTestId("skills-form")).not.toBeVisible();
		await expect(
			page.getByRole("tab", { name: /Hard Skills \(2\)/ }),
		).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// E. Change Flags Banner (2 tests)
// ---------------------------------------------------------------------------

test.describe("Change Flags Banner", () => {
	test("banner shows pending count with review link", async ({ page }) => {
		await setupPersonaOverviewWithFlagsMocks(page);
		await page.goto("/persona");

		const banner = page.getByTestId("change-flags-banner");
		await expect(banner).toBeVisible();
		await expect(banner).toContainText("3 changes need review");

		// Verify Review link exists
		await expect(banner.getByRole("link", { name: "Review" })).toBeVisible();
	});

	test("no banner when no pending flags", async ({ page }) => {
		await setupPersonaOverviewMocks(page);
		await page.goto("/persona");

		await expect(page.getByTestId("persona-overview")).toBeVisible();
		await expect(page.getByTestId("change-flags-banner")).not.toBeAttached();
	});
});

// ---------------------------------------------------------------------------
// F. Change Flags Resolution (3 tests)
// ---------------------------------------------------------------------------

test.describe("Change Flags Resolution", () => {
	test("add to all resolves flag and removes from list", async ({ page }) => {
		await setupChangeFlagsResolverMocks(page);
		await page.goto("/persona/change-flags");

		await expect(page.getByTestId("change-flags-resolver")).toBeVisible();
		await expect(page.getByText("3 changes need review")).toBeVisible();

		// Verify first flag shows skill description
		await expect(page.getByTestId(`flag-${CHANGE_FLAG_IDS[0]}`)).toContainText(
			"Kubernetes",
		);

		// Set up PATCH listener
		const patchPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/persona-change-flags/${CHANGE_FLAG_IDS[0]}`) &&
				res.request().method() === "PATCH",
		);

		// Click "Add to all resumes"
		await page.getByTestId(`add-all-${CHANGE_FLAG_IDS[0]}`).click();

		// Verify PATCH sent
		const response = await patchPromise;
		expect(response.status()).toBe(200);
		const body = response.request().postDataJSON();
		expect(body).toMatchObject({
			status: "Resolved",
			resolution: "added_to_all",
		});

		// Flag removed, heading updates
		await expect(page.getByText("2 changes need review")).toBeVisible();
	});

	test("add to some expands resume checklist and resolves", async ({
		page,
	}) => {
		await setupChangeFlagsResolverMocks(page);
		await page.goto("/persona/change-flags");

		await expect(page.getByTestId("change-flags-resolver")).toBeVisible();

		// Click "Add to some" for second flag
		await page.getByTestId(`add-some-${CHANGE_FLAG_IDS[1]}`).click();

		// Resume checklist should appear
		const checklist = page.getByTestId(
			`resume-checklist-${CHANGE_FLAG_IDS[1]}`,
		);
		await expect(checklist).toBeVisible();

		// Verify both resumes listed
		await expect(checklist).toContainText("General Resume");
		await expect(checklist).toContainText("Backend Focus");

		// Check "General Resume"
		await checklist.getByText("General Resume").click();

		// Set up PATCH listener
		const patchPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/persona-change-flags/${CHANGE_FLAG_IDS[1]}`) &&
				res.request().method() === "PATCH",
		);

		// Click Confirm
		await page.getByTestId(`confirm-some-${CHANGE_FLAG_IDS[1]}`).click();

		// Verify PATCH sent
		const response = await patchPromise;
		expect(response.status()).toBe(200);
		const body = response.request().postDataJSON();
		expect(body).toMatchObject({
			status: "Resolved",
			resolution: "added_to_some",
		});
	});

	test("skip resolves flag and shows empty state when all resolved", async ({
		page,
	}) => {
		await setupChangeFlagsResolverMocks(page);
		await page.goto("/persona/change-flags");

		await expect(page.getByTestId("change-flags-resolver")).toBeVisible();

		// Resolve first two flags quickly
		await page.getByTestId(`add-all-${CHANGE_FLAG_IDS[0]}`).click();
		await expect(page.getByText("2 changes need review")).toBeVisible();

		await page.getByTestId(`add-all-${CHANGE_FLAG_IDS[1]}`).click();
		await expect(page.getByText("1 change needs review")).toBeVisible();

		// Skip the last flag
		const patchPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/persona-change-flags/${CHANGE_FLAG_IDS[2]}`) &&
				res.request().method() === "PATCH",
		);

		await page.getByTestId(`skip-${CHANGE_FLAG_IDS[2]}`).click();

		const response = await patchPromise;
		expect(response.status()).toBe(200);
		const body = response.request().postDataJSON();
		expect(body).toMatchObject({
			status: "Resolved",
			resolution: "skipped",
		});

		// Empty state shown
		await expect(page.getByText("All changes resolved")).toBeVisible();
		await expect(page.getByText("Back to Profile")).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// G. Navigation (1 test)
// ---------------------------------------------------------------------------

test.describe("Navigation", () => {
	test("section card edit link navigates to editor", async ({ page }) => {
		await setupPersonaOverviewMocks(page);
		await page.goto("/persona");

		await expect(page.getByTestId("persona-overview")).toBeVisible();

		// Click the Edit link inside the skills section card
		const skillsCard = page.getByTestId("section-card-skills");
		await skillsCard.getByText("Edit").click();

		await expect(page).toHaveURL("/persona/skills");
	});
});
