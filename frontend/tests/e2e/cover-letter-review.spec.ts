/**
 * E2E tests for the cover letter review flow on the job detail page.
 *
 * REQ-012 §10.2: Cover letter review with agent reasoning, stories used,
 * editable textarea, word count indicator, and voice check badge.
 * REQ-012 §10.3: Validation display with error/warning banners.
 * REQ-012 §10.6: Approval and PDF download flow.
 * All API calls are mocked via Playwright's page.route() — no real backend.
 */

import { expect, test } from "@playwright/test";

import {
	AGENT_REASONING,
	COVER_LETTER_ID,
	JOB_POSTING_ID,
	setupDraftCoverLetterMocks,
	setupShortDraftMocks,
	setupValidationErrorMocks,
	setupValidationWarningMocks,
} from "../utils/cover-letter-api-mocks";

// ---------------------------------------------------------------------------
// A. Full render — header, reasoning, stories, word count, voice (1 test)
// ---------------------------------------------------------------------------

test.describe("Cover Letter Review — Full Render", () => {
	test("shows header, agent reasoning, stories, word count, and voice badge", async ({
		page,
	}) => {
		await setupDraftCoverLetterMocks(page);
		await page.goto(`/jobs/${JOB_POSTING_ID}`);

		// Cover letter section should appear with Draft status
		await expect(page.getByTestId("cover-letter-section")).toBeVisible();

		// CoverLetterReview rendered inline
		await expect(page.getByTestId("cover-letter-review")).toBeVisible();

		// Header with job title and company
		await expect(
			page.getByText("Cover Letter for: Frontend Engineer at AlphaTech"),
		).toBeVisible();

		// Agent reasoning panel
		await expect(page.getByTestId("agent-reasoning")).toBeVisible();
		await expect(page.getByText(AGENT_REASONING)).toBeVisible();

		// Stories used section with story titles and skill tags
		const storiesSection = page.getByTestId("stories-used");
		await expect(storiesSection).toBeVisible();
		await expect(
			storiesSection.getByText("Microservices Migration"),
		).toBeVisible();
		await expect(storiesSection.getByText("Mentoring Program")).toBeVisible();
		await expect(storiesSection.getByText("TypeScript")).toBeVisible();
		await expect(storiesSection.getByText("Leadership")).toBeVisible();

		// Word count indicator (in range for ~300-word default text)
		const wordCount = page.getByTestId("word-count");
		await expect(wordCount).toBeVisible();
		await expect(wordCount).toHaveAttribute("data-in-range", "true");

		// Voice check badge
		await expect(page.getByTestId("voice-check")).toBeVisible();
		await expect(page.getByTestId("voice-check")).toContainText(
			"Direct, confident",
		);
	});
});

// ---------------------------------------------------------------------------
// B. Editable textarea and word count (1 test)
// ---------------------------------------------------------------------------

test.describe("Cover Letter Review — Edit Body", () => {
	test("textarea is editable and word count tracks changes", async ({
		page,
	}) => {
		await setupDraftCoverLetterMocks(page);
		await page.goto(`/jobs/${JOB_POSTING_ID}`);

		await expect(page.getByTestId("cover-letter-review")).toBeVisible();

		// Textarea should contain the draft text
		const textarea = page.getByRole("textbox", { name: /cover letter/i });
		await expect(textarea).toBeVisible();
		await expect(textarea).not.toHaveAttribute("readonly");

		// Clear and type new short text
		await textarea.clear();
		await textarea.fill("Short replacement text.");

		// Word count should update and show out-of-range (amber)
		const wordCount = page.getByTestId("word-count");
		await expect(wordCount).toContainText("3");
		await expect(wordCount).toHaveAttribute("data-in-range", "false");
	});
});

// ---------------------------------------------------------------------------
// C. Word count indicator (1 test)
// ---------------------------------------------------------------------------

test.describe("Cover Letter Review — Word Count", () => {
	test("word count shows amber when text is below target range", async ({
		page,
	}) => {
		await setupShortDraftMocks(page);
		await page.goto(`/jobs/${JOB_POSTING_ID}`);

		await expect(page.getByTestId("cover-letter-review")).toBeVisible();

		// Short text (~20 words) should show out-of-range indicator
		const wordCount = page.getByTestId("word-count");
		await expect(wordCount).toBeVisible();
		await expect(wordCount).toHaveAttribute("data-in-range", "false");
	});
});

// ---------------------------------------------------------------------------
// D. Validation display (2 tests)
// ---------------------------------------------------------------------------

