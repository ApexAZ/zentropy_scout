/**
 * Tests for the non-negotiables step component (onboarding Step 8).
 *
 * REQ-012 §6.3.8: Non-negotiables form with sections.
 * §5.11: Location preferences (remote preference, commutable cities,
 *        max commute, relocation toggle/cities).
 * §5.12: Compensation (salary, currency, prefer-not-to-set) and
 *        other filters (visa, industry exclusions, company size, travel).
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NonNegotiablesStep } from "./non-negotiables-step";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const GENERIC_ERROR_TEXT = "Failed to save. Please try again.";
const FORM_TESTID = "non-negotiables-form";
const SUBMIT_BUTTON_TESTID = "submit-button";
const BACK_BUTTON_TESTID = "back-button";
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
		mockApiPatch: vi.fn(),
		MockApiError,
		mockNext: vi.fn(),
		mockBack: vi.fn(),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPatch: mocks.mockApiPatch,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/onboarding-provider", () => ({
	useOnboarding: () => ({
		personaId: DEFAULT_PERSONA_ID,
		next: mocks.mockNext,
		back: mocks.mockBack,
		isStepSkippable: false,
	}),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Minimal persona response with all fields NonNegotiablesStep reads. */
function makePersonaResponse(
	overrides: Partial<{
		remote_preference: string;
		commutable_cities: string[];
		max_commute_minutes: number | null;
		relocation_open: boolean;
		relocation_cities: string[];
		minimum_base_salary: number | null;
		salary_currency: string;
		visa_sponsorship_required: boolean;
		industry_exclusions: string[];
		company_size_preference: string;
		max_travel_percent: string;
	}> = {},
) {
	return {
		data: [
			{
				id: DEFAULT_PERSONA_ID,
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
				...overrides,
			},
		],
		meta: { total: 1, page: 1, per_page: 20, total_pages: 1 },
	};
}

