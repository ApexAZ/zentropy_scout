/**
 * E2E tests for PDF download and document export functionality.
 *
 * REQ-012 §9.2: Resume PDF preview with download.
 * REQ-026 §6.2, REQ-027 §4.5: Variant export as PDF/DOCX.
 * REQ-012 §10.6: Cover letter PDF download after approval.
 *
 * A. Resume Detail — PdfViewer toolbar download button
 * B. Variant Review — Export PDF and DOCX via window.open()
 * C. Cover Letter — Download PDF link after approval
 *
 * Note: Export and download links open new tabs (window.open / target="_blank").
 * Playwright's page.route() only applies to the originating page, not new tabs.
 * Export tests override window.open() to capture the target URL without opening
 * a new tab. Cover letter test removes target="_blank" to keep navigation on the
 * mock-routed page and verifies the response status and content type.
 */

import { expect, test, type Page } from "./base-test";

import {
	BASE_RESUME_IDS,
	JOB_VARIANT_IDS,
	setupResumeListMocks,
} from "../utils/resume-api-mocks";
import {
	COVER_LETTER_ID,
	JOB_POSTING_ID,
	setupDraftCoverLetterMocks,
} from "../utils/cover-letter-api-mocks";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const RESUME_DETAIL_URL = `/resumes/${BASE_RESUME_IDS[0]}`;
const VARIANT_REVIEW_URL = `/resumes/${BASE_RESUME_IDS[0]}/variants/${JOB_VARIANT_IDS[0]}/review`;
const COVER_LETTER_PAGE_URL = `/jobs/${JOB_POSTING_ID}`;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Inject a window.open() override that captures URLs instead of opening
 * new tabs. Must be called BEFORE page.goto() so it runs via addInitScript
 * before page JavaScript executes.
 */
async function captureWindowOpen(page: Page): Promise<void> {
	await page.addInitScript(`
		window.__testOpenUrls = [];
		window.open = function(url) {
			window.__testOpenUrls.push(String(url ?? ""));
			return null;
		};
	`);
}

/** Retrieve URLs captured by the window.open() override. */
async function getCapturedUrls(page: Page): Promise<string[]> {
	return page.evaluate(
		() => (globalThis as Record<string, unknown>).__testOpenUrls as string[],
	);
}

// ---------------------------------------------------------------------------
// A. Resume Detail — PDF Download (1 test)
// ---------------------------------------------------------------------------

test.describe("PDF Download — Resume Detail", () => {
	test("PdfViewer renders download control for rendered resume", async ({
		page,
	}) => {
		await setupResumeListMocks(page);
		await page.goto(RESUME_DETAIL_URL);

		// PDF Preview section visible (Scrum Master resume has rendered_at)
		await expect(
			page.getByRole("heading", { name: "PDF Preview" }),
		).toBeVisible();

		// PdfViewer shows either toolbar "Download PDF" button (when iframe
		// renders the PDF) or error-state "Download File" link (when iframe
		// fails — e.g., headless Firefox/WebKit can't render inline PDFs).
		// Both controls trigger a download of the same PDF file.
		const pdfViewer = page.locator('[data-slot="pdf-viewer"]');
		const downloadControl = pdfViewer
			.getByRole("button", { name: "Download PDF" })
			.or(pdfViewer.getByRole("link", { name: "Download File" }));
		await expect(downloadControl).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// B. Variant Review — Export (2 tests)
// ---------------------------------------------------------------------------

test.describe("PDF Download — Variant Export", () => {
	test("Export PDF button calls window.open with correct endpoint", async ({
		page,
	}) => {
		await captureWindowOpen(page);
		await setupResumeListMocks(page);

		await page.goto(VARIANT_REVIEW_URL);
		await expect(page.getByTestId("variant-review")).toBeVisible();

		await page.getByRole("button", { name: "Export PDF" }).click();

		const urls = await getCapturedUrls(page);
		expect(urls).toHaveLength(1);
		expect(urls[0]).toContain(`/job-variants/${JOB_VARIANT_IDS[0]}/export/pdf`);
	});

	test("Export DOCX button calls window.open with correct endpoint", async ({
		page,
	}) => {
		await captureWindowOpen(page);
		await setupResumeListMocks(page);

		await page.goto(VARIANT_REVIEW_URL);
		await expect(page.getByTestId("variant-review")).toBeVisible();

		await page.getByRole("button", { name: "Export DOCX" }).click();

		const urls = await getCapturedUrls(page);
		expect(urls).toHaveLength(1);
		expect(urls[0]).toContain(
			`/job-variants/${JOB_VARIANT_IDS[0]}/export/docx`,
		);
	});
});

// ---------------------------------------------------------------------------
// C. Cover Letter — PDF Download (1 test)
// ---------------------------------------------------------------------------

test.describe("PDF Download — Cover Letter", () => {
	test("download PDF link navigates to correct endpoint after approval", async ({
		page,
	}) => {
		await setupDraftCoverLetterMocks(page);
		await page.goto(COVER_LETTER_PAGE_URL);

		await expect(page.getByTestId("cover-letter-review")).toBeVisible();

		// Approve cover letter to reveal download link
		await page.getByRole("button", { name: "Approve" }).click();

		// Download link appears with new-tab behavior
		const downloadLink = page.getByTestId("download-pdf");
		await expect(downloadLink).toBeVisible();
		await expect(downloadLink).toHaveAttribute("target", "_blank");

		// Remove target="_blank" so the link navigates in-page where mock
		// routes are active. This tests that the href points to the correct
		// PDF download endpoint and the server responds with PDF content.
		await downloadLink.evaluate((el) => el.removeAttribute("target"));

		const responsePromise = page.waitForResponse(
			(res) =>
				res.url().includes("/submitted-cover-letter-pdfs/") &&
				res.url().includes("/download"),
		);
		await downloadLink.click();
		const response = await responsePromise;

		expect(response.url()).toContain(
			`/submitted-cover-letter-pdfs/${COVER_LETTER_ID}/download`,
		);
		expect(response.status()).toBe(200);
		expect(response.headers()["content-type"]).toContain("application/pdf");
	});
});
