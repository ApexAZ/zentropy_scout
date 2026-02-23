/**
 * E2E tests for the job discovery flow.
 *
 * REQ-012 §8: Dashboard tabs, opportunities table, job detail, mark as applied.
 * All API calls are mocked via Playwright's page.route() — no real backend.
 */

import { expect, test } from "@playwright/test";

import {
	APPLICATION_ID,
	JOB_IDS,
	JobDiscoveryMockController,
	PERSONA_JOB_IDS,
	setupAlreadyAppliedMocks,
	setupDashboardMocks,
	setupJobDetailMocks,
} from "../utils/job-discovery-api-mocks";

// ---------------------------------------------------------------------------
// Shared constants
// ---------------------------------------------------------------------------

const JOB_001_ID = JOB_IDS[0]; // Standard scored job (shared pool ID)
const JOB_003_ID = JOB_IDS[2]; // High ghost risk (shared pool ID)
const PJ_001_ID = PERSONA_JOB_IDS[0]; // Persona-job wrapper for job-001
const PJ_003_ID = PERSONA_JOB_IDS[2]; // Persona-job wrapper for job-003
const PJ_005_ID = PERSONA_JOB_IDS[4]; // Persona-job wrapper for job-005

// ---------------------------------------------------------------------------
// A. Dashboard Loading
// ---------------------------------------------------------------------------

