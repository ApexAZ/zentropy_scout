/**
 * Tests for the AchievementStoriesEditor component (§6.8).
 *
 * REQ-012 §7.2.5: Post-onboarding achievement stories management with
 * CRUD, skill links, and drag-drop reordering.
 */

import {
	cleanup,
	render,
	screen,
	waitFor,
	within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AchievementStory, Persona, Skill } from "@/types/persona";

import { AchievementStoriesEditor } from "./achievement-stories-editor";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const MOCK_SKILL_ID = "00000000-0000-4000-a000-000000000010";
const MOCK_STORY_ID_1 = "00000000-0000-4000-a000-000000000020";
const MOCK_STORY_ID_2 = "00000000-0000-4000-a000-000000000021";
const FORM_TESTID = "story-form";
const NETWORK_ERROR_MESSAGE = "Network error";
const MOCK_STORY_TITLE_1 = "Turned around failing project";
const MOCK_STORY_TITLE_2 = "Launched new product line";
const EDITED_STORY_TITLE = "Led major migration";
const ENTRY_1_TESTID = `entry-${MOCK_STORY_ID_1}`;
const ADD_BUTTON_LABEL = "Add story";
const SAVE_BUTTON_LABEL = "Save";
const CANCEL_BUTTON_LABEL = "Cancel";
const DELETE_BUTTON_LABEL = "Delete";
const EDIT_ENTRY_1_LABEL = `Edit ${MOCK_STORY_TITLE_1}`;
const DELETE_ENTRY_1_LABEL = `Delete ${MOCK_STORY_TITLE_1}`;
const STORIES_QUERY_KEY = [
	"personas",
	DEFAULT_PERSONA_ID,
	"achievement-stories",
] as const;
const MOCK_CONTEXT_1 = "Team was behind schedule by 3 weeks";
const MOCK_ACTION_1 = "Reorganized sprints and delegated tasks";
const MOCK_OUTCOME_1 = "Delivered 2 weeks early with 98% coverage";

const MOCK_SKILL: Skill = {
	id: MOCK_SKILL_ID,
	persona_id: DEFAULT_PERSONA_ID,
	skill_name: "Python",
	skill_type: "Hard",
	category: "Programming Language",
	proficiency: "Expert",
	years_used: 8,
	last_used: "Current",
	display_order: 0,
};

const MOCK_STORY_1: AchievementStory = {
	id: MOCK_STORY_ID_1,
	persona_id: DEFAULT_PERSONA_ID,
	title: MOCK_STORY_TITLE_1,
	context: MOCK_CONTEXT_1,
	action: MOCK_ACTION_1,
	outcome: MOCK_OUTCOME_1,
	skills_demonstrated: [MOCK_SKILL_ID],
	related_job_id: null,
	display_order: 0,
};

const MOCK_STORY_2: AchievementStory = {
	id: MOCK_STORY_ID_2,
	persona_id: DEFAULT_PERSONA_ID,
	title: MOCK_STORY_TITLE_2,
	context: "Market gap identified in Q3",
	action: "Built cross-functional team",
	outcome: "Generated $2M in first year",
	skills_demonstrated: [],
	related_job_id: null,
	display_order: 1,
};

const MOCK_STORIES_RESPONSE = {
	data: [MOCK_STORY_1, MOCK_STORY_2],
	meta: { total: 2, page: 1, per_page: 20 },
};

const MOCK_SKILLS_RESPONSE = {
	data: [MOCK_SKILL],
	meta: { total: 1, page: 1, per_page: 20 },
};

const MOCK_EMPTY_STORIES_RESPONSE = {
	data: [],
	meta: { total: 0, page: 1, per_page: 20 },
};

