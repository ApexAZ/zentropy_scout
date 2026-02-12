/**
 * Tests for the basic info step component (onboarding Step 2).
 *
 * REQ-012 §6.3.2: 8-field form with pre-fill from resume extraction,
 * client-side validation, API submission, friendly error messages.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BasicInfoStep } from "./basic-info-step";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const GENERIC_ERROR_TEXT = "Failed to save. Please try again.";
const SUBMIT_BUTTON_TESTID = "submit-button";
const BACK_BUTTON_TESTID = "back-button";
const FORM_TESTID = "basic-info-form";
const MOCK_PATCH_RESPONSE = { data: {} };

const FIELD_LABELS = [
	"Full Name",
	"Email",
	"Phone",
	"LinkedIn URL",
	"Portfolio URL",
	"City",
	"State",
	"Country",
] as const;

const PRE_FILLED_VALUES = {
	full_name: "Jane Doe",
	email: "jane@example.com",
	phone: "+1-555-0123",
	linkedin_url: "https://linkedin.com/in/janedoe",
	portfolio_url: "https://janedoe.com",
	home_city: "San Francisco",
	home_state: "CA",
	home_country: "USA",
} as const;

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
		mockApiGet: vi.fn(),
		MockApiError,
		mockNext: vi.fn(),
		mockBack: vi.fn(),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiPatch: mocks.mockApiPatch,
	apiGet: mocks.mockApiGet,
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

/** Minimal persona object with only the fields BasicInfoStep reads. */
function makePersonaResponse(
	overrides: Partial<typeof PRE_FILLED_VALUES> = {},
) {
	return {
		data: [
			{
				id: DEFAULT_PERSONA_ID,
				full_name: "",
				email: "",
				phone: "",
				home_city: "",
				home_state: "",
				home_country: "",
				linkedin_url: null,
				portfolio_url: null,
				...overrides,
			},
		],
		meta: { total: 1, page: 1, per_page: 20, total_pages: 1 },
	};
}

/** Render BasicInfoStep, wait for loading to finish, and return a user event instance. */
async function renderFormWithUser() {
	const user = userEvent.setup();
	render(<BasicInfoStep />);
	await screen.findByTestId(FORM_TESTID);
	return user;
}

