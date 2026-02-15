/**
 * E2E tests for the 12-step onboarding flow.
 *
 * REQ-012 §6: New user onboarding wizard.
 * All API calls are mocked via Playwright's page.route() — no real backend.
 */

import { expect, test } from "@playwright/test";

import {
	OnboardingMockController,
	setupFreshUserMocks,
	setupMidFlowMocks,
	setupNewOnboardingMocks,
	setupOnboardedUserMocks,
} from "../utils/onboarding-api-mocks";

// ---------------------------------------------------------------------------
// Shared selectors & text
// ---------------------------------------------------------------------------

const ONBOARDING_NAV = '[data-slot="onboarding-nav"]';
const SKIP_MANUAL_ENTRY = "Skip — I'll enter manually";

// ---------------------------------------------------------------------------
// A. Onboarding Gate
// ---------------------------------------------------------------------------

test.describe("Onboarding Gate", () => {
	test("redirects to /onboarding when no persona exists", async ({ page }) => {
		await setupFreshUserMocks(page);
		await page.goto("/");
		await expect(page).toHaveURL(/\/onboarding/);
	});

	test("redirects to /onboarding when onboarding_complete=false", async ({
		page,
	}) => {
		const controller = new OnboardingMockController({
			hasPersona: true,
			onboardingComplete: false,
		});
		await controller.setupRoutes(page);
		await page.goto("/");
		await expect(page).toHaveURL(/\/onboarding/);
	});

	test("allows dashboard access when onboarding_complete=true", async ({
		page,
	}) => {
		await setupOnboardedUserMocks(page);
		await page.goto("/");
		// Should NOT redirect — should stay on dashboard
		await expect(page).not.toHaveURL(/\/onboarding/);
		await expect(page).toHaveURL("/");
	});
});

// ---------------------------------------------------------------------------
// B. Happy Path — Full Flow
// ---------------------------------------------------------------------------