/** Render step, wait for loading to finish, and return a user event instance. */
async function renderFormWithUser() {
	const user = userEvent.setup();
	render(<NonNegotiablesStep />);
	await screen.findByTestId(FORM_TESTID);
	return user;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("NonNegotiablesStep", () => {
	beforeEach(() => {
		mocks.mockApiGet.mockReset();
		mocks.mockApiPatch.mockReset();
		mocks.mockNext.mockReset();
		mocks.mockBack.mockReset();
		// Default: apiGet returns persona with defaults (no pre-fill)
		mocks.mockApiGet.mockResolvedValue(makePersonaResponse());
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	// -----------------------------------------------------------------------
	// Rendering
	// -----------------------------------------------------------------------

	describe("rendering", () => {
		it("shows loading spinner while fetching persona", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
			render(<NonNegotiablesStep />);

			expect(screen.getByTestId("loading-non-negotiables")).toBeInTheDocument();
		});

		it("renders title and description after loading", async () => {
			await renderFormWithUser();

			expect(
				screen.getByRole("heading", { name: /non-negotiables/i }),
			).toBeInTheDocument();
			expect(
				screen.getByText(/set your location preferences/i),
			).toBeInTheDocument();
		});

		it("fetches persona data on mount", async () => {
			await renderFormWithUser();

			expect(mocks.mockApiGet).toHaveBeenCalledWith("/personas");
		});

		it("renders all 4 remote preference radio options", async () => {
			await renderFormWithUser();

			const remoteGroup = screen.getByRole("radiogroup", {
				name: /remote preference/i,
			});
			for (const option of REMOTE_OPTIONS) {
				const radio = remoteGroup.querySelector(`input[value="${option}"]`);
				expect(radio).toBeInTheDocument();
			}
		});

		it("renders relocation toggle", async () => {
			await renderFormWithUser();

			expect(screen.getByLabelText(/open to relocation/i)).toBeInTheDocument();
		});

		it("renders Compensation section heading", async () => {
			await renderFormWithUser();

			expect(screen.getByText("Compensation")).toBeInTheDocument();
		});

		it("renders salary input and currency selector defaulting to USD", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({ minimum_base_salary: 50000 }),
			);
			await renderFormWithUser();

			// Salary is set → prefer_no_salary = false → inputs visible
			expect(screen.getByLabelText(/minimum base salary/i)).toHaveValue(50000);
			expect(screen.getByLabelText(/currency/i)).toHaveValue("USD");
		});

		it("renders 'Prefer not to set' checkbox for salary", async () => {
			await renderFormWithUser();

			expect(screen.getByLabelText(/prefer not to set/i)).toBeInTheDocument();
		});

		it("renders Other Filters section heading", async () => {
			await renderFormWithUser();

			expect(screen.getByText("Other Filters")).toBeInTheDocument();
		});

		it("renders visa sponsorship toggle", async () => {
			await renderFormWithUser();

			expect(
				screen.getByLabelText(/visa sponsorship required/i),
			).toBeInTheDocument();
		});

		it("renders industry exclusions tag input", async () => {
			await renderFormWithUser();

			expect(screen.getByLabelText(/industry exclusions/i)).toBeInTheDocument();
		});

		it("renders all 4 company size preference radio options", async () => {
			await renderFormWithUser();

			// "No Preference" is shared with remote preference — use the radiogroup
			const companyGroup = screen.getByRole("radiogroup", {
				name: /company size/i,
			});
			for (const option of COMPANY_SIZE_OPTIONS) {
				const radio = companyGroup.querySelector(`input[value="${option}"]`);
				expect(radio).toBeInTheDocument();
			}
		});

		it("renders all 4 max travel radio options", async () => {
			await renderFormWithUser();

			const travelGroup = screen.getByRole("radiogroup", {
				name: /max travel/i,
			});
			for (const option of MAX_TRAVEL_OPTIONS) {
				const radio = travelGroup.querySelector(`input[value="${option}"]`);
				expect(radio).toBeInTheDocument();
			}
		});
	});

	// -----------------------------------------------------------------------
	// Pre-fill
	// -----------------------------------------------------------------------

	describe("pre-fill", () => {
		it("pre-fills remote preference from persona data", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({ remote_preference: "Hybrid OK" }),
			);
			await renderFormWithUser();

			const hybridRadio = screen.getByLabelText("Hybrid OK");
			expect(hybridRadio).toBeChecked();
		});

		it("pre-fills commutable cities from persona data", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({
					remote_preference: "Hybrid OK",
					commutable_cities: ["Boston", "NYC"],
				}),
			);
			await renderFormWithUser();

			expect(screen.getByText("Boston")).toBeInTheDocument();
			expect(screen.getByText("NYC")).toBeInTheDocument();
		});

		it("pre-fills max commute from persona data", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({
					remote_preference: "Hybrid OK",
					max_commute_minutes: 45,
				}),
			);
			await renderFormWithUser();

			const input = screen.getByLabelText(/max commute/i);
			expect(input).toHaveValue(45);
		});

		it("shows default form when persona fetch fails", async () => {
			mocks.mockApiGet.mockRejectedValue(new Error("Network error"));
			await renderFormWithUser();

			const remoteGroup = screen.getByRole("radiogroup", {
				name: /remote preference/i,
			});
			const noPreference = remoteGroup.querySelector(
				'input[value="No Preference"]',
			) as HTMLInputElement;
			expect(noPreference).toBeChecked();
			expect(screen.queryByLabelText(/open to relocation/i)).not.toBeChecked();
		});

		it("pre-fills relocation toggle and cities", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({
					relocation_open: true,
					relocation_cities: ["Austin", "Denver"],
				}),
			);
			await renderFormWithUser();

			expect(screen.getByLabelText(/open to relocation/i)).toBeChecked();
			expect(screen.getByText("Austin")).toBeInTheDocument();
			expect(screen.getByText("Denver")).toBeInTheDocument();
		});

		it("pre-fills salary and currency from persona data", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({
					minimum_base_salary: 120000,
					salary_currency: "EUR",
				}),
			);
			await renderFormWithUser();

			expect(screen.getByLabelText(/minimum base salary/i)).toHaveValue(120000);
			expect(screen.getByLabelText(/currency/i)).toHaveValue("EUR");
			expect(screen.getByLabelText(/prefer not to set/i)).not.toBeChecked();
		});

		it("checks 'Prefer not to set' when persona salary is null", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({ minimum_base_salary: null }),
			);
			await renderFormWithUser();

			expect(screen.getByLabelText(/prefer not to set/i)).toBeChecked();
		});

		it("pre-fills visa sponsorship from persona data", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({ visa_sponsorship_required: true }),
			);
			await renderFormWithUser();

			expect(screen.getByLabelText(/visa sponsorship required/i)).toBeChecked();
		});

		it("pre-fills industry exclusions from persona data", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({
					industry_exclusions: ["Tobacco", "Gambling"],
				}),
			);
			await renderFormWithUser();

			expect(screen.getByText("Tobacco")).toBeInTheDocument();
			expect(screen.getByText("Gambling")).toBeInTheDocument();
		});

		it("pre-fills company size preference from persona data", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({ company_size_preference: "Startup" }),
			);
			await renderFormWithUser();

			const companyGroup = screen.getByRole("radiogroup", {
				name: /company size/i,
			});
			const startupRadio = companyGroup.querySelector(
				'input[value="Startup"]',
			) as HTMLInputElement;
			expect(startupRadio).toBeChecked();
		});

		it("pre-fills max travel percent from persona data", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({ max_travel_percent: "<25%" }),
			);
			await renderFormWithUser();

			const travelGroup = screen.getByRole("radiogroup", {
				name: /max travel/i,
			});
			const radio = travelGroup.querySelector(
				'input[value="<25%"]',
			) as HTMLInputElement;
			expect(radio).toBeChecked();
		});
	});

	// -----------------------------------------------------------------------
	// Conditional field visibility
	// -----------------------------------------------------------------------

	describe("conditional field visibility", () => {
		it("hides commutable cities and max commute when Remote Only is selected", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({ remote_preference: "Remote Only" }),
			);
			await renderFormWithUser();

			expect(
				screen.queryByLabelText(/commutable cities/i),
			).not.toBeInTheDocument();
			expect(screen.queryByLabelText(/max commute/i)).not.toBeInTheDocument();
		});

		it("shows commutable cities and max commute when Hybrid OK is selected", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({ remote_preference: "Hybrid OK" }),
			);
			await renderFormWithUser();

			expect(screen.getByLabelText(/commutable cities/i)).toBeInTheDocument();
			expect(screen.getByLabelText(/max commute/i)).toBeInTheDocument();
		});

		it("shows commutable cities and max commute when Onsite OK is selected", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({ remote_preference: "Onsite OK" }),
			);
			await renderFormWithUser();

			expect(screen.getByLabelText(/commutable cities/i)).toBeInTheDocument();
			expect(screen.getByLabelText(/max commute/i)).toBeInTheDocument();
		});

		it("toggles commutable cities visibility when changing remote preference", async () => {
			const user = await renderFormWithUser();

			// Default is "No Preference" — commute fields visible
			expect(screen.getByLabelText(/commutable cities/i)).toBeInTheDocument();

			// Click "Remote Only" — commute fields hidden
			await user.click(screen.getByLabelText("Remote Only"));
			expect(
				screen.queryByLabelText(/commutable cities/i),
			).not.toBeInTheDocument();

			// Click "Hybrid OK" — commute fields visible again
			await user.click(screen.getByLabelText("Hybrid OK"));
			expect(screen.getByLabelText(/commutable cities/i)).toBeInTheDocument();
		});

		it("hides relocation cities when relocation is off", async () => {
			await renderFormWithUser();

			// Default relocation_open = false
			expect(
				screen.queryByLabelText(/relocation cities/i),
			).not.toBeInTheDocument();
		});

		it("shows relocation cities when relocation toggle is checked", async () => {
			const user = await renderFormWithUser();

			await user.click(screen.getByLabelText(/open to relocation/i));

			expect(screen.getByLabelText(/relocation cities/i)).toBeInTheDocument();
		});

		it("hides relocation cities when toggle is unchecked again", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({
					relocation_open: true,
					relocation_cities: ["Austin"],
				}),
			);
			const user = await renderFormWithUser();

			// Should be visible initially
			expect(screen.getByLabelText(/relocation cities/i)).toBeInTheDocument();

			// Uncheck toggle
			await user.click(screen.getByLabelText(/open to relocation/i));

			expect(
				screen.queryByLabelText(/relocation cities/i),
			).not.toBeInTheDocument();
		});

		it("hides salary input when 'Prefer not to set' is checked", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({ minimum_base_salary: 90000 }),
			);
			const user = await renderFormWithUser();

			// Salary should be visible (persona has a salary set)
			expect(screen.getByLabelText(/minimum base salary/i)).toBeInTheDocument();

			// Check "Prefer not to set"
			await user.click(screen.getByLabelText(/prefer not to set/i));

			expect(
				screen.queryByLabelText(/minimum base salary/i),
			).not.toBeInTheDocument();
		});

		it("shows salary input when 'Prefer not to set' is unchecked", async () => {
			// Default: salary is null → prefer_no_salary defaults to true
			const user = await renderFormWithUser();

			expect(
				screen.queryByLabelText(/minimum base salary/i),
			).not.toBeInTheDocument();

			// Uncheck "Prefer not to set"
			await user.click(screen.getByLabelText(/prefer not to set/i));

			expect(screen.getByLabelText(/minimum base salary/i)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Form submission
	// -----------------------------------------------------------------------

	describe("form submission", () => {
		it("submits location data with PATCH and advances", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({ remote_preference: "Hybrid OK" }),
			);
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);
			const user = await renderFormWithUser();

			// Add a commutable city
			const cityInput = screen.getByLabelText(/commutable cities/i);
			await user.type(cityInput, "Boston{Enter}");

			// Set max commute
			const commuteInput = screen.getByLabelText(/max commute/i);
			await user.clear(commuteInput);
			await user.type(commuteInput, "30");

			// Submit
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}`,
					expect.objectContaining({
						remote_preference: "Hybrid OK",
						commutable_cities: ["Boston"],
						max_commute_minutes: 30,
						relocation_open: false,
						relocation_cities: [],
					}),
				);
			});

			await waitFor(() => {
				expect(mocks.mockNext).toHaveBeenCalled();
			});
		});

		it("submits Remote Only with null commute fields", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({ remote_preference: "Remote Only" }),
			);
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);
			const user = await renderFormWithUser();

			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}`,
					expect.objectContaining({
						remote_preference: "Remote Only",
						commutable_cities: [],
						max_commute_minutes: null,
						relocation_open: false,
						relocation_cities: [],
					}),
				);
			});
		});

		it("clears relocation cities when relocation is off on submit", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({
					relocation_open: true,
					relocation_cities: ["Austin"],
				}),
			);
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);
			const user = await renderFormWithUser();

			// Turn off relocation
			await user.click(screen.getByLabelText(/open to relocation/i));

			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}`,
					expect.objectContaining({
						relocation_open: false,
						relocation_cities: [],
					}),
				);
			});
		});

		it("submits salary and currency when salary is set", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({
					minimum_base_salary: 100000,
					salary_currency: "USD",
				}),
			);
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);
			const user = await renderFormWithUser();

			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}`,
					expect.objectContaining({
						minimum_base_salary: 100000,
						salary_currency: "USD",
					}),
				);
			});
		});

		it("submits updated currency when changed by user", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({ minimum_base_salary: 100000 }),
			);
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);
			const user = await renderFormWithUser();

			await user.selectOptions(screen.getByLabelText(/currency/i), "EUR");
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}`,
					expect.objectContaining({ salary_currency: "EUR" }),
				);
			});
		});

		it("submits null salary when 'Prefer not to set' is checked", async () => {
			// Default: null salary → prefer_no_salary = true
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);
			const user = await renderFormWithUser();

			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}`,
					expect.objectContaining({
						minimum_base_salary: null,
					}),
				);
			});
		});

		it("submits other filter fields correctly", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({
					visa_sponsorship_required: true,
					industry_exclusions: ["Tobacco"],
					company_size_preference: "Enterprise",
					max_travel_percent: "<50%",
				}),
			);
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);
			const user = await renderFormWithUser();

			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}`,
					expect.objectContaining({
						visa_sponsorship_required: true,
						industry_exclusions: ["Tobacco"],
						company_size_preference: "Enterprise",
						max_travel_percent: "<50%",
					}),
				);
			});
		});

		it("shows submit error on API failure", async () => {
			mocks.mockApiPatch.mockRejectedValue(
				new mocks.MockApiError("SERVER_ERROR", "Internal error", 500),
			);
			const user = await renderFormWithUser();

			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(screen.getByTestId("submit-error")).toHaveTextContent(
					GENERIC_ERROR_TEXT,
				);
			});
		});

		it("shows friendly error for validation failure", async () => {
			mocks.mockApiPatch.mockRejectedValue(
				new mocks.MockApiError("VALIDATION_ERROR", "Invalid data", 422),
			);
			const user = await renderFormWithUser();

			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(screen.getByTestId("submit-error")).toHaveTextContent(
					"Please check your input and try again.",
				);
			});
		});

		it("shows saving state during submission", async () => {
			mocks.mockApiPatch.mockReturnValue(new Promise(() => {}));
			const user = await renderFormWithUser();

			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				const btn = screen.getByTestId(SUBMIT_BUTTON_TESTID);
				expect(btn).toHaveTextContent("Saving...");
				expect(btn).toBeDisabled();
			});
		});

		it("re-enables submit button after failed submission", async () => {
			mocks.mockApiPatch.mockRejectedValueOnce(new Error("fail"));
			const user = await renderFormWithUser();

			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				const btn = screen.getByTestId(SUBMIT_BUTTON_TESTID);
				expect(btn).not.toBeDisabled();
				expect(btn).toHaveTextContent("Next");
			});
		});
	});

	// -----------------------------------------------------------------------
	// Validation
	// -----------------------------------------------------------------------

	describe("validation", () => {
		it("rejects negative max commute value on submit", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({ remote_preference: "Hybrid OK" }),
			);
			const user = await renderFormWithUser();

			const commuteInput = screen.getByLabelText(/max commute/i);
			await user.type(commuteInput, "-10");

			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				// Error shows in both FormMessage and FormErrorSummary
				const errors = screen.getAllByText(/must be a positive number/i);
				expect(errors.length).toBeGreaterThan(0);
			});
			expect(mocks.mockApiPatch).not.toHaveBeenCalled();
		});

		it("rejects max commute exceeding 480 minutes on submit", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({ remote_preference: "Hybrid OK" }),
			);
			const user = await renderFormWithUser();

			const commuteInput = screen.getByLabelText(/max commute/i);
			await user.type(commuteInput, "500");

			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				// Error shows in both FormMessage and FormErrorSummary
				const errors = screen.getAllByText(/cannot exceed 480 minutes/i);
				expect(errors.length).toBeGreaterThan(0);
			});
			expect(mocks.mockApiPatch).not.toHaveBeenCalled();
		});

		it("rejects negative salary value on submit", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({ minimum_base_salary: 100000 }),
			);
			const user = await renderFormWithUser();

			const salaryInput = screen.getByLabelText(/minimum base salary/i);
			await user.clear(salaryInput);
			await user.type(salaryInput, "-5000");

			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				const errors = screen.getAllByText(/must be a positive number/i);
				expect(errors.length).toBeGreaterThan(0);
			});
			expect(mocks.mockApiPatch).not.toHaveBeenCalled();
		});

		it("rejects zero salary value on submit", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({ minimum_base_salary: 100000 }),
			);
			const user = await renderFormWithUser();

			const salaryInput = screen.getByLabelText(/minimum base salary/i);
			await user.clear(salaryInput);
			await user.type(salaryInput, "0");

			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				const errors = screen.getAllByText(/must be a positive number/i);
				expect(errors.length).toBeGreaterThan(0);
			});
			expect(mocks.mockApiPatch).not.toHaveBeenCalled();
		});
	});

	// -----------------------------------------------------------------------
	// Navigation
	// -----------------------------------------------------------------------

	describe("navigation", () => {
		it("calls back() when Back button is clicked", async () => {
			const user = await renderFormWithUser();

			await user.click(screen.getByTestId(BACK_BUTTON_TESTID));

			expect(mocks.mockBack).toHaveBeenCalled();
		});

		it("does not show a Skip button (non-skippable step)", async () => {
			await renderFormWithUser();

			expect(
				screen.queryByRole("button", { name: /skip/i }),
			).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Tag input interaction
	// -----------------------------------------------------------------------

	describe("tag input interaction", () => {
		it("adds and removes commutable cities", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({ remote_preference: "Hybrid OK" }),
			);
			const user = await renderFormWithUser();

			const cityInput = screen.getByLabelText(/commutable cities/i);
			await user.type(cityInput, "Boston{Enter}");
			await user.type(cityInput, "NYC{Enter}");

			expect(screen.getByText("Boston")).toBeInTheDocument();
			expect(screen.getByText("NYC")).toBeInTheDocument();

			// Remove Boston
			await user.click(screen.getByLabelText("Remove Boston"));

			expect(screen.queryByText("Boston")).not.toBeInTheDocument();
			expect(screen.getByText("NYC")).toBeInTheDocument();
		});

		it("adds and removes relocation cities", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({ relocation_open: true }),
			);
			const user = await renderFormWithUser();

			const cityInput = screen.getByLabelText(/relocation cities/i);
			await user.type(cityInput, "Austin{Enter}");

			expect(screen.getByText("Austin")).toBeInTheDocument();

			await user.click(screen.getByLabelText("Remove Austin"));

			expect(screen.queryByText("Austin")).not.toBeInTheDocument();
		});

		it("adds and removes industry exclusions", async () => {
			const user = await renderFormWithUser();

			const input = screen.getByLabelText(/industry exclusions/i);
			await user.type(input, "Tobacco{Enter}");
			await user.type(input, "Gambling{Enter}");

			expect(screen.getByText("Tobacco")).toBeInTheDocument();
			expect(screen.getByText("Gambling")).toBeInTheDocument();

			await user.click(screen.getByLabelText("Remove Tobacco"));

			expect(screen.queryByText("Tobacco")).not.toBeInTheDocument();
			expect(screen.getByText("Gambling")).toBeInTheDocument();
		});
	});
});