test.describe("Cover Letter Review — Validation", () => {
	test("shows error banner for error-severity validation issues", async ({
		page,
	}) => {
		await setupValidationErrorMocks(page);
		await page.goto(`/jobs/${JOB_POSTING_ID}`);

		await expect(page.getByTestId("cover-letter-review")).toBeVisible();

		// Error banner with red styling
		const errorBanner = page.getByTestId("validation-errors");
		await expect(errorBanner).toBeVisible();
		await expect(errorBanner).toContainText(
			"Cover letter is too short (minimum 250 words).",
		);
		await expect(errorBanner).toContainText("Contains blacklisted phrase.");
	});

	test("shows warning notice for warning-severity validation issues", async ({
		page,
	}) => {
		await setupValidationWarningMocks(page);
		await page.goto(`/jobs/${JOB_POSTING_ID}`);

		await expect(page.getByTestId("cover-letter-review")).toBeVisible();

		// Warning notice with amber styling
		const warningNotice = page.getByTestId("validation-warnings");
		await expect(warningNotice).toBeVisible();
		await expect(warningNotice).toContainText(
			"Company name not mentioned in opening paragraph.",
		);
	});
});

// ---------------------------------------------------------------------------
// E. Approval flow (1 test)
// ---------------------------------------------------------------------------

test.describe("Cover Letter Review — Approval", () => {
	test("approve sends PATCH and shows download link", async ({ page }) => {
		await setupDraftCoverLetterMocks(page);
		await page.goto(`/jobs/${JOB_POSTING_ID}`);

		await expect(page.getByTestId("cover-letter-review")).toBeVisible();

		// Approve button should be visible for Draft status
		const approveButton = page.getByRole("button", { name: "Approve" });
		await expect(approveButton).toBeVisible();

		// No download link before approval
		await expect(page.getByTestId("download-pdf")).not.toBeVisible();

		// Set up PATCH listener
		const patchPromise = page.waitForResponse(
			(res) =>
				res.url().includes(`/cover-letters/${COVER_LETTER_ID}`) &&
				res.request().method() === "PATCH",
		);

		// Click Approve
		await approveButton.click();

		// Verify PATCH sent with status Approved
		const response = await patchPromise;
		expect(response.status()).toBe(200);
		const body = response.request().postDataJSON();
		expect(body).toMatchObject({ status: "Approved" });

		// After approval, download PDF link should appear
		await expect(page.getByTestId("download-pdf")).toBeVisible();

		// Approve button should be gone
		await expect(
			page.getByRole("button", { name: "Approve" }),
		).not.toBeVisible();

		// Textarea should be read-only
		const textarea = page.getByRole("textbox", { name: /cover letter/i });
		await expect(textarea).toHaveAttribute("readonly");
	});
});

// ---------------------------------------------------------------------------
// F. PDF download (1 test)
// ---------------------------------------------------------------------------

test.describe("Cover Letter Review — PDF Download", () => {
	test("download link has correct href after approval", async ({ page }) => {
		await setupDraftCoverLetterMocks(page);
		await page.goto(`/jobs/${JOB_POSTING_ID}`);

		await expect(page.getByTestId("cover-letter-review")).toBeVisible();

		// Approve first
		await page.getByRole("button", { name: "Approve" }).click();

		// Wait for download link
		const downloadLink = page.getByTestId("download-pdf");
		await expect(downloadLink).toBeVisible();

		// Verify href points to correct PDF endpoint
		await expect(downloadLink).toHaveAttribute(
			"href",
			new RegExp(`/submitted-cover-letter-pdfs/${COVER_LETTER_ID}/download`),
		);
	});
});

// ---------------------------------------------------------------------------
// G. Agent reasoning toggle (1 test)
// ---------------------------------------------------------------------------

test.describe("Cover Letter Review — Agent Reasoning Toggle", () => {
	test("reasoning panel can be collapsed and expanded", async ({ page }) => {
		await setupDraftCoverLetterMocks(page);
		await page.goto(`/jobs/${JOB_POSTING_ID}`);

		await expect(page.getByTestId("cover-letter-review")).toBeVisible();

		// Reasoning should be visible initially
		await expect(page.getByText(AGENT_REASONING)).toBeVisible();

		// Click toggle to collapse
		await page.getByTestId("agent-reasoning-toggle").click();
		await expect(page.getByText(AGENT_REASONING)).not.toBeVisible();

		// Click toggle again to expand
		await page.getByTestId("agent-reasoning-toggle").click();
		await expect(page.getByText(AGENT_REASONING)).toBeVisible();
	});
});