test.describe("Happy Path", () => {
	test("completes full onboarding from step 1 through step 12", async ({
		page,
	}) => {
		test.slow();

		const controller = await setupNewOnboardingMocks(page);
		await page.goto("/onboarding");

		// ---- Step 1: Resume Upload (skip) ----
		await expect(page.getByText("Step 1 of 12")).toBeVisible();
		await expect(page.getByTestId("drop-zone")).toBeVisible();
		await page.getByText(SKIP_MANUAL_ENTRY).click();

		// ---- Step 2: Basic Info ----
		await expect(page.getByText("Step 2 of 12")).toBeVisible();
		await page.getByLabel("Full Name").fill("Jane Doe");
		await page.getByLabel("Email").fill("jane@example.com");
		await page.getByLabel("Phone").fill("+1 555-123-4567");
		await page.getByLabel("City").fill("San Francisco");
		await page.getByLabel("State").fill("CA");
		await page.getByLabel("Country").fill("USA");
		await page.getByTestId("submit-button").click();

		// ---- Step 3: Work History (add 1 job + 1 bullet) ----
		await expect(page.getByText("Step 3 of 12")).toBeVisible();
		await page.getByRole("button", { name: "Add a job" }).click();
		await page.getByLabel("Job Title").fill("Senior Engineer");
		await page.getByLabel("Company Name").fill("Acme Corp");
		await page.getByLabel("Location").fill("San Francisco, CA");
		// Start date — type="month" input requires YYYY-MM format
		const startDateInput = page.locator('input[name="start_date"]');
		await startDateInput.fill("2022-01");
		// Check "current" if there's a checkbox
		const currentCheckbox = page.getByLabel(/current/i);
		if (await currentCheckbox.isVisible()) {
			await currentCheckbox.check();
		}
		// Submit the work history form
		await page.getByRole("button", { name: /save/i }).click();

		// Now we should see the job card — expand it and add a bullet
		controller.state.workHistoryCount = 1;
		// The work history list should show 1 entry now
		await expect(page.getByText("Senior Engineer")).toBeVisible();

		// Expand bullets section
		const expandButton = page.getByRole("button", {
			name: /expand bullets/i,
		});
		if (await expandButton.isVisible()) {
			await expandButton.click();
		}

		// Add a bullet
		const addBulletButton = page.getByRole("button", {
			name: /add.*bullet|add accomplishment/i,
		});
		if (await addBulletButton.isVisible()) {
			await addBulletButton.click();
			// Fill the bullet text
			const bulletInput = page.locator(
				'textarea[name="text"], input[name="text"]',
			);
			if (await bulletInput.isVisible()) {
				await bulletInput.fill(
					"Led migration to microservices, reducing deploy time by 60%",
				);
				await page.getByRole("button", { name: /save/i }).click();
			}
		}

		// Advance: click Next (button in the step's own nav)
		await page.getByTestId("next-button").click();

		// ---- Step 4: Education (skip via shell Skip button) ----
		await expect(page.getByText("Step 4 of 12")).toBeVisible();
		// Education is skippable — use shell Skip button
		await page
			.locator(ONBOARDING_NAV)
			.getByRole("button", { name: "Skip" })
			.click();

		// ---- Step 5: Skills (add 1 skill with all 6 required fields) ----
		await expect(page.getByText("Step 5 of 12")).toBeVisible();
		await page.getByRole("button", { name: "Add skill" }).click();
		await page.getByLabel("Skill Name").fill("TypeScript");
		// Skill type radio
		await page.getByLabel("Hard", { exact: true }).check();
		// Category dropdown
		await page.getByLabel("Category").selectOption("Programming Language");
		// Proficiency radio
		await page.getByLabel("Expert").check();
		// Years Used
		await page.getByLabel("Years Used").fill("5");
		// Last Used
		await page.getByLabel("Last Used").fill("Current");
		await page.getByRole("button", { name: /save/i }).click();
		controller.state.skillCount = 1;

		// Wait for list view to return, then advance
		await expect(page.getByText("TypeScript")).toBeVisible();
		await page.getByTestId("next-button").click();

		// ---- Step 6: Certifications (skip) ----
		await expect(page.getByText("Step 6 of 12")).toBeVisible();
		await page
			.locator(ONBOARDING_NAV)
			.getByRole("button", { name: "Skip" })
			.click();

		// ---- Step 7: Achievement Stories (add 3 stories) ----
		await expect(page.getByText("Step 7 of 12")).toBeVisible();

		for (let i = 1; i <= 3; i++) {
			await page.getByRole("button", { name: "Add story" }).click();
			await page.getByLabel("Story Title").fill(`Story ${i}`);
			await page.getByLabel("Context").fill(`Context for story ${i}`);
			await page.getByLabel("What did you do?").fill(`Action for story ${i}`);
			await page.getByLabel("Outcome").fill(`Outcome for story ${i}`);
			await page.getByRole("button", { name: /save/i }).click();
			// Wait for list view to return (heading is unique per story card)
			await expect(
				page.getByRole("heading", { name: `Story ${i}` }),
			).toBeVisible();
		}

		await page.getByTestId("next-button").click();

		// ---- Step 8: Non-Negotiables ----
		await expect(page.getByText("Step 8 of 12")).toBeVisible();
		// Select "Remote Only" to simplify the form
		await page.getByLabel("Remote Only").check();
		// Check "Prefer not to set" for salary
		await page.getByLabel("Prefer not to set").check();
		await page.getByTestId("submit-button").click();

		// ---- Step 9: Growth Targets (pre-filled from persona data) ----
		await expect(page.getByText("Step 9 of 12")).toBeVisible();
		// Form is pre-filled with target_roles, target_skills, stretch_appetite
		// from persona mock data — just submit
		await page.getByTestId("submit-button").click();

		// ---- Step 10: Voice Profile ----
		await expect(page.getByText("Step 10 of 12")).toBeVisible();
		// No voice profile exists, so we're in edit mode
		await page.getByLabel("Tone").fill("Direct and confident");
		await page.getByLabel("Style").fill("Short sentences, active voice");
		await page.getByLabel("Vocabulary").fill("Technical when relevant");
		await page.getByTestId("submit-button").click();

		// ---- Step 11: Review ----
		await expect(page.getByText("Step 11 of 12")).toBeVisible();
		// Set up state for review fetches
		controller.state.workHistoryCount = 2;
		controller.state.skillCount = 3;
		controller.state.storyCount = 3;
		controller.state.hasEducation = true;
		controller.state.hasCertifications = true;
		controller.state.hasVoiceProfile = true;
		await page.getByTestId("confirm-button").click();

		// ---- Step 12: Base Resume Setup ----
		await expect(page.getByText("Step 12 of 12")).toBeVisible();
		await page.getByLabel("Resume Name").fill("My First Resume");
		await page.getByLabel("Role Type").fill("Software Engineer");
		await page.getByLabel("Summary").fill("Experienced software engineer");
		await page.getByTestId("submit-button").click();

		// Should redirect to dashboard
		await expect(page).toHaveURL("/");
	});
});

