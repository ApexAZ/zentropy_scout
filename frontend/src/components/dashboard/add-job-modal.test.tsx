/**
 * Tests for the AddJobModal component (§7.11).
 *
 * REQ-012 §8.7: "Add Job" modal — two-step ingest flow:
 * Step 1: Paste raw job text with source selection
 * Step 2: Preview extracted data and confirm
 */

import { cleanup, render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MODAL_TITLE = "Add Job";
const PREVIEW_TITLE = "Preview Extracted Data";
const SOURCE_LABEL = "Source";
const URL_LABEL = "Source URL";
const RAW_TEXT_LABEL = "Job Posting Text";
const EXTRACT_BUTTON = "Extract & Preview";
const CONFIRM_BUTTON = "Confirm & Save";
const BACK_BUTTON = "Back";

const MOCK_PREVIEW = {
	job_title: "Senior Engineer",
	company_name: "Acme Corp",
	location: "Remote",
	salary_min: 150000,
	salary_max: 200000,
	salary_currency: "USD",
	employment_type: "Full-time",
	extracted_skills: [
		{
			skill_name: "TypeScript",
			skill_type: "Hard",
			is_required: true,
			years_requested: 3,
		},
		{
			skill_name: "React",
			skill_type: "Hard",
			is_required: true,
			years_requested: null,
		},
	],
	culture_text: "Fast-paced startup",
	description_snippet: "We are looking for a senior engineer...",
};

const MOCK_INGEST_RESPONSE = {
	data: {
		preview: MOCK_PREVIEW,
		confirmation_token: "token-abc-123",
		expires_at: new Date(Date.now() + 5 * 60 * 1000).toISOString(),
	},
};

const MOCK_CONFIRM_RESPONSE = {
	data: {
		id: "job-new-1",
		job_title: "Senior Engineer",
		company_name: "Acme Corp",
		status: "Discovered",
	},
};

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
		mockApiPost: vi.fn(),
		MockApiError,
		mockShowToast: {
			success: vi.fn(),
			error: vi.fn(),
			warning: vi.fn(),
			info: vi.fn(),
			dismiss: vi.fn(),
		},
		mockPush: vi.fn(),
		mockInvalidateQueries: vi.fn().mockResolvedValue(undefined),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiPost: mocks.mockApiPost,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

vi.mock("next/navigation", () => ({
	useRouter: () => ({ push: mocks.mockPush }),
}));

import { AddJobModal } from "./add-job-modal";

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

function createWrapper() {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	// Override invalidateQueries to track calls
	queryClient.invalidateQueries = mocks.mockInvalidateQueries;
	return function Wrapper({ children }: { children: ReactNode }) {
		return (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);
	};
}

function renderModal(open = true) {
	const onOpenChange = vi.fn();
	const Wrapper = createWrapper();
	const result = render(
		<Wrapper>
			<AddJobModal open={open} onOpenChange={onOpenChange} />
		</Wrapper>,
	);
	return { ...result, onOpenChange };
}

/** Fill step 1 form and submit to transition to step 2 preview. */
async function goToStep2() {
	const user = userEvent.setup();
	mocks.mockApiPost.mockResolvedValueOnce(MOCK_INGEST_RESPONSE);
	renderModal();

	await user.click(screen.getByRole("combobox"));
	await user.click(screen.getByRole("option", { name: "LinkedIn" }));
	await user.type(
		screen.getByRole("textbox", { name: RAW_TEXT_LABEL }),
		"Job text",
	);
	await user.click(screen.getByRole("button", { name: EXTRACT_BUTTON }));

	await waitFor(() => {
		expect(screen.getByText(PREVIEW_TITLE)).toBeInTheDocument();
	});

	return user;
}

/** Fill step 1 form fields and click submit (does not wait for step 2). */
async function fillAndSubmit() {
	const user = userEvent.setup();
	renderModal();
	await user.click(screen.getByRole("combobox"));
	await user.click(screen.getByRole("option", { name: "LinkedIn" }));
	await user.type(
		screen.getByRole("textbox", { name: RAW_TEXT_LABEL }),
		"Job text",
	);
	await user.click(screen.getByRole("button", { name: EXTRACT_BUTTON }));
}

beforeEach(() => {
	mocks.mockApiPost.mockReset();
	mocks.mockPush.mockReset();
	mocks.mockInvalidateQueries.mockReset().mockResolvedValue(undefined);
	Object.values(mocks.mockShowToast).forEach((fn) => fn.mockReset());
});

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AddJobModal", () => {
	// ----- Step 1: Rendering -----

	describe("step 1 rendering", () => {
		it("renders modal title when open", () => {
			renderModal();

			expect(screen.getByText(MODAL_TITLE)).toBeInTheDocument();
		});

		it("renders source select, URL input, and raw text fields", () => {
			renderModal();

			expect(screen.getByText(SOURCE_LABEL)).toBeInTheDocument();
			expect(screen.getByText(URL_LABEL)).toBeInTheDocument();
			expect(screen.getByText(RAW_TEXT_LABEL)).toBeInTheDocument();
		});

		it("renders extract button", () => {
			renderModal();

			expect(
				screen.getByRole("button", { name: EXTRACT_BUTTON }),
			).toBeInTheDocument();
		});
	});

	// ----- Step 1: Validation -----

	describe("step 1 validation", () => {
		it("shows error when source_name is not selected", async () => {
			const user = userEvent.setup();
			renderModal();

			// Fill raw_text but leave source_name empty
			await user.type(
				screen.getByRole("textbox", { name: RAW_TEXT_LABEL }),
				"Job posting text here",
			);
			await user.click(screen.getByRole("button", { name: EXTRACT_BUTTON }));

			await waitFor(() => {
				expect(screen.getByText(/source is required/i)).toBeInTheDocument();
			});
			expect(mocks.mockApiPost).not.toHaveBeenCalled();
		});

		it("shows error when raw_text is empty", async () => {
			const user = userEvent.setup();
			renderModal();

			// Select source but leave raw_text empty
			await user.click(screen.getByRole("combobox"));
			await user.click(screen.getByRole("option", { name: "LinkedIn" }));

			await user.click(screen.getByRole("button", { name: EXTRACT_BUTTON }));

			await waitFor(() => {
				expect(
					screen.getByText(/job posting text is required/i),
				).toBeInTheDocument();
			});
			expect(mocks.mockApiPost).not.toHaveBeenCalled();
		});
	});

	// ----- Step 1: Submission -----

	describe("step 1 submission", () => {
		it("calls apiPost with form data on submit", async () => {
			const user = userEvent.setup();
			mocks.mockApiPost.mockResolvedValue(MOCK_INGEST_RESPONSE);
			renderModal();

			await user.click(screen.getByRole("combobox"));
			await user.click(screen.getByRole("option", { name: "LinkedIn" }));
			await user.type(
				screen.getByRole("textbox", { name: RAW_TEXT_LABEL }),
				"Senior Engineer at Acme Corp",
			);
			await user.click(screen.getByRole("button", { name: EXTRACT_BUTTON }));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					"/job-postings/ingest",
					expect.objectContaining({
						raw_text: "Senior Engineer at Acme Corp",
						source_name: "LinkedIn",
					}),
				);
			});
		});

		it("shows loading state during extraction", async () => {
			const user = userEvent.setup();
			mocks.mockApiPost.mockReturnValue(new Promise(() => {}));
			renderModal();

			await user.click(screen.getByRole("combobox"));
			await user.click(screen.getByRole("option", { name: "Indeed" }));
			await user.type(
				screen.getByRole("textbox", { name: RAW_TEXT_LABEL }),
				"Job text",
			);
			await user.click(screen.getByRole("button", { name: EXTRACT_BUTTON }));

			await waitFor(() => {
				expect(screen.getByTestId("submit-spinner")).toBeInTheDocument();
			});
		});

		it("transitions to step 2 on success", async () => {
			await goToStep2();

			expect(screen.getByText(PREVIEW_TITLE)).toBeInTheDocument();
		});
	});

	// ----- Step 1: Errors -----

	describe("step 1 errors", () => {
		it("shows toast on EXTRACTION_FAILED", async () => {
			mocks.mockApiPost.mockRejectedValue(
				new mocks.MockApiError("EXTRACTION_FAILED", "Failed", 422),
			);

			await fillAndSubmit();

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					"Couldn't extract job details. Try pasting more of the description.",
				);
			});
		});

		it("shows toast on DUPLICATE_JOB", async () => {
			mocks.mockApiPost.mockRejectedValue(
				new mocks.MockApiError("DUPLICATE_JOB", "Duplicate", 409),
			);

			await fillAndSubmit();

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					"This job is already in your list.",
				);
			});
		});

		it("shows generic toast on unknown error", async () => {
			mocks.mockApiPost.mockRejectedValue(
				new mocks.MockApiError("UNKNOWN", "Something broke", 500),
			);

			await fillAndSubmit();

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalled();
			});
		});
	});

	// ----- Step 2: Rendering -----

	describe("step 2 rendering", () => {
		it("displays extracted job title and company", async () => {
			await goToStep2();

			expect(screen.getByText("Senior Engineer")).toBeInTheDocument();
			expect(screen.getByText("Acme Corp")).toBeInTheDocument();
		});

		it("displays location and employment type", async () => {
			await goToStep2();

			expect(screen.getByText("Remote")).toBeInTheDocument();
			expect(screen.getByText("Full-time")).toBeInTheDocument();
		});

		it("displays salary range", async () => {
			await goToStep2();

			expect(screen.getByText(/\$150,000/)).toBeInTheDocument();
			expect(screen.getByText(/\$200,000/)).toBeInTheDocument();
		});

		it("displays extracted skills", async () => {
			await goToStep2();

			expect(screen.getByText("TypeScript")).toBeInTheDocument();
			expect(screen.getByText("React")).toBeInTheDocument();
		});
	});

	// ----- Step 2: Countdown -----

	describe("step 2 countdown", () => {
		it("shows countdown timer", async () => {
			await goToStep2();

			expect(screen.getByTestId("countdown-timer")).toBeInTheDocument();
		});

		it("shows expired message and disables confirm when timer reaches 0", async () => {
			const user = userEvent.setup();
			// Set expires_at to 1 second in the future
			const expiredResponse = {
				data: {
					...MOCK_INGEST_RESPONSE.data,
					expires_at: new Date(Date.now() + 1000).toISOString(),
				},
			};
			mocks.mockApiPost.mockResolvedValue(expiredResponse);
			renderModal();

			await user.click(screen.getByRole("combobox"));
			await user.click(screen.getByRole("option", { name: "LinkedIn" }));
			await user.type(
				screen.getByRole("textbox", { name: RAW_TEXT_LABEL }),
				"Job text",
			);
			await user.click(screen.getByRole("button", { name: EXTRACT_BUTTON }));

			await waitFor(() => {
				expect(screen.getByText(PREVIEW_TITLE)).toBeInTheDocument();
			});

			// Fast-forward timer
			await act(async () => {
				vi.useFakeTimers();
				vi.advanceTimersByTime(2000);
				vi.useRealTimers();
			});

			await waitFor(() => {
				expect(screen.getByText(/expired/i)).toBeInTheDocument();
			});

			const confirmButton = screen.getByRole("button", {
				name: CONFIRM_BUTTON,
			});
			expect(confirmButton).toBeDisabled();
		});
	});

	// ----- Step 2: Confirm -----

	describe("step 2 confirm", () => {
		it("calls apiPost with confirmation token on confirm", async () => {
			const user = await goToStep2();
			mocks.mockApiPost.mockResolvedValueOnce(MOCK_CONFIRM_RESPONSE);

			await user.click(screen.getByRole("button", { name: CONFIRM_BUTTON }));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					"/job-postings/ingest/confirm",
					{ confirmation_token: "token-abc-123" },
				);
			});
		});

		it("invalidates queries and navigates on success", async () => {
			const user = await goToStep2();
			mocks.mockApiPost.mockResolvedValueOnce(MOCK_CONFIRM_RESPONSE);

			await user.click(screen.getByRole("button", { name: CONFIRM_BUTTON }));

			await waitFor(() => {
				expect(mocks.mockInvalidateQueries).toHaveBeenCalled();
			});
			expect(mocks.mockPush).toHaveBeenCalledWith("/jobs/job-new-1");
		});

		it("shows success toast on confirm", async () => {
			const user = await goToStep2();
			mocks.mockApiPost.mockResolvedValueOnce(MOCK_CONFIRM_RESPONSE);

			await user.click(screen.getByRole("button", { name: CONFIRM_BUTTON }));

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
					expect.stringContaining("saved"),
				);
			});
		});
	});

	// ----- Step 2: Errors -----

	describe("step 2 errors", () => {
		it("resets to step 1 on TOKEN_EXPIRED", async () => {
			const user = await goToStep2();
			mocks.mockApiPost.mockRejectedValueOnce(
				new mocks.MockApiError("TOKEN_EXPIRED", "Expired", 404),
			);

			await user.click(screen.getByRole("button", { name: CONFIRM_BUTTON }));

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					"Preview expired. Please resubmit.",
				);
			});
			// Should be back to step 1
			await waitFor(() => {
				expect(screen.getByText(MODAL_TITLE)).toBeInTheDocument();
				expect(screen.queryByText(PREVIEW_TITLE)).not.toBeInTheDocument();
			});
		});

		it("shows generic toast on unknown confirm error", async () => {
			const user = await goToStep2();
			mocks.mockApiPost.mockRejectedValueOnce(
				new mocks.MockApiError("UNKNOWN", "Server error", 500),
			);

			await user.click(screen.getByRole("button", { name: CONFIRM_BUTTON }));

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalled();
			});
		});
	});

	// ----- Modal behavior -----

	describe("modal behavior", () => {
		it("back button returns to step 1 from step 2", async () => {
			const user = await goToStep2();

			await user.click(screen.getByRole("button", { name: BACK_BUTTON }));

			await waitFor(() => {
				expect(screen.getByText(MODAL_TITLE)).toBeInTheDocument();
				expect(screen.queryByText(PREVIEW_TITLE)).not.toBeInTheDocument();
			});
		});

		it("resets to step 1 when modal is reopened", async () => {
			const user = userEvent.setup();
			mocks.mockApiPost.mockResolvedValueOnce(MOCK_INGEST_RESPONSE);
			const { onOpenChange, rerender } = renderModal();

			// Go to step 2
			await user.click(screen.getByRole("combobox"));
			await user.click(screen.getByRole("option", { name: "LinkedIn" }));
			await user.type(
				screen.getByRole("textbox", { name: RAW_TEXT_LABEL }),
				"Job text",
			);
			await user.click(screen.getByRole("button", { name: EXTRACT_BUTTON }));

			await waitFor(() => {
				expect(screen.getByText(PREVIEW_TITLE)).toBeInTheDocument();
			});

			// Close and reopen
			const Wrapper = createWrapper();
			rerender(
				<Wrapper>
					<AddJobModal open={false} onOpenChange={onOpenChange} />
				</Wrapper>,
			);
			rerender(
				<Wrapper>
					<AddJobModal open={true} onOpenChange={onOpenChange} />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByText(MODAL_TITLE)).toBeInTheDocument();
				expect(screen.queryByText(PREVIEW_TITLE)).not.toBeInTheDocument();
			});
		});
	});
});
