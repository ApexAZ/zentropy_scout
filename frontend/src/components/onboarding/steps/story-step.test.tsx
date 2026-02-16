import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AchievementStory, Skill } from "@/types/persona";

import { StoryStep } from "./story-step";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";

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

vi.mock("@/components/ui/checkbox", () => ({
	Checkbox: ({
		checked,
		onCheckedChange,
		id,
		...props
	}: {
		checked?: boolean;
		onCheckedChange?: (val: boolean) => void;
		id?: string;
		[key: string]: unknown;
	}) => (
		<input
			type="checkbox"
			checked={checked ?? false}
			onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
				onCheckedChange?.(e.target.checked)
			}
			id={id}
			{...props}
		/>
	),
}));

vi.mock("@/components/ui/reorderable-list", () => ({
	ReorderableList: ({
		items,
		renderItem,
		onReorder,
	}: {
		items: AchievementStory[];
		renderItem: (item: AchievementStory, dragHandle: null) => React.ReactNode;
		onReorder: (items: AchievementStory[]) => void;
		label?: string;
	}) => (
		<div data-testid="reorderable-list">
			{items.map((item) => (
				<div key={item.id} data-testid={`entry-${item.id}`}>
					{renderItem(item, null)}
				</div>
			))}
			<button
				type="button"
				data-testid="trigger-reorder"
				onClick={() => onReorder([...items].reverse())}
			>
				Reorder
			</button>
		</div>
	),
}));

vi.mock("@/components/ui/confirmation-dialog", () => ({
	ConfirmationDialog: ({
		open,
		title,
		description,
		onConfirm,
		onOpenChange,
		loading,
	}: {
		open: boolean;
		title: string;
		description: string;
		confirmLabel?: string;
		variant?: string;
		onConfirm: () => void;
		onOpenChange: (open: boolean) => void;
		loading?: boolean;
	}) =>
		open ? (
			<div data-testid="confirmation-dialog" role="alertdialog">
				<p data-testid="dialog-title">{title}</p>
				<p data-testid="dialog-description">{description}</p>
				<button
					type="button"
					data-testid="dialog-confirm"
					onClick={onConfirm}
					disabled={loading}
				>
					Delete
				</button>
				<button
					type="button"
					data-testid="dialog-cancel"
					onClick={() => onOpenChange(false)}
				>
					Cancel
				</button>
			</div>
		) : null,
}));

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const MOCK_SKILLS: Skill[] = [
	{
		id: "00000000-0000-4000-a000-000000000011",
		persona_id: DEFAULT_PERSONA_ID,
		skill_name: "Leadership",
		skill_type: "Soft",
		category: "Management",
		proficiency: "Expert",
		years_used: 5,
		last_used: "Current",
		display_order: 0,
	},
	{
		id: "00000000-0000-4000-a000-000000000012",
		persona_id: DEFAULT_PERSONA_ID,
		skill_name: "React",
		skill_type: "Hard",
		category: "Frontend",
		proficiency: "Expert",
		years_used: 4,
		last_used: "Current",
		display_order: 1,
	},
];

const MOCK_STORY_1: AchievementStory = {
	id: "story-1",
	persona_id: DEFAULT_PERSONA_ID,
	title: "Turned around failing project",
	context: "Team was behind schedule on a critical product launch.",
	action: "Reorganized sprints and mentored junior developers.",
	outcome: "Delivered 2 weeks early with zero critical bugs.",
	skills_demonstrated: ["00000000-0000-4000-a000-000000000011"],
	related_job_id: null,
	display_order: 0,
};

const MOCK_STORY_2: AchievementStory = {
	id: "story-2",
	persona_id: DEFAULT_PERSONA_ID,
	title: "Built analytics pipeline",
	context: "Company lacked data visibility into user behavior.",
	action: "Designed and built a real-time analytics pipeline.",
	outcome: "Increased conversion by 15% through data-driven decisions.",
	skills_demonstrated: ["00000000-0000-4000-a000-000000000012"],
	related_job_id: null,
	display_order: 1,
};

