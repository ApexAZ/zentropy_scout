/**
 * E2E tests for persona sub-entity CRUD editors.
 *
 * REQ-012 §7.2: Post-onboarding editors for work history, education,
 * certifications, achievement stories, voice profile, non-negotiables,
 * and discovery preferences with add/delete support. CRUD editors use
 * the delete-with-references flow (reference check → DELETE).
 * All API calls are mocked via Playwright's page.route() — no real backend.
 */

import { expect, test } from "@playwright/test";

import {
	CERT_ID,
	CUSTOM_FILTER_IDS,
	EDUCATION_ID,
	PERSONA_ID,
	setupAchievementStoriesEditorMocks,
	setupDiscoveryPreferencesEditorMocks,
	setupNonNegotiablesEditorMocks,
	setupPersonaEditorCrudMocks,
	setupVoiceProfileEditorMocks,
	STORY_IDS,
	WORK_HISTORY_IDS,
} from "../utils/persona-update-api-mocks";
import { removeDevToolsOverlay } from "../utils/playwright-helpers";

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

// ---------------------------------------------------------------------------
// D. Achievement Stories Editor (3 tests)
// ---------------------------------------------------------------------------

test.describe("Achievement Stories Editor", () => {
	test("displays achievement stories with skill tags", async ({ page }) => {
		await setupAchievementStoriesEditorMocks(page);
		await page.goto("/persona/achievement-stories");

		// Mock data: 3 stories — verify titles visible (use heading role to
		// avoid strict mode violations from action text containing the title)
		await expect(
			page.getByRole("heading", { name: "Microservices Migration" }),
		).toBeVisible();
		await expect(
			page.getByRole("heading", { name: "Mentoring Program" }),
		).toBeVisible();
		await expect(
			page.getByRole("heading", { name: "Real-time Pipeline" }),
		).toBeVisible();

		// Skill tags should be resolved and displayed on story cards
		await expect(page.getByText("TypeScript")).toBeVisible();
		await expect(page.getByText("Leadership")).toBeVisible();
	});

	test("add a new story via form", async ({ page }) => {
		await setupAchievementStoriesEditorMocks(page);
		await page.goto("/persona/achievement-stories");

		await page.getByRole("button", { name: "Add story" }).click();
		await expect(page.getByTestId("story-form")).toBeVisible();

		// Fill required fields
		await page.getByLabel("Story Title").fill("API Redesign");
		await page
			.getByLabel("Context")
			.fill("Legacy REST API was hard to maintain");
		await page.getByLabel("What did you do?").fill("Led full API redesign");
		await page.getByLabel("Outcome").fill("50% fewer support tickets");

		// Listen for POST
		const postPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/personas/${PERSONA_ID}/achievement-stories`) &&
				!res.url().includes("/references") &&
				res.request().method() === "POST",
		);

		await page.getByRole("button", { name: "Save" }).click();

		const response = await postPromise;
		expect(response.status()).toBe(201);

		// Form should disappear
		await expect(page.getByTestId("story-form")).not.toBeVisible();
	});

	test("delete a story", async ({ page }) => {
		await setupAchievementStoriesEditorMocks(page);
		await page.goto("/persona/achievement-stories");

		// Verify entry exists
		await expect(page.getByText("Microservices Migration")).toBeVisible();

		// Listen for DELETE
		const deletePromise = page.waitForResponse(
			(res) =>
				res
					.url()
					.includes(
						`/personas/${PERSONA_ID}/achievement-stories/${STORY_IDS[0]}`,
					) &&
				!res.url().includes("/references") &&
				res.request().method() === "DELETE",
		);

		// aria-label is "Delete ${entry.title}"
		await page
			.getByRole("button", { name: "Delete Microservices Migration" })
			.click();

		const response = await deletePromise;
		expect(response.status()).toBe(204);

		// Card's delete button should be gone
		await expect(
			page.getByRole("button", { name: "Delete Microservices Migration" }),
		).not.toBeAttached();
	});
});

// ---------------------------------------------------------------------------
// E. Voice Profile Editor (2 tests)
// ---------------------------------------------------------------------------

test.describe("Voice Profile Editor", () => {
	test("displays pre-filled voice profile form", async ({ page }) => {
		await setupVoiceProfileEditorMocks(page);
		await page.goto("/persona/voice-profile");

		// Form should be visible with pre-filled values from mock data
		await expect(page.getByTestId("voice-profile-editor-form")).toBeVisible();
		await expect(page.getByLabel("Tone")).toHaveValue(
			"Direct, confident, avoids buzzwords",
		);
		await expect(page.getByLabel("Style")).toHaveValue(
			"Short sentences, active voice",
		);
		await expect(page.getByLabel("Vocabulary")).toHaveValue(
			"Technical when relevant, plain otherwise",
		);
	});

	test("saves voice profile changes", async ({ page }) => {
		await setupVoiceProfileEditorMocks(page);
		await page.goto("/persona/voice-profile");

		// Wait for form to be populated
		await expect(page.getByLabel("Tone")).toHaveValue(
			"Direct, confident, avoids buzzwords",
		);

		// Modify tone field
		await page.getByLabel("Tone").fill("Casual and approachable");

		// Remove TanStack Query devtools — its floating toggle SVG at the page
		// bottom intercepts pointer events on the Save button
		await removeDevToolsOverlay(page);

		// Listen for PATCH
		const patchPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/personas/${PERSONA_ID}/voice-profile`) &&
				res.request().method() === "PATCH",
		);

		await page.getByRole("button", { name: "Save" }).click();

		const response = await patchPromise;
		expect(response.status()).toBe(200);

		// Success message should appear
		await expect(page.getByTestId("save-success")).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// F. Non-Negotiables Editor (3 tests)
// ---------------------------------------------------------------------------

test.describe("Non-Negotiables Editor", () => {
	test("displays pre-filled non-negotiables form", async ({ page }) => {
		await setupNonNegotiablesEditorMocks(page);
		await page.goto("/persona/non-negotiables");

		// Form should be visible
		await expect(page.getByTestId("non-negotiables-editor-form")).toBeVisible();

		// Verify pre-filled values from persona mock data
		await expect(page.getByRole("radio", { name: "Hybrid OK" })).toBeChecked();
		await expect(page.getByText("San Francisco")).toBeVisible();
		await expect(page.getByText("Oakland")).toBeVisible();
		await expect(page.getByLabel("Max Commute (minutes)")).toHaveValue("45");
		await expect(page.getByLabel("Minimum Base Salary")).toHaveValue("180000");

		// Custom filters should be visible
		await expect(page.getByText("No defense contractors")).toBeVisible();
		await expect(page.getByText("Must have 401k")).toBeVisible();
	});

	test("add a custom filter via form", async ({ page }) => {
		await setupNonNegotiablesEditorMocks(page);
		await page.goto("/persona/non-negotiables");

		// Wait for custom filters to load
		await expect(page.getByText("No defense contractors")).toBeVisible();

		await page.getByRole("button", { name: "Add filter" }).click();
		await expect(page.getByTestId("custom-filter-form")).toBeVisible();

		// Fill the custom filter form
		const filterForm = page.getByTestId("custom-filter-form");
		await filterForm.getByLabel("Filter Name").fill("No gambling companies");
		await filterForm.getByRole("radio", { name: "Exclude" }).check();
		await filterForm.getByLabel("Field to Check").selectOption("company_name");
		await filterForm.getByLabel("Value to Match").fill("DraftKings");

		// Remove TanStack Query devtools — intercepts pointer events on Save
		await removeDevToolsOverlay(page);

		// Listen for POST
		const postPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/personas/${PERSONA_ID}/custom-non-negotiables`) &&
				!res.url().includes("/references") &&
				res.request().method() === "POST",
		);

		await filterForm.getByRole("button", { name: "Save" }).click();

		const response = await postPromise;
		expect(response.status()).toBe(201);

		// Form should disappear
		await expect(page.getByTestId("custom-filter-form")).not.toBeVisible();
	});

	test("delete a custom filter", async ({ page }) => {
		await setupNonNegotiablesEditorMocks(page);
		await page.goto("/persona/non-negotiables");

		// Verify filter exists
		await expect(page.getByText("No defense contractors")).toBeVisible();

		// Listen for DELETE (custom filters use a confirmation dialog instead
		// of the reference-check flow, so no /references filter needed)
		const deletePromise = page.waitForResponse(
			(res) =>
				res
					.url()
					.includes(
						`/personas/${PERSONA_ID}/custom-non-negotiables/${CUSTOM_FILTER_IDS[0]}`,
					) && res.request().method() === "DELETE",
		);

		// aria-label is "Delete {filter_name}"
		await page
			.getByRole("button", { name: "Delete No defense contractors" })
			.click();

		// Confirmation dialog should appear
		await page.getByRole("button", { name: "Delete" }).click();

		const response = await deletePromise;
		expect(response.status()).toBe(204);

		// Filter card should be gone
		await expect(
			page.getByRole("button", {
				name: "Delete No defense contractors",
			}),
		).not.toBeAttached();
	});
});

// ---------------------------------------------------------------------------
// G. Discovery Preferences Editor (3 tests)
// ---------------------------------------------------------------------------

test.describe("Discovery Preferences Editor", () => {
	test("displays pre-filled discovery preferences form", async ({ page }) => {
		await setupDiscoveryPreferencesEditorMocks(page);
		await page.goto("/persona/discovery");

		// Form should be visible
		await expect(
			page.getByTestId("discovery-preferences-editor-form"),
		).toBeVisible();

		// Verify pre-filled slider values (persona has minimum_fit=60, auto_draft=80)
		await expect(page.getByLabel("Minimum Fit Threshold")).toHaveValue("60");
		await expect(page.getByLabel("Auto-Draft Threshold")).toHaveValue("80");

		// Verify polling frequency
		await expect(page.getByLabel("Polling Frequency")).toHaveValue("Daily");

		// No threshold warning should be shown (auto_draft > minimum_fit)
		await expect(page.getByTestId("threshold-warning")).not.toBeAttached();
	});

	test("shows cross-field warning when auto-draft < minimum fit", async ({
		page,
	}) => {
		await setupDiscoveryPreferencesEditorMocks(page);
		await page.goto("/persona/discovery");

		// Wait for form to be populated
		await expect(page.getByLabel("Minimum Fit Threshold")).toHaveValue("60");

		// Set auto-draft below minimum fit to trigger warning
		await page.getByLabel("Auto-Draft Threshold").fill("40");

		await expect(page.getByTestId("threshold-warning")).toBeVisible();
		await expect(page.getByTestId("threshold-warning")).toContainText(
			"Auto-draft threshold is below your fit threshold",
		);
	});

	test("saves discovery preferences changes", async ({ page }) => {
		await setupDiscoveryPreferencesEditorMocks(page);
		await page.goto("/persona/discovery");

		// Wait for form to be populated
		await expect(page.getByLabel("Minimum Fit Threshold")).toHaveValue("60");

		// Change polling frequency
		await page.getByLabel("Polling Frequency").selectOption("Weekly");

		// Remove TanStack Query devtools overlay if needed
		await removeDevToolsOverlay(page);

		// Listen for PATCH
		const patchPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/personas/${PERSONA_ID}`) &&
				!res.url().includes("/custom-non-negotiables") &&
				!res.url().includes("/voice-profile") &&
				res.request().method() === "PATCH",
		);

		await page.getByRole("button", { name: "Save" }).click();

		const response = await patchPromise;
		expect(response.status()).toBe(200);

		// Success message should appear
		await expect(page.getByTestId("save-success")).toBeVisible();
	});
});
