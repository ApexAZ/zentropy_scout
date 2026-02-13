/**
 * Tests for the CertificationEditor component (§6.6).
 *
 * REQ-012 §7.2.3: Post-onboarding certification management with CRUD,
 * drag-drop reordering, and "Does not expire" toggle handling.
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

import type { Certification, Persona } from "@/types/persona";

import { CertificationEditor } from "./certification-editor";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const FORM_TESTID = "certification-form";
const NETWORK_ERROR_MESSAGE = "Network error";
const MOCK_CERT_NAME_1 = "AWS Solutions Architect";
const MOCK_CERT_NAME_2 = "PMP";
const EDITED_CERT_NAME = "Azure Administrator";
const ENTRY_1_TESTID = "entry-cert-001";
const ADD_BUTTON_LABEL = "Add certification";
const SAVE_BUTTON_LABEL = "Save";
const CANCEL_BUTTON_LABEL = "Cancel";
const DELETE_BUTTON_LABEL = "Delete";
const EDIT_ENTRY_1_LABEL = `Edit ${MOCK_CERT_NAME_1}`;
const DELETE_ENTRY_1_LABEL = `Delete ${MOCK_CERT_NAME_1}`;
const CERTIFICATIONS_QUERY_KEY = [
	"personas",
	DEFAULT_PERSONA_ID,
	"certifications",
] as const;

const MOCK_ENTRY_1: Certification = {
	id: "cert-001",
	persona_id: DEFAULT_PERSONA_ID,
	certification_name: MOCK_CERT_NAME_1,
	issuing_organization: "Amazon Web Services",
	date_obtained: "2023-06-15",
	expiration_date: "2026-06-15",
	credential_id: "ABC-123",
	verification_url: "https://verify.example.com/abc",
	display_order: 0,
};

const MOCK_ENTRY_2: Certification = {
	id: "cert-002",
	persona_id: DEFAULT_PERSONA_ID,
	certification_name: MOCK_CERT_NAME_2,
	issuing_organization: "PMI",
	date_obtained: "2024-01-15",
	expiration_date: null,
	credential_id: null,
	verification_url: null,
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
let capturedOnReorder: ((items: Certification[]) => void) | null = null;

vi.mock("@/components/ui/reorderable-list", () => ({
	ReorderableList: ({
		items,
		renderItem,
		onReorder,
		label,
	}: {
		items: Certification[];
		renderItem: (
			item: Certification,
			dragHandle: React.ReactNode | null,
		) => React.ReactNode;
		onReorder: (items: Certification[]) => void;
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
			<CertificationEditor persona={persona} />
		</Wrapper>,
	);
	await waitFor(() => {
		expect(
			screen.queryByTestId("loading-certification-editor"),
		).not.toBeInTheDocument();
	});
	return user;
}

async function fillCertificationForm(
	user: ReturnType<typeof userEvent.setup>,
	overrides?: Partial<{
		certName: string;
		issuer: string;
		dateObtained: string;
	}>,
) {
	const values = {
		certName: "CompTIA Security+",
		issuer: "CompTIA",
		dateObtained: "2025-01-01",
		...overrides,
	};

	const form = screen.getByTestId(FORM_TESTID);
	const nameInput = within(form).getByLabelText("Certification Name");
	const issuerInput = within(form).getByLabelText("Issuing Organization");
	const dateInput = within(form).getByLabelText("Date Obtained");

	await user.clear(nameInput);
	await user.type(nameInput, values.certName);
	await user.clear(issuerInput);
	await user.type(issuerInput, values.issuer);
	await user.clear(dateInput);
	await user.type(dateInput, values.dateObtained);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CertificationEditor", () => {
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
					<CertificationEditor persona={MOCK_PERSONA} />
				</Wrapper>,
			);

			expect(
				screen.getByTestId("loading-certification-editor"),
			).toBeInTheDocument();
		});

		it("renders heading and description after loading", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			await renderAndWaitForLoad();

			expect(screen.getByText("Certifications")).toBeInTheDocument();
			expect(
				screen.getByText("Manage your certifications."),
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

			expect(screen.getByText("No certifications yet.")).toBeInTheDocument();
		});

		it("renders Add certification button", async () => {
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
		it("fetches certifications on mount", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			await renderAndWaitForLoad();

			expect(mocks.mockApiGet).toHaveBeenCalledWith(
				`/personas/${DEFAULT_PERSONA_ID}/certifications`,
			);
		});

		it("renders certification cards from API data", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			await renderAndWaitForLoad();

			expect(screen.getByText(MOCK_CERT_NAME_1)).toBeInTheDocument();
			expect(screen.getByText(MOCK_CERT_NAME_2)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Add
	// -----------------------------------------------------------------------

	describe("add", () => {
		it("shows form when Add certification is clicked", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByRole("button", { name: ADD_BUTTON_LABEL }));

			expect(screen.getByTestId(FORM_TESTID)).toBeInTheDocument();
		});

		it("creates entry via POST and shows card", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
			const newEntry: Certification = {
				...MOCK_ENTRY_1,
				id: "cert-new",
				certification_name: "CompTIA Security+",
				issuing_organization: "CompTIA",
				date_obtained: "2025-01-01",
			};
			mocks.mockApiPost.mockResolvedValue({ data: newEntry });

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByRole("button", { name: ADD_BUTTON_LABEL }));
			await fillCertificationForm(user);
			await user.click(screen.getByRole("button", { name: SAVE_BUTTON_LABEL }));

			await waitFor(() => {
				expect(screen.getByText("CompTIA Security+")).toBeInTheDocument();
			});
			expect(mocks.mockApiPost).toHaveBeenCalledWith(
				`/personas/${DEFAULT_PERSONA_ID}/certifications`,
				expect.objectContaining({
					certification_name: "CompTIA Security+",
				}),
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
			expect(screen.getByText(MOCK_CERT_NAME_1)).toBeInTheDocument();
		});

		it("shows error when POST fails", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
			mocks.mockApiPost.mockRejectedValue(
				new mocks.MockApiError("VALIDATION_ERROR", NETWORK_ERROR_MESSAGE, 422),
			);

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByRole("button", { name: ADD_BUTTON_LABEL }));
			await fillCertificationForm(user);
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
				within(form).getByDisplayValue(MOCK_CERT_NAME_1),
			).toBeInTheDocument();
		});

		it("updates entry via PATCH and shows updated card", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			const updatedEntry: Certification = {
				...MOCK_ENTRY_1,
				certification_name: EDITED_CERT_NAME,
			};
			mocks.mockApiPatch.mockResolvedValue({ data: updatedEntry });

			const user = await renderAndWaitForLoad();

			const entry = screen.getByTestId(ENTRY_1_TESTID);
			await user.click(
				within(entry).getByRole("button", {
					name: EDIT_ENTRY_1_LABEL,
				}),
			);
			await fillCertificationForm(user, { certName: EDITED_CERT_NAME });
			await user.click(screen.getByRole("button", { name: SAVE_BUTTON_LABEL }));

			await waitFor(() => {
				expect(screen.getByText(EDITED_CERT_NAME)).toBeInTheDocument();
			});
			expect(mocks.mockApiPatch).toHaveBeenCalledWith(
				`/personas/${DEFAULT_PERSONA_ID}/certifications/${MOCK_ENTRY_1.id}`,
				expect.objectContaining({
					certification_name: EDITED_CERT_NAME,
				}),
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
			expect(screen.getByText(MOCK_CERT_NAME_1)).toBeInTheDocument();
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

			expect(screen.getByText("Delete certification")).toBeInTheDocument();
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
				expect(screen.queryByText(MOCK_CERT_NAME_1)).not.toBeInTheDocument();
			});
			expect(mocks.mockApiDelete).toHaveBeenCalledWith(
				`/personas/${DEFAULT_PERSONA_ID}/certifications/${MOCK_ENTRY_1.id}`,
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

			expect(screen.getByText(MOCK_CERT_NAME_1)).toBeInTheDocument();
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
		it("invalidates certifications query after add", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
			const newEntry: Certification = {
				...MOCK_ENTRY_1,
				id: "cert-new",
			};
			mocks.mockApiPost.mockResolvedValue({ data: newEntry });

			const user = await renderAndWaitForLoad();

			const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

			await user.click(screen.getByRole("button", { name: ADD_BUTTON_LABEL }));
			await fillCertificationForm(user);
			await user.click(screen.getByRole("button", { name: SAVE_BUTTON_LABEL }));

			await waitFor(() => {
				expect(invalidateSpy).toHaveBeenCalledWith({
					queryKey: [...CERTIFICATIONS_QUERY_KEY],
				});
			});
		});

		it("invalidates certifications query after delete", async () => {
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
					queryKey: [...CERTIFICATIONS_QUERY_KEY],
				});
			});
		});
	});
});
