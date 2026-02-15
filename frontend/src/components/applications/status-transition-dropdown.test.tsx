/**
 * Tests for the StatusTransitionDropdown component (§10.3).
 *
 * REQ-012 §11.3: Status transition dropdown with conditional prompts.
 * Transition matrix: Applied → Interviewing/Rejected/Withdrawn,
 * Interviewing → Offer/Rejected/Withdrawn, Offer → Accepted/Rejected/Withdrawn.
 * Terminal statuses (Accepted, Rejected, Withdrawn) disable the dropdown.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TRIGGER_LABEL = "Update status";
const MOCK_APP_ID = "app-1";
const INTERVIEW_STAGE_TITLE = "Select Interview Stage";
const OFFER_DIALOG_TITLE = "Offer Details";
const STATUS_UPDATE_ERROR = "Failed to update status.";

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
		mockApiPatch: vi.fn(),
		MockApiError,
		mockShowToast: {
			success: vi.fn(),
			error: vi.fn(),
			warning: vi.fn(),
			info: vi.fn(),
			dismiss: vi.fn(),
		},
		mockInvalidateQueries: vi.fn().mockResolvedValue(undefined),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiPatch: mocks.mockApiPatch,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

import { StatusTransitionDropdown } from "./status-transition-dropdown";
import type { ApplicationStatus } from "@/types/application";

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

function createWrapper() {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	queryClient.invalidateQueries = mocks.mockInvalidateQueries;
	return function Wrapper({ children }: { children: ReactNode }) {
		return (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);
	};
}

function renderDropdown(
	currentStatus: ApplicationStatus = "Applied",
	applicationId: string = MOCK_APP_ID,
) {
	const Wrapper = createWrapper();
	return render(
		<Wrapper>
			<StatusTransitionDropdown
				applicationId={applicationId}
				currentStatus={currentStatus}
			/>
		</Wrapper>,
	);
}

/** Opens the dropdown and selects the given option, then waits for its effect. */
async function selectTransition(
	user: ReturnType<typeof userEvent.setup>,
	optionName: string,
) {
	await user.click(screen.getByRole("combobox", { name: TRIGGER_LABEL }));
	await waitFor(() => {
		expect(
			screen.getByRole("option", { name: optionName }),
		).toBeInTheDocument();
	});
	await user.click(screen.getByRole("option", { name: optionName }));
}

beforeEach(() => {
	mocks.mockApiPatch.mockReset();
	mocks.mockInvalidateQueries.mockReset().mockResolvedValue(undefined);
	Object.values(mocks.mockShowToast).forEach((fn) => fn.mockReset());
});

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests — Rendering
// ---------------------------------------------------------------------------

