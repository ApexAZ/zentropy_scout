/**
 * Tests for the EducationEditor component (§6.6).
 *
 * REQ-012 §7.2.3: Post-onboarding education management with CRUD
 * and drag-drop reordering.
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

import type { Education, Persona } from "@/types/persona";

import { EducationEditor } from "./education-editor";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const FORM_TESTID = "education-form";
const NETWORK_ERROR_MESSAGE = "Network error";
const MOCK_DEGREE_1 = "Bachelor of Science";
const MOCK_DEGREE_2 = "Master of Arts";
const EDITED_DEGREE = "Doctor of Philosophy";
const MOCK_INSTITUTION_1 = "MIT";
const MOCK_INSTITUTION_2 = "Stanford";
const ENTRY_1_TESTID = "entry-ed-001";
const ADD_BUTTON_LABEL = "Add education";
const SAVE_BUTTON_LABEL = "Save";
const CANCEL_BUTTON_LABEL = "Cancel";
const EDIT_ENTRY_1_LABEL = `Edit ${MOCK_DEGREE_1}`;
const DELETE_ENTRY_1_LABEL = `Delete ${MOCK_DEGREE_1}`;
const EDUCATION_QUERY_KEY = [
	"personas",
	DEFAULT_PERSONA_ID,
	"education",
] as const;

const MOCK_ENTRY_1: Education = {
	id: "ed-001",
	persona_id: DEFAULT_PERSONA_ID,
	institution: "MIT",
	degree: MOCK_DEGREE_1,
	field_of_study: "Computer Science",
	graduation_year: 2020,
	gpa: 3.8,
	honors: "Magna Cum Laude",
	display_order: 0,
};

const MOCK_ENTRY_2: Education = {
	id: "ed-002",
	persona_id: DEFAULT_PERSONA_ID,
	institution: "Stanford",
	degree: MOCK_DEGREE_2,
	field_of_study: "History",
	graduation_year: 2023,
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

const MOCK_NO_REFS_RESPONSE = {
	data: {
		has_references: false,
		has_immutable_references: false,
		references: [],
	},
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
	apiPost: mocks.mockApiPost,
	apiPatch: mocks.mockApiPatch,
	apiDelete: mocks.mockApiDelete,
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
			<EducationEditor persona={persona} />
		</Wrapper>,
	);
	await waitFor(() => {
		expect(
			screen.queryByTestId("loading-education-editor"),
		).not.toBeInTheDocument();
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
	}>,
) {
	const values = {
		institution: "Harvard",
		degree: "Bachelor of Arts",
		fieldOfStudy: "Economics",
		graduationYear: "2025",
		...overrides,
	};

	const form = screen.getByTestId(FORM_TESTID);
	const institutionInput = within(form).getByLabelText("Institution");
	const degreeInput = within(form).getByLabelText("Degree");
	const fieldInput = within(form).getByLabelText("Field of Study");
	const yearInput = within(form).getByLabelText("Graduation Year");

	await user.clear(institutionInput);
	await user.type(institutionInput, values.institution);
	await user.clear(degreeInput);
	await user.type(degreeInput, values.degree);
	await user.clear(fieldInput);
	await user.type(fieldInput, values.fieldOfStudy);
	await user.clear(yearInput);
	await user.type(yearInput, values.graduationYear);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("EducationEditor", () => {
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
					<EducationEditor persona={MOCK_PERSONA} />
				</Wrapper>,
			);

			expect(
				screen.getByTestId("loading-education-editor"),
			).toBeInTheDocument();
		});

		it("renders heading and description after loading", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			await renderAndWaitForLoad();

			expect(screen.getByText("Education")).toBeInTheDocument();
			expect(
				screen.getByText("Manage your education entries."),
			).toBeInTheDocument();
		});

		it("renders back link to /persona", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			await renderAndWaitForLoad();

			const link = screen.getByText("Back to Profile");
			expect(link).toHaveAttribute("href", "/persona");
		});

		it("renders empty state when no entries exist", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
			await renderAndWaitForLoad();

			expect(screen.getByText("No education entries yet.")).toBeInTheDocument();
		});

		it("renders Add education button", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			await renderAndWaitForLoad();

			expect(
				screen.getByRole("button", { name: ADD_BUTTON_LABEL }),
			).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Fetch
	// -----------------------------------------------------------------------

	describe("fetch", () => {
		it("fetches education entries on mount", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			await renderAndWaitForLoad();

			expect(mocks.mockApiGet).toHaveBeenCalledWith(
				`/personas/${DEFAULT_PERSONA_ID}/education`,
			);
		});

		it("renders education cards from API data", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			await renderAndWaitForLoad();

			expect(screen.getByText(MOCK_INSTITUTION_1)).toBeInTheDocument();
			expect(screen.getByText(MOCK_INSTITUTION_2)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Add
	// -----------------------------------------------------------------------

	describe("add", () => {
		it("shows form when Add education is clicked", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByRole("button", { name: ADD_BUTTON_LABEL }));

			expect(screen.getByTestId(FORM_TESTID)).toBeInTheDocument();
		});

		it("creates entry via POST and shows card", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
			const newEntry: Education = {
				...MOCK_ENTRY_1,
				id: "ed-new",
				institution: "Harvard",
				degree: "Bachelor of Arts",
				field_of_study: "Economics",
				graduation_year: 2025,
			};
			mocks.mockApiPost.mockResolvedValue({ data: newEntry });

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByRole("button", { name: ADD_BUTTON_LABEL }));
			await fillEducationForm(user);
			await user.click(screen.getByRole("button", { name: SAVE_BUTTON_LABEL }));

			await waitFor(() => {
				expect(screen.getByText("Harvard")).toBeInTheDocument();
			});
			expect(mocks.mockApiPost).toHaveBeenCalledWith(
				`/personas/${DEFAULT_PERSONA_ID}/education`,
				expect.objectContaining({ institution: "Harvard" }),
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
			expect(screen.getByText(MOCK_INSTITUTION_1)).toBeInTheDocument();
		});

		it("shows error when POST fails", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
			mocks.mockApiPost.mockRejectedValue(
				new mocks.MockApiError("VALIDATION_ERROR", NETWORK_ERROR_MESSAGE, 422),
			);

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByRole("button", { name: ADD_BUTTON_LABEL }));
			await fillEducationForm(user);
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
			expect(within(form).getByDisplayValue("MIT")).toBeInTheDocument();
		});

		it("updates entry via PATCH and shows updated card", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			const updatedEntry: Education = {
				...MOCK_ENTRY_1,
				degree: EDITED_DEGREE,
			};
			mocks.mockApiPatch.mockResolvedValue({ data: updatedEntry });

			const user = await renderAndWaitForLoad();

			const entry = screen.getByTestId(ENTRY_1_TESTID);
			await user.click(
				within(entry).getByRole("button", {
					name: EDIT_ENTRY_1_LABEL,
				}),
			);
			await fillEducationForm(user, { degree: EDITED_DEGREE });
			await user.click(screen.getByRole("button", { name: SAVE_BUTTON_LABEL }));

			await waitFor(() => {
				expect(
					screen.getByText(`${EDITED_DEGREE} in Computer Science`),
				).toBeInTheDocument();
			});
			expect(mocks.mockApiPatch).toHaveBeenCalledWith(
				`/personas/${DEFAULT_PERSONA_ID}/education/${MOCK_ENTRY_1.id}`,
				expect.objectContaining({ degree: EDITED_DEGREE }),
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
			expect(screen.getByText(MOCK_INSTITUTION_1)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Delete
	// -----------------------------------------------------------------------

	describe("delete", () => {
		it("shows checking state when delete is clicked", async () => {
			mocks.mockApiGet.mockImplementation((path: string) => {
				if (path.includes("/references")) {
					return new Promise(() => {});
				}
				return Promise.resolve(MOCK_LIST_RESPONSE);
			});
			const user = await renderAndWaitForLoad();

			const entry = screen.getByTestId(ENTRY_1_TESTID);
			await user.click(
				within(entry).getByRole("button", {
					name: DELETE_ENTRY_1_LABEL,
				}),
			);

			expect(screen.getByText("Checking references...")).toBeInTheDocument();
		});

		it("removes entry when no references found", async () => {
			mocks.mockApiGet.mockImplementation((path: string) => {
				if (path.includes("/references")) {
					return Promise.resolve(MOCK_NO_REFS_RESPONSE);
				}
				return Promise.resolve(MOCK_LIST_RESPONSE);
			});
			mocks.mockApiDelete.mockResolvedValue(undefined);

			const user = await renderAndWaitForLoad();

			const entry = screen.getByTestId(ENTRY_1_TESTID);
			await user.click(
				within(entry).getByRole("button", {
					name: DELETE_ENTRY_1_LABEL,
				}),
			);

			await waitFor(() => {
				expect(screen.queryByText(MOCK_INSTITUTION_1)).not.toBeInTheDocument();
			});
			expect(mocks.mockApiDelete).toHaveBeenCalledWith(
				`/personas/${DEFAULT_PERSONA_ID}/education/${MOCK_ENTRY_1.id}`,
			);
			expect(mocks.mockShowToast.success).toHaveBeenCalled();
		});

		it("keeps entry when cancel is clicked", async () => {
			mocks.mockApiGet.mockImplementation((path: string) => {
				if (path.includes("/references")) {
					return Promise.resolve({
						data: {
							has_references: true,
							has_immutable_references: false,
							references: [
								{
									id: "ref-1",
									name: "My Resume",
									type: "base_resume",
									immutable: false,
								},
							],
						},
					});
				}
				return Promise.resolve(MOCK_LIST_RESPONSE);
			});
			const user = await renderAndWaitForLoad();

			const entry = screen.getByTestId(ENTRY_1_TESTID);
			await user.click(
				within(entry).getByRole("button", {
					name: DELETE_ENTRY_1_LABEL,
				}),
			);

			await waitFor(() => {
				expect(screen.getByText(/used in 1 document/i)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("button", { name: CANCEL_BUTTON_LABEL }),
			);

			expect(screen.getByText(MOCK_INSTITUTION_1)).toBeInTheDocument();
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

			const reversed = [
				{ ...MOCK_ENTRY_2, display_order: 1 },
				{ ...MOCK_ENTRY_1, display_order: 0 },
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
				{ ...MOCK_ENTRY_2, display_order: 1 },
				{ ...MOCK_ENTRY_1, display_order: 0 },
			];
			capturedOnReorder!(reversed);

			await waitFor(() => {
				const list = screen.getByTestId("reorderable-list");
				const entries = within(list).getAllByTestId(/^entry-/);
				expect(entries[0]).toHaveAttribute("data-testid", ENTRY_1_TESTID);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Cache invalidation
	// -----------------------------------------------------------------------

	describe("cache invalidation", () => {
		it("invalidates education query after add", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
			const newEntry: Education = {
				...MOCK_ENTRY_1,
				id: "ed-new",
			};
			mocks.mockApiPost.mockResolvedValue({ data: newEntry });

			const user = await renderAndWaitForLoad();

			const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

			await user.click(screen.getByRole("button", { name: ADD_BUTTON_LABEL }));
			await fillEducationForm(user);
			await user.click(screen.getByRole("button", { name: SAVE_BUTTON_LABEL }));

			await waitFor(() => {
				expect(invalidateSpy).toHaveBeenCalledWith({
					queryKey: [...EDUCATION_QUERY_KEY],
				});
			});
		});

		it("invalidates education query after delete", async () => {
			mocks.mockApiGet.mockImplementation((path: string) => {
				if (path.includes("/references")) {
					return Promise.resolve(MOCK_NO_REFS_RESPONSE);
				}
				return Promise.resolve(MOCK_LIST_RESPONSE);
			});
			mocks.mockApiDelete.mockResolvedValue(undefined);

			const user = await renderAndWaitForLoad();

			const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

			const entry = screen.getByTestId(ENTRY_1_TESTID);
			await user.click(
				within(entry).getByRole("button", {
					name: DELETE_ENTRY_1_LABEL,
				}),
			);

			await waitFor(() => {
				expect(invalidateSpy).toHaveBeenCalledWith({
					queryKey: [...EDUCATION_QUERY_KEY],
				});
			});
		});
	});
});
