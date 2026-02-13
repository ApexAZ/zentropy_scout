/**
 * Tests for the SkillsEditor component (§6.7).
 *
 * REQ-012 §7.2.4: Post-onboarding skills management with Hard/Soft
 * tabs, CRUD, and per-type drag-drop reordering.
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

import type { Persona, Skill } from "@/types/persona";

import { SkillsEditor } from "./skills-editor";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const FORM_TESTID = "skills-form";
const NETWORK_ERROR_MESSAGE = "Network error";
const MOCK_SKILL_NAME_1 = "Python";
const MOCK_SKILL_NAME_2 = "Leadership";
const EDITED_SKILL_NAME = "Advanced Python";
const ENTRY_1_TESTID = "entry-skill-001";
const ADD_BUTTON_LABEL = "Add skill";
const SAVE_BUTTON_LABEL = "Save";
const CANCEL_BUTTON_LABEL = "Cancel";
const DELETE_BUTTON_LABEL = "Delete";
const EDIT_ENTRY_1_LABEL = `Edit ${MOCK_SKILL_NAME_1}`;
const DELETE_ENTRY_1_LABEL = `Delete ${MOCK_SKILL_NAME_1}`;
const SKILLS_QUERY_KEY = ["personas", DEFAULT_PERSONA_ID, "skills"] as const;

const MOCK_HARD_SKILL: Skill = {
	id: "skill-001",
	persona_id: DEFAULT_PERSONA_ID,
	skill_name: MOCK_SKILL_NAME_1,
	skill_type: "Hard",
	category: "Programming Language",
	proficiency: "Expert",
	years_used: 8,
	last_used: "Current",
	display_order: 0,
};

const MOCK_HARD_SKILL_2: Skill = {
	id: "skill-003",
	persona_id: DEFAULT_PERSONA_ID,
	skill_name: "JavaScript",
	skill_type: "Hard",
	category: "Programming Language",
	proficiency: "Proficient",
	years_used: 5,
	last_used: "Current",
	display_order: 1,
};

const MOCK_SOFT_SKILL: Skill = {
	id: "skill-002",
	persona_id: DEFAULT_PERSONA_ID,
	skill_name: MOCK_SKILL_NAME_2,
	skill_type: "Soft",
	category: "Leadership & Management",
	proficiency: "Proficient",
	years_used: 5,
	last_used: "2024",
	display_order: 0,
};

const MOCK_LIST_RESPONSE = {
	data: [MOCK_HARD_SKILL, MOCK_SOFT_SKILL, MOCK_HARD_SKILL_2],
	meta: { total: 3, page: 1, per_page: 20 },
};

const MOCK_EMPTY_LIST_RESPONSE = {
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

async function renderAndWaitForLoad(persona: Persona = MOCK_PERSONA) {
	const user = userEvent.setup();
	const Wrapper = createWrapper();
	render(
		<Wrapper>
			<SkillsEditor persona={persona} />
		</Wrapper>,
	);
	await waitFor(() => {
		expect(
			screen.queryByTestId("loading-skills-editor"),
		).not.toBeInTheDocument();
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
		skillName: "Docker",
		skillType: "Hard",
		category: "Tool / Software",
		proficiency: "Proficient",
		yearsUsed: "3",
		lastUsed: "Current",
		...overrides,
	};

	const form = screen.getByTestId(FORM_TESTID);
	const nameInput = within(form).getByLabelText(/skill name/i);
	await user.clear(nameInput);
	await user.type(nameInput, values.skillName);

	await user.click(within(form).getByRole("radio", { name: values.skillType }));

	// Wait for category options to load after skill type selection
	await waitFor(() => {
		expect(within(form).getByLabelText(/category/i)).not.toBeDisabled();
	});
	await user.selectOptions(
		within(form).getByLabelText(/category/i),
		values.category,
	);

	await user.click(
		within(form).getByRole("radio", { name: values.proficiency }),
	);

	const yearsInput = within(form).getByLabelText(/years used/i);
	await user.clear(yearsInput);
	await user.type(yearsInput, values.yearsUsed);

	const lastUsedInput = within(form).getByLabelText(/last used/i);
	await user.clear(lastUsedInput);
	await user.type(lastUsedInput, values.lastUsed);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SkillsEditor", () => {
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
					<SkillsEditor persona={MOCK_PERSONA} />
				</Wrapper>,
			);

			expect(screen.getByTestId("loading-skills-editor")).toBeInTheDocument();
		});

		it("renders heading and description after loading", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			await renderAndWaitForLoad();

			expect(screen.getByText("Skills")).toBeInTheDocument();
			expect(screen.getByText("Manage your skills.")).toBeInTheDocument();
		});

		it("renders back link to /persona", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			await renderAndWaitForLoad();

			const link = screen.getByText("Back to Profile");
			expect(link).toHaveAttribute("href", "/persona");
		});

		it("renders Add skill button", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			await renderAndWaitForLoad();

			expect(
				screen.getByRole("button", { name: ADD_BUTTON_LABEL }),
			).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Tabs
	// -----------------------------------------------------------------------

	describe("tabs", () => {
		it("renders Hard Skills and Soft Skills tabs", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			await renderAndWaitForLoad();

			expect(
				screen.getByRole("tab", { name: /hard skills/i }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("tab", { name: /soft skills/i }),
			).toBeInTheDocument();
		});

		it("shows hard skills by default", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			await renderAndWaitForLoad();

			// Hard skill visible
			expect(screen.getByText(MOCK_SKILL_NAME_1)).toBeInTheDocument();
			// Soft skill not visible in active tab
			expect(screen.queryByText(MOCK_SKILL_NAME_2)).not.toBeInTheDocument();
		});

		it("switches to soft skills tab", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByRole("tab", { name: /soft skills/i }));

			expect(screen.getByText(MOCK_SKILL_NAME_2)).toBeInTheDocument();
			expect(screen.queryByText(MOCK_SKILL_NAME_1)).not.toBeInTheDocument();
		});

		it("shows empty state when tab has no entries", async () => {
			// Only hard skills, no soft skills
			const hardOnlyResponse = {
				data: [MOCK_HARD_SKILL],
				meta: { total: 1, page: 1, per_page: 20 },
			};
			mocks.mockApiGet.mockResolvedValue(hardOnlyResponse);
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByRole("tab", { name: /soft skills/i }));

			expect(screen.getByText("No soft skills yet.")).toBeInTheDocument();
		});

		it("shows empty state for hard skills tab when empty", async () => {
			const softOnlyResponse = {
				data: [MOCK_SOFT_SKILL],
				meta: { total: 1, page: 1, per_page: 20 },
			};
			mocks.mockApiGet.mockResolvedValue(softOnlyResponse);
			await renderAndWaitForLoad();

			expect(screen.getByText("No hard skills yet.")).toBeInTheDocument();
		});

		it("displays skill counts in tab labels", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			await renderAndWaitForLoad();

			// 2 hard skills, 1 soft skill
			expect(
				screen.getByRole("tab", { name: /hard skills \(2\)/i }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("tab", { name: /soft skills \(1\)/i }),
			).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Fetch
	// -----------------------------------------------------------------------

	describe("fetch", () => {
		it("fetches skill entries on mount", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			await renderAndWaitForLoad();

			expect(mocks.mockApiGet).toHaveBeenCalledWith(
				`/personas/${DEFAULT_PERSONA_ID}/skills`,
			);
		});

		it("renders skill cards from API data", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			await renderAndWaitForLoad();

			// Hard tab is default — should see hard skills
			expect(screen.getByText(MOCK_SKILL_NAME_1)).toBeInTheDocument();
			expect(screen.getByText("JavaScript")).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Add
	// -----------------------------------------------------------------------

	describe("add", () => {
		it("shows form when Add skill is clicked", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByRole("button", { name: ADD_BUTTON_LABEL }));

			expect(screen.getByTestId(FORM_TESTID)).toBeInTheDocument();
		});

		it("creates entry via POST and shows card", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
			const newEntry: Skill = {
				...MOCK_HARD_SKILL,
				id: "skill-new",
				skill_name: "Docker",
				category: "Tool / Software",
				proficiency: "Proficient",
				years_used: 3,
				last_used: "Current",
				display_order: 0,
			};
			mocks.mockApiPost.mockResolvedValue({ data: newEntry });

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByRole("button", { name: ADD_BUTTON_LABEL }));
			await fillSkillForm(user);
			await user.click(screen.getByRole("button", { name: SAVE_BUTTON_LABEL }));

			await waitFor(() => {
				expect(screen.getByText("Docker")).toBeInTheDocument();
			});
			expect(mocks.mockApiPost).toHaveBeenCalledWith(
				`/personas/${DEFAULT_PERSONA_ID}/skills`,
				expect.objectContaining({ skill_name: "Docker" }),
			);
		});

		it("returns to list on cancel", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByRole("button", { name: ADD_BUTTON_LABEL }));
			expect(screen.getByTestId(FORM_TESTID)).toBeInTheDocument();

			await user.click(
				screen.getByRole("button", { name: CANCEL_BUTTON_LABEL }),
			);

			expect(screen.queryByTestId(FORM_TESTID)).not.toBeInTheDocument();
			expect(screen.getByText(MOCK_SKILL_NAME_1)).toBeInTheDocument();
		});

		it("shows error when POST fails", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
			mocks.mockApiPost.mockRejectedValue(
				new mocks.MockApiError("VALIDATION_ERROR", NETWORK_ERROR_MESSAGE, 422),
			);

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByRole("button", { name: ADD_BUTTON_LABEL }));
			await fillSkillForm(user);
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
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			const user = await renderAndWaitForLoad();

			const entry = screen.getByTestId(ENTRY_1_TESTID);
			await user.click(
				within(entry).getByRole("button", {
					name: EDIT_ENTRY_1_LABEL,
				}),
			);

			const form = screen.getByTestId(FORM_TESTID);
			expect(
				within(form).getByDisplayValue(MOCK_SKILL_NAME_1),
			).toBeInTheDocument();
		});

		it("updates entry via PATCH and shows updated card", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			const updatedEntry: Skill = {
				...MOCK_HARD_SKILL,
				skill_name: EDITED_SKILL_NAME,
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
			const nameInput = within(form).getByLabelText(/skill name/i);
			await user.clear(nameInput);
			await user.type(nameInput, EDITED_SKILL_NAME);
			await user.click(screen.getByRole("button", { name: SAVE_BUTTON_LABEL }));

			await waitFor(() => {
				expect(screen.getByText(EDITED_SKILL_NAME)).toBeInTheDocument();
			});
			expect(mocks.mockApiPatch).toHaveBeenCalledWith(
				`/personas/${DEFAULT_PERSONA_ID}/skills/${MOCK_HARD_SKILL.id}`,
				expect.objectContaining({ skill_name: EDITED_SKILL_NAME }),
			);
		});

		it("returns to list on cancel without saving", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
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
			expect(screen.getByText(MOCK_SKILL_NAME_1)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Delete
	// -----------------------------------------------------------------------

	describe("delete", () => {
		it("shows confirmation dialog when delete is clicked", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			const user = await renderAndWaitForLoad();

			const entry = screen.getByTestId(ENTRY_1_TESTID);
			await user.click(
				within(entry).getByRole("button", {
					name: DELETE_ENTRY_1_LABEL,
				}),
			);

			expect(screen.getByText("Delete skill")).toBeInTheDocument();
		});

		it("removes entry on confirm", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
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
				expect(screen.queryByText(MOCK_SKILL_NAME_1)).not.toBeInTheDocument();
			});
			expect(mocks.mockApiDelete).toHaveBeenCalledWith(
				`/personas/${DEFAULT_PERSONA_ID}/skills/${MOCK_HARD_SKILL.id}`,
			);
		});

		it("keeps entry when cancel is clicked", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
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

			expect(screen.getByText(MOCK_SKILL_NAME_1)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Reorder
	// -----------------------------------------------------------------------

	describe("reorder", () => {
		it("patches display_order after reorder", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			mocks.mockApiPatch.mockResolvedValue({});

			await renderAndWaitForLoad();

			expect(capturedOnReorder).not.toBeNull();

			// Reverse the hard skills
			const reversed = [
				{ ...MOCK_HARD_SKILL_2, display_order: 1 },
				{ ...MOCK_HARD_SKILL, display_order: 0 },
			];
			capturedOnReorder!(reversed);

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalled();
			});
		});

		it("rolls back on reorder failure", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			mocks.mockApiPatch.mockRejectedValue(new Error("Network error"));

			await renderAndWaitForLoad();

			const reversed = [
				{ ...MOCK_HARD_SKILL_2, display_order: 1 },
				{ ...MOCK_HARD_SKILL, display_order: 0 },
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
		it("invalidates skills query after add", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
			const newEntry: Skill = {
				...MOCK_HARD_SKILL,
				id: "skill-new",
			};
			mocks.mockApiPost.mockResolvedValue({ data: newEntry });

			const user = await renderAndWaitForLoad();

			const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

			await user.click(screen.getByRole("button", { name: ADD_BUTTON_LABEL }));
			await fillSkillForm(user);
			await user.click(screen.getByRole("button", { name: SAVE_BUTTON_LABEL }));

			await waitFor(() => {
				expect(invalidateSpy).toHaveBeenCalledWith({
					queryKey: [...SKILLS_QUERY_KEY],
				});
			});
		});

		it("invalidates skills query after delete", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
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
					queryKey: [...SKILLS_QUERY_KEY],
				});
			});
		});
	});
});
