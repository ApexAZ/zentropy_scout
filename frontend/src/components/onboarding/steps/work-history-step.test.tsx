/**
 * Tests for the work history step component.
 *
 * REQ-012 §6.3.3: Display extracted jobs in editable cards with
 * add/edit/delete and ordering, minimum 1 job required to proceed.
 */

import {
	cleanup,
	render,
	screen,
	waitFor,
	within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { WorkHistory } from "@/types/persona";

import { WorkHistoryStep } from "./work-history-step";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const GENERIC_ERROR_TEXT = "Failed to save. Please try again.";

const MOCK_ENTRY_1: WorkHistory = {
	id: "wh-001",
	persona_id: DEFAULT_PERSONA_ID,
	job_title: "Software Engineer",
	company_name: "Acme Corp",
	company_industry: "Technology",
	location: "San Francisco, CA",
	work_model: "Remote",
	start_date: "2020-01-01",
	end_date: "2023-06-01",
	is_current: false,
	description: "Built web applications",
	display_order: 0,
	bullets: [],
};

const MOCK_ENTRY_2: WorkHistory = {
	id: "wh-002",
	persona_id: DEFAULT_PERSONA_ID,
	job_title: "Senior Developer",
	company_name: "TechCo",
	company_industry: null,
	location: "New York, NY",
	work_model: "Hybrid",
	start_date: "2023-07-01",
	end_date: null,
	is_current: true,
	description: null,
	display_order: 1,
	bullets: [],
};

const MOCK_LIST_RESPONSE = {
	data: [MOCK_ENTRY_1, MOCK_ENTRY_2],
	meta: { total: 2, page: 1, per_page: 20 },
};

const MOCK_EMPTY_LIST_RESPONSE = {
	data: [],
	meta: { total: 0, page: 1, per_page: 20 },
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
		mockApiGet: vi.fn(),
		mockApiPost: vi.fn(),
		mockApiPatch: vi.fn(),
		mockApiDelete: vi.fn(),
		MockApiError,
		mockNext: vi.fn(),
		mockBack: vi.fn(),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPost: mocks.mockApiPost,
	apiPatch: mocks.mockApiPatch,
	apiDelete: mocks.mockApiDelete,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/onboarding-provider", () => ({
	useOnboarding: () => ({
		personaId: DEFAULT_PERSONA_ID,
		next: mocks.mockNext,
		back: mocks.mockBack,
	}),
}));

// Mock ReorderableList to avoid DnD complexity in jsdom
let capturedOnReorder: ((items: WorkHistory[]) => void) | null = null;

