/**
 * Tests for the ChangeFlagsResolver component (§6.13).
 *
 * REQ-012 §7.6: Resolution UI for PersonaChangeFlags — review each
 * flag and choose "Add to all resumes", "Add to some", or "Skip".
 */

import {
	cleanup,
	fireEvent,
	render,
	screen,
	waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ChangeFlagsResolver } from "./change-flags-resolver";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const RESOLVER_TESTID = "change-flags-resolver";
const LOADING_TESTID = "loading-spinner";
const ADD_ALL_1 = "add-all-1";
const ADD_SOME_1 = "add-some-1";
const SKIP_1 = "skip-1";
const CONFIRM_SOME_1 = "confirm-some-1";
const RESUME_CHECKLIST_1 = "resume-checklist-1";
const FLAG_ERROR_1 = "flag-error-1";
const PATCH_FLAG_1_URL = "/persona-change-flags/1";
const GENERAL_RESUME = "General Resume";

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
		mockApiGet: vi.fn(),
		mockApiPatch: vi.fn(),
		mockShowToast: {
			success: vi.fn(),
			error: vi.fn(),
			warning: vi.fn(),
			info: vi.fn(),
			dismiss: vi.fn(),
		},
		MockApiError,
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPatch: mocks.mockApiPatch,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

vi.mock("next/link", () => ({
	default: ({
		href,
		children,
		...props
	}: {
		href: string;
		children: ReactNode;
		[key: string]: unknown;
	}) => (
		<a href={href} {...props}>
			{children}
		</a>
	),
}));

// ---------------------------------------------------------------------------
// Factories
// ---------------------------------------------------------------------------

const MOCK_LIST_META = { total: 0, page: 1, per_page: 20, total_pages: 1 };

function makeFlag(id: string, overrides: Record<string, unknown> = {}) {
	return {
		id,
		persona_id: "00000000-0000-4000-a000-000000000001",
		change_type: "skill_added" as const,
		item_id: `item-${id}`,
		item_description: `Added skill ${id}`,
		status: "Pending" as const,
		resolution: null,
		resolved_at: null,
		created_at: "2026-01-15T00:00:00Z",
		...overrides,
	};
}

function makeBaseResume(id: string, overrides: Record<string, unknown> = {}) {
	return {
		id,
		persona_id: "00000000-0000-4000-a000-000000000001",
		name: `Resume ${id}`,
		role_type: "Software Engineer",
		summary: "A summary",
		included_jobs: [],
		included_education: null,
		included_certifications: null,
		skills_emphasis: null,
		job_bullet_selections: {},
		job_bullet_order: {},
		rendered_at: null,
		is_primary: id === "1",
		status: "Active" as const,
		display_order: Number(id),
		archived_at: null,
		created_at: "2026-01-15T00:00:00Z",
		updated_at: "2026-01-15T00:00:00Z",
		...overrides,
	};
}

const MOCK_FLAGS_RESPONSE = {
	data: [
		makeFlag("1", {
			change_type: "job_added",
			item_description: "Senior Engineer at Acme",
		}),
		makeFlag("2", {
			change_type: "skill_added",
			item_description: "TypeScript",
		}),
		makeFlag("3", {
			change_type: "education_added",
			item_description: "MIT CS Degree",
		}),
	],
	meta: { ...MOCK_LIST_META, total: 3 },
};

const MOCK_SINGLE_FLAG_RESPONSE = {
	data: [makeFlag("1")],
	meta: { ...MOCK_LIST_META, total: 1 },
};

const MOCK_EMPTY_FLAGS_RESPONSE = {
	data: [],
	meta: { ...MOCK_LIST_META, total: 0 },
};

const MOCK_BASE_RESUMES_RESPONSE = {
	data: [
		makeBaseResume("1", { name: "General Resume" }),
		makeBaseResume("2", { name: "Tech Resume" }),
		makeBaseResume("3", { name: "Old Resume", status: "Archived" }),
	],
	meta: { ...MOCK_LIST_META, total: 3 },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createWrapper() {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: { retry: false },
		},
	});
	return function Wrapper({ children }: { children: ReactNode }) {
		return (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);
	};
}

