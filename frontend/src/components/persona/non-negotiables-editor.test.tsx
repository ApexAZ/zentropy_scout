/**
 * Tests for the NonNegotiablesEditor component (§6.10).
 *
 * REQ-012 §7.2.7: Sectioned form for location preferences, compensation,
 * other filters, and embedded custom filters CRUD. Pre-fills from persona
 * prop, PATCHes on save, invalidates cache, shows success message.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Persona } from "@/types/persona";

import { NonNegotiablesEditor } from "./non-negotiables-editor";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const PERSONA_PATCH_URL = `/personas/${DEFAULT_PERSONA_ID}`;
const GENERIC_ERROR_TEXT = "Failed to save. Please try again.";
const FORM_TESTID = "non-negotiables-editor-form";
const MOCK_PATCH_RESPONSE = { data: {} };

const REMOTE_OPTIONS = [
	"Remote Only",
	"Hybrid OK",
	"Onsite OK",
	"No Preference",
] as const;

const COMPANY_SIZE_OPTIONS = [
	"Startup",
	"Mid-size",
	"Enterprise",
	"No Preference",
] as const;

const MAX_TRAVEL_OPTIONS = ["None", "<25%", "<50%", "Any"] as const;

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
	commutable_cities: ["Boston", "NYC"],
	max_commute_minutes: 45,
	remote_preference: "Hybrid OK",
	relocation_open: true,
	relocation_cities: ["Austin", "Denver"],
	minimum_base_salary: 120000,
	salary_currency: "EUR",
	visa_sponsorship_required: true,
	industry_exclusions: ["Tobacco", "Gambling"],
	company_size_preference: "Startup",
	max_travel_percent: "<25%",
	minimum_fit_threshold: 70,
	auto_draft_threshold: 85,
	polling_frequency: "Daily",
	onboarding_complete: true,
	onboarding_step: null,
	created_at: "2026-01-01T00:00:00Z",
	updated_at: "2026-01-01T00:00:00Z",
};

const MOCK_PERSONA_NULL_SALARY: Persona = {
	...MOCK_PERSONA,
	minimum_base_salary: null,
	salary_currency: "USD",
};

const MOCK_PERSONA_DEFAULTS: Persona = {
	...MOCK_PERSONA,
	remote_preference: "No Preference",
	commutable_cities: [],
	max_commute_minutes: null,
	relocation_open: false,
	relocation_cities: [],
	minimum_base_salary: null,
	salary_currency: "USD",
	visa_sponsorship_required: false,
	industry_exclusions: [],
	company_size_preference: "No Preference",
	max_travel_percent: "None",
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
		mockApiPatch: vi.fn(),
		MockApiError,
	};
});

vi.mock("@/lib/api-client", () => ({
	apiPatch: mocks.mockApiPatch,
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

vi.mock("@/components/onboarding/steps/custom-filters-section", () => ({
	CustomFiltersSection: ({ personaId }: { personaId: string }) => (
		<div data-testid="custom-filters-section">{personaId}</div>
	),
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

function renderEditor(persona: Persona = MOCK_PERSONA) {
	const user = userEvent.setup();
	const Wrapper = createWrapper();
	render(
		<Wrapper>
			<NonNegotiablesEditor persona={persona} />
		</Wrapper>,
	);
	return user;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("NonNegotiablesEditor", () => {
	beforeEach(() => {
		mocks.mockApiPatch.mockReset();
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	// -----------------------------------------------------------------------
	// Rendering
	// -----------------------------------------------------------------------

	describe("rendering", () => {
		it("renders heading", () => {
			renderEditor();

			expect(
				screen.getByRole("heading", { name: /non-negotiables/i }),
			).toBeInTheDocument();
		});

		it("renders Location Preferences section heading", () => {
			renderEditor();

			expect(screen.getByText("Location Preferences")).toBeInTheDocument();
		});

		it("renders Relocation section heading", () => {
			renderEditor();

			expect(screen.getByText("Relocation")).toBeInTheDocument();
		});

		it("renders Compensation section heading", () => {
			renderEditor();

			expect(screen.getByText("Compensation")).toBeInTheDocument();
		});

		it("renders Other Filters section heading", () => {
			renderEditor();

			expect(screen.getByText("Other Filters")).toBeInTheDocument();
		});

		it("renders all 4 remote preference radio options", () => {
			renderEditor();

			const remoteGroup = screen.getByRole("radiogroup", {
				name: /remote preference/i,
			});
			for (const option of REMOTE_OPTIONS) {
				const radio = remoteGroup.querySelector(`input[value="${option}"]`);
				expect(radio).toBeInTheDocument();
			}
		});

		it("renders all 4 company size preference radio options", () => {
			renderEditor();

			const companyGroup = screen.getByRole("radiogroup", {
				name: /company size/i,
			});
			for (const option of COMPANY_SIZE_OPTIONS) {
				const radio = companyGroup.querySelector(`input[value="${option}"]`);
				expect(radio).toBeInTheDocument();
			}
		});

		it("renders all 4 max travel radio options", () => {
			renderEditor();

			const travelGroup = screen.getByRole("radiogroup", {
				name: /max travel/i,
			});
			for (const option of MAX_TRAVEL_OPTIONS) {
				const radio = travelGroup.querySelector(`input[value="${option}"]`);
				expect(radio).toBeInTheDocument();
			}
		});

		it("renders Save button", () => {
			renderEditor();

			expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
		});

		it("has correct form testid", () => {
			renderEditor();

			expect(screen.getByTestId(FORM_TESTID)).toBeInTheDocument();
		});

		it("renders Back to Profile link", () => {
			renderEditor();

			expect(
				screen.getByRole("link", { name: /back to profile/i }),
			).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Pre-fill
	// -----------------------------------------------------------------------

	describe("pre-fill", () => {
		it("pre-fills remote preference radio selection", () => {
			renderEditor();

			const hybridRadio = screen.getByLabelText("Hybrid OK");
			expect(hybridRadio).toBeChecked();
		});

		it("pre-fills commutable cities as tag chips", () => {
			renderEditor();

			expect(screen.getByText("Boston")).toBeInTheDocument();
			expect(screen.getByText("NYC")).toBeInTheDocument();
		});

		it("pre-fills salary with currency", () => {
			renderEditor();

			expect(screen.getByLabelText(/minimum base salary/i)).toHaveValue(120000);
			expect(screen.getByLabelText(/currency/i)).toHaveValue("EUR");
		});

		it("pre-fills checkboxes from persona data", () => {
			renderEditor();

			expect(screen.getByLabelText(/open to relocation/i)).toBeChecked();
			expect(screen.getByLabelText(/visa sponsorship required/i)).toBeChecked();
			expect(screen.getByLabelText(/prefer not to set/i)).not.toBeChecked();
		});

		it("checks 'Prefer not to set' when persona salary is null", () => {
			renderEditor(MOCK_PERSONA_NULL_SALARY);

			expect(screen.getByLabelText(/prefer not to set/i)).toBeChecked();
		});
	});

	// -----------------------------------------------------------------------
	// Conditional field visibility
	// -----------------------------------------------------------------------

	describe("conditional field visibility", () => {
		it("hides commute fields when Remote Only is selected", () => {
			renderEditor({
				...MOCK_PERSONA,
				remote_preference: "Remote Only",
				commutable_cities: [],
				max_commute_minutes: null,
			});

			expect(
				screen.queryByLabelText(/commutable cities/i),
			).not.toBeInTheDocument();
			expect(screen.queryByLabelText(/max commute/i)).not.toBeInTheDocument();
		});

		it("toggles commute field visibility when changing remote preference", async () => {
			const user = renderEditor();

			// Hybrid OK → commute fields visible
			expect(screen.getByLabelText(/commutable cities/i)).toBeInTheDocument();

			// Click Remote Only → hidden
			await user.click(screen.getByLabelText("Remote Only"));
			expect(
				screen.queryByLabelText(/commutable cities/i),
			).not.toBeInTheDocument();

			// Click Onsite OK → visible again
			await user.click(screen.getByLabelText("Onsite OK"));
			expect(screen.getByLabelText(/commutable cities/i)).toBeInTheDocument();
		});

		it("hides relocation cities when relocation is off", () => {
			renderEditor(MOCK_PERSONA_DEFAULTS);

			expect(
				screen.queryByLabelText(/relocation cities/i),
			).not.toBeInTheDocument();
		});

		it("shows relocation cities when relocation is on", () => {
			renderEditor();

			expect(screen.getByLabelText(/relocation cities/i)).toBeInTheDocument();
			expect(screen.getByText("Austin")).toBeInTheDocument();
			expect(screen.getByText("Denver")).toBeInTheDocument();
		});

		it("hides salary input when 'Prefer not to set' is checked", async () => {
			const user = renderEditor();

			// Salary is visible (persona has salary set)
			expect(screen.getByLabelText(/minimum base salary/i)).toBeInTheDocument();

			// Check "Prefer not to set"
			await user.click(screen.getByLabelText(/prefer not to set/i));

			expect(
				screen.queryByLabelText(/minimum base salary/i),
			).not.toBeInTheDocument();
		});

		it("shows salary input when 'Prefer not to set' is unchecked", async () => {
			const user = renderEditor(MOCK_PERSONA_NULL_SALARY);

			// Salary hidden (prefer_no_salary defaults to true)
			expect(
				screen.queryByLabelText(/minimum base salary/i),
			).not.toBeInTheDocument();

			// Uncheck "Prefer not to set"
			await user.click(screen.getByLabelText(/prefer not to set/i));

			expect(screen.getByLabelText(/minimum base salary/i)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Submission
	// -----------------------------------------------------------------------

	describe("submission", () => {
		it("calls apiPatch with correct URL and body", async () => {
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);
			const user = renderEditor();

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(PERSONA_PATCH_URL, {
					remote_preference: "Hybrid OK",
					commutable_cities: ["Boston", "NYC"],
					max_commute_minutes: 45,
					relocation_open: true,
					relocation_cities: ["Austin", "Denver"],
					minimum_base_salary: 120000,
					salary_currency: "EUR",
					visa_sponsorship_required: true,
					industry_exclusions: ["Tobacco", "Gambling"],
					company_size_preference: "Startup",
					max_travel_percent: "<25%",
				});
			});
		});

		it("clears commute fields when Remote Only on submit", async () => {
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);
			const user = renderEditor({
				...MOCK_PERSONA,
				remote_preference: "Remote Only",
				commutable_cities: [],
				max_commute_minutes: null,
			});

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					PERSONA_PATCH_URL,
					expect.objectContaining({
						remote_preference: "Remote Only",
						commutable_cities: [],
						max_commute_minutes: null,
					}),
				);
			});
		});

		it("clears relocation cities when relocation is off on submit", async () => {
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);
			const user = renderEditor();

			// Turn off relocation
			await user.click(screen.getByLabelText(/open to relocation/i));

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					PERSONA_PATCH_URL,
					expect.objectContaining({
						relocation_open: false,
						relocation_cities: [],
					}),
				);
			});
		});

		it("sends null salary when 'Prefer not to set' is checked", async () => {
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);
			const user = renderEditor(MOCK_PERSONA_NULL_SALARY);

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					PERSONA_PATCH_URL,
					expect.objectContaining({
						minimum_base_salary: null,
					}),
				);
			});
		});

		it("shows success message after save", async () => {
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);
			const user = renderEditor();

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(screen.getByText(/saved/i)).toBeInTheDocument();
			});
		});

		it("shows error message on submission failure", async () => {
			mocks.mockApiPatch.mockRejectedValueOnce(new Error("Network failure"));
			const user = renderEditor();

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(screen.getByText(GENERIC_ERROR_TEXT)).toBeInTheDocument();
			});
		});

		it("shows saving state during submission", async () => {
			mocks.mockApiPatch.mockReturnValue(new Promise(() => {}));
			const user = renderEditor();

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				const btn = screen.getByRole("button", { name: /saving/i });
				expect(btn).toBeDisabled();
			});
		});

		it("re-enables save button after failed submission", async () => {
			mocks.mockApiPatch.mockRejectedValueOnce(new Error("fail"));
			const user = renderEditor();

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				const btn = screen.getByRole("button", { name: /save/i });
				expect(btn).not.toBeDisabled();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Cache invalidation
	// -----------------------------------------------------------------------

	describe("cache invalidation", () => {
		it("invalidates personas query after success", async () => {
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);
			const user = renderEditor();

			const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(invalidateSpy).toHaveBeenCalledWith({
					queryKey: ["personas"],
				});
			});
		});
	});

	// -----------------------------------------------------------------------
	// Custom filters section
	// -----------------------------------------------------------------------

	describe("custom filters", () => {
		it("renders CustomFiltersSection with persona id", () => {
			renderEditor();

			const section = screen.getByTestId("custom-filters-section");
			expect(section).toBeInTheDocument();
			expect(section).toHaveTextContent(DEFAULT_PERSONA_ID);
		});
	});

	// -----------------------------------------------------------------------
	// Navigation
	// -----------------------------------------------------------------------

	describe("navigation", () => {
		it("Back to Profile link has href /persona", () => {
			renderEditor();

			const link = screen.getByRole("link", { name: /back to profile/i });
			expect(link).toHaveAttribute("href", "/persona");
		});
	});
});
