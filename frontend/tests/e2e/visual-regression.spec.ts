/**
 * Visual regression tests — baseline screenshots for key pages.
 *
 * Captures toHaveScreenshot() baselines at a fixed 1280x720 viewport.
 * Baselines are generated inside Docker for OS-consistent rendering
 * (see docker/docker-compose.playwright.yml).
 *
 * Generate/update baselines:  cd frontend && npm run test:e2e:visual:update
 * Run comparison tests:       cd frontend && npm run test:e2e:visual
 *
 * Baselines live in tests/__screenshots__/{projectName}/... and MUST be
 * committed to git. Regenerate after any UI change that affects screenshots.
 */

import { expect, test } from "./base-test";

import { setupApplicationsListMocks } from "../utils/app-tracking-api-mocks";
import {
	JOB_POSTING_ID,
	setupGhostwriterReviewMocks,
} from "../utils/ghostwriter-api-mocks";
import { setupDashboardMocks } from "../utils/job-discovery-api-mocks";
import { setupBasicInfoEditorMocks } from "../utils/persona-update-api-mocks";
import {
	BASE_RESUME_IDS,
	setupResumeListMocks,
} from "../utils/resume-api-mocks";
import { setupSettingsMocks } from "../utils/settings-api-mocks";

// ---------------------------------------------------------------------------
// Constants — test IDs
// ---------------------------------------------------------------------------

const TID_LANDING_PAGE = "landing-page";
const TID_LOGIN_SUBMIT = "login-submit";
const TID_REGISTER_SUBMIT = "register-submit";
const TID_DASHBOARD_TABS = "dashboard-tabs";
const TID_BASIC_INFO_FORM = "basic-info-editor-form";
const TID_RESUME_LIST = "resume-list";
const TID_RESUME_DETAIL = "resume-detail";
const TID_APPLICATIONS_LIST = "applications-list";
const TID_SETTINGS_PAGE = "settings-page";
const TID_GHOSTWRITER_REVIEW = "ghostwriter-review";

// ---------------------------------------------------------------------------
// Viewport — all visual regression tests use a fixed desktop viewport
// ---------------------------------------------------------------------------

test.use({ viewport: { width: 1280, height: 720 } });

// ---------------------------------------------------------------------------
// Public Pages (unauthenticated)
// ---------------------------------------------------------------------------

test.describe("Visual Regression — Public Pages", () => {
	test.beforeEach(async ({ page }) => {
		await page.context().clearCookies();

		// Override base-test /auth/me mock → 401 so AuthProvider
		// sets status="unauthenticated" and pages render public layout.
		await page.route(/\/api\/v1\/auth\/me/, async (route) => {
			await route.fulfill({ status: 401, body: "Unauthorized" });
		});
	});

	test("landing page", async ({ page }) => {
		await page.goto("/", { waitUntil: "networkidle" });
		await expect(page.getByTestId(TID_LANDING_PAGE)).toBeVisible();
		await expect(page).toHaveScreenshot("landing-desktop.png");
	});

	test("login page", async ({ page }) => {
		await page.goto("/login", { waitUntil: "networkidle" });
		await expect(page.getByTestId(TID_LOGIN_SUBMIT)).toBeVisible();
		await expect(page).toHaveScreenshot("login-desktop.png");
	});

	test("register page", async ({ page }) => {
		await page.goto("/register", { waitUntil: "networkidle" });
		await expect(page.getByTestId(TID_REGISTER_SUBMIT)).toBeVisible();
		await expect(page).toHaveScreenshot("register-desktop.png");
	});
});

// ---------------------------------------------------------------------------
// Authenticated Pages (mock controllers provide API data)
// ---------------------------------------------------------------------------

test.describe("Visual Regression — Authenticated Pages", () => {
	test("dashboard", async ({ page }) => {
		await setupDashboardMocks(page);
		await page.goto("/dashboard", { waitUntil: "networkidle" });
		await expect(page.getByTestId(TID_DASHBOARD_TABS)).toBeVisible();
		await expect(page).toHaveScreenshot("dashboard-desktop.png");
	});

	test("persona basic info", async ({ page }) => {
		await setupBasicInfoEditorMocks(page);
		await page.goto("/persona/basic-info", { waitUntil: "networkidle" });
		await expect(page.getByTestId(TID_BASIC_INFO_FORM)).toBeVisible();
		await expect(page).toHaveScreenshot("persona-basic-info-desktop.png");
	});

	test("resume list", async ({ page }) => {
		await setupResumeListMocks(page);
		await page.goto("/resumes", { waitUntil: "networkidle" });
		await expect(page.getByTestId(TID_RESUME_LIST)).toBeVisible();
		await expect(page).toHaveScreenshot("resumes-desktop.png");
	});

	test("resume detail", async ({ page }) => {
		await setupResumeListMocks(page);
		await page.goto(`/resumes/${BASE_RESUME_IDS[0]}`, {
			waitUntil: "networkidle",
		});
		await expect(page.getByTestId(TID_RESUME_DETAIL)).toBeVisible();
		await expect(page).toHaveScreenshot("resume-detail-desktop.png");
	});

	test("applications", async ({ page }) => {
		await setupApplicationsListMocks(page);
		await page.goto("/applications", { waitUntil: "networkidle" });
		await expect(page.getByTestId(TID_APPLICATIONS_LIST)).toBeVisible();
		await expect(page).toHaveScreenshot("applications-desktop.png");
	});

	test("settings", async ({ page }) => {
		await setupSettingsMocks(page);
		await page.goto("/settings", { waitUntil: "networkidle" });
		await expect(page.getByTestId(TID_SETTINGS_PAGE)).toBeVisible();
		await expect(page).toHaveScreenshot("settings-desktop.png");
	});

	test("ghostwriter review", async ({ page }) => {
		await setupGhostwriterReviewMocks(page);
		await page.goto(`/jobs/${JOB_POSTING_ID}/review`, {
			waitUntil: "networkidle",
		});
		await expect(page.getByTestId(TID_GHOSTWRITER_REVIEW)).toBeVisible();
		await expect(page).toHaveScreenshot("ghostwriter-review-desktop.png");
	});
});
