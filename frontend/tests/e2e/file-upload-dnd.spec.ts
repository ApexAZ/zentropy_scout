/**
 * E2E tests for drag-and-drop file upload on the onboarding resume step.
 *
 * REQ-019 §7.2: Resume upload via drag-and-drop with PDF validation.
 *
 * The existing onboarding tests verify upload via the hidden file input
 * (setInputFiles). These tests cover the drag-and-drop path:
 * A. Valid PDF drop → active visual state → upload → auto-advance
 * B. Invalid file type (.docx) → client-side error
 * C. Oversized file (>10MB) → client-side error
 * D. Error retry → "Try again" resets to idle drop zone
 *
 * Note: Playwright does not support native drag-and-drop with files.
 * Tests use page.evaluate() to dispatch synthetic events with a mock
 * dataTransfer. Uses plain Event + Object.defineProperty instead of
 * DragEvent constructor for cross-browser compatibility (WebKit's
 * DragEvent constructor ignores the dataTransfer init parameter).
 */

import { expect, test, type Page } from "./base-test";

import { setupNewOnboardingMocks } from "../utils/onboarding-api-mocks";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ONBOARDING_URL = "/onboarding";
const DROP_ZONE_SELECTOR = '[data-testid="drop-zone"]';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Simulate dropping a file onto the onboarding drop zone.
 *
 * Dispatches a synthetic "drop" event with a mock dataTransfer containing
 * a File object. Uses plain Event + Object.defineProperty for cross-browser
 * compatibility (WebKit's DragEvent constructor ignores dataTransfer).
 */
async function simulateFileDrop(
	page: Page,
	options: {
		fileName: string;
		mimeType: string;
		content?: string;
		/** Override File.size for testing size validation without large allocations. */
		sizeOverride?: number;
	},
): Promise<void> {
	await page.evaluate(
		({ selector, fileName, mimeType, content, sizeOverride }) => {
			const el = document.querySelector(selector);
			if (!el) throw new Error(`Element not found: ${selector}`);

			const file = new File([content ?? "fake file content"], fileName, {
				type: mimeType,
			});

			if (sizeOverride !== undefined) {
				Object.defineProperty(file, "size", { value: sizeOverride });
			}

			const event = new Event("drop", { bubbles: true, cancelable: true });
			Object.defineProperty(event, "dataTransfer", {
				value: { files: [file], types: ["Files"] },
			});
			el.dispatchEvent(event);
		},
		{
			selector: DROP_ZONE_SELECTOR,
			fileName: options.fileName,
			mimeType: options.mimeType,
			content: options.content,
			sizeOverride: options.sizeOverride,
		},
	);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("File Upload DnD", () => {
	test("dropping a valid PDF triggers upload and auto-advances to step 2", async ({
		page,
	}) => {
		await setupNewOnboardingMocks(page);
		await page.goto(ONBOARDING_URL);

		const dropZone = page.getByTestId("drop-zone");
		await expect(dropZone).toBeVisible();

		// Simulate dragenter — drop zone shows active visual state
		await page.evaluate((sel) => {
			const el = document.querySelector(sel);
			if (!el) throw new Error("Drop zone not found");
			const event = new Event("dragenter", {
				bubbles: true,
				cancelable: true,
			});
			Object.defineProperty(event, "dataTransfer", {
				value: { types: ["Files"] },
			});
			el.dispatchEvent(event);
		}, DROP_ZONE_SELECTOR);

		await expect(dropZone).toHaveClass(/bg-primary/);

		// Simulate file drop
		await simulateFileDrop(page, {
			fileName: "resume.pdf",
			mimeType: "application/pdf",
			content: "%PDF-1.4 fake content",
		});

		// Auto-advance to step 2 after successful upload + 1.5s delay
		await expect(page.getByText("Step 2 of 11")).toBeVisible({
			timeout: 5000,
		});
	});

	test("dropping a non-PDF file shows file type error", async ({ page }) => {
		await setupNewOnboardingMocks(page);
		await page.goto(ONBOARDING_URL);

		await expect(page.getByTestId("drop-zone")).toBeVisible();

		await simulateFileDrop(page, {
			fileName: "resume.docx",
			mimeType:
				"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
		});

		await expect(page.getByTestId("upload-error")).toBeVisible();
		await expect(page.getByText("Only PDF files are accepted.")).toBeVisible();
	});

	test("dropping an oversized PDF shows file size error", async ({ page }) => {
		await setupNewOnboardingMocks(page);
		await page.goto(ONBOARDING_URL);

		await expect(page.getByTestId("drop-zone")).toBeVisible();

		await simulateFileDrop(page, {
			fileName: "huge-resume.pdf",
			mimeType: "application/pdf",
			content: "%PDF-1.4 small content",
			sizeOverride: 10 * 1024 * 1024 + 1, // 10 MB + 1 byte
		});

		await expect(page.getByTestId("upload-error")).toBeVisible();
		await expect(page.getByText("File must be 10MB or smaller.")).toBeVisible();
	});

	test("clicking Try again after error resets to idle drop zone", async ({
		page,
	}) => {
		await setupNewOnboardingMocks(page);
		await page.goto(ONBOARDING_URL);

		await expect(page.getByTestId("drop-zone")).toBeVisible();

		// Trigger an error via invalid file type
		await simulateFileDrop(page, {
			fileName: "resume.docx",
			mimeType:
				"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
		});

		await expect(page.getByTestId("upload-error")).toBeVisible();

		// Click "Try again" to reset
		await page.getByRole("button", { name: "Try again" }).click();

		// Drop zone returns to idle state
		await expect(page.getByTestId("drop-zone")).toBeVisible();
		await expect(page.getByTestId("upload-error")).not.toBeVisible();
	});
});