test.describe("Dashboard Loading", () => {
	test("dashboard loads with Opportunities tab active", async ({ page }) => {
		await setupDashboardMocks(page);
		await page.goto("/");

		await expect(page.getByTestId("dashboard-tabs")).toBeVisible();
		await expect(page.getByTestId("tab-content-opportunities")).toBeVisible();
		await expect(
			page.getByRole("tab", { name: "Opportunities" }),
		).toHaveAttribute("data-state", "active");
	});

	test("tab navigation persists in URL", async ({ page }) => {
		await setupDashboardMocks(page);
		await page.goto("/");

		// Click "In Progress" tab
		await page.getByRole("tab", { name: "In Progress" }).click();
		await expect(page).toHaveURL(/\?tab=in-progress/);
		await expect(page.getByTestId("tab-content-in-progress")).toBeVisible();

		// Click "History" tab
		await page.getByRole("tab", { name: "History" }).click();
		await expect(page).toHaveURL(/\?tab=history/);
		await expect(page.getByTestId("tab-content-history")).toBeVisible();
	});

	test("empty state when no jobs", async ({ page }) => {
		const controller = new JobDiscoveryMockController({ jobCount: 0 });
		await controller.setupRoutes(page);
		await page.goto("/");

		await expect(page.getByText("No opportunities found.")).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// B. Opportunities Table
// ---------------------------------------------------------------------------

test.describe("Opportunities Table", () => {
	test("displays job list with titles and scores", async ({ page }) => {
		await setupDashboardMocks(page);
		await page.goto("/");

		// Verify job titles visible (job-004 is filtered, hidden by default)
		await expect(page.getByText("Senior Software Engineer")).toBeVisible();
		await expect(page.getByText("Full Stack Developer")).toBeVisible();
		await expect(page.getByText("Platform Engineer")).toBeVisible();
		await expect(page.getByText("Junior Developer")).toBeVisible();

		// Ghost warning icon on job-003 (ghost_score=82) — testid uses persona job ID
		await expect(page.getByTestId(`ghost-warning-${PJ_003_ID}`)).toBeVisible();
	});

	test("clicking job row navigates to detail", async ({ page }) => {
		await setupDashboardMocks(page);
		await page.goto("/");

		// Click the row containing the first job title — URL uses persona job ID
		await page.getByText("Senior Software Engineer").click();
		await expect(page).toHaveURL(`/jobs/${PJ_001_ID}`);
		await expect(page.getByTestId("job-detail-header")).toBeVisible();
	});

	test("favorite toggle sends PATCH", async ({ page }) => {
		await setupDashboardMocks(page);
		await page.goto("/");

		// Wait for table to be visible
		await expect(page.getByTestId("opportunities-table")).toBeVisible();

		// Click favorite toggle — testid and PATCH URL use persona job ID
		const patchPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/job-postings/${PJ_001_ID}`) &&
				res.request().method() === "PATCH",
		);
		await page.getByTestId(`favorite-toggle-${PJ_001_ID}`).click();
		const response = await patchPromise;
		expect(response.status()).toBe(200);
	});

	test("show filtered toggle reveals dimmed filtered jobs", async ({
		page,
	}) => {
		await setupDashboardMocks(page);
		await page.goto("/");

		// job-004 (Backend Developer at LowPay Inc) should be hidden by default
		await expect(page.getByText("Backend Developer")).not.toBeVisible();

		// Check "Show filtered" checkbox
		await page.getByLabel("Show filtered jobs").check();

		// job-004 should now be visible
		await expect(page.getByText("Backend Developer")).toBeVisible();
	});

	test("bulk select and dismiss", async ({ page }) => {
		await setupDashboardMocks(page);
		await page.goto("/");

		// Enter select mode
		await page.getByTestId("select-mode-button").click();

		// Select first two row checkboxes
		const rowCheckboxes = page.getByLabel("Select row");
		await rowCheckboxes.nth(0).check();
		await rowCheckboxes.nth(1).check();

		// Verify selection count
		await expect(page.getByTestId("selected-count")).toContainText("2");

		// Click bulk dismiss
		const dismissPromise = page.waitForResponse(
			(res) =>
				res.url().includes("/job-postings/bulk-dismiss") &&
				res.request().method() === "POST",
		);
		await page.getByTestId("bulk-dismiss-button").click();
		const response = await dismissPromise;
		expect(response.status()).toBe(200);
	});
});

// ---------------------------------------------------------------------------
// C. Job Detail — Metadata & Scores
// ---------------------------------------------------------------------------

test.describe("Job Detail — Metadata & Scores", () => {
	test("displays job metadata", async ({ page }) => {
		await setupDashboardMocks(page);
		await page.goto(`/jobs/${JOB_001_ID}`);

		await expect(page.getByTestId("job-detail-header")).toBeVisible();
		// Title (use heading role to avoid matching description text)
		await expect(
			page.getByRole("heading", { name: "Senior Software Engineer" }),
		).toBeVisible();
		await expect(page.getByText("TechCorp")).toBeVisible();
		// Salary
		await expect(page.getByTestId("job-salary")).toBeVisible();
		// Status badge
		await expect(page.getByTestId("job-status-badge")).toBeVisible();
		// Back link
		await expect(page.getByTestId("back-to-jobs")).toBeVisible();
	});

	test("fit score breakdown is expandable", async ({ page }) => {
		await setupDashboardMocks(page);
		await page.goto(`/jobs/${JOB_001_ID}`);

		// Fit score toggle should be visible
		await expect(page.getByTestId("fit-score-toggle")).toBeVisible();

		// Click to expand
		await page.getByTestId("fit-score-toggle").click();

		// Panel with 5 component rows should be visible
		await expect(page.getByTestId("fit-score-panel")).toBeVisible();
		await expect(page.getByTestId("fit-component-hard_skills")).toBeVisible();
		await expect(page.getByTestId("fit-component-soft_skills")).toBeVisible();
		await expect(
			page.getByTestId("fit-component-experience_level"),
		).toBeVisible();
		await expect(page.getByTestId("fit-component-role_title")).toBeVisible();
		await expect(
			page.getByTestId("fit-component-location_logistics"),
		).toBeVisible();
	});

	test("stretch score breakdown is expandable", async ({ page }) => {
		await setupDashboardMocks(page);
		await page.goto(`/jobs/${JOB_001_ID}`);

		await expect(page.getByTestId("stretch-score-toggle")).toBeVisible();
		await page.getByTestId("stretch-score-toggle").click();

		await expect(page.getByTestId("stretch-score-panel")).toBeVisible();
		await expect(
			page.getByTestId("stretch-component-target_role"),
		).toBeVisible();
		await expect(
			page.getByTestId("stretch-component-target_skills"),
		).toBeVisible();
		await expect(
			page.getByTestId("stretch-component-growth_trajectory"),
		).toBeVisible();
	});

	test("ghost risk section with severity on high-risk job", async ({
		page,
	}) => {
		await setupDashboardMocks(page);
		await page.goto(`/jobs/${JOB_003_ID}`);

		await expect(page.getByTestId("ghost-risk-section")).toBeVisible();
		// Ghost score 82 → "High Risk" tier
		await expect(page.getByText("High Risk")).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// D. Job Detail — Content
// ---------------------------------------------------------------------------

test.describe("Job Detail — Content", () => {
	test("score explanation shows all sections", async ({ page }) => {
		await setupDashboardMocks(page);
		await page.goto(`/jobs/${JOB_001_ID}`);

		await expect(page.getByTestId("explanation-summary")).toBeVisible();
		await expect(page.getByTestId("explanation-strengths")).toBeVisible();
		await expect(page.getByTestId("explanation-gaps")).toBeVisible();
		await expect(page.getByTestId("explanation-stretch")).toBeVisible();
	});

	test("extracted skills shows required and preferred groups", async ({
		page,
	}) => {
		await setupDashboardMocks(page);
		await page.goto(`/jobs/${JOB_001_ID}`);

		await expect(page.getByTestId("skills-required-group")).toBeVisible();
		await expect(page.getByTestId("skills-preferred-group")).toBeVisible();

		// Verify individual skill chips
		await expect(page.getByTestId("skill-chip-es-001")).toBeVisible();
		await expect(page.getByTestId("skill-chip-es-002")).toBeVisible();
		await expect(page.getByTestId("skill-chip-es-003")).toBeVisible();
		await expect(page.getByTestId("skill-chip-es-004")).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// E. Mark as Applied Flow
// ---------------------------------------------------------------------------

test.describe("Mark as Applied Flow", () => {
	test("shows ready to apply card with download links", async ({ page }) => {
		await setupJobDetailMocks(page);
		await page.goto(`/jobs/${JOB_001_ID}`);

		await expect(page.getByTestId("mark-as-applied-card")).toBeVisible();
		await expect(page.getByTestId("resume-download-link")).toBeVisible();
		await expect(page.getByTestId("cover-letter-download-link")).toBeVisible();
		await expect(page.getByTestId("apply-external-link")).toBeVisible();
	});

	test("confirm applied creates application and redirects", async ({
		page,
	}) => {
		await setupJobDetailMocks(page);
		await page.goto(`/jobs/${JOB_001_ID}`);

		await expect(page.getByTestId("mark-as-applied-card")).toBeVisible();

		// Click confirm and wait for POST
		const postPromise = page.waitForResponse(
			(res) =>
				res.url().includes("/applications") &&
				res.request().method() === "POST",
		);
		await page.getByTestId("confirm-applied-button").click();
		const response = await postPromise;
		expect(response.status()).toBe(201);

		// Should redirect to application detail page
		await expect(page).toHaveURL(`/applications/${APPLICATION_ID}`);
	});

	test("shows already applied notice when application exists", async ({
		page,
	}) => {
		await setupAlreadyAppliedMocks(page);
		await page.goto(`/jobs/${JOB_001_ID}`);

		await expect(page.getByTestId("already-applied-notice")).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// F. Navigation & Tabs
// ---------------------------------------------------------------------------

test.describe("Navigation & Tabs", () => {
	test("back to jobs link works from detail page", async ({ page }) => {
		await setupDashboardMocks(page);
		await page.goto(`/jobs/${JOB_001_ID}`);

		await expect(page.getByTestId("back-to-jobs")).toBeVisible();
		await page.getByTestId("back-to-jobs").click();
		await expect(page).toHaveURL("/");
	});

	test("in progress tab shows applications table", async ({ page }) => {
		await setupDashboardMocks(page);
		await page.goto("/");

		await page.getByRole("tab", { name: "In Progress" }).click();
		await expect(page.getByTestId("tab-content-in-progress")).toBeVisible();
		await expect(page.getByTestId("applications-table")).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// G. Shared Pool & Actions (REQ-015 §8–§9)
// ---------------------------------------------------------------------------

test.describe("Shared Pool & Actions", () => {
	test("rescore button triggers POST /job-postings/rescore", async ({
		page,
	}) => {
		await setupDashboardMocks(page);
		await page.goto(`/jobs/${JOB_001_ID}`);

		const postPromise = page.waitForResponse(
			(res) =>
				res.url().includes("/job-postings/rescore") &&
				res.request().method() === "POST",
		);
		await page.getByRole("button", { name: "Rescore" }).click();
		const response = await postPromise;
		expect(response.status()).toBe(200);
	});

	test("dismiss button sends PATCH and redirects to dashboard", async ({
		page,
	}) => {
		await setupDashboardMocks(page);
		await page.goto(`/jobs/${JOB_001_ID}`);

		const patchPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/job-postings/${PJ_001_ID}`) &&
				res.request().method() === "PATCH",
		);
		await page.getByRole("button", { name: "Dismiss" }).click();
		const response = await patchPromise;
		expect(response.status()).toBe(200);

		// Component redirects to dashboard after dismissing
		await expect(page).toHaveURL("/");
	});

	test("undismiss button restores job to Discovered", async ({ page }) => {
		// Set up job-005 as Dismissed via status override
		const controller = new JobDiscoveryMockController({
			statusOverrides: new Map([[PJ_005_ID, "Dismissed"]]),
		});
		await controller.setupRoutes(page);
		await page.goto(`/jobs/${PJ_005_ID}`);

		// Job is Dismissed, so Undismiss button should be visible
		await expect(page.getByRole("button", { name: "Undismiss" })).toBeVisible();

		const patchPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/job-postings/${PJ_005_ID}`) &&
				res.request().method() === "PATCH",
		);
		await page.getByRole("button", { name: "Undismiss" }).click();
		const response = await patchPromise;
		expect(response.status()).toBe(200);
	});

	test("pool-discovered job displays identically to scouter-discovered", async ({
		page,
	}) => {
		await setupDashboardMocks(page);
		await page.goto("/");

		// job-005 (Junior Developer at SmallCo) has discovery_method="pool"
		// It should appear in the table with no distinction from scouter jobs
		await expect(page.getByText("Junior Developer")).toBeVisible();

		// Navigate to detail — should render normal detail page
		await page.getByText("Junior Developer").click();
		await expect(page).toHaveURL(`/jobs/${PJ_005_ID}`);
		await expect(
			page.getByRole("heading", { name: "Junior Developer" }),
		).toBeVisible();

		// No discovery method indicator visible to user
		await expect(page.getByText(/discovery.?method/i)).not.toBeVisible();
	});

	test("shared job data has no edit controls on detail page", async ({
		page,
	}) => {
		await setupDashboardMocks(page);
		await page.goto(`/jobs/${JOB_001_ID}`);

		// Shared data fields should be present
		await expect(
			page.getByRole("heading", { name: "Senior Software Engineer" }),
		).toBeVisible();
		await expect(page.getByText("TechCorp")).toBeVisible();

		// No edit button or link for shared data sections
		await expect(page.getByRole("button", { name: /edit/i })).not.toBeVisible();
		await expect(page.getByRole("link", { name: /edit/i })).not.toBeVisible();

		// Job description should be plain text, not in an input/textarea
		await expect(
			page.getByText("We are looking for a Senior Software Engineer", {
				exact: false,
			}),
		).toBeVisible();
	});

	test("dismissed job disappears from opportunities table", async ({
		page,
	}) => {
		await setupDashboardMocks(page);
		await page.goto("/");

		// Verify job-001 is initially visible
		await expect(page.getByText("Senior Software Engineer")).toBeVisible();

		// Navigate to detail and dismiss
		await page.getByText("Senior Software Engineer").click();
		await expect(page).toHaveURL(`/jobs/${PJ_001_ID}`);

		const patchPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/job-postings/${PJ_001_ID}`) &&
				res.request().method() === "PATCH",
		);
		await page.getByRole("button", { name: "Dismiss" }).click();
		await patchPromise;

		// Should redirect to dashboard
		await expect(page).toHaveURL("/");

		// Job should no longer appear in the table
		await expect(page.getByText("Senior Software Engineer")).not.toBeVisible();
	});
});