describe("StatusTransitionDropdown", () => {
	describe("rendering", () => {
		it("renders a dropdown trigger with 'Update Status' text", () => {
			renderDropdown("Applied");
			expect(
				screen.getByRole("combobox", { name: TRIGGER_LABEL }),
			).toBeInTheDocument();
		});

		it("disables the trigger for terminal status Accepted", () => {
			renderDropdown("Accepted");
			expect(
				screen.getByRole("combobox", { name: TRIGGER_LABEL }),
			).toBeDisabled();
		});

		it("disables the trigger for terminal status Rejected", () => {
			renderDropdown("Rejected");
			expect(
				screen.getByRole("combobox", { name: TRIGGER_LABEL }),
			).toBeDisabled();
		});

		it("disables the trigger for terminal status Withdrawn", () => {
			renderDropdown("Withdrawn");
			expect(
				screen.getByRole("combobox", { name: TRIGGER_LABEL }),
			).toBeDisabled();
		});

		it("shows correct options for Applied status", async () => {
			const user = userEvent.setup();
			renderDropdown("Applied");

			await user.click(screen.getByRole("combobox", { name: TRIGGER_LABEL }));

			await waitFor(() => {
				expect(
					screen.getByRole("option", { name: "Interviewing" }),
				).toBeInTheDocument();
				expect(
					screen.getByRole("option", { name: "Rejected" }),
				).toBeInTheDocument();
				expect(
					screen.getByRole("option", { name: "Withdrawn" }),
				).toBeInTheDocument();
			});

			// Should NOT show Applied, Offer, Accepted
			expect(
				screen.queryByRole("option", { name: "Applied" }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("option", { name: "Offer" }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("option", { name: "Accepted" }),
			).not.toBeInTheDocument();
		});

		it("shows correct options for Interviewing status", async () => {
			const user = userEvent.setup();
			renderDropdown("Interviewing");

			await user.click(screen.getByRole("combobox", { name: TRIGGER_LABEL }));

			await waitFor(() => {
				expect(
					screen.getByRole("option", { name: "Offer" }),
				).toBeInTheDocument();
				expect(
					screen.getByRole("option", { name: "Rejected" }),
				).toBeInTheDocument();
				expect(
					screen.getByRole("option", { name: "Withdrawn" }),
				).toBeInTheDocument();
			});

			expect(
				screen.queryByRole("option", { name: "Applied" }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("option", { name: "Interviewing" }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("option", { name: "Accepted" }),
			).not.toBeInTheDocument();
		});

		it("shows correct options for Offer status", async () => {
			const user = userEvent.setup();
			renderDropdown("Offer");

			await user.click(screen.getByRole("combobox", { name: TRIGGER_LABEL }));

			await waitFor(() => {
				expect(
					screen.getByRole("option", { name: "Accepted" }),
				).toBeInTheDocument();
				expect(
					screen.getByRole("option", { name: "Rejected" }),
				).toBeInTheDocument();
				expect(
					screen.getByRole("option", { name: "Withdrawn" }),
				).toBeInTheDocument();
			});

			expect(
				screen.queryByRole("option", { name: "Applied" }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("option", { name: "Interviewing" }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("option", { name: "Offer" }),
			).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Interviewing transition (with interview stage dialog)
	// -----------------------------------------------------------------------

	describe("interviewing transition", () => {
		it("shows interview stage dialog when Interviewing is selected", async () => {
			const user = userEvent.setup();
			renderDropdown("Applied");

			await selectTransition(user, "Interviewing");

			await waitFor(() => {
				expect(screen.getByText(INTERVIEW_STAGE_TITLE)).toBeInTheDocument();
			});
		});

		it("interview stage dialog shows all 3 stages", async () => {
			const user = userEvent.setup();
			renderDropdown("Applied");

			await selectTransition(user, "Interviewing");

			await waitFor(() => {
				expect(screen.getByText(INTERVIEW_STAGE_TITLE)).toBeInTheDocument();
			});
			expect(
				screen.getByRole("radio", { name: "Phone Screen" }),
			).toBeInTheDocument();
			expect(screen.getByRole("radio", { name: "Onsite" })).toBeInTheDocument();
			expect(
				screen.getByRole("radio", { name: "Final Round" }),
			).toBeInTheDocument();
		});

		it("calls PATCH with status and interview stage on confirm", async () => {
			const user = userEvent.setup();
			mocks.mockApiPatch.mockResolvedValue({ data: {} });
			renderDropdown("Applied");

			await selectTransition(user, "Interviewing");

			await waitFor(() => {
				expect(screen.getByText(INTERVIEW_STAGE_TITLE)).toBeInTheDocument();
			});

			await user.click(screen.getByRole("radio", { name: "Onsite" }));
			await user.click(screen.getByRole("button", { name: "Confirm" }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/applications/${MOCK_APP_ID}`,
					{ status: "Interviewing", current_interview_stage: "Onsite" },
				);
			});
		});

		it("shows success toast after successful interviewing transition", async () => {
			const user = userEvent.setup();
			mocks.mockApiPatch.mockResolvedValue({ data: {} });
			renderDropdown("Applied");

			await selectTransition(user, "Interviewing");

			await waitFor(() => {
				expect(screen.getByText(INTERVIEW_STAGE_TITLE)).toBeInTheDocument();
			});

			await user.click(screen.getByRole("radio", { name: "Phone Screen" }));
			await user.click(screen.getByRole("button", { name: "Confirm" }));

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
					"Status updated to Interviewing.",
				);
			});
		});

		it("shows error toast when interview stage transition PATCH fails", async () => {
			const user = userEvent.setup();
			mocks.mockApiPatch.mockRejectedValue(new Error("Network error"));
			renderDropdown("Applied");

			await selectTransition(user, "Interviewing");

			await waitFor(() => {
				expect(screen.getByText(INTERVIEW_STAGE_TITLE)).toBeInTheDocument();
			});

			await user.click(screen.getByRole("radio", { name: "Onsite" }));
			await user.click(screen.getByRole("button", { name: "Confirm" }));

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					STATUS_UPDATE_ERROR,
				);
			});
		});

		it("closes interview stage dialog on cancel", async () => {
			const user = userEvent.setup();
			renderDropdown("Applied");

			await selectTransition(user, "Interviewing");

			await waitFor(() => {
				expect(screen.getByText(INTERVIEW_STAGE_TITLE)).toBeInTheDocument();
			});

			await user.click(screen.getByRole("button", { name: "Cancel" }));

			await waitFor(() => {
				expect(
					screen.queryByText(INTERVIEW_STAGE_TITLE),
				).not.toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Confirmation dialog transitions (Accepted, Withdrawn)
	// -----------------------------------------------------------------------

	describe("confirmation dialog transitions", () => {
		it("shows confirmation dialog when Accepted is selected", async () => {
			const user = userEvent.setup();
			renderDropdown("Offer");

			await selectTransition(user, "Accepted");

			await waitFor(() => {
				expect(screen.getByText(/Mark as Accepted/)).toBeInTheDocument();
			});
		});

		it("shows confirmation dialog when Withdrawn is selected", async () => {
			const user = userEvent.setup();
			renderDropdown("Applied");

			await selectTransition(user, "Withdrawn");

			await waitFor(() => {
				expect(screen.getByText(/Mark as Withdrawn/)).toBeInTheDocument();
			});
		});

		it("calls PATCH with target status on confirm", async () => {
			const user = userEvent.setup();
			mocks.mockApiPatch.mockResolvedValue({ data: {} });
			renderDropdown("Offer");

			await selectTransition(user, "Accepted");

			await waitFor(() => {
				expect(screen.getByText(/Mark as Accepted/)).toBeInTheDocument();
			});

			await user.click(screen.getByRole("button", { name: "Confirm" }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/applications/${MOCK_APP_ID}`,
					{ status: "Accepted" },
				);
			});
		});

		it("shows success toast after successful transition", async () => {
			const user = userEvent.setup();
			mocks.mockApiPatch.mockResolvedValue({ data: {} });
			renderDropdown("Applied");

			await selectTransition(user, "Withdrawn");

			await waitFor(() => {
				expect(screen.getByText(/Mark as Withdrawn/)).toBeInTheDocument();
			});

			await user.click(screen.getByRole("button", { name: "Confirm" }));

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
					"Status updated to Withdrawn.",
				);
			});
		});

		it("closes dialog and resets on cancel", async () => {
			const user = userEvent.setup();
			renderDropdown("Applied");

			await selectTransition(user, "Withdrawn");

			await waitFor(() => {
				expect(screen.getByText(/Mark as Withdrawn/)).toBeInTheDocument();
			});

			await user.click(screen.getByRole("button", { name: "Cancel" }));

			await waitFor(() => {
				expect(screen.queryByText(/Mark as Withdrawn/)).not.toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Offer transition (with offer details dialog, §10.5)
	// -----------------------------------------------------------------------

	describe("offer transition", () => {
		it("shows offer details dialog when Offer is selected", async () => {
			const user = userEvent.setup();
			renderDropdown("Interviewing");

			await selectTransition(user, "Offer");

			await waitFor(() => {
				expect(screen.getByText(OFFER_DIALOG_TITLE)).toBeInTheDocument();
			});
		});

		it("calls PATCH with offer_details when offer dialog is saved", async () => {
			const user = userEvent.setup();
			mocks.mockApiPatch.mockResolvedValue({ data: {} });
			renderDropdown("Interviewing");

			await selectTransition(user, "Offer");

			await waitFor(() => {
				expect(screen.getByText(OFFER_DIALOG_TITLE)).toBeInTheDocument();
			});
			await user.click(screen.getByRole("button", { name: "Save" }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/applications/${MOCK_APP_ID}`,
					{
						status: "Offer",
						offer_details: { salary_currency: "USD" },
					},
				);
			});
		});

		it("closes offer dialog on cancel", async () => {
			const user = userEvent.setup();
			renderDropdown("Interviewing");

			await selectTransition(user, "Offer");

			await waitFor(() => {
				expect(screen.getByText(OFFER_DIALOG_TITLE)).toBeInTheDocument();
			});
			await user.click(screen.getByRole("button", { name: "Cancel" }));

			await waitFor(() => {
				expect(screen.queryByText(OFFER_DIALOG_TITLE)).not.toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Rejected transition (confirmation placeholder for §10.6)
	// -----------------------------------------------------------------------

	describe("rejected transition", () => {
		it("shows confirmation dialog when Rejected is selected", async () => {
			const user = userEvent.setup();
			renderDropdown("Applied");

			await selectTransition(user, "Rejected");

			await waitFor(() => {
				expect(screen.getByText(/Mark as Rejected/)).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Error handling
	// -----------------------------------------------------------------------

	describe("error handling", () => {
		it("shows error toast when confirmation PATCH fails", async () => {
			const user = userEvent.setup();
			mocks.mockApiPatch.mockRejectedValue(new Error("Network error"));
			renderDropdown("Offer");

			await selectTransition(user, "Accepted");

			await waitFor(() => {
				expect(screen.getByText(/Mark as Accepted/)).toBeInTheDocument();
			});
			await user.click(screen.getByRole("button", { name: "Confirm" }));

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					STATUS_UPDATE_ERROR,
				);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Cache invalidation
	// -----------------------------------------------------------------------

	describe("cache invalidation", () => {
		it("invalidates query cache on successful transition", async () => {
			const user = userEvent.setup();
			mocks.mockApiPatch.mockResolvedValue({ data: {} });
			renderDropdown("Offer");

			await selectTransition(user, "Accepted");

			await waitFor(() => {
				expect(screen.getByText(/Mark as Accepted/)).toBeInTheDocument();
			});
			await user.click(screen.getByRole("button", { name: "Confirm" }));

			await waitFor(() => {
				expect(mocks.mockInvalidateQueries).toHaveBeenCalled();
			});
		});
	});
});
