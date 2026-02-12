/**
 * Tests for the non-negotiables step component (onboarding Step 8).
 *
 * REQ-012 §6.3.8: Non-negotiables form with sections. §5.11 covers
 * the location preferences section: remote preference radio group,
 * commutable cities tag input (hidden if Remote Only), max commute
 * number input (hidden if Remote Only), open to relocation toggle,
 * relocation cities tag input (hidden if relocation = false).
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

/** Minimal persona response with only the fields NonNegotiablesStep reads. */
function makePersonaResponse(
	overrides: Partial<{
		remote_preference: string;
		commutable_cities: string[];
		max_commute_minutes: number | null;
		relocation_open: boolean;
		relocation_cities: string[];
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

			for (const option of REMOTE_OPTIONS) {
				expect(screen.getByLabelText(option)).toBeInTheDocument();
			}
		});

		it("renders relocation toggle", async () => {
			await renderFormWithUser();

			expect(screen.getByLabelText(/open to relocation/i)).toBeInTheDocument();
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

			expect(screen.getByLabelText("No Preference")).toBeChecked();
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
	});
});
