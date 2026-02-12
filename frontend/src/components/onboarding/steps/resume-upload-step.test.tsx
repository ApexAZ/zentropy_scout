/**
 * Tests for the resume upload step component.
 *
 * REQ-012 §6.3.1: Drag-and-drop or file picker for PDF/DOCX upload,
 * client-side validation, progress indicator, skip option, auto-advance.
 */

import {
	cleanup,
	fireEvent,
	render,
	screen,
	waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ResumeUploadStep } from "./resume-upload-step";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const RESUME_FILES_PATH = "/resume-files";
const TEN_MB = 10 * 1024 * 1024;
const DROP_ZONE_TEXT = "Drop PDF or DOCX here";
const UPLOADING_TEXT = "Uploading...";
const GENERIC_ERROR_TEXT = "Upload failed. Please try again.";
const MOCK_UPLOAD_RESPONSE = { data: { id: "f1" } };

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	class MockApiError extends Error {
		code: string;
		status: number;
		constructor(code: string, message: string, status: number) {
			super(message);
			this.name = "ApiError";
			this.code = code;
			this.status = status;
		}
	}
	return {
		mockApiUploadFile: vi.fn(),
		MockApiError,
		mockNext: vi.fn(),
		mockSkip: vi.fn(),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiUploadFile: mocks.mockApiUploadFile,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/onboarding-provider", () => ({
	useOnboarding: () => ({
		personaId: DEFAULT_PERSONA_ID,
		next: mocks.mockNext,
		skip: mocks.mockSkip,
	}),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makePdfFile(name = "resume.pdf", sizeBytes?: number): File {
	const content = sizeBytes ? new Uint8Array(sizeBytes) : "pdf content";
	return new File([content], name, { type: "application/pdf" });
}

function makeDocxFile(name = "resume.docx"): File {
	return new File(["docx content"], name, {
		type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
	});
}

function selectFileViaInput(file: File): void {
	const input = screen.getByTestId("file-input");
	Object.defineProperty(input, "files", {
		value: [file],
		configurable: true,
	});
	fireEvent.change(input);
}

function dropFileOnZone(dropZone: HTMLElement, file: File): void {
	const event = new Event("drop", { bubbles: true, cancelable: true });
	Object.defineProperty(event, "dataTransfer", {
		value: { files: [file], types: ["Files"] },
	});
	fireEvent(dropZone, event);
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

describe("ResumeUploadStep", () => {
	beforeEach(() => {
		mocks.mockApiUploadFile.mockReset();
		mocks.mockNext.mockReset();
		mocks.mockSkip.mockReset();
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	// -----------------------------------------------------------------------
	// Rendering
	// -----------------------------------------------------------------------

	describe("rendering", () => {
		it("renders introductory text", () => {
			render(<ResumeUploadStep />);

			expect(
				screen.getByText(/upload it and I.ll use it to pre-fill/i),
			).toBeInTheDocument();
		});

		it("renders drop zone with instructions", () => {
			render(<ResumeUploadStep />);

			expect(screen.getByText(DROP_ZONE_TEXT)).toBeInTheDocument();
			expect(screen.getByText("or click to browse")).toBeInTheDocument();
		});

		it("renders file size and type hint", () => {
			render(<ResumeUploadStep />);

			expect(screen.getByText(/Max 10MB.*PDF or DOCX/)).toBeInTheDocument();
		});

		it("renders skip link", () => {
			render(<ResumeUploadStep />);

			expect(screen.getByRole("button", { name: /skip/i })).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// File validation
	// -----------------------------------------------------------------------

	describe("file validation", () => {
		it("accepts PDF files", async () => {
			mocks.mockApiUploadFile.mockResolvedValueOnce(MOCK_UPLOAD_RESPONSE);
			render(<ResumeUploadStep />);

			selectFileViaInput(makePdfFile());

			await waitFor(() => {
				expect(mocks.mockApiUploadFile).toHaveBeenCalledTimes(1);
			});
		});

		it("accepts DOCX files", async () => {
			mocks.mockApiUploadFile.mockResolvedValueOnce(MOCK_UPLOAD_RESPONSE);
			render(<ResumeUploadStep />);

			selectFileViaInput(makeDocxFile());

			await waitFor(() => {
				expect(mocks.mockApiUploadFile).toHaveBeenCalledTimes(1);
			});
		});

		it("rejects non-PDF/DOCX files with error", async () => {
			render(<ResumeUploadStep />);

			const txtFile = new File(["text"], "notes.txt", {
				type: "text/plain",
			});
			selectFileViaInput(txtFile);

			await waitFor(() => {
				expect(
					screen.getByText(/Only PDF and DOCX files are accepted/i),
				).toBeInTheDocument();
			});
			expect(mocks.mockApiUploadFile).not.toHaveBeenCalled();
		});

		it("rejects files over 10MB with error", async () => {
			render(<ResumeUploadStep />);

			const largeFile = makePdfFile("large.pdf", TEN_MB + 1);
			selectFileViaInput(largeFile);

			await waitFor(() => {
				expect(screen.getByText(/10MB or smaller/i)).toBeInTheDocument();
			});
			expect(mocks.mockApiUploadFile).not.toHaveBeenCalled();
		});

		it("accepts files exactly at 10MB", async () => {
			mocks.mockApiUploadFile.mockResolvedValueOnce(MOCK_UPLOAD_RESPONSE);
			render(<ResumeUploadStep />);

			const exactFile = makePdfFile("exact.pdf", TEN_MB);
			selectFileViaInput(exactFile);

			await waitFor(() => {
				expect(mocks.mockApiUploadFile).toHaveBeenCalledTimes(1);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Upload flow
	// -----------------------------------------------------------------------

	describe("upload flow", () => {
		it("shows progress indicator during upload", async () => {
			mocks.mockApiUploadFile.mockReturnValueOnce(new Promise(() => {}));
			render(<ResumeUploadStep />);

			selectFileViaInput(makePdfFile());

			await waitFor(() => {
				expect(screen.getByText(UPLOADING_TEXT)).toBeInTheDocument();
			});
		});

		it("shows success message after upload completes", async () => {
			mocks.mockApiUploadFile.mockResolvedValueOnce(MOCK_UPLOAD_RESPONSE);
			render(<ResumeUploadStep />);

			selectFileViaInput(makePdfFile());

			await waitFor(() => {
				expect(screen.getByText(/Resume uploaded/i)).toBeInTheDocument();
			});
		});

		it("auto-advances after successful upload", async () => {
			mocks.mockApiUploadFile.mockResolvedValueOnce(MOCK_UPLOAD_RESPONSE);
			render(<ResumeUploadStep />);

			selectFileViaInput(makePdfFile());

			await waitFor(
				() => {
					expect(mocks.mockNext).toHaveBeenCalledTimes(1);
				},
				{ timeout: 3000 },
			);
		});

		it("sends file to correct endpoint with persona_id", async () => {
			mocks.mockApiUploadFile.mockResolvedValueOnce(MOCK_UPLOAD_RESPONSE);
			render(<ResumeUploadStep />);

			selectFileViaInput(makePdfFile());

			await waitFor(() => {
				expect(mocks.mockApiUploadFile).toHaveBeenCalledWith(
					RESUME_FILES_PATH,
					expect.any(File),
					{ persona_id: DEFAULT_PERSONA_ID },
					expect.objectContaining({ signal: expect.any(AbortSignal) }),
				);
			});
		});

		it("hides skip link during upload", async () => {
			mocks.mockApiUploadFile.mockReturnValueOnce(new Promise(() => {}));
			render(<ResumeUploadStep />);

			selectFileViaInput(makePdfFile());

			await waitFor(() => {
				expect(screen.getByText(UPLOADING_TEXT)).toBeInTheDocument();
			});
			expect(
				screen.queryByRole("button", { name: /skip/i }),
			).not.toBeInTheDocument();
		});

		it("hides drop zone during upload", async () => {
			mocks.mockApiUploadFile.mockReturnValueOnce(new Promise(() => {}));
			render(<ResumeUploadStep />);

			selectFileViaInput(makePdfFile());

			await waitFor(() => {
				expect(screen.getByText(UPLOADING_TEXT)).toBeInTheDocument();
			});
			expect(screen.queryByText(DROP_ZONE_TEXT)).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Error handling
	// -----------------------------------------------------------------------

	describe("error handling", () => {
		it("shows friendly message for known API error codes", async () => {
			mocks.mockApiUploadFile.mockRejectedValueOnce(
				new mocks.MockApiError(
					"FILE_TOO_LARGE",
					"Server: file exceeds maximum size",
					413,
				),
			);
			render(<ResumeUploadStep />);

			selectFileViaInput(makePdfFile());

			await waitFor(() => {
				expect(
					screen.getByText("File must be 10MB or smaller."),
				).toBeInTheDocument();
			});
		});

		it("shows generic error for unknown API error codes", async () => {
			mocks.mockApiUploadFile.mockRejectedValueOnce(
				new mocks.MockApiError(
					"INTERNAL_ERROR",
					"Unexpected server error",
					500,
				),
			);
			render(<ResumeUploadStep />);

			selectFileViaInput(makePdfFile());

			await waitFor(() => {
				expect(screen.getByText(GENERIC_ERROR_TEXT)).toBeInTheDocument();
			});
		});

		it("shows generic error for non-API errors", async () => {
			mocks.mockApiUploadFile.mockRejectedValueOnce(new Error("Unknown error"));
			render(<ResumeUploadStep />);

			selectFileViaInput(makePdfFile());

			await waitFor(() => {
				expect(screen.getByText(GENERIC_ERROR_TEXT)).toBeInTheDocument();
			});
		});

		it("allows retry after failure", async () => {
			mocks.mockApiUploadFile.mockRejectedValueOnce(new Error("fail"));
			render(<ResumeUploadStep />);

			selectFileViaInput(makePdfFile());

			await waitFor(() => {
				expect(screen.getByText(GENERIC_ERROR_TEXT)).toBeInTheDocument();
			});

			fireEvent.click(screen.getByRole("button", { name: /try again/i }));

			expect(screen.getByText(DROP_ZONE_TEXT)).toBeInTheDocument();
		});

		it("shows skip link after error", async () => {
			mocks.mockApiUploadFile.mockRejectedValueOnce(new Error("fail"));
			render(<ResumeUploadStep />);

			selectFileViaInput(makePdfFile());

			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: /skip/i }),
				).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Drag and drop
	// -----------------------------------------------------------------------

	describe("drag and drop", () => {
		it("shows drag-over visual feedback", () => {
			render(<ResumeUploadStep />);

			const dropZone = screen.getByTestId("drop-zone");
			fireEvent.dragEnter(dropZone, {
				dataTransfer: { types: ["Files"] },
			});

			expect(dropZone.className).toContain("bg-primary");
		});

		it("removes drag-over feedback on drag leave", () => {
			render(<ResumeUploadStep />);

			const dropZone = screen.getByTestId("drop-zone");
			fireEvent.dragEnter(dropZone, {
				dataTransfer: { types: ["Files"] },
			});
			fireEvent.dragLeave(dropZone);

			expect(dropZone.className).not.toContain("bg-primary");
		});

		it("accepts files via drag-and-drop", async () => {
			mocks.mockApiUploadFile.mockResolvedValueOnce(MOCK_UPLOAD_RESPONSE);
			render(<ResumeUploadStep />);

			const dropZone = screen.getByTestId("drop-zone");
			dropFileOnZone(dropZone, makePdfFile());

			await waitFor(() => {
				expect(mocks.mockApiUploadFile).toHaveBeenCalledTimes(1);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Skip
	// -----------------------------------------------------------------------

	describe("skip", () => {
		it("calls skip when skip link is clicked", () => {
			render(<ResumeUploadStep />);

			fireEvent.click(screen.getByRole("button", { name: /skip/i }));

			expect(mocks.mockSkip).toHaveBeenCalledTimes(1);
		});
	});
});