/** Fill all required fields with valid data. */
async function fillRequiredFields(user: ReturnType<typeof userEvent.setup>) {
	await user.type(
		screen.getByLabelText("Full Name"),
		PRE_FILLED_VALUES.full_name,
	);
	await user.type(screen.getByLabelText("Email"), PRE_FILLED_VALUES.email);
	await user.type(screen.getByLabelText("Phone"), PRE_FILLED_VALUES.phone);
	await user.type(screen.getByLabelText("City"), PRE_FILLED_VALUES.home_city);
	await user.type(screen.getByLabelText("State"), PRE_FILLED_VALUES.home_state);
	await user.type(
		screen.getByLabelText("Country"),
		PRE_FILLED_VALUES.home_country,
	);
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

describe("BasicInfoStep", () => {
	beforeEach(() => {
		mocks.mockApiPatch.mockReset();
		mocks.mockApiGet.mockReset();
		mocks.mockNext.mockReset();
		mocks.mockBack.mockReset();

		// Default: apiGet returns empty persona (no pre-fill)
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
		it("shows loading state while fetching persona data", () => {
			// Make apiGet hang (never resolves)
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
			render(<BasicInfoStep />);

			expect(screen.getByTestId("loading-persona")).toBeInTheDocument();
			expect(screen.getByText(/loading your information/i)).toBeInTheDocument();
		});

		it("renders all 8 form field labels", async () => {
			await renderFormWithUser();

			for (const label of FIELD_LABELS) {
				expect(screen.getByLabelText(label)).toBeInTheDocument();
			}
		});

		it("renders a submit/next button", async () => {
			await renderFormWithUser();

			const btn = screen.getByTestId(SUBMIT_BUTTON_TESTID);
			expect(btn).toBeInTheDocument();
			expect(btn).toHaveTextContent("Next");
		});

		it("renders a back button", async () => {
			await renderFormWithUser();

			const btn = screen.getByTestId(BACK_BUTTON_TESTID);
			expect(btn).toBeInTheDocument();
			expect(btn).toHaveTextContent("Back");
		});

		it("renders heading and description", async () => {
			await renderFormWithUser();

			expect(screen.getByText("Basic Information")).toBeInTheDocument();
			expect(
				screen.getByText(/foundation for your resume/i),
			).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Pre-fill
	// -----------------------------------------------------------------------

	describe("pre-fill", () => {
		it("pre-fills form fields from persona data", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse(PRE_FILLED_VALUES),
			);
			await renderFormWithUser();

			expect(screen.getByLabelText("Full Name")).toHaveValue(
				PRE_FILLED_VALUES.full_name,
			);
			expect(screen.getByLabelText("Email")).toHaveValue(
				PRE_FILLED_VALUES.email,
			);
			expect(screen.getByLabelText("Phone")).toHaveValue(
				PRE_FILLED_VALUES.phone,
			);
			expect(screen.getByLabelText("LinkedIn URL")).toHaveValue(
				PRE_FILLED_VALUES.linkedin_url,
			);
			expect(screen.getByLabelText("Portfolio URL")).toHaveValue(
				PRE_FILLED_VALUES.portfolio_url,
			);
			expect(screen.getByLabelText("City")).toHaveValue(
				PRE_FILLED_VALUES.home_city,
			);
			expect(screen.getByLabelText("State")).toHaveValue(
				PRE_FILLED_VALUES.home_state,
			);
			expect(screen.getByLabelText("Country")).toHaveValue(
				PRE_FILLED_VALUES.home_country,
			);
		});

		it("shows empty form when persona has no data", async () => {
			mocks.mockApiGet.mockResolvedValue(makePersonaResponse());
			await renderFormWithUser();

			expect(screen.getByLabelText("Full Name")).toHaveValue("");
			expect(screen.getByLabelText("Email")).toHaveValue("");
			expect(screen.getByLabelText("Phone")).toHaveValue("");
		});

		it("shows empty form when persona fetch fails", async () => {
			mocks.mockApiGet.mockRejectedValue(new Error("Network error"));
			await renderFormWithUser();

			expect(screen.getByLabelText("Full Name")).toHaveValue("");
			expect(screen.getByLabelText("Email")).toHaveValue("");
		});

		it("fetches persona data from /personas endpoint", async () => {
			await renderFormWithUser();

			expect(mocks.mockApiGet).toHaveBeenCalledWith("/personas");
		});
	});

	// -----------------------------------------------------------------------
	// Validation
	// -----------------------------------------------------------------------

	describe("validation", () => {
		it("shows error when full name is empty on submit", async () => {
			const user = await renderFormWithUser();

			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				// Error appears in both inline FormMessage and FormErrorSummary
				expect(
					screen.getAllByText("Full name is required").length,
				).toBeGreaterThanOrEqual(1);
			});
			expect(mocks.mockApiPatch).not.toHaveBeenCalled();
		});

		it("shows error when email is empty on submit", async () => {
			const user = await renderFormWithUser();

			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(
					screen.getAllByText("Email is required").length,
				).toBeGreaterThanOrEqual(1);
			});
		});

		it("shows error for invalid email format", async () => {
			const user = await renderFormWithUser();

			await user.type(screen.getByLabelText("Email"), "not-an-email");
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(
					screen.getAllByText("Invalid email format").length,
				).toBeGreaterThanOrEqual(1);
			});
		});

		it("shows error when phone is empty on submit", async () => {
			const user = await renderFormWithUser();

			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(
					screen.getAllByText("Phone number is required").length,
				).toBeGreaterThanOrEqual(1);
			});
		});

		it("shows error for invalid LinkedIn URL format", async () => {
			const user = await renderFormWithUser();

			await user.type(screen.getByLabelText("LinkedIn URL"), "not-a-url");
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(
					screen.getAllByText("Invalid URL format").length,
				).toBeGreaterThanOrEqual(1);
			});
		});

		it("shows error for invalid Portfolio URL format", async () => {
			const user = await renderFormWithUser();

			await user.type(screen.getByLabelText("Portfolio URL"), "not-a-url");
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(
					screen.getAllByText("Invalid URL format").length,
				).toBeGreaterThanOrEqual(1);
			});
		});

		it("rejects javascript: URL scheme", async () => {
			const user = await renderFormWithUser();

			await user.type(
				screen.getByLabelText("LinkedIn URL"),
				"javascript:alert(1)",
			);
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				// Zod .url() accepts javascript: as valid URL, but refine rejects it
				expect(
					screen.getAllByText("URL must start with http:// or https://").length,
				).toBeGreaterThanOrEqual(1);
			});
		});

		it("allows empty optional URL fields", async () => {
			const user = await renderFormWithUser();
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);

			await fillRequiredFields(user);
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledTimes(1);
			});
		});

		it("shows error when location fields are empty on submit", async () => {
			const user = await renderFormWithUser();

			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(
					screen.getAllByText("City is required").length,
				).toBeGreaterThanOrEqual(1);
				expect(
					screen.getAllByText("State is required").length,
				).toBeGreaterThanOrEqual(1);
				expect(
					screen.getAllByText("Country is required").length,
				).toBeGreaterThanOrEqual(1);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Form submission
	// -----------------------------------------------------------------------

	describe("form submission", () => {
		it("calls apiPatch with correct data on valid submit", async () => {
			const user = await renderFormWithUser();
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);

			await fillRequiredFields(user);
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}`,
					expect.objectContaining({
						full_name: PRE_FILLED_VALUES.full_name,
						email: PRE_FILLED_VALUES.email,
						phone: PRE_FILLED_VALUES.phone,
						home_city: PRE_FILLED_VALUES.home_city,
						home_state: PRE_FILLED_VALUES.home_state,
						home_country: PRE_FILLED_VALUES.home_country,
						linkedin_url: null,
						portfolio_url: null,
					}),
				);
			});
		});

		it("sends URL values when provided", async () => {
			const user = await renderFormWithUser();
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);

			await fillRequiredFields(user);
			await user.type(
				screen.getByLabelText("LinkedIn URL"),
				PRE_FILLED_VALUES.linkedin_url,
			);
			await user.type(
				screen.getByLabelText("Portfolio URL"),
				PRE_FILLED_VALUES.portfolio_url,
			);
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}`,
					expect.objectContaining({
						linkedin_url: PRE_FILLED_VALUES.linkedin_url,
						portfolio_url: PRE_FILLED_VALUES.portfolio_url,
					}),
				);
			});
		});

		it("calls next() after successful submit", async () => {
			const user = await renderFormWithUser();
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);

			await fillRequiredFields(user);
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockNext).toHaveBeenCalledTimes(1);
			});
		});

		it("shows friendly error for VALIDATION_ERROR", async () => {
			const user = await renderFormWithUser();
			mocks.mockApiPatch.mockRejectedValueOnce(
				new mocks.MockApiError(
					"VALIDATION_ERROR",
					"Server validation failed",
					422,
				),
			);

			await fillRequiredFields(user);
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(
					screen.getByText("Please check your input and try again."),
				).toBeInTheDocument();
			});
			expect(mocks.mockNext).not.toHaveBeenCalled();
		});

		it("shows friendly error for DUPLICATE_EMAIL", async () => {
			const user = await renderFormWithUser();
			mocks.mockApiPatch.mockRejectedValueOnce(
				new mocks.MockApiError("DUPLICATE_EMAIL", "Email already exists", 409),
			);

			await fillRequiredFields(user);
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(
					screen.getByText("This email address is already in use."),
				).toBeInTheDocument();
			});
		});

		it("shows generic error for non-API errors", async () => {
			const user = await renderFormWithUser();
			mocks.mockApiPatch.mockRejectedValueOnce(new Error("Network failure"));

			await fillRequiredFields(user);
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(screen.getByText(GENERIC_ERROR_TEXT)).toBeInTheDocument();
			});
		});

		it("shows saving state during submission", async () => {
			const user = await renderFormWithUser();
			mocks.mockApiPatch.mockReturnValue(new Promise(() => {}));

			await fillRequiredFields(user);
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				const btn = screen.getByTestId(SUBMIT_BUTTON_TESTID);
				expect(btn).toHaveTextContent("Saving...");
				expect(btn).toBeDisabled();
			});
		});

		it("re-enables submit button after failed submission", async () => {
			const user = await renderFormWithUser();
			mocks.mockApiPatch.mockRejectedValueOnce(new Error("fail"));

			await fillRequiredFields(user);
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				const btn = screen.getByTestId(SUBMIT_BUTTON_TESTID);
				expect(btn).not.toBeDisabled();
				expect(btn).toHaveTextContent("Next");
			});
		});
	});

	// -----------------------------------------------------------------------
	// Navigation
	// -----------------------------------------------------------------------

	describe("navigation", () => {
		it("calls back() when back button is clicked", async () => {
			const user = await renderFormWithUser();

			await user.click(screen.getByTestId(BACK_BUTTON_TESTID));

			expect(mocks.mockBack).toHaveBeenCalledTimes(1);
		});
	});
});
