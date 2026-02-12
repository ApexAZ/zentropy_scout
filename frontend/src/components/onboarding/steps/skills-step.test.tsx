/**
 * Tests for the skills step component.
 *
 * REQ-012 §6.3.5: Skills editor with proficiency selector and category
 * dropdown. Not skippable. All 6 fields required per skill.
 * Category options change based on skill_type (Hard / Soft).
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

import type { Skill } from "@/types/persona";

import { SkillsStep } from "./skills-step";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";

const MOCK_SKILL_1: Skill = {
	id: "skill-001",
	persona_id: DEFAULT_PERSONA_ID,
	skill_name: "Python",
	skill_type: "Hard",
	category: "Programming Language",
	proficiency: "Expert",
	years_used: 8,
	last_used: "Current",
	display_order: 0,
};

const MOCK_SKILL_2: Skill = {
	id: "skill-002",
	persona_id: DEFAULT_PERSONA_ID,
	skill_name: "Leadership",
	skill_type: "Soft",
	category: "Leadership & Management",
	proficiency: "Proficient",
	years_used: 5,
	last_used: "2024",
	display_order: 1,
};

const MOCK_LIST_RESPONSE = {
	data: [MOCK_SKILL_1, MOCK_SKILL_2],
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
let capturedOnReorder: ((items: Skill[]) => void) | null = null;

vi.mock("@/components/ui/reorderable-list", () => ({
	ReorderableList: ({
		items,
		renderItem,
		onReorder,
		label,
	}: {
		items: Skill[];
		renderItem: (
			item: Skill,
			dragHandle: React.ReactNode | null,
		) => React.ReactNode;
		onReorder: (items: Skill[]) => void;
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
	render(<SkillsStep />);
	await waitFor(() => {
		expect(screen.queryByTestId("loading-skills")).not.toBeInTheDocument();
	});
	return user;
}

async function fillSkillForm(
	user: ReturnType<typeof userEvent.setup>,
	overrides?: Partial<{
		skillName: string;
		skillType: string;
		category: string;
		proficiency: string;
		yearsUsed: string;
		lastUsed: string;
	}>,
) {
	const values = {
		skillName: "JavaScript",
		skillType: "Hard",
		category: "Programming Language",
		proficiency: "Proficient",
		yearsUsed: "5",
		lastUsed: "Current",
		...overrides,
	};

	await user.type(screen.getByLabelText(/skill name/i), values.skillName);
	await user.click(screen.getByRole("radio", { name: values.skillType }));
	await user.selectOptions(screen.getByLabelText(/category/i), values.category);
	await user.click(screen.getByRole("radio", { name: values.proficiency }));
	await user.clear(screen.getByLabelText(/years used/i));
	await user.type(screen.getByLabelText(/years used/i), values.yearsUsed);
	await user.clear(screen.getByLabelText(/last used/i));
	await user.type(screen.getByLabelText(/last used/i), values.lastUsed);
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

describe("SkillsStep", () => {
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
		it("shows loading spinner while fetching skills", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
			render(<SkillsStep />);
			expect(screen.getByTestId("loading-skills")).toBeInTheDocument();
		});

		it("renders list view after loading completes", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			await renderAndWaitForLoad();
			expect(screen.getByText("Skills")).toBeInTheDocument();
			expect(screen.getByText(/add skill/i)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Empty state
	// -----------------------------------------------------------------------

	describe("empty state", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
		});

		it("shows empty message when no skills exist", async () => {
			await renderAndWaitForLoad();
			expect(screen.getByText(/no skills yet/i)).toBeInTheDocument();
		});

		it("does not show skip button (skills is not skippable)", async () => {
			await renderAndWaitForLoad();
			expect(
				screen.queryByRole("button", { name: /skip/i }),
			).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Card display
	// -----------------------------------------------------------------------

	describe("card display", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
		});

		it("shows skill name and type badge for each entry", async () => {
			await renderAndWaitForLoad();
			expect(screen.getByText("Python")).toBeInTheDocument();
			expect(screen.getByText("Leadership")).toBeInTheDocument();
			// Type badges
			expect(screen.getByText("Hard")).toBeInTheDocument();
			expect(screen.getByText("Soft")).toBeInTheDocument();
		});

		it("shows category for each entry", async () => {
			await renderAndWaitForLoad();
			expect(screen.getByText("Programming Language")).toBeInTheDocument();
			expect(screen.getByText("Leadership & Management")).toBeInTheDocument();
		});

		it("shows proficiency for each entry", async () => {
			await renderAndWaitForLoad();
			// Proficiency is combined with metadata in a single line
			expect(screen.getByText(/expert/i)).toBeInTheDocument();
			expect(screen.getByText(/proficient/i)).toBeInTheDocument();
		});

		it("shows years used and last used metadata", async () => {
			await renderAndWaitForLoad();
			expect(screen.getByText(/8 years/i)).toBeInTheDocument();
			expect(screen.getByText(/current/i)).toBeInTheDocument();
			expect(screen.getByText(/5 years/i)).toBeInTheDocument();
			expect(screen.getByText(/2024/)).toBeInTheDocument();
		});

		it("shows edit and delete buttons for each card", async () => {
			await renderAndWaitForLoad();
			expect(screen.getByLabelText(/edit python/i)).toBeInTheDocument();
			expect(screen.getByLabelText(/delete python/i)).toBeInTheDocument();
			expect(screen.getByLabelText(/edit leadership/i)).toBeInTheDocument();
			expect(screen.getByLabelText(/delete leadership/i)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Add flow
	// -----------------------------------------------------------------------

	describe("add flow", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
		});

		it("opens form when clicking add skill", async () => {
			const user = await renderAndWaitForLoad();
			await user.click(screen.getByText(/add skill/i));
			expect(screen.getByTestId("skills-form")).toBeInTheDocument();
		});

		it("submits new skill via POST and returns to list", async () => {
			const newSkill: Skill = {
				id: "skill-new",
				persona_id: DEFAULT_PERSONA_ID,
				skill_name: "JavaScript",
				skill_type: "Hard",
				category: "Programming Language",
				proficiency: "Proficient",
				years_used: 5,
				last_used: "Current",
				display_order: 0,
			};
			mocks.mockApiPost.mockResolvedValue({ data: newSkill });

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByText(/add skill/i));
			await fillSkillForm(user);
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/skills`,
					expect.objectContaining({
						skill_name: "JavaScript",
						skill_type: "Hard",
						category: "Programming Language",
						proficiency: "Proficient",
						years_used: 5,
						last_used: "Current",
					}),
				);
			});

			// Returns to list
			await waitFor(() => {
				expect(screen.queryByTestId("skills-form")).not.toBeInTheDocument();
			});
			expect(screen.getByText("JavaScript")).toBeInTheDocument();
		});

		it("returns to list on cancel without saving", async () => {
			const user = await renderAndWaitForLoad();
			await user.click(screen.getByText(/add skill/i));
			expect(screen.getByTestId("skills-form")).toBeInTheDocument();

			await user.click(screen.getByRole("button", { name: /cancel/i }));
			expect(screen.queryByTestId("skills-form")).not.toBeInTheDocument();
			expect(mocks.mockApiPost).not.toHaveBeenCalled();
		});

		it("shows error message on API failure", async () => {
			mocks.mockApiPost.mockRejectedValue(new Error("Network error"));

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByText(/add skill/i));
			await fillSkillForm(user);
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(screen.getByTestId("submit-error")).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Edit flow
	// -----------------------------------------------------------------------

	describe("edit flow", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
		});

		it("opens pre-filled form on edit click", async () => {
			const user = await renderAndWaitForLoad();
			await user.click(screen.getByLabelText(/edit python/i));

			expect(screen.getByTestId("skills-form")).toBeInTheDocument();
			expect(screen.getByLabelText(/skill name/i)).toHaveValue("Python");
			expect(screen.getByRole("radio", { name: "Hard" })).toBeChecked();
			expect(screen.getByLabelText(/category/i)).toHaveValue(
				"Programming Language",
			);
			expect(screen.getByRole("radio", { name: "Expert" })).toBeChecked();
			expect(screen.getByLabelText(/years used/i)).toHaveValue(8);
			expect(screen.getByLabelText(/last used/i)).toHaveValue("Current");
		});

		it("submits update via PATCH", async () => {
			const updated = { ...MOCK_SKILL_1, proficiency: "Proficient" as const };
			mocks.mockApiPatch.mockResolvedValue({ data: updated });

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByLabelText(/edit python/i));

			// Change proficiency
			await user.click(screen.getByRole("radio", { name: "Proficient" }));
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/skills/${MOCK_SKILL_1.id}`,
					expect.objectContaining({
						skill_name: "Python",
						proficiency: "Proficient",
					}),
				);
			});
		});

		it("shows error on API failure during edit", async () => {
			mocks.mockApiPatch.mockRejectedValue(new Error("Server error"));

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByLabelText(/edit python/i));
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(screen.getByTestId("submit-error")).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Delete flow
	// -----------------------------------------------------------------------

	describe("delete flow", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
		});

		it("opens confirmation dialog on delete click", async () => {
			const user = await renderAndWaitForLoad();
			await user.click(screen.getByLabelText(/delete python/i));

			const dialog = screen.getByRole("alertdialog");
			expect(
				within(dialog).getByText(/are you sure you want to delete/i),
			).toBeInTheDocument();
		});

		it("deletes skill via DELETE on confirm", async () => {
			mocks.mockApiDelete.mockResolvedValue(undefined);

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByLabelText(/delete python/i));

			const dialog = screen.getByRole("alertdialog");
			await user.click(within(dialog).getByRole("button", { name: /delete/i }));

			await waitFor(() => {
				expect(mocks.mockApiDelete).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/skills/${MOCK_SKILL_1.id}`,
				);
			});

			// Card removed from list
			await waitFor(() => {
				expect(screen.queryByText("Python")).not.toBeInTheDocument();
			});
		});

		it("closes dialog without deleting on cancel", async () => {
			const user = await renderAndWaitForLoad();
			await user.click(screen.getByLabelText(/delete python/i));

			const dialog = screen.getByRole("alertdialog");
			await user.click(within(dialog).getByRole("button", { name: /cancel/i }));

			await waitFor(() => {
				expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
			});
			expect(screen.getByText("Python")).toBeInTheDocument();
			expect(mocks.mockApiDelete).not.toHaveBeenCalled();
		});
	});

	// -----------------------------------------------------------------------
	// Reorder
	// -----------------------------------------------------------------------

	describe("reorder", () => {
		it("PATCHes display_order when entries are reordered", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			mocks.mockApiPatch.mockResolvedValue({});

			await renderAndWaitForLoad();

			// Pass original objects in swapped order — handler detects
			// display_order mismatch with array index
			const reordered = [MOCK_SKILL_2, MOCK_SKILL_1];

			capturedOnReorder!(reordered);

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/skills/${MOCK_SKILL_2.id}`,
					{ display_order: 0 },
				);
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/skills/${MOCK_SKILL_1.id}`,
					{ display_order: 1 },
				);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Navigation
	// -----------------------------------------------------------------------

	describe("navigation", () => {
		it("calls next() on Next button click", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			const user = await renderAndWaitForLoad();
			await user.click(screen.getByTestId("next-button"));
			expect(mocks.mockNext).toHaveBeenCalledTimes(1);
		});

		it("calls back() on Back button click", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			const user = await renderAndWaitForLoad();
			await user.click(screen.getByTestId("back-button"));
			expect(mocks.mockBack).toHaveBeenCalledTimes(1);
		});

		it("does not show skip button even when list is empty", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
			await renderAndWaitForLoad();
			expect(
				screen.queryByRole("button", { name: /skip/i }),
			).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Category conditional
	// -----------------------------------------------------------------------

	describe("category conditional", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
		});

		it("shows hard skill categories when Hard is selected", async () => {
			const user = await renderAndWaitForLoad();
			await user.click(screen.getByText(/add skill/i));

			await user.click(screen.getByRole("radio", { name: "Hard" }));

			const categorySelect = screen.getByLabelText(/category/i);
			const options = within(categorySelect).getAllByRole("option");
			const optionTexts = options.map((o) => o.textContent);

			expect(optionTexts).toContain("Programming Language");
			expect(optionTexts).toContain("Framework / Library");
			expect(optionTexts).not.toContain("Leadership & Management");
		});

		it("shows soft skill categories when Soft is selected", async () => {
			const user = await renderAndWaitForLoad();
			await user.click(screen.getByText(/add skill/i));

			await user.click(screen.getByRole("radio", { name: "Soft" }));

			const categorySelect = screen.getByLabelText(/category/i);
			const options = within(categorySelect).getAllByRole("option");
			const optionTexts = options.map((o) => o.textContent);

			expect(optionTexts).toContain("Leadership & Management");
			expect(optionTexts).toContain("Communication");
			expect(optionTexts).not.toContain("Programming Language");
		});

		it("clears category when switching skill type", async () => {
			const user = await renderAndWaitForLoad();
			await user.click(screen.getByText(/add skill/i));

			// Select Hard and choose a hard category
			await user.click(screen.getByRole("radio", { name: "Hard" }));
			await user.selectOptions(
				screen.getByLabelText(/category/i),
				"Programming Language",
			);

			// Switch to Soft — category should be cleared
			await user.click(screen.getByRole("radio", { name: "Soft" }));
			expect(screen.getByLabelText(/category/i)).toHaveValue("");
		});
	});

	// -----------------------------------------------------------------------
	// Validation
	// -----------------------------------------------------------------------

	describe("validation", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
		});

		it("shows validation errors for empty required fields", async () => {
			const user = await renderAndWaitForLoad();
			await user.click(screen.getByText(/add skill/i));

			// Submit empty form
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				// FormErrorSummary may duplicate the message, so use getAllByText
				const errors = screen.getAllByText(/skill name is required/i);
				expect(errors.length).toBeGreaterThanOrEqual(1);
			});
		});

		it("validates years used is a positive number", async () => {
			const user = await renderAndWaitForLoad();
			await user.click(screen.getByText(/add skill/i));

			// Fill all fields but with invalid years
			await fillSkillForm(user, { yearsUsed: "0" });
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				const errors = screen.getAllByText(/must be at least 1/i);
				expect(errors.length).toBeGreaterThanOrEqual(1);
			});
		});
	});
});