function setupDefaultMocks() {
	mocks.mockApiGet.mockImplementation((path: string) => {
		if (path.includes("base-resumes")) {
			return Promise.resolve(MOCK_BASE_RESUMES_RESPONSE);
		}
		return Promise.resolve(MOCK_FLAGS_RESPONSE);
	});
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ChangeFlagsResolver", () => {
	beforeEach(() => {
		mocks.mockApiGet.mockReset();
		mocks.mockApiPatch.mockReset();
		mocks.mockShowToast.success.mockReset();
		mocks.mockShowToast.error.mockReset();
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	// -----------------------------------------------------------------------
	// Rendering
	// -----------------------------------------------------------------------

	describe("rendering", () => {
		it("shows loading spinner initially", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
		});

		it("renders heading with flag count after loading", async () => {
			setupDefaultMocks();

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByText("3 changes need review")).toBeInTheDocument();
			});
		});

		it("shows singular heading for 1 flag", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_SINGLE_FLAG_RESPONSE);

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByText("1 change needs review")).toBeInTheDocument();
			});
		});

		it("renders flag items with descriptions", async () => {
			setupDefaultMocks();

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByText(/Senior Engineer at Acme/)).toBeInTheDocument();
				expect(screen.getByText(/TypeScript/)).toBeInTheDocument();
				expect(screen.getByText(/MIT CS Degree/)).toBeInTheDocument();
			});
		});

		it("renders change type labels correctly", async () => {
			setupDefaultMocks();

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByText(/New job/)).toBeInTheDocument();
				expect(screen.getByText(/Added skill/)).toBeInTheDocument();
				expect(screen.getByText(/New education/)).toBeInTheDocument();
			});
		});

		it("renders three action buttons per flag", async () => {
			setupDefaultMocks();

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId(RESOLVER_TESTID)).toBeInTheDocument();
			});

			// 3 flags × 3 buttons = 9 action buttons total
			expect(screen.getAllByTestId(/^add-all-/)).toHaveLength(3);
			expect(screen.getAllByTestId(/^add-some-/)).toHaveLength(3);
			expect(screen.getAllByTestId(/^skip-/)).toHaveLength(3);
		});
	});

	// -----------------------------------------------------------------------
	// Empty state
	// -----------------------------------------------------------------------

	describe("empty state", () => {
		it("shows empty state when no pending flags", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_FLAGS_RESPONSE);

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByText("All changes resolved")).toBeInTheDocument();
			});
		});

		it("shows link to /persona in empty state", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_FLAGS_RESPONSE);

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				const link = screen.getByRole("link", { name: /back to profile/i });
				expect(link).toHaveAttribute("href", "/persona");
			});
		});
	});

	// -----------------------------------------------------------------------
	// Error state
	// -----------------------------------------------------------------------

	describe("error state", () => {
		it("shows failed state when API errors", async () => {
			mocks.mockApiGet.mockRejectedValue(
				new mocks.MockApiError("NETWORK_ERROR", "Connection failed", 0),
			);

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByRole("alert")).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Resolution — Add to All
	// -----------------------------------------------------------------------

	describe("resolution — add to all", () => {
		it("calls PATCH with added_to_all", async () => {
			setupDefaultMocks();
			mocks.mockApiPatch.mockResolvedValue({});

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId(ADD_ALL_1)).toBeInTheDocument();
			});

			fireEvent.click(screen.getByTestId(ADD_ALL_1));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(PATCH_FLAG_1_URL, {
					status: "Resolved",
					resolution: "added_to_all",
				});
			});
		});

		it("shows toast on success", async () => {
			setupDefaultMocks();
			mocks.mockApiPatch.mockResolvedValue({});

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId(ADD_ALL_1)).toBeInTheDocument();
			});

			fireEvent.click(screen.getByTestId(ADD_ALL_1));

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
					"Change resolved.",
				);
			});
		});

		it("removes resolved flag from list after invalidation", async () => {
			setupDefaultMocks();
			mocks.mockApiPatch.mockResolvedValue({});

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId("flag-1")).toBeInTheDocument();
			});

			// After resolving, mock returns without flag 1
			const updatedResponse = {
				data: [MOCK_FLAGS_RESPONSE.data[1], MOCK_FLAGS_RESPONSE.data[2]],
				meta: { ...MOCK_LIST_META, total: 2 },
			};
			mocks.mockApiGet.mockImplementation((path: string) => {
				if (path.includes("base-resumes")) {
					return Promise.resolve(MOCK_BASE_RESUMES_RESPONSE);
				}
				return Promise.resolve(updatedResponse);
			});

			fireEvent.click(screen.getByTestId(ADD_ALL_1));

			await waitFor(() => {
				expect(screen.queryByTestId("flag-1")).not.toBeInTheDocument();
			});
		});

		it("shows per-flag error on PATCH failure", async () => {
			setupDefaultMocks();
			mocks.mockApiPatch.mockRejectedValue(
				new mocks.MockApiError("SERVER_ERROR", "Internal error", 500),
			);

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId(ADD_ALL_1)).toBeInTheDocument();
			});

			fireEvent.click(screen.getByTestId(ADD_ALL_1));

			await waitFor(() => {
				expect(screen.getByTestId(FLAG_ERROR_1)).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Resolution — Skip
	// -----------------------------------------------------------------------

	describe("resolution — skip", () => {
		it("calls PATCH with skipped", async () => {
			setupDefaultMocks();
			mocks.mockApiPatch.mockResolvedValue({});

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId(SKIP_1)).toBeInTheDocument();
			});

			fireEvent.click(screen.getByTestId(SKIP_1));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(PATCH_FLAG_1_URL, {
					status: "Resolved",
					resolution: "skipped",
				});
			});
		});

		it("shows toast on successful skip", async () => {
			setupDefaultMocks();
			mocks.mockApiPatch.mockResolvedValue({});

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId(SKIP_1)).toBeInTheDocument();
			});

			fireEvent.click(screen.getByTestId(SKIP_1));

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
					"Change resolved.",
				);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Resolution — Add to Some
	// -----------------------------------------------------------------------

	describe("resolution — add to some", () => {
		it("expands base resume checklist on click", async () => {
			setupDefaultMocks();

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId(ADD_SOME_1)).toBeInTheDocument();
			});

			expect(screen.queryByTestId(RESUME_CHECKLIST_1)).not.toBeInTheDocument();

			fireEvent.click(screen.getByTestId(ADD_SOME_1));

			await waitFor(() => {
				expect(screen.getByTestId(RESUME_CHECKLIST_1)).toBeInTheDocument();
			});
		});

		it("fetches base resumes when expanding", async () => {
			setupDefaultMocks();

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId(ADD_SOME_1)).toBeInTheDocument();
			});

			fireEvent.click(screen.getByTestId(ADD_SOME_1));

			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith("/base-resumes");
			});
		});

		it("shows only Active base resumes", async () => {
			setupDefaultMocks();

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId(ADD_SOME_1)).toBeInTheDocument();
			});

			fireEvent.click(screen.getByTestId(ADD_SOME_1));

			await waitFor(() => {
				expect(screen.getByText(GENERAL_RESUME)).toBeInTheDocument();
				expect(screen.getByText("Tech Resume")).toBeInTheDocument();
			});

			// Archived resume should not appear
			expect(screen.queryByText("Old Resume")).not.toBeInTheDocument();
		});

		it("disables Confirm button when no checkboxes selected", async () => {
			setupDefaultMocks();

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId(ADD_SOME_1)).toBeInTheDocument();
			});

			fireEvent.click(screen.getByTestId(ADD_SOME_1));

			await waitFor(() => {
				expect(screen.getByTestId(CONFIRM_SOME_1)).toBeDisabled();
			});
		});

		it("enables Confirm button when checkbox selected", async () => {
			setupDefaultMocks();

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId(ADD_SOME_1)).toBeInTheDocument();
			});

			fireEvent.click(screen.getByTestId(ADD_SOME_1));

			await waitFor(() => {
				expect(screen.getByText(GENERAL_RESUME)).toBeInTheDocument();
			});

			// Click the first checkbox (General Resume)
			const checkboxes = screen.getAllByRole("checkbox");
			fireEvent.click(checkboxes[0]);

			expect(screen.getByTestId(CONFIRM_SOME_1)).not.toBeDisabled();
		});

		it("calls PATCH with added_to_some on confirm", async () => {
			setupDefaultMocks();
			mocks.mockApiPatch.mockResolvedValue({});

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId(ADD_SOME_1)).toBeInTheDocument();
			});

			fireEvent.click(screen.getByTestId(ADD_SOME_1));

			await waitFor(() => {
				expect(screen.getByText(GENERAL_RESUME)).toBeInTheDocument();
			});

			// Select a checkbox and confirm
			const checkboxes = screen.getAllByRole("checkbox");
			fireEvent.click(checkboxes[0]);
			fireEvent.click(screen.getByTestId(CONFIRM_SOME_1));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(PATCH_FLAG_1_URL, {
					status: "Resolved",
					resolution: "added_to_some",
				});
			});
		});

		it("collapses checklist on Cancel click", async () => {
			setupDefaultMocks();

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId(ADD_SOME_1)).toBeInTheDocument();
			});

			fireEvent.click(screen.getByTestId(ADD_SOME_1));

			await waitFor(() => {
				expect(screen.getByTestId(RESUME_CHECKLIST_1)).toBeInTheDocument();
			});

			fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

			expect(screen.queryByTestId(RESUME_CHECKLIST_1)).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Loading states
	// -----------------------------------------------------------------------

	describe("loading states", () => {
		it("disables buttons during resolution", async () => {
			setupDefaultMocks();
			// Make PATCH hang to keep resolving state
			mocks.mockApiPatch.mockReturnValue(new Promise(() => {}));

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId(ADD_ALL_1)).toBeInTheDocument();
			});

			fireEvent.click(screen.getByTestId(ADD_ALL_1));

			await waitFor(() => {
				expect(screen.getByTestId(ADD_ALL_1)).toBeDisabled();
				expect(screen.getByTestId(ADD_SOME_1)).toBeDisabled();
				expect(screen.getByTestId(SKIP_1)).toBeDisabled();
			});
		});

		it("re-enables buttons after failed resolution", async () => {
			setupDefaultMocks();
			mocks.mockApiPatch.mockRejectedValue(
				new mocks.MockApiError("SERVER_ERROR", "Internal error", 500),
			);

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId(ADD_ALL_1)).toBeInTheDocument();
			});

			fireEvent.click(screen.getByTestId(ADD_ALL_1));

			await waitFor(() => {
				expect(screen.getByTestId(FLAG_ERROR_1)).toBeInTheDocument();
			});

			expect(screen.getByTestId(ADD_ALL_1)).not.toBeDisabled();
			expect(screen.getByTestId(ADD_SOME_1)).not.toBeDisabled();
			expect(screen.getByTestId(SKIP_1)).not.toBeDisabled();
		});
	});

	// -----------------------------------------------------------------------
	// Navigation
	// -----------------------------------------------------------------------

	describe("navigation", () => {
		it("renders back link to /persona", async () => {
			setupDefaultMocks();

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<ChangeFlagsResolver />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId(RESOLVER_TESTID)).toBeInTheDocument();
			});

			const link = screen.getByRole("link", { name: /back to profile/i });
			expect(link).toHaveAttribute("href", "/persona");
		});
	});
});
