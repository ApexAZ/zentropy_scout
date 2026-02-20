/**
 * E2E tests for the settings page.
 *
 * REQ-012 §12: Job source toggles, inactive source styling,
 * agent configuration table, and about section.
 * All API calls are mocked via Playwright's page.route() — no real backend.
 */

import { expect, test } from "@playwright/test";

import {
	JOB_SOURCE_IDS,
	PREFERENCE_IDS,
	setupSettingsMocks,
} from "../utils/settings-api-mocks";

// ---------------------------------------------------------------------------
// A. Settings Page Layout (1 test)
// ---------------------------------------------------------------------------

test.describe("Settings Page Layout", () => {
	test("displays all four settings sections", async ({ page }) => {
		await setupSettingsMocks(page);
		await page.goto("/settings");

		await expect(page.getByTestId("settings-page")).toBeVisible();
		await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();

		// Four section cards
		await expect(page.getByTestId("settings-account")).toBeVisible();
		await expect(page.getByTestId("settings-job-sources")).toBeVisible();
		await expect(
			page.getByTestId("settings-agent-configuration"),
		).toBeVisible();
		await expect(page.getByTestId("settings-about")).toBeVisible();

		// About section static content
		await expect(page.getByText("Zentropy Scout v0.1.0")).toBeVisible();
		await expect(
			page.getByText("AI-Powered Job Application Assistant"),
		).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// B. Job Sources (3 tests)
// ---------------------------------------------------------------------------

test.describe("Job Sources", () => {
	test("displays source names with correct toggle states", async ({ page }) => {
		await setupSettingsMocks(page);
		await page.goto("/settings");

		const section = page.getByTestId("job-sources-section");
		await expect(section).toBeVisible();

		// 4 sources rendered
		await expect(
			page.getByTestId(`source-item-${JOB_SOURCE_IDS[0]}`),
		).toBeVisible();
		await expect(
			page.getByTestId(`source-item-${JOB_SOURCE_IDS[1]}`),
		).toBeVisible();
		await expect(
			page.getByTestId(`source-item-${JOB_SOURCE_IDS[2]}`),
		).toBeVisible();
		await expect(
			page.getByTestId(`source-item-${JOB_SOURCE_IDS[3]}`),
		).toBeVisible();

		// Source names visible
		await expect(page.getByText("Adzuna")).toBeVisible();
		await expect(page.getByText("The Muse")).toBeVisible();
		await expect(page.getByText("RemoteOK")).toBeVisible();
		await expect(page.getByText("Chrome Extension")).toBeVisible();

		// Toggle states: Adzuna=enabled, The Muse=disabled, RemoteOK=enabled
		const adzunaToggle = page.getByRole("switch", {
			name: "Toggle Adzuna",
		});
		await expect(adzunaToggle).toBeChecked();

		const museToggle = page.getByRole("switch", {
			name: "Toggle The Muse",
		});
		await expect(museToggle).not.toBeChecked();

		const remoteToggle = page.getByRole("switch", {
			name: "Toggle RemoteOK",
		});
		await expect(remoteToggle).toBeChecked();
	});

	test("toggling a source sends PATCH and shows toast", async ({ page }) => {
		await setupSettingsMocks(page);
		await page.goto("/settings");

		await expect(page.getByTestId("job-sources-section")).toBeVisible();

		// Set up PATCH listener for disabling Adzuna
		const patchPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/user-source-preferences/${PREFERENCE_IDS[0]}`) &&
				res.request().method() === "PATCH",
		);

		// Click Adzuna toggle (currently enabled → disable)
		await page.getByRole("switch", { name: "Toggle Adzuna" }).click();

		// Verify PATCH sent with is_enabled: false
		const response = await patchPromise;
		expect(response.status()).toBe(200);
		const body = response.request().postDataJSON();
		expect(body).toMatchObject({ is_enabled: false });

		// Verify success toast
		await expect(page.getByText("Adzuna disabled.")).toBeVisible();
	});

	test("inactive source is grayed out with disabled toggle", async ({
		page,
	}) => {
		await setupSettingsMocks(page);
		await page.goto("/settings");

		await expect(page.getByTestId("job-sources-section")).toBeVisible();

		// Chrome Extension (is_active=false) should have opacity-50
		const extensionItem = page.getByTestId(`source-item-${JOB_SOURCE_IDS[3]}`);
		await expect(extensionItem).toBeVisible();
		await expect(extensionItem).toHaveClass(/opacity-50/);

		// Toggle should be disabled
		const extensionToggle = page.getByRole("switch", {
			name: "Toggle Chrome Extension",
		});
		await expect(extensionToggle).toBeDisabled();
	});
});

// ---------------------------------------------------------------------------
// C. Agent Configuration (1 test)
// ---------------------------------------------------------------------------

test.describe("Agent Configuration", () => {
	test("displays model routing table and provider info", async ({ page }) => {
		await setupSettingsMocks(page);
		await page.goto("/settings");

		const section = page.getByTestId("agent-configuration-section");
		await expect(section).toBeVisible();

		// "Model Routing · read-only" label
		await expect(section).toContainText("Model Routing");
		await expect(section).toContainText("read-only");

		// 3 routing rows with correct categories and models
		await expect(page.getByTestId("routing-row-chat-onboarding")).toContainText(
			"Chat / Onboarding",
		);
		await expect(page.getByTestId("routing-row-chat-onboarding")).toContainText(
			"Claude 3.5 Sonnet",
		);

		await expect(
			page.getByTestId("routing-row-scouter-ghost-detection"),
		).toContainText("Scouter / Ghost Detection");
		await expect(
			page.getByTestId("routing-row-scouter-ghost-detection"),
		).toContainText("Claude 3.5 Haiku");

		await expect(
			page.getByTestId("routing-row-scoring-generation"),
		).toContainText("Scoring / Generation");
		await expect(
			page.getByTestId("routing-row-scoring-generation"),
		).toContainText("Claude 3.5 Sonnet");

		// Provider info
		await expect(section).toContainText("Local (Claude SDK)");
	});
});
