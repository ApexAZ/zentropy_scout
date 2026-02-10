/**
 * Tests for the PdfViewer component.
 *
 * REQ-012 §13.4: Inline PDF preview for resume and cover letter review.
 * Uses browser-native iframe with blob URL lifecycle management.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PdfViewer } from "./pdf-viewer";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	const OBJECT_URL = "http://localhost/mock-object-url";
	return {
		OBJECT_URL,
		createObjectURL: vi.fn(() => OBJECT_URL),
		revokeObjectURL: vi.fn(),
		requestFullscreen: vi.fn(),
		exitFullscreen: vi.fn(),
		anchorClick: vi.fn(),
	};
});

// ---------------------------------------------------------------------------
// Constants & Helpers
// ---------------------------------------------------------------------------

const TEST_BLOB = new Blob(["fake-pdf"], { type: "application/pdf" });
const TEST_URL = "https://example.com/resume.pdf";
const TEST_FILENAME = "resume.pdf";

function getIframe() {
	return screen.getByTitle(`PDF preview: ${TEST_FILENAME}`);
}

function setFullscreenElement(value: Element | null) {
	Object.defineProperty(document, "fullscreenElement", {
		writable: true,
		configurable: true,
		value,
	});
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("PdfViewer", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		URL.createObjectURL = mocks.createObjectURL;
		URL.revokeObjectURL = mocks.revokeObjectURL;
		Element.prototype.requestFullscreen = mocks.requestFullscreen;
		document.exitFullscreen = mocks.exitFullscreen;
		setFullscreenElement(null);
		vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
			mocks.anchorClick,
		);
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	describe("Rendering", () => {
		it("renders iframe with blob URL when src is Blob", () => {
			render(<PdfViewer src={TEST_BLOB} fileName={TEST_FILENAME} />);
			expect(mocks.createObjectURL).toHaveBeenCalledWith(TEST_BLOB);
			expect(getIframe()).toHaveAttribute("src", mocks.OBJECT_URL);
		});

		it("renders iframe with string URL when src is string", () => {
			render(<PdfViewer src={TEST_URL} fileName={TEST_FILENAME} />);
			expect(mocks.createObjectURL).not.toHaveBeenCalled();
			expect(getIframe()).toHaveAttribute("src", TEST_URL);
		});

		it("renders toolbar with zoom, download, and fullscreen buttons", () => {
			render(<PdfViewer src={TEST_URL} fileName={TEST_FILENAME} />);
			expect(
				screen.getByRole("button", { name: "Zoom out" }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: "Zoom in" }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: "Download PDF" }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: "Enter full screen" }),
			).toBeInTheDocument();
		});

		it("spreads props and merges className", () => {
			render(
				<PdfViewer
					src={TEST_URL}
					fileName={TEST_FILENAME}
					data-testid="custom-viewer"
					className="custom-class"
				/>,
			);
			expect(screen.getByTestId("custom-viewer")).toHaveClass("custom-class");
		});
	});

	describe("Zoom", () => {
		it("displays default zoom of 100%", () => {
			render(<PdfViewer src={TEST_URL} fileName={TEST_FILENAME} />);
			expect(screen.getByText("100%")).toBeInTheDocument();
		});

		it("zoom in increases to 125%", async () => {
			const user = userEvent.setup();
			render(<PdfViewer src={TEST_URL} fileName={TEST_FILENAME} />);
			await user.click(screen.getByRole("button", { name: "Zoom in" }));
			expect(screen.getByText("125%")).toBeInTheDocument();
		});

		it("zoom out decreases to 75%", async () => {
			const user = userEvent.setup();
			render(<PdfViewer src={TEST_URL} fileName={TEST_FILENAME} />);
			await user.click(screen.getByRole("button", { name: "Zoom out" }));
			expect(screen.getByText("75%")).toBeInTheDocument();
		});

		it("disables buttons at zoom boundaries", async () => {
			const user = userEvent.setup();
			render(<PdfViewer src={TEST_URL} fileName={TEST_FILENAME} />);
			const zoomIn = screen.getByRole("button", { name: "Zoom in" });
			const zoomOut = screen.getByRole("button", { name: "Zoom out" });

			// Zoom to max (100 → 125 → 150 → 175 → 200)
			for (let i = 0; i < 4; i++) await user.click(zoomIn);
			expect(screen.getByText("200%")).toBeInTheDocument();
			expect(zoomIn).toBeDisabled();

			// Zoom to min (200 → 175 → ... → 50)
			for (let i = 0; i < 6; i++) await user.click(zoomOut);
			expect(screen.getByText("50%")).toBeInTheDocument();
			expect(zoomOut).toBeDisabled();
		});
	});

	describe("Download", () => {
		it("creates anchor with correct fileName and triggers click", async () => {
			const user = userEvent.setup();
			render(<PdfViewer src={TEST_URL} fileName={TEST_FILENAME} />);
			await user.click(screen.getByRole("button", { name: "Download PDF" }));
			expect(mocks.anchorClick).toHaveBeenCalledOnce();
		});

		it("download works in fallback mode", async () => {
			const user = userEvent.setup();
			render(<PdfViewer src={TEST_URL} fileName={TEST_FILENAME} />);
			fireEvent.error(getIframe());
			await user.click(screen.getByRole("link", { name: "Download File" }));
		});
	});

	describe("Fullscreen", () => {
		it("calls requestFullscreen when entering fullscreen", async () => {
			const user = userEvent.setup();
			render(<PdfViewer src={TEST_URL} fileName={TEST_FILENAME} />);
			await user.click(
				screen.getByRole("button", { name: "Enter full screen" }),
			);
			expect(mocks.requestFullscreen).toHaveBeenCalledOnce();
		});

		it("calls exitFullscreen when already in fullscreen", async () => {
			const user = userEvent.setup();
			render(<PdfViewer src={TEST_URL} fileName={TEST_FILENAME} />);
			setFullscreenElement(document.body);
			await user.click(
				screen.getByRole("button", { name: "Enter full screen" }),
			);
			expect(mocks.exitFullscreen).toHaveBeenCalledOnce();
		});

		it("updates label on fullscreenchange event", () => {
			render(<PdfViewer src={TEST_URL} fileName={TEST_FILENAME} />);
			setFullscreenElement(document.body);
			act(() => {
				document.dispatchEvent(new Event("fullscreenchange"));
			});
			expect(
				screen.getByRole("button", { name: "Exit full screen" }),
			).toBeInTheDocument();
		});
	});

	describe("Fallback", () => {
		it("shows fallback on iframe error", () => {
			render(<PdfViewer src={TEST_URL} fileName={TEST_FILENAME} />);
			fireEvent.error(getIframe());
			expect(
				screen.getByText("Unable to preview this PDF."),
			).toBeInTheDocument();
			expect(
				screen.getByRole("link", { name: "Download File" }),
			).toBeInTheDocument();
		});

		it("resets error on src change", () => {
			const { rerender } = render(
				<PdfViewer src={TEST_URL} fileName={TEST_FILENAME} />,
			);
			fireEvent.error(getIframe());
			expect(
				screen.getByText("Unable to preview this PDF."),
			).toBeInTheDocument();

			rerender(
				<PdfViewer
					src="https://example.com/new.pdf"
					fileName={TEST_FILENAME}
				/>,
			);
			expect(
				screen.queryByText("Unable to preview this PDF."),
			).not.toBeInTheDocument();
			expect(getIframe()).toBeInTheDocument();
		});
	});

	describe("Cleanup", () => {
		it("revokes blob URL on unmount", () => {
			const { unmount } = render(
				<PdfViewer src={TEST_BLOB} fileName={TEST_FILENAME} />,
			);
			unmount();
			expect(mocks.revokeObjectURL).toHaveBeenCalledWith(mocks.OBJECT_URL);
		});
	});

	describe("Security", () => {
		it("rejects javascript: URI and shows fallback", () => {
			render(<PdfViewer src="javascript:alert(1)" fileName={TEST_FILENAME} />);
			expect(
				screen.getByText("Unable to preview this PDF."),
			).toBeInTheDocument();
		});

		it("rejects data: URI and shows fallback", () => {
			render(
				<PdfViewer
					src="data:text/html,<script>alert(1)</script>"
					fileName={TEST_FILENAME}
				/>,
			);
			expect(
				screen.getByText("Unable to preview this PDF."),
			).toBeInTheDocument();
		});

		it("rejects non-PDF Blob and shows fallback", () => {
			const htmlBlob = new Blob(["<script>alert(1)</script>"], {
				type: "text/html",
			});
			render(<PdfViewer src={htmlBlob} fileName={TEST_FILENAME} />);
			expect(mocks.createObjectURL).not.toHaveBeenCalled();
			expect(
				screen.getByText("Unable to preview this PDF."),
			).toBeInTheDocument();
		});

		it("sanitizes path traversal in fileName", () => {
			render(<PdfViewer src={TEST_URL} fileName="../../etc/passwd" />);
			const iframe = screen.getByTitle("PDF preview: .._.._etc_passwd");
			expect(iframe).toBeInTheDocument();
		});

		it("renders iframe with sandbox attribute", () => {
			render(<PdfViewer src={TEST_URL} fileName={TEST_FILENAME} />);
			expect(getIframe()).toHaveAttribute("sandbox", "allow-same-origin");
		});

		it("renders iframe with no-referrer policy", () => {
			render(<PdfViewer src={TEST_URL} fileName={TEST_FILENAME} />);
			expect(getIframe()).toHaveAttribute("referrerpolicy", "no-referrer");
		});
	});
});
