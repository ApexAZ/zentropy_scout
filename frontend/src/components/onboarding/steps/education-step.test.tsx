/**
 * Tests for the education step component.
 *
 * REQ-012 §6.3.4: Education form with skip option. Skippable step —
 * 0 entries is valid. Fields: degree, field_of_study, institution,
 * graduation_year (required), gpa, honors (optional).
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

import type { Education } from "@/types/persona";

import { EducationStep } from "./education-step";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const GENERIC_ERROR_TEXT = "Failed to save. Please try again.";

const MOCK_ENTRY_1: Education = {
	id: "edu-001",
	persona_id: DEFAULT_PERSONA_ID,
	institution: "MIT",
	degree: "Bachelor of Science",
	field_of_study: "Computer Science",
	graduation_year: 2018,
	gpa: 3.8,
	honors: "Magna Cum Laude",
	display_order: 0,
};

const MOCK_ENTRY_2: Education = {
	id: "edu-002",
	persona_id: DEFAULT_PERSONA_ID,
	institution: "Stanford University",
	degree: "Master of Science",
	field_of_study: "Machine Learning",
	graduation_year: 2020,
	gpa: null,
	honors: null,
	display_order: 1,
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
		mockSkip: vi.fn(),
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
		skip: mocks.mockSkip,
	}),
}));

// Mock ReorderableList to avoid DnD complexity in jsdom
let capturedOnReorder: ((items: Education[]) => void) | null = null;

vi.mock("@/components/ui/reorderable-list", () => ({
	ReorderableList: ({
		items,
		renderItem,
		onReorder,
		label,
	}: {
		items: Education[];
		renderItem: (
			item: Education,
			dragHandle: React.ReactNode | null,
		) => React.ReactNode;
		onReorder: (items: Education[]) => void;
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
	render(<EducationStep />);
	await waitFor(() => {
		expect(screen.queryByTestId("loading-education")).not.toBeInTheDocument();
	});
	return user;
}

async function fillEducationForm(
	user: ReturnType<typeof userEvent.setup>,
	overrides?: Partial<{
		institution: string;
		degree: string;
		fieldOfStudy: string;
		graduationYear: string;
		gpa: string;
		honors: string;
	}>,
) {
	const values = {
		institution: "Harvard University",
		degree: "Bachelor of Arts",
		fieldOfStudy: "Economics",
		graduationYear: "2019",
		...overrides,
	};

	await user.type(screen.getByLabelText(/institution/i), values.institution);
	await user.type(screen.getByLabelText(/degree/i), values.degree);
	await user.type(
		screen.getByLabelText(/field of study/i),
		values.fieldOfStudy,
	);
	await user.clear(screen.getByLabelText(/graduation year/i));
	await user.type(
		screen.getByLabelText(/graduation year/i),
		values.graduationYear,
	);

	if (values.gpa) {
		await user.type(screen.getByLabelText(/gpa/i), values.gpa);
	}
	if (values.honors) {
		await user.type(screen.getByLabelText(/honors/i), values.honors);
	}
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

describe("EducationStep", () => {
	beforeEach(() => {
		mocks.mockApiGet.mockReset();
		mocks.mockApiPost.mockReset();
		mocks.mockApiPatch.mockReset();
		mocks.mockApiDelete.mockReset();
		mocks.mockNext.mockReset();
		mocks.mockBack.mockReset();
		mocks.mockSkip.mockReset();
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
		it("shows loading spinner while fetching education", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
			render(<EducationStep />);

			expect(screen.getByTestId("loading-education")).toBeInTheDocument();
		});

		it("renders title and description after loading", async () => {
			mocks.mockApiGet.mockResolvedValueOnce(MOCK_EMPTY_LIST_RESPONSE);
			await renderAndWaitForLoad();

			expect(screen.getByText("Education")).toBeInTheDocument();
		});

		it("fetches education from correct endpoint", async () => {
			mocks.mockApiGet.mockResolvedValueOnce(MOCK_EMPTY_LIST_RESPONSE);
			await renderAndWaitForLoad();

			expect(mocks.mockApiGet).toHaveBeenCalledWith(
				`/personas/${DEFAULT_PERSONA_ID}/education`,
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

		it("shows skip prompt when no entries exist", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByText(/optional/i)).toBeInTheDocument();
		});

		it("shows Add education button", async () => {
			await renderAndWaitForLoad();

			expect(
				screen.getByRole("button", { name: /add education/i }),
			).toBeInTheDocument();
		});

		it("shows Skip button", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByRole("button", { name: /skip/i })).toBeInTheDocument();
		});

		it("enables Next button when no entries exist (skippable)", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByTestId("next-button")).toBeEnabled();
		});
	});

	// -----------------------------------------------------------------------
	// Card display
	// -----------------------------------------------------------------------

	describe("card display", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
		});

		it("renders education cards for each entry", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByText(/Bachelor of Science/)).toBeInTheDocument();
			expect(screen.getByText(/Master of Science/)).toBeInTheDocument();
		});

		it("shows institution name on cards", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByText("MIT")).toBeInTheDocument();
			expect(screen.getByText("Stanford University")).toBeInTheDocument();
		});

		it("shows graduation year on cards", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByText(/2018/)).toBeInTheDocument();
			expect(screen.getByText(/2020/)).toBeInTheDocument();
		});

		it("shows GPA when present", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByText(/3\.8/)).toBeInTheDocument();
		});

		it("shows honors when present", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByText(/Magna Cum Laude/)).toBeInTheDocument();
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

		it("hides skip button when entries exist", async () => {
			await renderAndWaitForLoad();

			expect(
				screen.queryByRole("button", { name: /skip/i }),
			).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Add education flow
	// -----------------------------------------------------------------------

	describe("add education flow", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
		});

		it("shows form when Add education is clicked", async () => {
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByRole("button", { name: /add education/i }));

			expect(screen.getByTestId("education-form")).toBeInTheDocument();
		});

		it("submits new education via POST and shows card", async () => {
			const newEntry: Education = {
				id: "edu-new",
				persona_id: DEFAULT_PERSONA_ID,
				institution: "Harvard University",
				degree: "Bachelor of Arts",
				field_of_study: "Economics",
				graduation_year: 2019,
				gpa: null,
				honors: null,
				display_order: 0,
			};
			mocks.mockApiPost.mockResolvedValueOnce({ data: newEntry });

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByRole("button", { name: /add education/i }));
			await fillEducationForm(user);
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/education`,
					expect.objectContaining({
						institution: "Harvard University",
						degree: "Bachelor of Arts",
						field_of_study: "Economics",
						graduation_year: 2019,
					}),
				);
			});
		});

		it("cancels add form and returns to list", async () => {
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByRole("button", { name: /add education/i }));
			expect(screen.getByTestId("education-form")).toBeInTheDocument();

			await user.click(screen.getByRole("button", { name: /cancel/i }));
			expect(screen.queryByTestId("education-form")).not.toBeInTheDocument();
		});

		it("shows error on failed POST", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(new Error("Network error"));

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByRole("button", { name: /add education/i }));
			await fillEducationForm(user);
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(screen.getByText(GENERIC_ERROR_TEXT)).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Edit education flow
	// -----------------------------------------------------------------------

	describe("edit education flow", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
		});

		it("opens form with pre-filled data when edit is clicked", async () => {
			const user = await renderAndWaitForLoad();

			const entry1 = screen.getByTestId("entry-edu-001");
			await user.click(within(entry1).getByRole("button", { name: /edit/i }));

			const form = screen.getByTestId("education-form");
			expect(within(form).getByDisplayValue("MIT")).toBeInTheDocument();
			expect(
				within(form).getByDisplayValue("Bachelor of Science"),
			).toBeInTheDocument();
			expect(
				within(form).getByDisplayValue("Computer Science"),
			).toBeInTheDocument();
		});

		it("submits updated education via PATCH", async () => {
			mocks.mockApiPatch.mockResolvedValueOnce({
				data: { ...MOCK_ENTRY_1, degree: "Master of Science" },
			});

			const user = await renderAndWaitForLoad();
			const entry1 = screen.getByTestId("entry-edu-001");
			await user.click(within(entry1).getByRole("button", { name: /edit/i }));

			const degreeInput = screen.getByDisplayValue("Bachelor of Science");
			await user.clear(degreeInput);
			await user.type(degreeInput, "Master of Science");
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/education/edu-001`,
					expect.objectContaining({ degree: "Master of Science" }),
				);
			});
		});

		it("cancels edit without saving changes", async () => {
			const user = await renderAndWaitForLoad();
			const entry1 = screen.getByTestId("entry-edu-001");
			await user.click(within(entry1).getByRole("button", { name: /edit/i }));

			await user.click(screen.getByRole("button", { name: /cancel/i }));

			expect(mocks.mockApiPatch).not.toHaveBeenCalled();
			expect(screen.getByText(/Bachelor of Science/)).toBeInTheDocument();
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

			const entry1 = screen.getByTestId("entry-edu-001");
			await user.click(within(entry1).getByRole("button", { name: /delete/i }));

			expect(screen.getByText(/are you sure/i)).toBeInTheDocument();
		});

		it("deletes education on confirm and removes card", async () => {
			mocks.mockApiDelete.mockResolvedValueOnce(undefined);

			const user = await renderAndWaitForLoad();
			const entry1 = screen.getByTestId("entry-edu-001");
			await user.click(within(entry1).getByRole("button", { name: /delete/i }));

			const confirmButton = screen.getByRole("button", {
				name: /^delete$/i,
			});
			await user.click(confirmButton);

			await waitFor(() => {
				expect(mocks.mockApiDelete).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/education/edu-001`,
				);
			});
			expect(screen.queryByText("Bachelor of Science")).not.toBeInTheDocument();
		});

		it("keeps card when delete API call fails", async () => {
			mocks.mockApiDelete.mockRejectedValueOnce(new Error("Network error"));

			const user = await renderAndWaitForLoad();
			const entry1 = screen.getByTestId("entry-edu-001");
			await user.click(within(entry1).getByRole("button", { name: /delete/i }));

			const confirmButton = screen.getByRole("button", {
				name: /^delete$/i,
			});
			await user.click(confirmButton);

			await waitFor(() => {
				expect(mocks.mockApiDelete).toHaveBeenCalledTimes(1);
			});
			// Card should still be visible after failed delete
			expect(screen.getByTestId("entry-edu-001")).toBeInTheDocument();
		});

		it("cancels delete without removing card", async () => {
			const user = await renderAndWaitForLoad();
			const entry1 = screen.getByTestId("entry-edu-001");
			await user.click(within(entry1).getByRole("button", { name: /delete/i }));

			await user.click(screen.getByRole("button", { name: /cancel/i }));

			expect(mocks.mockApiDelete).not.toHaveBeenCalled();
			expect(screen.getByText(/Bachelor of Science/)).toBeInTheDocument();
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

			// Simulate reorder: swap entries
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
		it("calls next() when Next is clicked", async () => {
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

		it("calls skip() when Skip is clicked", async () => {
			mocks.mockApiGet.mockResolvedValueOnce(MOCK_EMPTY_LIST_RESPONSE);
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByRole("button", { name: /skip/i }));

			expect(mocks.mockSkip).toHaveBeenCalledTimes(1);
		});

		it("allows Next with zero entries (skippable step)", async () => {
			mocks.mockApiGet.mockResolvedValueOnce(MOCK_EMPTY_LIST_RESPONSE);
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByTestId("next-button"));

			expect(mocks.mockNext).toHaveBeenCalledTimes(1);
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

			await user.click(screen.getByRole("button", { name: /add education/i }));
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(
					screen.getAllByText(/is required/i).length,
				).toBeGreaterThanOrEqual(1);
			});
			expect(mocks.mockApiPost).not.toHaveBeenCalled();
		});

		it("validates graduation year is a reasonable number", async () => {
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByRole("button", { name: /add education/i }));

			await user.type(screen.getByLabelText(/institution/i), "Test U");
			await user.type(screen.getByLabelText(/degree/i), "BS");
			await user.type(screen.getByLabelText(/field of study/i), "Math");
			await user.clear(screen.getByLabelText(/graduation year/i));
			await user.type(screen.getByLabelText(/graduation year/i), "1800");

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(
					screen.getAllByText(/1950 or later/i).length,
				).toBeGreaterThanOrEqual(1);
			});
			expect(mocks.mockApiPost).not.toHaveBeenCalled();
		});
	});
});
