/**
 * Tests for the JobDetailActions component.
 *
 * REQ-015 §8–§9: Rescore triggers re-scoring of discovered jobs.
 * Dismiss/Undismiss updates persona_jobs status via PATCH.
 * Shared data is immutable — only per-user fields change.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { JobPostingStatus } from "@/types/job";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PERSONA_JOB_ID = "pj-1";
const ACTIONS_TESTID = "job-detail-actions";
const RESCORE_LABEL = /^rescore$/i;
const DISMISS_LABEL = /^dismiss$/i;
const UNDISMISS_LABEL = /^undismiss$/i;

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
		mockApiPatch: vi.fn(),
		MockApiError,
		mockShowToast: {
			success: vi.fn(),
			error: vi.fn(),
			warning: vi.fn(),
			info: vi.fn(),
			dismiss: vi.fn(),
		},
		mockPush: vi.fn(),
		mockInvalidateQueries: vi.fn(),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiPost: mocks.mockApiPost,
	apiPatch: mocks.mockApiPatch,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

vi.mock("next/navigation", () => ({
	useRouter: () => ({ push: mocks.mockPush }),
}));

import { JobDetailActions } from "./job-detail-actions";

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

function createWrapper() {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	// Spy on invalidateQueries
	vi.spyOn(queryClient, "invalidateQueries").mockImplementation(
		mocks.mockInvalidateQueries,
	);
	const wrapper = function Wrapper({ children }: { children: ReactNode }) {
		return (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);
	};
	wrapper.displayName = "TestWrapper";
	return wrapper;
}

function renderActions(status: JobPostingStatus = "Discovered") {
	const Wrapper = createWrapper();
	return render(
		<Wrapper>
			<JobDetailActions personaJobId={PERSONA_JOB_ID} status={status} />
		</Wrapper>,
	);
}

beforeEach(() => {
	mocks.mockApiPost.mockReset();
	mocks.mockApiPatch.mockReset();
	mocks.mockPush.mockReset();
	mocks.mockInvalidateQueries.mockReset();
	mocks.mockInvalidateQueries.mockResolvedValue(undefined);
	Object.values(mocks.mockShowToast).forEach((fn) => fn.mockReset());
});

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("JobDetailActions", () => {
	describe("status-based visibility", () => {
		it("shows Rescore and Dismiss buttons when status is Discovered", () => {
			renderActions("Discovered");
			expect(
				screen.getByRole("button", { name: RESCORE_LABEL }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: DISMISS_LABEL }),
			).toBeInTheDocument();
		});

		it("shows Undismiss button when status is Dismissed", () => {
			renderActions("Dismissed");
			expect(
				screen.getByRole("button", { name: UNDISMISS_LABEL }),
			).toBeInTheDocument();
			expect(
				screen.queryByRole("button", { name: RESCORE_LABEL }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("button", { name: DISMISS_LABEL }),
			).not.toBeInTheDocument();
		});

		it("renders nothing when status is Applied", () => {
			const { container } = renderActions("Applied");
			expect(
				container.querySelector(`[data-testid="${ACTIONS_TESTID}"]`),
			).not.toBeInTheDocument();
		});

		it("renders nothing when status is Expired", () => {
			const { container } = renderActions("Expired");
			expect(
				container.querySelector(`[data-testid="${ACTIONS_TESTID}"]`),
			).not.toBeInTheDocument();
		});
	});

	describe("rescore action", () => {
		it("calls POST /job-postings/rescore on click", async () => {
			mocks.mockApiPost.mockResolvedValueOnce({ data: { status: "queued" } });
			const user = userEvent.setup();
			renderActions("Discovered");

			await user.click(screen.getByRole("button", { name: RESCORE_LABEL }));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith("/job-postings/rescore");
			});
		});

		it("shows success toast on rescore success", async () => {
			mocks.mockApiPost.mockResolvedValueOnce({ data: { status: "queued" } });
			const user = userEvent.setup();
			renderActions("Discovered");

			await user.click(screen.getByRole("button", { name: RESCORE_LABEL }));

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
					"Rescoring started.",
				);
			});
		});

		it("invalidates job queries on rescore success", async () => {
			mocks.mockApiPost.mockResolvedValueOnce({ data: { status: "queued" } });
			const user = userEvent.setup();
			renderActions("Discovered");

			await user.click(screen.getByRole("button", { name: RESCORE_LABEL }));

			await waitFor(() => {
				expect(mocks.mockInvalidateQueries).toHaveBeenCalled();
			});
		});

		it("shows error toast on rescore failure", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(
				new mocks.MockApiError("SERVER_ERROR", "Internal error", 500),
			);
			const user = userEvent.setup();
			renderActions("Discovered");

			await user.click(screen.getByRole("button", { name: RESCORE_LABEL }));

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					"Failed to start rescoring.",
				);
			});
		});

		it("disables button during rescore", async () => {
			let resolvePost: (value: unknown) => void;
			mocks.mockApiPost.mockReturnValueOnce(
				new Promise((resolve) => {
					resolvePost = resolve;
				}),
			);
			const user = userEvent.setup();
			renderActions("Discovered");

			await user.click(screen.getByRole("button", { name: RESCORE_LABEL }));

			expect(
				screen.getByRole("button", { name: RESCORE_LABEL }),
			).toBeDisabled();

			resolvePost!({ data: { status: "queued" } });

			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: RESCORE_LABEL }),
				).toBeEnabled();
			});
		});
	});

	describe("dismiss action", () => {
		it("calls PATCH with status Dismissed on click", async () => {
			mocks.mockApiPatch.mockResolvedValueOnce(undefined);
			const user = userEvent.setup();
			renderActions("Discovered");

			await user.click(screen.getByRole("button", { name: DISMISS_LABEL }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/job-postings/${PERSONA_JOB_ID}`,
					{ status: "Dismissed" },
				);
			});
		});

		it("shows success toast on dismiss", async () => {
			mocks.mockApiPatch.mockResolvedValueOnce(undefined);
			const user = userEvent.setup();
			renderActions("Discovered");

			await user.click(screen.getByRole("button", { name: DISMISS_LABEL }));

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
					"Job dismissed.",
				);
			});
		});

		it("navigates to dashboard on dismiss success", async () => {
			mocks.mockApiPatch.mockResolvedValueOnce(undefined);
			const user = userEvent.setup();
			renderActions("Discovered");

			await user.click(screen.getByRole("button", { name: DISMISS_LABEL }));

			await waitFor(() => {
				expect(mocks.mockPush).toHaveBeenCalledWith("/");
			});
		});

		it("shows error toast on dismiss failure", async () => {
			mocks.mockApiPatch.mockRejectedValueOnce(
				new mocks.MockApiError("SERVER_ERROR", "Failed", 500),
			);
			const user = userEvent.setup();
			renderActions("Discovered");

			await user.click(screen.getByRole("button", { name: DISMISS_LABEL }));

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					"Failed to dismiss job.",
				);
			});
		});

		it("disables button during dismiss", async () => {
			let resolvePatch: (value: unknown) => void;
			mocks.mockApiPatch.mockReturnValueOnce(
				new Promise((resolve) => {
					resolvePatch = resolve;
				}),
			);
			const user = userEvent.setup();
			renderActions("Discovered");

			await user.click(screen.getByRole("button", { name: DISMISS_LABEL }));

			expect(
				screen.getByRole("button", { name: DISMISS_LABEL }),
			).toBeDisabled();

			resolvePatch!(undefined);

			await waitFor(() => {
				expect(mocks.mockPush).toHaveBeenCalledWith("/");
			});
		});
	});

	describe("undismiss action", () => {
		it("calls PATCH with status Discovered on click", async () => {
			mocks.mockApiPatch.mockResolvedValueOnce(undefined);
			const user = userEvent.setup();
			renderActions("Dismissed");

			await user.click(screen.getByRole("button", { name: UNDISMISS_LABEL }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/job-postings/${PERSONA_JOB_ID}`,
					{ status: "Discovered" },
				);
			});
		});

		it("shows success toast on undismiss", async () => {
			mocks.mockApiPatch.mockResolvedValueOnce(undefined);
			const user = userEvent.setup();
			renderActions("Dismissed");

			await user.click(screen.getByRole("button", { name: UNDISMISS_LABEL }));

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
					"Job restored.",
				);
			});
		});

		it("invalidates queries but does not navigate on undismiss", async () => {
			mocks.mockApiPatch.mockResolvedValueOnce(undefined);
			const user = userEvent.setup();
			renderActions("Dismissed");

			await user.click(screen.getByRole("button", { name: UNDISMISS_LABEL }));

			await waitFor(() => {
				expect(mocks.mockInvalidateQueries).toHaveBeenCalled();
			});
			expect(mocks.mockPush).not.toHaveBeenCalled();
		});

		it("shows error toast on undismiss failure", async () => {
			mocks.mockApiPatch.mockRejectedValueOnce(
				new mocks.MockApiError("SERVER_ERROR", "Failed", 500),
			);
			const user = userEvent.setup();
			renderActions("Dismissed");

			await user.click(screen.getByRole("button", { name: UNDISMISS_LABEL }));

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					"Failed to restore job.",
				);
			});
		});
	});
});