// ---------------------------------------------------------------------------
// C. Step-Level Tests
// ---------------------------------------------------------------------------

test.describe("Step-Level", () => {
	test("Step 1: shows drop zone and skip link", async ({ page }) => {
		await setupNewOnboardingMocks(page);
		await page.goto("/onboarding");

		await expect(page.getByTestId("drop-zone")).toBeVisible();
		await expect(page.getByText(SKIP_MANUAL_ENTRY)).toBeVisible();
	});

	test("Step 1: skip advances to step 2", async ({ page }) => {
		await setupNewOnboardingMocks(page);
		await page.goto("/onboarding");

		await page.getByText(SKIP_MANUAL_ENTRY).click();
		await expect(page.getByText("Step 2 of 12")).toBeVisible();
		await expect(page.getByText("Basic Information")).toBeVisible();
	});

	test("Step 2: shows validation errors for empty required fields", async ({
		page,
	}) => {
		// Use fresh user mocks so persona fields are empty (no pre-fill)
		await setupFreshUserMocks(page);
		await page.goto("/onboarding");

		// Skip to step 2
		await page.getByText(SKIP_MANUAL_ENTRY).click();
		await expect(page.getByText("Step 2 of 12")).toBeVisible();

		// Touch then clear the Full Name field to trigger validation
		await page.getByLabel("Full Name").click();
		await page.getByLabel("Full Name").blur();

		// Submit empty form — form.handleSubmit validates before calling onSubmit
		await page.getByTestId("submit-button").click();

		// Should show validation errors (use .first() — inline + summary both render)
		await expect(page.getByText("Full name is required").first()).toBeVisible();
		await expect(page.getByText("Email is required").first()).toBeVisible();
	});

	test("Step 3: next button disabled when no entries exist", async ({
		page,
	}) => {
		await setupNewOnboardingMocks(page);
		await page.goto("/onboarding");

		// Navigate to step 3
		await page.getByText(SKIP_MANUAL_ENTRY).click();
		await page.getByLabel("Full Name").fill("Jane Doe");
		await page.getByLabel("Email").fill("jane@example.com");
		await page.getByLabel("Phone").fill("+1 555-123-4567");
		await page.getByLabel("City").fill("San Francisco");
		await page.getByLabel("State").fill("CA");
		await page.getByLabel("Country").fill("USA");
		await page.getByTestId("submit-button").click();

		await expect(page.getByText("Step 3 of 12")).toBeVisible();

		// Next should be disabled with no entries
		await expect(page.getByTestId("next-button")).toBeDisabled();
	});

	test("Step 4: can skip education step", async ({ page }) => {
		const controller = await setupMidFlowMocks(page, "work-history");
		controller.state.onboardingStep = "education";
		await page.goto("/onboarding");

		// Wait for checkpoint to load — should resume at education step
		await expect(page.getByText("Step 4 of 12")).toBeVisible();

		// Skip button should be available (education is skippable)
		await page
			.locator(ONBOARDING_NAV)
			.getByRole("button", { name: "Skip" })
			.click();
		await expect(page.getByText("Step 5 of 12")).toBeVisible();
	});

	test("Step 6: can skip certifications step", async ({ page }) => {
		const controller = await setupMidFlowMocks(page, "skills");
		controller.state.onboardingStep = "certifications";
		await page.goto("/onboarding");

		await expect(page.getByText("Step 6 of 12")).toBeVisible();

		await page
			.locator(ONBOARDING_NAV)
			.getByRole("button", { name: "Skip" })
			.click();
		await expect(page.getByText("Step 7 of 12")).toBeVisible();
	});

	test("Step 10: shows review card when voice profile exists", async ({
		page,
	}) => {
		const controller = await setupMidFlowMocks(page, "growth-targets");
		controller.state.onboardingStep = "voice-profile";
		await page.goto("/onboarding");

		await expect(page.getByText("Step 10 of 12")).toBeVisible();
		// Voice profile data exists, so review card should appear
		await expect(page.getByTestId("voice-profile-review")).toBeVisible();
		await expect(page.getByText("Looks good!")).toBeVisible();
		await expect(page.getByText("Let me edit")).toBeVisible();
	});

	test("Step 11: displays all 10 review sections", async ({ page }) => {
		const controller = await setupMidFlowMocks(page, "voice-profile");
		controller.state.onboardingStep = "review";
		await page.goto("/onboarding");

		await expect(page.getByText("Step 11 of 12")).toBeVisible();

		// All 10 sections should be present
		const sectionKeys = [
			"basic-info",
			"professional-overview",
			"work-history",
			"education",
			"skills",
			"certifications",
			"achievement-stories",
			"non-negotiables",
			"growth-targets",
			"voice-profile",
		];

		for (const key of sectionKeys) {
			await expect(page.getByTestId(`review-section-${key}`)).toBeVisible();
		}
	});
});