vi.mock("@/components/ui/reorderable-list", () => ({
	ReorderableList: ({
		items,
		renderItem,
		onReorder,
		label,
	}: {
		items: WorkHistory[];
		renderItem: (
			item: WorkHistory,
			dragHandle: React.ReactNode | null,
		) => React.ReactNode;
		onReorder: (items: WorkHistory[]) => void;
		label: string;
	}) => {
		capturedOnReorder = onReorder;
		return (
			<div aria-label={label} data-testid="reorderable-list">
				{items.map((item) => (
					<div key={item.id} data-testid={`entry-${item.id}`}>
						{renderItem(item, null)}
					</div>
				))}
			</div>
		);
	},
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function renderAndWaitForLoad() {
	const user = userEvent.setup();
	render(<WorkHistoryStep />);
	await waitFor(() => {
		expect(
			screen.queryByTestId("loading-work-history"),
		).not.toBeInTheDocument();
	});
	return user;
}

async function fillJobForm(
	user: ReturnType<typeof userEvent.setup>,
	overrides?: Partial<{
		jobTitle: string;
		company: string;
		location: string;
		workModel: string;
		startDate: string;
		isCurrent: boolean;
	}>,
) {
	const values = {
		jobTitle: "QA Engineer",
		company: "TestCorp",
		location: "Austin, TX",
		workModel: "Remote",
		startDate: "2024-01",
		isCurrent: true,
		...overrides,
	};

	await user.type(screen.getByLabelText(/job title/i), values.jobTitle);
	await user.type(screen.getByLabelText(/company name/i), values.company);
	await user.type(screen.getByLabelText(/location/i), values.location);

	await user.selectOptions(
		screen.getByLabelText(/work model/i),
		values.workModel,
	);

	await user.type(screen.getByLabelText(/start date/i), values.startDate);

	if (values.isCurrent) {
		await user.click(screen.getByRole("checkbox", { name: /current/i }));
	}
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

describe("WorkHistoryStep", () => {
	beforeEach(() => {
		mocks.mockApiGet.mockReset();
		mocks.mockApiPost.mockReset();
		mocks.mockApiPatch.mockReset();
		mocks.mockApiDelete.mockReset();
		mocks.mockNext.mockReset();
		mocks.mockBack.mockReset();
		capturedOnReorder = null;
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	// -----------------------------------------------------------------------
	// Rendering & loading
	// -----------------------------------------------------------------------

	describe("rendering", () => {
		it("shows loading spinner while fetching work history", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
			render(<WorkHistoryStep />);

			expect(screen.getByTestId("loading-work-history")).toBeInTheDocument();
		});

		it("renders title and description after loading", async () => {
			mocks.mockApiGet.mockResolvedValueOnce(MOCK_EMPTY_LIST_RESPONSE);
			await renderAndWaitForLoad();

			expect(screen.getByText("Work History")).toBeInTheDocument();
		});

		it("fetches work history from correct endpoint", async () => {
			mocks.mockApiGet.mockResolvedValueOnce(MOCK_EMPTY_LIST_RESPONSE);
			await renderAndWaitForLoad();

			expect(mocks.mockApiGet).toHaveBeenCalledWith(
				`/personas/${DEFAULT_PERSONA_ID}/work-history`,
			);
		});
	});

	// -----------------------------------------------------------------------
	// Empty state
	// -----------------------------------------------------------------------

	describe("empty state", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
		});

		it("shows empty message when no entries exist", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByText(/add your first job/i)).toBeInTheDocument();
		});

		it("shows Add a job button", async () => {
			await renderAndWaitForLoad();

			expect(
				screen.getByRole("button", { name: /add a job/i }),
			).toBeInTheDocument();
		});

		it("disables Next button when no entries exist", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByTestId("next-button")).toBeDisabled();
		});
	});

	// -----------------------------------------------------------------------
	// Card display
	// -----------------------------------------------------------------------

	describe("card display", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
		});

		it("renders job cards for each entry", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByText("Software Engineer")).toBeInTheDocument();
			expect(screen.getByText("Senior Developer")).toBeInTheDocument();
		});

		it("shows company name on cards", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByText("Acme Corp")).toBeInTheDocument();
			expect(screen.getByText("TechCo")).toBeInTheDocument();
		});

		it("shows formatted date range on cards", async () => {
			await renderAndWaitForLoad();

			// MOCK_ENTRY_1: 2020-01 to 2023-06
			expect(screen.getByText(/Jan 2020/)).toBeInTheDocument();
			expect(screen.getByText(/Jun 2023/)).toBeInTheDocument();
		});

		it("shows Present for current jobs", async () => {
			await renderAndWaitForLoad();

			// MOCK_ENTRY_2: is_current = true
			expect(screen.getByText(/Present/)).toBeInTheDocument();
		});

		it("shows location and work model on cards", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByText(/San Francisco, CA/)).toBeInTheDocument();
			expect(screen.getByText(/Remote/)).toBeInTheDocument();
		});

		it("shows edit and delete buttons on each card", async () => {
			await renderAndWaitForLoad();

			const editButtons = screen.getAllByRole("button", { name: /edit/i });
			const deleteButtons = screen.getAllByRole("button", {
				name: /delete/i,
			});

			expect(editButtons.length).toBeGreaterThanOrEqual(2);
			expect(deleteButtons.length).toBeGreaterThanOrEqual(2);
		});

		it("enables Next button when entries exist", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByTestId("next-button")).toBeEnabled();
		});
	});

	// -----------------------------------------------------------------------
	// Add job flow
	// -----------------------------------------------------------------------

	describe("add job flow", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
		});

		it("shows form when Add a job is clicked", async () => {
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByRole("button", { name: /add a job/i }));

			expect(screen.getByTestId("work-history-form")).toBeInTheDocument();
		});

		it("submits new job via POST and shows card", async () => {
			const newEntry: WorkHistory = {
				...MOCK_ENTRY_1,
				id: "wh-new",
				job_title: "QA Engineer",
				company_name: "TestCorp",
				location: "Austin, TX",
				work_model: "Remote",
				is_current: true,
				end_date: null,
			};
			mocks.mockApiPost.mockResolvedValueOnce({ data: newEntry });

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByRole("button", { name: /add a job/i }));
			await fillJobForm(user);
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/work-history`,
					expect.objectContaining({
						job_title: "QA Engineer",
						company_name: "TestCorp",
					}),
				);
			});
		});

		it("cancels add form and returns to list", async () => {
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByRole("button", { name: /add a job/i }));
			expect(screen.getByTestId("work-history-form")).toBeInTheDocument();

			await user.click(screen.getByRole("button", { name: /cancel/i }));
			expect(screen.queryByTestId("work-history-form")).not.toBeInTheDocument();
		});

		it("shows error on failed POST", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(new Error("Network error"));

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByRole("button", { name: /add a job/i }));
			await fillJobForm(user);
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(screen.getByText(GENERIC_ERROR_TEXT)).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Edit job flow
	// -----------------------------------------------------------------------

	describe("edit job flow", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
		});

		it("opens form with pre-filled data when edit is clicked", async () => {
			const user = await renderAndWaitForLoad();

			const entry1 = screen.getByTestId("entry-wh-001");
			await user.click(within(entry1).getByRole("button", { name: /edit/i }));

			const form = screen.getByTestId("work-history-form");
			expect(
				within(form).getByDisplayValue("Software Engineer"),
			).toBeInTheDocument();
			expect(within(form).getByDisplayValue("Acme Corp")).toBeInTheDocument();
		});

		it("submits updated job via PATCH", async () => {
			mocks.mockApiPatch.mockResolvedValueOnce({
				data: { ...MOCK_ENTRY_1, job_title: "Lead Engineer" },
			});

			const user = await renderAndWaitForLoad();
			const entry1 = screen.getByTestId("entry-wh-001");
			await user.click(within(entry1).getByRole("button", { name: /edit/i }));

			const titleInput = screen.getByDisplayValue("Software Engineer");
			await user.clear(titleInput);
			await user.type(titleInput, "Lead Engineer");
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/work-history/wh-001`,
					expect.objectContaining({ job_title: "Lead Engineer" }),
				);
			});
		});

		it("cancels edit without saving changes", async () => {
			const user = await renderAndWaitForLoad();
			const entry1 = screen.getByTestId("entry-wh-001");
			await user.click(within(entry1).getByRole("button", { name: /edit/i }));

			await user.click(screen.getByRole("button", { name: /cancel/i }));

			expect(mocks.mockApiPatch).not.toHaveBeenCalled();
			expect(screen.getByText("Software Engineer")).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Delete flow
	// -----------------------------------------------------------------------

	describe("delete flow", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
		});

		it("shows confirmation dialog when delete is clicked", async () => {
			const user = await renderAndWaitForLoad();

			const entry1 = screen.getByTestId("entry-wh-001");
			await user.click(within(entry1).getByRole("button", { name: /delete/i }));

			expect(screen.getByText(/are you sure/i)).toBeInTheDocument();
		});

		it("deletes job on confirm and removes card", async () => {
			mocks.mockApiDelete.mockResolvedValueOnce(undefined);

			const user = await renderAndWaitForLoad();
			const entry1 = screen.getByTestId("entry-wh-001");
			await user.click(within(entry1).getByRole("button", { name: /delete/i }));

			// Click confirm in the ConfirmationDialog
			const confirmButton = screen.getByRole("button", {
				name: /^delete$/i,
			});
			await user.click(confirmButton);

			await waitFor(() => {
				expect(mocks.mockApiDelete).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/work-history/wh-001`,
				);
			});
			expect(screen.queryByText("Software Engineer")).not.toBeInTheDocument();
		});

		it("keeps card when delete API call fails", async () => {
			mocks.mockApiDelete.mockRejectedValueOnce(new Error("Network error"));

			const user = await renderAndWaitForLoad();
			const entry1 = screen.getByTestId("entry-wh-001");
			await user.click(within(entry1).getByRole("button", { name: /delete/i }));

			const confirmButton = screen.getByRole("button", {
				name: /^delete$/i,
			});
			await user.click(confirmButton);

			await waitFor(() => {
				expect(mocks.mockApiDelete).toHaveBeenCalledTimes(1);
			});
			// Card should still be visible after failed delete
			expect(screen.getByText("Software Engineer")).toBeInTheDocument();
		});

		it("cancels delete without removing card", async () => {
			const user = await renderAndWaitForLoad();
			const entry1 = screen.getByTestId("entry-wh-001");
			await user.click(within(entry1).getByRole("button", { name: /delete/i }));

			await user.click(screen.getByRole("button", { name: /cancel/i }));

			expect(mocks.mockApiDelete).not.toHaveBeenCalled();
			expect(screen.getByText("Software Engineer")).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Reordering
	// -----------------------------------------------------------------------

	describe("reordering", () => {
		it("calls PATCH to update display_order after reorder", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			mocks.mockApiPatch.mockResolvedValue({ data: {} });

			await renderAndWaitForLoad();

			expect(capturedOnReorder).not.toBeNull();

			// Simulate reorder: swap entries (keep original display_order values
			// so handleReorder detects the change)
			capturedOnReorder!([MOCK_ENTRY_2, MOCK_ENTRY_1]);

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalled();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Navigation
	// -----------------------------------------------------------------------

	describe("navigation", () => {
		it("calls next() when Next is clicked with entries", async () => {
			mocks.mockApiGet.mockResolvedValueOnce(MOCK_LIST_RESPONSE);
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByTestId("next-button"));

			expect(mocks.mockNext).toHaveBeenCalledTimes(1);
		});

		it("calls back() when Back is clicked", async () => {
			mocks.mockApiGet.mockResolvedValueOnce(MOCK_LIST_RESPONSE);
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByTestId("back-button"));

			expect(mocks.mockBack).toHaveBeenCalledTimes(1);
		});
	});

	// -----------------------------------------------------------------------
	// Form validation
	// -----------------------------------------------------------------------

	describe("form validation", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
		});

		it("shows validation errors for empty required fields", async () => {
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByRole("button", { name: /add a job/i }));
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(
					screen.getAllByText(/is required/i).length,
				).toBeGreaterThanOrEqual(1);
			});
			expect(mocks.mockApiPost).not.toHaveBeenCalled();
		});

		it("requires end date when job is not current", async () => {
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByRole("button", { name: /add a job/i }));

			// Fill required fields but leave is_current unchecked and end_date empty
			await user.type(screen.getByLabelText(/job title/i), "Test Role");
			await user.type(screen.getByLabelText(/company name/i), "Test Co");
			await user.type(screen.getByLabelText(/location/i), "Denver, CO");
			await user.selectOptions(screen.getByLabelText(/work model/i), "Remote");
			await user.type(screen.getByLabelText(/start date/i), "2020-01");
			// Do NOT check is_current, do NOT fill end_date

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(
					screen.getAllByText(/end date is required/i).length,
				).toBeGreaterThanOrEqual(1);
			});
		});

		it("does not require end date when is_current is checked", async () => {
			const newEntry: WorkHistory = {
				...MOCK_ENTRY_1,
				id: "wh-new",
				is_current: true,
				end_date: null,
			};
			mocks.mockApiPost.mockResolvedValueOnce({ data: newEntry });

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByRole("button", { name: /add a job/i }));
			await fillJobForm(user);
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledTimes(1);
			});
		});
	});
});