const MOCK_STORY_3: AchievementStory = {
	id: "story-3",
	persona_id: DEFAULT_PERSONA_ID,
	title: "Led team restructuring",
	context: "Engineering team was siloed with poor communication.",
	action: "Proposed and implemented a squad-based team structure.",
	outcome: "Reduced project delivery time by 30%.",
	skills_demonstrated: [
		"00000000-0000-4000-a000-000000000011",
		"00000000-0000-4000-a000-000000000012",
	],
	related_job_id: null,
	display_order: 2,
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function setupApiMocks(stories: AchievementStory[] = []) {
	mocks.mockApiGet.mockImplementation((url: string) => {
		if (url.includes("/achievement-stories")) {
			return Promise.resolve({
				data: stories,
				meta: { total: stories.length, page: 1, per_page: 20 },
			});
		}
		if (url.includes("/skills")) {
			return Promise.resolve({
				data: MOCK_SKILLS,
				meta: { total: MOCK_SKILLS.length, page: 1, per_page: 20 },
			});
		}
		return Promise.reject(new Error(`Unexpected GET: ${url}`));
	});
}

async function renderStep(stories?: AchievementStory[]) {
	setupApiMocks(stories);
	const result = render(<StoryStep />);
	await waitFor(() => {
		expect(screen.queryByTestId("loading-stories")).not.toBeInTheDocument();
	});
	return result;
}

async function fillStoryForm(
	user: ReturnType<typeof userEvent.setup>,
	overrides: {
		title?: string;
		context?: string;
		action?: string;
		outcome?: string;
	} = {},
) {
	const {
		title = "Test Story Title",
		context = "Test context description.",
		action = "Test action taken.",
		outcome = "Test measurable outcome.",
	} = overrides;

	if (title) {
		await user.clear(screen.getByLabelText(/story title/i));
		await user.type(screen.getByLabelText(/story title/i), title);
	}
	if (context) {
		await user.clear(screen.getByLabelText(/context/i));
		await user.type(screen.getByLabelText(/context/i), context);
	}
	if (action) {
		await user.clear(screen.getByLabelText(/what did you do/i));
		await user.type(screen.getByLabelText(/what did you do/i), action);
	}
	if (outcome) {
		await user.clear(screen.getByLabelText(/outcome/i));
		await user.type(screen.getByLabelText(/outcome/i), outcome);
	}
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("StoryStep", () => {
	beforeEach(() => {
		mocks.mockApiGet.mockReset();
		mocks.mockApiPost.mockReset();
		mocks.mockApiPatch.mockReset();
		mocks.mockApiDelete.mockReset();
		mocks.mockNext.mockReset();
		mocks.mockBack.mockReset();
		mocks.mockSkip.mockReset();
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	// -----------------------------------------------------------------------
	// Rendering
	// -----------------------------------------------------------------------

	describe("Rendering", () => {
		it("shows loading spinner initially", () => {
			setupApiMocks();
			render(<StoryStep />);
			expect(screen.getByTestId("loading-stories")).toBeInTheDocument();
		});

		it("renders step title and description", async () => {
			await renderStep();
			expect(screen.getByText("Achievement Stories")).toBeInTheDocument();
		});

		it("renders story counter", async () => {
			await renderStep([MOCK_STORY_1, MOCK_STORY_2, MOCK_STORY_3]);
			expect(screen.getByText(/3 of 3–5 stories/)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Empty state
	// -----------------------------------------------------------------------

	describe("Empty state", () => {
		it("shows empty message when no stories exist", async () => {
			await renderStep([]);
			expect(screen.getByText(/no stories yet/i)).toBeInTheDocument();
		});

		it("shows Add Story button", async () => {
			await renderStep([]);
			expect(
				screen.getByRole("button", { name: /add story/i }),
			).toBeInTheDocument();
		});

		it("disables Next button when fewer than 3 stories", async () => {
			await renderStep([]);
			expect(screen.getByTestId("next-button")).toBeDisabled();
		});

		it("does not show Skip button", async () => {
			await renderStep([]);
			expect(
				screen.queryByRole("button", { name: /skip/i }),
			).not.toBeInTheDocument();
		});

		it("shows minimum required message when under 3", async () => {
			await renderStep([MOCK_STORY_1]);
			expect(screen.getByText(/minimum 3 required/i)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Story cards
	// -----------------------------------------------------------------------

	describe("Story cards", () => {
		it("renders all story cards with titles", async () => {
			await renderStep([MOCK_STORY_1, MOCK_STORY_2, MOCK_STORY_3]);
			expect(
				screen.getByText("Turned around failing project"),
			).toBeInTheDocument();
			expect(screen.getByText("Built analytics pipeline")).toBeInTheDocument();
			expect(screen.getByText("Led team restructuring")).toBeInTheDocument();
		});

		it("displays context, action, outcome in card", async () => {
			await renderStep([MOCK_STORY_1]);
			expect(screen.getByText(MOCK_STORY_1.context)).toBeInTheDocument();
			expect(screen.getByText(MOCK_STORY_1.action)).toBeInTheDocument();
			expect(screen.getByText(MOCK_STORY_1.outcome)).toBeInTheDocument();
		});

		it("displays resolved skill names in card", async () => {
			await renderStep([MOCK_STORY_1]);
			// MOCK_STORY_1 has skills_demonstrated: ["00000000-0000-4000-a000-000000000011"] → "Leadership"
			expect(screen.getByText(/Leadership/)).toBeInTheDocument();
		});

		it("displays multiple skill names for stories with multiple skills", async () => {
			await renderStep([MOCK_STORY_3]);
			// MOCK_STORY_3 has skills_demonstrated: ["00000000-0000-4000-a000-000000000011", "00000000-0000-4000-a000-000000000012"]
			expect(screen.getByText(/Leadership/)).toBeInTheDocument();
			expect(screen.getByText(/React/)).toBeInTheDocument();
		});

		it("shows edit and delete buttons for each card", async () => {
			await renderStep([MOCK_STORY_1]);
			expect(
				screen.getByRole("button", {
					name: `Edit ${MOCK_STORY_1.title}`,
				}),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", {
					name: `Delete ${MOCK_STORY_1.title}`,
				}),
			).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Add flow
	// -----------------------------------------------------------------------

	describe("Add flow", () => {
		it("clicking Add Story shows form", async () => {
			const user = userEvent.setup();
			await renderStep([]);
			await user.click(screen.getByRole("button", { name: /add story/i }));
			expect(screen.getByTestId("story-form")).toBeInTheDocument();
		});

		it("submitting form creates story via API", async () => {
			const user = userEvent.setup();
			await renderStep([]);

			const created: AchievementStory = {
				id: "new-story",
				persona_id: DEFAULT_PERSONA_ID,
				title: "Test Story Title",
				context: "Test context description.",
				action: "Test action taken.",
				outcome: "Test measurable outcome.",
				skills_demonstrated: [],
				related_job_id: null,
				display_order: 0,
			};
			mocks.mockApiPost.mockResolvedValueOnce({ data: created });

			await user.click(screen.getByRole("button", { name: /add story/i }));
			await fillStoryForm(user);
			await user.click(screen.getByRole("button", { name: /^save$/i }));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/achievement-stories`,
					expect.objectContaining({
						title: "Test Story Title",
						context: "Test context description.",
						action: "Test action taken.",
						outcome: "Test measurable outcome.",
					}),
				);
			});

			// Returns to list and shows new card
			expect(screen.getByText("Test Story Title")).toBeInTheDocument();
		});

		it("cancel returns to list view", async () => {
			const user = userEvent.setup();
			await renderStep([]);
			await user.click(screen.getByRole("button", { name: /add story/i }));
			expect(screen.getByTestId("story-form")).toBeInTheDocument();
			await user.click(screen.getByRole("button", { name: /cancel/i }));
			expect(screen.queryByTestId("story-form")).not.toBeInTheDocument();
		});

		it("displays submit error on API failure", async () => {
			const user = userEvent.setup();
			await renderStep([]);

			mocks.mockApiPost.mockRejectedValueOnce(new Error("Server error"));

			await user.click(screen.getByRole("button", { name: /add story/i }));
			await fillStoryForm(user);
			await user.click(screen.getByRole("button", { name: /^save$/i }));

			await waitFor(() => {
				expect(screen.getByTestId("submit-error")).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Edit flow
	// -----------------------------------------------------------------------

	describe("Edit flow", () => {
		it("clicking edit shows form with pre-filled values", async () => {
			const user = userEvent.setup();
			await renderStep([MOCK_STORY_1]);

			await user.click(
				screen.getByRole("button", {
					name: `Edit ${MOCK_STORY_1.title}`,
				}),
			);

			expect(screen.getByTestId("story-form")).toBeInTheDocument();
			expect(screen.getByLabelText(/story title/i)).toHaveValue(
				MOCK_STORY_1.title,
			);
			expect(screen.getByLabelText(/context/i)).toHaveValue(
				MOCK_STORY_1.context,
			);
			expect(screen.getByLabelText(/what did you do/i)).toHaveValue(
				MOCK_STORY_1.action,
			);
			expect(screen.getByLabelText(/outcome/i)).toHaveValue(
				MOCK_STORY_1.outcome,
			);
		});

		it("submitting edit updates via API", async () => {
			const user = userEvent.setup();
			await renderStep([MOCK_STORY_1]);

			const updated = {
				...MOCK_STORY_1,
				title: "Updated Title",
			};
			mocks.mockApiPatch.mockResolvedValueOnce({ data: updated });

			await user.click(
				screen.getByRole("button", {
					name: `Edit ${MOCK_STORY_1.title}`,
				}),
			);

			const titleInput = screen.getByLabelText(/story title/i);
			await user.clear(titleInput);
			await user.type(titleInput, "Updated Title");
			await user.click(screen.getByRole("button", { name: /^save$/i }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/achievement-stories/${MOCK_STORY_1.id}`,
					expect.objectContaining({
						title: "Updated Title",
					}),
				);
			});

			expect(screen.getByText("Updated Title")).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Delete flow
	// -----------------------------------------------------------------------

	describe("Delete flow", () => {
		it("clicking delete shows confirmation dialog", async () => {
			const user = userEvent.setup();
			await renderStep([MOCK_STORY_1]);

			await user.click(
				screen.getByRole("button", {
					name: `Delete ${MOCK_STORY_1.title}`,
				}),
			);

			expect(screen.getByTestId("confirmation-dialog")).toBeInTheDocument();
			expect(screen.getByTestId("dialog-description")).toHaveTextContent(
				MOCK_STORY_1.title,
			);
		});

		it("confirming delete removes story from list", async () => {
			const user = userEvent.setup();
			await renderStep([MOCK_STORY_1]);

			mocks.mockApiDelete.mockResolvedValueOnce(undefined);

			await user.click(
				screen.getByRole("button", {
					name: `Delete ${MOCK_STORY_1.title}`,
				}),
			);
			await user.click(screen.getByTestId("dialog-confirm"));

			await waitFor(() => {
				expect(mocks.mockApiDelete).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/achievement-stories/${MOCK_STORY_1.id}`,
				);
			});
			expect(screen.queryByText(MOCK_STORY_1.title)).not.toBeInTheDocument();
		});

		it("cancel closes confirmation dialog", async () => {
			const user = userEvent.setup();
			await renderStep([MOCK_STORY_1]);

			await user.click(
				screen.getByRole("button", {
					name: `Delete ${MOCK_STORY_1.title}`,
				}),
			);
			expect(screen.getByTestId("confirmation-dialog")).toBeInTheDocument();

			await user.click(screen.getByTestId("dialog-cancel"));
			expect(
				screen.queryByTestId("confirmation-dialog"),
			).not.toBeInTheDocument();
		});

		it("shows error message on delete failure", async () => {
			const user = userEvent.setup();
			await renderStep([MOCK_STORY_1]);

			mocks.mockApiDelete.mockRejectedValueOnce(new Error("Server error"));

			await user.click(
				screen.getByRole("button", {
					name: `Delete ${MOCK_STORY_1.title}`,
				}),
			);
			await user.click(screen.getByTestId("dialog-confirm"));

			await waitFor(() => {
				expect(screen.getByTestId("dialog-description")).toHaveTextContent(
					/failed to delete/i,
				);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Reorder
	// -----------------------------------------------------------------------

	describe("Reorder", () => {
		it("reorders entries and patches API", async () => {
			const user = userEvent.setup();
			await renderStep([MOCK_STORY_1, MOCK_STORY_2, MOCK_STORY_3]);

			await user.click(screen.getByTestId("trigger-reorder"));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalled();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Navigation
	// -----------------------------------------------------------------------

	describe("Navigation", () => {
		it("enables Next button with 3 or more stories", async () => {
			await renderStep([MOCK_STORY_1, MOCK_STORY_2, MOCK_STORY_3]);
			expect(screen.getByTestId("next-button")).toBeEnabled();
		});

		it("disables Next button with fewer than 3 stories", async () => {
			await renderStep([MOCK_STORY_1, MOCK_STORY_2]);
			expect(screen.getByTestId("next-button")).toBeDisabled();
		});

		it("clicking Next calls next()", async () => {
			const user = userEvent.setup();
			await renderStep([MOCK_STORY_1, MOCK_STORY_2, MOCK_STORY_3]);
			await user.click(screen.getByTestId("next-button"));
			expect(mocks.mockNext).toHaveBeenCalled();
		});

		it("clicking Back calls back()", async () => {
			const user = userEvent.setup();
			await renderStep([]);
			await user.click(screen.getByTestId("back-button"));
			expect(mocks.mockBack).toHaveBeenCalled();
		});
	});

	// -----------------------------------------------------------------------
	// Validation
	// -----------------------------------------------------------------------

	describe("Validation", () => {
		it("shows errors for empty required fields on submit", async () => {
			const user = userEvent.setup();
			await renderStep([]);

			await user.click(screen.getByRole("button", { name: /add story/i }));

			// Submit without filling any fields
			await user.click(screen.getByRole("button", { name: /^save$/i }));

			await waitFor(() => {
				expect(
					screen.getAllByText(/is required/i).length,
				).toBeGreaterThanOrEqual(1);
			});
			expect(mocks.mockApiPost).not.toHaveBeenCalled();
		});
	});

	// -----------------------------------------------------------------------
	// Skills selection in form
	// -----------------------------------------------------------------------

	describe("Skills selection", () => {
		it("shows available skills as checkboxes in the form", async () => {
			const user = userEvent.setup();
			await renderStep([]);

			await user.click(screen.getByRole("button", { name: /add story/i }));

			expect(screen.getByLabelText("Leadership")).toBeInTheDocument();
			expect(screen.getByLabelText("React")).toBeInTheDocument();
		});

		it("saves selected skills with the story", async () => {
			const user = userEvent.setup();
			await renderStep([]);

			const created: AchievementStory = {
				id: "new-story",
				persona_id: DEFAULT_PERSONA_ID,
				title: "Test Story Title",
				context: "Test context description.",
				action: "Test action taken.",
				outcome: "Test measurable outcome.",
				skills_demonstrated: ["00000000-0000-4000-a000-000000000011"],
				related_job_id: null,
				display_order: 0,
			};
			mocks.mockApiPost.mockResolvedValueOnce({ data: created });

			await user.click(screen.getByRole("button", { name: /add story/i }));
			await fillStoryForm(user);

			// Select the "Leadership" skill
			await user.click(screen.getByLabelText("Leadership"));
			await user.click(screen.getByRole("button", { name: /^save$/i }));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/achievement-stories`,
					expect.objectContaining({
						skills_demonstrated: ["00000000-0000-4000-a000-000000000011"],
					}),
				);
			});
		});
	});
});