// ---------------------------------------------------------------------------
// D. Step 12 Completion
// ---------------------------------------------------------------------------

test.describe("Step 12 Completion", () => {
	test("creates base resume with checkboxes defaulted to checked", async ({
		page,
	}) => {
		const controller = await setupMidFlowMocks(page, "review");
		controller.state.onboardingStep = "base-resume";
		await page.goto("/onboarding");

		await expect(page.getByText("Step 12 of 12")).toBeVisible();
		await expect(page.getByText("Base Resume Setup")).toBeVisible();

		// All job checkboxes should be checked by default
		const jobCheckboxes = page.locator('[data-testid^="job-checkbox-"]');
		const jobCount = await jobCheckboxes.count();
		expect(jobCount).toBeGreaterThan(0);

		for (let i = 0; i < jobCount; i++) {
			await expect(jobCheckboxes.nth(i)).toBeChecked();
		}
	});

	test("redirects to dashboard after completion", async ({ page }) => {
		const controller = await setupMidFlowMocks(page, "review");
		controller.state.onboardingStep = "base-resume";
		await page.goto("/onboarding");

		await expect(page.getByText("Step 12 of 12")).toBeVisible();

		// Fill required fields
		await page.getByLabel("Resume Name").fill("My Resume");
		await page.getByLabel("Role Type").fill("Software Engineer");
		await page.getByLabel("Summary").fill("Experienced software engineer");

		await page.getByTestId("submit-button").click();

		// Should redirect to dashboard
		await expect(page).toHaveURL("/");
	});
});

// ---------------------------------------------------------------------------
// E. Checkpoint Resume
// ---------------------------------------------------------------------------

test.describe("Checkpoint Resume", () => {
	test("shows resume prompt when returning to mid-onboarding persona", async ({
		page,
	}) => {
		const controller = new OnboardingMockController({
			hasPersona: true,
			onboardingComplete: false,
			onboardingStep: "skills",
		});
		await controller.setupRoutes(page);
		await page.goto("/onboarding");

		// Provider should detect mid-flow and show a resume prompt
		// The exact UI depends on the provider — we check that the step counter
		// shows the resumed step (step 5 for "skills")
		await expect(page.getByText("Step 5 of 12")).toBeVisible();
	});

	test("resumes at correct step after checkpoint load", async ({ page }) => {
		const controller = new OnboardingMockController({
			hasPersona: true,
			onboardingComplete: false,
			onboardingStep: "non-negotiables",
			workHistoryCount: 2,
			skillCount: 3,
			storyCount: 3,
			hasEducation: true,
			hasCertifications: true,
		});
		await controller.setupRoutes(page);
		await page.goto("/onboarding");

		// Should resume at step 8 (non-negotiables)
		await expect(page.getByText("Step 8 of 12")).toBeVisible();
		await expect(page.getByText("Non-Negotiables")).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// F. Navigation
// ---------------------------------------------------------------------------

test.describe("Navigation", () => {
	test("progress bar updates as steps advance", async ({ page }) => {
		await setupNewOnboardingMocks(page);
		await page.goto("/onboarding");

		// Step 1: progress should be ~8% (1/12)
		const progressBar = page.locator('[role="progressbar"]');
		await expect(progressBar).toBeVisible();
		const step1Value = await progressBar.getAttribute("aria-valuenow");

		// Skip to step 2
		await page.getByText(SKIP_MANUAL_ENTRY).click();
		await expect(page.getByText("Step 2 of 12")).toBeVisible();

		// Progress should have increased
		const step2Value = await progressBar.getAttribute("aria-valuenow");
		expect(Number(step2Value)).toBeGreaterThan(Number(step1Value));
	});

	test("back button hidden at step 1", async ({ page }) => {
		await setupNewOnboardingMocks(page);
		await page.goto("/onboarding");

		await expect(page.getByText("Step 1 of 12")).toBeVisible();

		// Shell's onBack is undefined at step 1, so Back button should not be visible
		const shellNav = page.locator(ONBOARDING_NAV);
		await expect(
			shellNav.getByRole("button", { name: "Back" }),
		).not.toBeVisible();
	});
});
