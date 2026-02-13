/**
 * Tests for the WorkHistoryEditor component (§6.4).
 *
 * REQ-012 §7.2.2: Post-onboarding work history management with CRUD,
 * drag-drop reordering, and bullet expansion (read-only).
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

import type { Persona, WorkHistory } from "@/types/persona";

import { WorkHistoryEditor } from "./work-history-editor";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const GENERIC_ERROR_TEXT = "Failed to save. Please try again.";
const FORM_TESTID = "work-history-form";
const NETWORK_ERROR_MESSAGE = "Network error";
const MOCK_JOB_TITLE_1 = "Software Engineer";
const MOCK_JOB_TITLE_2 = "Senior Developer";
const EDITED_JOB_TITLE = "Lead Engineer";

const MOCK_BULLET_1 = {
	id: "b-001",
	work_history_id: "wh-001",
	text: "Built scalable microservices",
	skills_demonstrated: [],
	metrics: null,
	display_order: 0,
};

const MOCK_BULLET_2 = {
	id: "b-002",
	work_history_id: "wh-002",
	text: "Led team of 5 engineers",
	skills_demonstrated: [],
	metrics: null,
	display_order: 0,
};

const MOCK_ENTRY_1: WorkHistory = {
	id: "wh-001",
	persona_id: DEFAULT_PERSONA_ID,
	job_title: MOCK_JOB_TITLE_1,
	company_name: "Acme Corp",
	company_industry: "Technology",
	location: "San Francisco, CA",
	work_model: "Remote",
	start_date: "2020-01-01",
	end_date: "2023-06-01",
	is_current: false,
	description: "Built web applications",
	display_order: 0,
	bullets: [MOCK_BULLET_1],
};

const MOCK_ENTRY_2: WorkHistory = {
	id: "wh-002",
	persona_id: DEFAULT_PERSONA_ID,
	job_title: MOCK_JOB_TITLE_2,
	company_name: "TechCo",
	company_industry: null,
	location: "New York, NY",
	work_model: "Hybrid",
	start_date: "2023-07-01",
	end_date: null,
	is_current: true,
	description: null,
	display_order: 1,
	bullets: [MOCK_BULLET_2],
};

const MOCK_ENTRY_NO_BULLETS: WorkHistory = {
	...MOCK_ENTRY_1,
	id: "wh-003",
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
			<WorkHistoryEditor persona={persona} />
		</Wrapper>,
	);
	await waitFor(() => {
		expect(
			screen.queryByTestId("loading-work-history-editor"),
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

describe("WorkHistoryEditor", () => {
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
	// Rendering & loading
	// -----------------------------------------------------------------------

	describe("rendering", () => {
		it("shows loading spinner while fetching work history", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<WorkHistoryEditor persona={MOCK_PERSONA} />
				</Wrapper>,
			);

			expect(
				screen.getByTestId("loading-work-history-editor"),
			).toBeInTheDocument();
		});

		it("renders heading after loading", async () => {
			mocks.mockApiGet.mockResolvedValueOnce(MOCK_EMPTY_LIST_RESPONSE);
			await renderAndWaitForLoad();

			expect(
				screen.getByRole("heading", { name: /work history/i }),
			).toBeInTheDocument();
		});

		it("renders Back to Profile link to /persona", async () => {
			mocks.mockApiGet.mockResolvedValueOnce(MOCK_EMPTY_LIST_RESPONSE);
			await renderAndWaitForLoad();

			const link = screen.getByRole("link", { name: /back to profile/i });
			expect(link).toHaveAttribute("href", "/persona");
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

			expect(
				screen.getByText(/no work history entries yet/i),
			).toBeInTheDocument();
		});

		it("shows Add a job button", async () => {
			await renderAndWaitForLoad();

			expect(
				screen.getByRole("button", { name: /add a job/i }),
			).toBeInTheDocument();
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

			expect(screen.getByText(MOCK_JOB_TITLE_1)).toBeInTheDocument();
			expect(screen.getByText(MOCK_JOB_TITLE_2)).toBeInTheDocument();
		});

		it("shows company name on cards", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByText("Acme Corp")).toBeInTheDocument();
			expect(screen.getByText("TechCo")).toBeInTheDocument();
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

			expect(screen.getByTestId(FORM_TESTID)).toBeInTheDocument();
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
			expect(screen.getByTestId(FORM_TESTID)).toBeInTheDocument();

			await user.click(screen.getByRole("button", { name: /cancel/i }));
			expect(screen.queryByTestId(FORM_TESTID)).not.toBeInTheDocument();
		});

		it("shows error on failed POST", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(new Error(NETWORK_ERROR_MESSAGE));

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

			const form = screen.getByTestId(FORM_TESTID);
			expect(
				within(form).getByDisplayValue(MOCK_JOB_TITLE_1),
			).toBeInTheDocument();
			expect(within(form).getByDisplayValue("Acme Corp")).toBeInTheDocument();
		});

		it("submits updated job via PATCH", async () => {
			mocks.mockApiPatch.mockResolvedValueOnce({
				data: { ...MOCK_ENTRY_1, job_title: EDITED_JOB_TITLE },
			});

			const user = await renderAndWaitForLoad();
			const entry1 = screen.getByTestId("entry-wh-001");
			await user.click(within(entry1).getByRole("button", { name: /edit/i }));

			const titleInput = screen.getByDisplayValue(MOCK_JOB_TITLE_1);
			await user.clear(titleInput);
			await user.type(titleInput, EDITED_JOB_TITLE);
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/work-history/wh-001`,
					expect.objectContaining({ job_title: EDITED_JOB_TITLE }),
				);
			});
		});

		it("cancels edit without saving changes", async () => {
			const user = await renderAndWaitForLoad();
			const entry1 = screen.getByTestId("entry-wh-001");
			await user.click(within(entry1).getByRole("button", { name: /edit/i }));

			await user.click(screen.getByRole("button", { name: /cancel/i }));

			expect(mocks.mockApiPatch).not.toHaveBeenCalled();
			expect(screen.getByText(MOCK_JOB_TITLE_1)).toBeInTheDocument();
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

			const confirmButton = screen.getByRole("button", {
				name: /^delete$/i,
			});
			await user.click(confirmButton);

			await waitFor(() => {
				expect(mocks.mockApiDelete).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/work-history/wh-001`,
				);
			});
			expect(screen.queryByText(MOCK_JOB_TITLE_1)).not.toBeInTheDocument();
		});

		it("keeps card when delete API call fails", async () => {
			mocks.mockApiDelete.mockRejectedValueOnce(
				new Error(NETWORK_ERROR_MESSAGE),
			);

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
			expect(screen.getByText(MOCK_JOB_TITLE_1)).toBeInTheDocument();
		});

		it("cancels delete without removing card", async () => {
			const user = await renderAndWaitForLoad();
			const entry1 = screen.getByTestId("entry-wh-001");
			await user.click(within(entry1).getByRole("button", { name: /delete/i }));

			await user.click(screen.getByRole("button", { name: /cancel/i }));

			expect(mocks.mockApiDelete).not.toHaveBeenCalled();
			expect(screen.getByText(MOCK_JOB_TITLE_1)).toBeInTheDocument();
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

		it("reverts entries on reorder failure", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			mocks.mockApiPatch.mockRejectedValue(new Error(NETWORK_ERROR_MESSAGE));

			await renderAndWaitForLoad();

			capturedOnReorder!([MOCK_ENTRY_2, MOCK_ENTRY_1]);

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalled();
			});

			// After rollback, original order should be restored
			await waitFor(() => {
				const entries = screen.getAllByTestId(/^entry-wh-/);
				expect(entries[0]).toHaveAttribute("data-testid", "entry-wh-001");
			});
		});
	});

	// -----------------------------------------------------------------------
	// Bullet expansion
	// -----------------------------------------------------------------------

	describe("bullet expansion", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
		});

		it("shows bullet expand toggle on each card", async () => {
			await renderAndWaitForLoad();

			const expandButtons = screen.getAllByRole("button", {
				name: /bullets for/i,
			});
			expect(expandButtons).toHaveLength(2);
		});

		it("shows bullet count on cards with bullets", async () => {
			await renderAndWaitForLoad();

			const bulletLabels = screen.getAllByText("1 bullet");
			expect(bulletLabels).toHaveLength(2);
		});

		it("shows read-only bullet list when expanded", async () => {
			const user = await renderAndWaitForLoad();

			const expandButton = screen.getAllByRole("button", {
				name: /bullets for/i,
			})[0];
			await user.click(expandButton);

			expect(screen.getByText(MOCK_BULLET_1.text)).toBeInTheDocument();
		});

		it("collapses bullet list on second click", async () => {
			const user = await renderAndWaitForLoad();

			const expandButton = screen.getAllByRole("button", {
				name: /bullets for/i,
			})[0];
			await user.click(expandButton);
			expect(screen.getByText(MOCK_BULLET_1.text)).toBeInTheDocument();

			await user.click(expandButton);
			expect(screen.queryByText(MOCK_BULLET_1.text)).not.toBeInTheDocument();
		});

		it("shows 'No bullets yet' when entry has no bullets", async () => {
			mocks.mockApiGet.mockReset();
			mocks.mockApiGet.mockResolvedValueOnce({
				data: [MOCK_ENTRY_NO_BULLETS],
				meta: { total: 1, page: 1, per_page: 20 },
			});

			const user = await renderAndWaitForLoad();

			const expandButton = screen.getByRole("button", {
				name: /bullets for/i,
			});
			await user.click(expandButton);

			expect(screen.getByText(/no bullets yet/i)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Cache invalidation
	// -----------------------------------------------------------------------

	describe("cache invalidation", () => {
		it("invalidates workHistory query after add", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
			const newEntry: WorkHistory = {
				...MOCK_ENTRY_1,
				id: "wh-new",
				is_current: true,
				end_date: null,
			};
			mocks.mockApiPost.mockResolvedValueOnce({ data: newEntry });

			const user = await renderAndWaitForLoad();
			const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

			await user.click(screen.getByRole("button", { name: /add a job/i }));
			await fillJobForm(user);
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(invalidateSpy).toHaveBeenCalledWith({
					queryKey: ["personas", DEFAULT_PERSONA_ID, "work-history"],
				});
			});
		});

		it("invalidates workHistory query after edit", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			mocks.mockApiPatch.mockResolvedValueOnce({
				data: { ...MOCK_ENTRY_1, job_title: EDITED_JOB_TITLE },
			});

			const user = await renderAndWaitForLoad();
			const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

			const entry1 = screen.getByTestId("entry-wh-001");
			await user.click(within(entry1).getByRole("button", { name: /edit/i }));
			const titleInput = screen.getByDisplayValue(MOCK_JOB_TITLE_1);
			await user.clear(titleInput);
			await user.type(titleInput, EDITED_JOB_TITLE);
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(invalidateSpy).toHaveBeenCalledWith({
					queryKey: ["personas", DEFAULT_PERSONA_ID, "work-history"],
				});
			});
		});

		it("invalidates workHistory query after delete", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			mocks.mockApiDelete.mockResolvedValueOnce(undefined);

			const user = await renderAndWaitForLoad();
			const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

			const entry1 = screen.getByTestId("entry-wh-001");
			await user.click(within(entry1).getByRole("button", { name: /delete/i }));
			const confirmButton = screen.getByRole("button", {
				name: /^delete$/i,
			});
			await user.click(confirmButton);

			await waitFor(() => {
				expect(invalidateSpy).toHaveBeenCalledWith({
					queryKey: ["personas", DEFAULT_PERSONA_ID, "work-history"],
				});
			});
		});
	});

	// -----------------------------------------------------------------------
	// Navigation
	// -----------------------------------------------------------------------

	describe("navigation", () => {
		it("Back to Profile link has href /persona", async () => {
			mocks.mockApiGet.mockResolvedValueOnce(MOCK_EMPTY_LIST_RESPONSE);
			await renderAndWaitForLoad();

			const link = screen.getByRole("link", { name: /back to profile/i });
			expect(link).toHaveAttribute("href", "/persona");
		});
	});

	// -----------------------------------------------------------------------
	// No onboarding-specific features
	// -----------------------------------------------------------------------

	describe("no onboarding features", () => {
		it("does not show bullet validation hint", async () => {
			mocks.mockApiGet.mockResolvedValueOnce({
				data: [MOCK_ENTRY_NO_BULLETS],
				meta: { total: 1, page: 1, per_page: 20 },
			});
			await renderAndWaitForLoad();

			expect(screen.queryByTestId("bullet-hint")).not.toBeInTheDocument();
		});

		it("does not show Next/Back wizard buttons", async () => {
			mocks.mockApiGet.mockResolvedValueOnce(MOCK_LIST_RESPONSE);
			await renderAndWaitForLoad();

			expect(screen.queryByTestId("next-button")).not.toBeInTheDocument();
			expect(screen.queryByTestId("back-button")).not.toBeInTheDocument();
		});
	});
});