const MOCK_PERSONA: Persona = {
	id: DEFAULT_PERSONA_ID,
	user_id: "00000000-0000-4000-a000-000000000002",
	full_name: "Jane Doe",
	email: "jane@example.com",
	phone: "+1-555-0123",
	home_city: "San Francisco",
	home_state: "CA",
	home_country: "USA",
	linkedin_url: null,
	portfolio_url: null,
	professional_summary: null,
	years_experience: null,
	current_role: null,
	current_company: null,
	target_roles: [],
	target_skills: [],
	stretch_appetite: "Medium",
	commutable_cities: [],
	max_commute_minutes: null,
	remote_preference: "Hybrid OK",
	relocation_open: false,
	relocation_cities: [],
	minimum_base_salary: null,
	salary_currency: "USD",
	visa_sponsorship_required: false,
	industry_exclusions: [],
	company_size_preference: "No Preference",
	max_travel_percent: "None",
	minimum_fit_threshold: 70,
	auto_draft_threshold: 85,
	polling_frequency: "Daily",
	onboarding_complete: true,
	onboarding_step: null,
	created_at: "2026-01-01T00:00:00Z",
	updated_at: "2026-01-01T00:00:00Z",
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
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPost: mocks.mockApiPost,
	apiPatch: mocks.mockApiPatch,
	apiDelete: mocks.mockApiDelete,
	ApiError: mocks.MockApiError,
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

// Mock ReorderableList to avoid DnD complexity in jsdom
let capturedOnReorder: ((items: AchievementStory[]) => void) | null = null;

vi.mock("@/components/ui/reorderable-list", () => ({
	ReorderableList: ({
		items,
		renderItem,
		onReorder,
		label,
	}: {
		items: AchievementStory[];
		renderItem: (
			item: AchievementStory,
			dragHandle: React.ReactNode | null,
		) => React.ReactNode;
		onReorder: (items: AchievementStory[]) => void;
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

const STORIES_URL = `/personas/${DEFAULT_PERSONA_ID}/achievement-stories`;
const SKILLS_URL = `/personas/${DEFAULT_PERSONA_ID}/skills`;

let queryClient: QueryClient;

function createWrapper() {
	queryClient = new QueryClient({
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

function mockDefaultApiGet() {
	mocks.mockApiGet.mockImplementation((url: string) => {
		if (url === STORIES_URL) return Promise.resolve(MOCK_STORIES_RESPONSE);
		if (url === SKILLS_URL) return Promise.resolve(MOCK_SKILLS_RESPONSE);
		return Promise.reject(new Error(`Unexpected GET: ${url}`));
	});
}

function mockEmptyStoriesApiGet() {
	mocks.mockApiGet.mockImplementation((url: string) => {
		if (url === STORIES_URL)
			return Promise.resolve(MOCK_EMPTY_STORIES_RESPONSE);
		if (url === SKILLS_URL) return Promise.resolve(MOCK_SKILLS_RESPONSE);
		return Promise.reject(new Error(`Unexpected GET: ${url}`));
	});
}

async function renderAndWaitForLoad(persona: Persona = MOCK_PERSONA) {
	const user = userEvent.setup();
	const Wrapper = createWrapper();
	render(
		<Wrapper>
			<AchievementStoriesEditor persona={persona} />
		</Wrapper>,
	);
	await waitFor(() => {
		expect(
			screen.queryByTestId("loading-stories-editor"),
		).not.toBeInTheDocument();
	});
	return user;
}

async function fillStoryForm(
	user: ReturnType<typeof userEvent.setup>,
	overrides?: Partial<{
		title: string;
		context: string;
		action: string;
		outcome: string;
	}>,
) {
	const values = {
		title: "New achievement story",
		context: "The situation was complex",
		action: "I took decisive action",
		outcome: "Results exceeded expectations",
		...overrides,
	};

	const form = screen.getByTestId(FORM_TESTID);
	const titleInput = within(form).getByLabelText(/story title/i);
	await user.clear(titleInput);
	await user.type(titleInput, values.title);

	const contextInput = within(form).getByLabelText(/^context$/i);
	await user.clear(contextInput);
	await user.type(contextInput, values.context);

	const actionInput = within(form).getByLabelText(/what did you do/i);
	await user.clear(actionInput);
	await user.type(actionInput, values.action);

	const outcomeInput = within(form).getByLabelText(/^outcome$/i);
	await user.clear(outcomeInput);
	await user.type(outcomeInput, values.outcome);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AchievementStoriesEditor", () => {
	beforeEach(() => {
		mocks.mockApiGet.mockReset();
		mocks.mockApiPost.mockReset();
		mocks.mockApiPatch.mockReset();
		mocks.mockApiDelete.mockReset();
		capturedOnReorder = null;
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
					<AchievementStoriesEditor persona={MOCK_PERSONA} />
				</Wrapper>,
			);

			expect(screen.getByTestId("loading-stories-editor")).toBeInTheDocument();
		});

		it("renders heading and description after loading", async () => {
			mockDefaultApiGet();
			await renderAndWaitForLoad();

			expect(screen.getByText("Achievement Stories")).toBeInTheDocument();
			expect(
				screen.getByText("Manage your achievement stories."),
			).toBeInTheDocument();
		});

		it("renders back link to /persona", async () => {
			mockDefaultApiGet();
			await renderAndWaitForLoad();

			const link = screen.getByText("Back to Profile");
			expect(link).toHaveAttribute("href", "/persona");
		});

		it("renders Add story button", async () => {
			mockDefaultApiGet();
			await renderAndWaitForLoad();

			expect(
				screen.getByRole("button", { name: ADD_BUTTON_LABEL }),
			).toBeInTheDocument();
		});

		it("shows empty state when no stories exist", async () => {
			mockEmptyStoriesApiGet();
			await renderAndWaitForLoad();

			expect(screen.getByText("No stories yet.")).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Fetch
	// -----------------------------------------------------------------------

	describe("fetch", () => {
		it("fetches stories and skills on mount", async () => {
			mockDefaultApiGet();
			await renderAndWaitForLoad();

			expect(mocks.mockApiGet).toHaveBeenCalledWith(STORIES_URL);
			expect(mocks.mockApiGet).toHaveBeenCalledWith(SKILLS_URL);
		});

		it("renders story cards from API data", async () => {
			mockDefaultApiGet();
			await renderAndWaitForLoad();

			expect(screen.getByText(MOCK_STORY_TITLE_1)).toBeInTheDocument();
			expect(screen.getByText(MOCK_STORY_TITLE_2)).toBeInTheDocument();
		});

		it("resolves skill names on story cards", async () => {
			mockDefaultApiGet();
			await renderAndWaitForLoad();

			// MOCK_STORY_1 has skills_demonstrated: ["skill-001"] which maps to "Python"
			expect(screen.getByText(/Python/)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Add
	// -----------------------------------------------------------------------

	describe("add", () => {
		it("shows form when Add story is clicked", async () => {
			mockEmptyStoriesApiGet();
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByRole("button", { name: ADD_BUTTON_LABEL }));

			expect(screen.getByTestId(FORM_TESTID)).toBeInTheDocument();
		});

		it("creates entry via POST and shows card", async () => {
			mockEmptyStoriesApiGet();
			const newEntry: AchievementStory = {
				id: "00000000-0000-4000-a000-000000000098",
				persona_id: DEFAULT_PERSONA_ID,
				title: "New achievement story",
				context: "The situation was complex",
				action: "I took decisive action",
				outcome: "Results exceeded expectations",
				skills_demonstrated: [],
				related_job_id: null,
				display_order: 0,
			};
			mocks.mockApiPost.mockResolvedValue({ data: newEntry });

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByRole("button", { name: ADD_BUTTON_LABEL }));
			await fillStoryForm(user);
			await user.click(screen.getByRole("button", { name: SAVE_BUTTON_LABEL }));

			await waitFor(() => {
				expect(screen.getByText("New achievement story")).toBeInTheDocument();
			});
			expect(mocks.mockApiPost).toHaveBeenCalledWith(
				STORIES_URL,
				expect.objectContaining({ title: "New achievement story" }),
			);
		});

		it("returns to list on cancel", async () => {
			mockDefaultApiGet();
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByRole("button", { name: ADD_BUTTON_LABEL }));
			expect(screen.getByTestId(FORM_TESTID)).toBeInTheDocument();

			await user.click(
				screen.getByRole("button", { name: CANCEL_BUTTON_LABEL }),
			);

			expect(screen.queryByTestId(FORM_TESTID)).not.toBeInTheDocument();
			expect(screen.getByText(MOCK_STORY_TITLE_1)).toBeInTheDocument();
		});

		it("shows error when POST fails", async () => {
			mockEmptyStoriesApiGet();
			mocks.mockApiPost.mockRejectedValue(
				new mocks.MockApiError("VALIDATION_ERROR", NETWORK_ERROR_MESSAGE, 422),
			);

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByRole("button", { name: ADD_BUTTON_LABEL }));
			await fillStoryForm(user);
			await user.click(screen.getByRole("button", { name: SAVE_BUTTON_LABEL }));

			await waitFor(() => {
				expect(screen.getByTestId("submit-error")).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Edit
	// -----------------------------------------------------------------------

	describe("edit", () => {
		it("shows pre-filled form when edit is clicked", async () => {
			mockDefaultApiGet();
			const user = await renderAndWaitForLoad();

			const entry = screen.getByTestId(ENTRY_1_TESTID);
			await user.click(
				within(entry).getByRole("button", {
					name: EDIT_ENTRY_1_LABEL,
				}),
			);

			const form = screen.getByTestId(FORM_TESTID);
			expect(
				within(form).getByDisplayValue(MOCK_STORY_TITLE_1),
			).toBeInTheDocument();
		});

		it("updates entry via PATCH and shows updated card", async () => {
			mockDefaultApiGet();
			const updatedEntry: AchievementStory = {
				...MOCK_STORY_1,
				title: EDITED_STORY_TITLE,
			};
			mocks.mockApiPatch.mockResolvedValue({ data: updatedEntry });

			const user = await renderAndWaitForLoad();

			const entry = screen.getByTestId(ENTRY_1_TESTID);
			await user.click(
				within(entry).getByRole("button", {
					name: EDIT_ENTRY_1_LABEL,
				}),
			);

			const form = screen.getByTestId(FORM_TESTID);
			const titleInput = within(form).getByLabelText(/story title/i);
			await user.clear(titleInput);
			await user.type(titleInput, EDITED_STORY_TITLE);
			await user.click(screen.getByRole("button", { name: SAVE_BUTTON_LABEL }));

			await waitFor(() => {
				expect(screen.getByText(EDITED_STORY_TITLE)).toBeInTheDocument();
			});
			expect(mocks.mockApiPatch).toHaveBeenCalledWith(
				`${STORIES_URL}/${MOCK_STORY_1.id}`,
				expect.objectContaining({ title: EDITED_STORY_TITLE }),
			);
		});

		it("returns to list on cancel without saving", async () => {
			mockDefaultApiGet();
			const user = await renderAndWaitForLoad();

			const entry = screen.getByTestId(ENTRY_1_TESTID);
			await user.click(
				within(entry).getByRole("button", {
					name: EDIT_ENTRY_1_LABEL,
				}),
			);
			await user.click(
				screen.getByRole("button", { name: CANCEL_BUTTON_LABEL }),
			);

			expect(screen.queryByTestId(FORM_TESTID)).not.toBeInTheDocument();
			expect(screen.getByText(MOCK_STORY_TITLE_1)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Delete
	// -----------------------------------------------------------------------

	describe("delete", () => {
		it("shows confirmation dialog when delete is clicked", async () => {
			mockDefaultApiGet();
			const user = await renderAndWaitForLoad();

			const entry = screen.getByTestId(ENTRY_1_TESTID);
			await user.click(
				within(entry).getByRole("button", {
					name: DELETE_ENTRY_1_LABEL,
				}),
			);

			expect(screen.getByText("Delete story")).toBeInTheDocument();
		});

		it("removes entry on confirm", async () => {
			mockDefaultApiGet();
			mocks.mockApiDelete.mockResolvedValue(undefined);

			const user = await renderAndWaitForLoad();

			const entry = screen.getByTestId(ENTRY_1_TESTID);
			await user.click(
				within(entry).getByRole("button", {
					name: DELETE_ENTRY_1_LABEL,
				}),
			);
			await user.click(
				screen.getByRole("button", { name: DELETE_BUTTON_LABEL }),
			);

			await waitFor(() => {
				expect(screen.queryByText(MOCK_STORY_TITLE_1)).not.toBeInTheDocument();
			});
			expect(mocks.mockApiDelete).toHaveBeenCalledWith(
				`${STORIES_URL}/${MOCK_STORY_1.id}`,
			);
		});

		it("keeps entry when cancel is clicked", async () => {
			mockDefaultApiGet();
			const user = await renderAndWaitForLoad();

			const entry = screen.getByTestId(ENTRY_1_TESTID);
			await user.click(
				within(entry).getByRole("button", {
					name: DELETE_ENTRY_1_LABEL,
				}),
			);
			await user.click(
				screen.getByRole("button", { name: CANCEL_BUTTON_LABEL }),
			);

			expect(screen.getByText(MOCK_STORY_TITLE_1)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Reorder
	// -----------------------------------------------------------------------

	describe("reorder", () => {
		it("patches display_order after reorder", async () => {
			mockDefaultApiGet();
			mocks.mockApiPatch.mockResolvedValue({});

			await renderAndWaitForLoad();

			expect(capturedOnReorder).not.toBeNull();

			const reversed = [
				{ ...MOCK_STORY_2, display_order: 1 },
				{ ...MOCK_STORY_1, display_order: 0 },
			];
			capturedOnReorder!(reversed);

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalled();
			});
		});

		it("rolls back on reorder failure", async () => {
			mockDefaultApiGet();
			mocks.mockApiPatch.mockRejectedValue(new Error(NETWORK_ERROR_MESSAGE));

			await renderAndWaitForLoad();

			const reversed = [
				{ ...MOCK_STORY_2, display_order: 1 },
				{ ...MOCK_STORY_1, display_order: 0 },
			];
			capturedOnReorder!(reversed);

			await waitFor(() => {
				const list = screen.getByTestId("reorderable-list");
				const listEntries = within(list).getAllByTestId(/^entry-/);
				expect(listEntries[0]).toHaveAttribute("data-testid", ENTRY_1_TESTID);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Cache invalidation
	// -----------------------------------------------------------------------

	describe("cache invalidation", () => {
		it("invalidates stories query after add", async () => {
			mockEmptyStoriesApiGet();
			const newEntry: AchievementStory = {
				...MOCK_STORY_1,
				id: "00000000-0000-4000-a000-000000000099",
			};
			mocks.mockApiPost.mockResolvedValue({ data: newEntry });

			const user = await renderAndWaitForLoad();

			const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

			await user.click(screen.getByRole("button", { name: ADD_BUTTON_LABEL }));
			await fillStoryForm(user);
			await user.click(screen.getByRole("button", { name: SAVE_BUTTON_LABEL }));

			await waitFor(() => {
				expect(invalidateSpy).toHaveBeenCalledWith({
					queryKey: [...STORIES_QUERY_KEY],
				});
			});
		});

		it("invalidates stories query after delete", async () => {
			mockDefaultApiGet();
			mocks.mockApiDelete.mockResolvedValue(undefined);

			const user = await renderAndWaitForLoad();

			const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

			const entry = screen.getByTestId(ENTRY_1_TESTID);
			await user.click(
				within(entry).getByRole("button", {
					name: DELETE_ENTRY_1_LABEL,
				}),
			);
			await user.click(
				screen.getByRole("button", { name: DELETE_BUTTON_LABEL }),
			);

			await waitFor(() => {
				expect(invalidateSpy).toHaveBeenCalledWith({
					queryKey: [...STORIES_QUERY_KEY],
				});
			});
		});
	});
});
