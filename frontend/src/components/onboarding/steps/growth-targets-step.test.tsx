/**
 * Tests for the growth targets step component (onboarding Step 9).
 *
 * REQ-012 §6.3.9: Growth targets form with tag inputs for target
 * roles and skills, and a stretch appetite radio group with
 * descriptions (Low / Medium / High, default Medium).
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GrowthTargetsStep } from "./growth-targets-step";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const GENERIC_ERROR_TEXT = "Failed to save. Please try again.";
const FORM_TESTID = "growth-targets-form";
const SUBMIT_BUTTON_TESTID = "submit-button";
const BACK_BUTTON_TESTID = "back-button";
const MOCK_PATCH_RESPONSE = { data: {} };

const STRETCH_OPTIONS = [
	{ value: "Low", description: "Show me roles I'm already qualified for" },
	{
		value: "Medium",
		description: "Mix of comfortable and stretch roles",
	},
	{
		value: "High",
		description: "Challenge me — I want to grow into new areas",
	},
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
	}),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Minimal persona response with growth target fields. */
function makePersonaResponse(
	overrides: Partial<{
		target_roles: string[];
		target_skills: string[];
		stretch_appetite: string;
	}> = {},
) {
	return {
		data: [
			{
				id: DEFAULT_PERSONA_ID,
				target_roles: [],
				target_skills: [],
				stretch_appetite: "Medium",
				...overrides,
			},
		],
		meta: { total: 1, page: 1, per_page: 20, total_pages: 1 },
	};
}

/** Render step, wait for loading to finish, and return a user event instance. */
async function renderFormWithUser() {
	const user = userEvent.setup();
	render(<GrowthTargetsStep />);
	await screen.findByTestId(FORM_TESTID);
	return user;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("GrowthTargetsStep", () => {
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
			render(<GrowthTargetsStep />);

			expect(screen.getByTestId("loading-growth-targets")).toBeInTheDocument();
		});

		it("renders title and description after loading", async () => {
			await renderFormWithUser();

			expect(
				screen.getByRole("heading", { name: /growth targets/i }),
			).toBeInTheDocument();
		});

		it("fetches persona data on mount", async () => {
			await renderFormWithUser();

			expect(mocks.mockApiGet).toHaveBeenCalledWith("/personas");
		});

		it("renders Target Roles tag input", async () => {
			await renderFormWithUser();

			expect(screen.getByText("Target Roles")).toBeInTheDocument();
		});

		it("renders Target Skills tag input", async () => {
			await renderFormWithUser();

			expect(screen.getByText("Target Skills")).toBeInTheDocument();
		});

		it("renders all 3 stretch appetite radio options with descriptions", async () => {
			await renderFormWithUser();

			const group = screen.getByRole("radiogroup", {
				name: /stretch appetite/i,
			});
			for (const option of STRETCH_OPTIONS) {
				const radio = group.querySelector(`input[value="${option.value}"]`);
				expect(radio).toBeInTheDocument();
			}

			// Check descriptions are shown
			for (const option of STRETCH_OPTIONS) {
				expect(screen.getByText(option.description)).toBeInTheDocument();
			}
		});

		it("defaults stretch appetite to Medium", async () => {
			await renderFormWithUser();

			const group = screen.getByRole("radiogroup", {
				name: /stretch appetite/i,
			});
			const mediumRadio = group.querySelector(
				'input[value="Medium"]',
			) as HTMLInputElement;
			expect(mediumRadio.checked).toBe(true);
		});
	});

	// -----------------------------------------------------------------------
	// Pre-fill
	// -----------------------------------------------------------------------

	describe("pre-fill", () => {
		it("pre-fills target roles from persona data", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({
					target_roles: ["Engineering Manager", "Staff Engineer"],
				}),
			);

			await renderFormWithUser();

			expect(screen.getByText("Engineering Manager")).toBeInTheDocument();
			expect(screen.getByText("Staff Engineer")).toBeInTheDocument();
		});

		it("pre-fills target skills from persona data", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({
					target_skills: ["Kubernetes", "People Management"],
				}),
			);

			await renderFormWithUser();

			expect(screen.getByText("Kubernetes")).toBeInTheDocument();
			expect(screen.getByText("People Management")).toBeInTheDocument();
		});

		it("pre-fills stretch appetite from persona data", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makePersonaResponse({ stretch_appetite: "High" }),
			);

			await renderFormWithUser();

			const group = screen.getByRole("radiogroup", {
				name: /stretch appetite/i,
			});
			const highRadio = group.querySelector(
				'input[value="High"]',
			) as HTMLInputElement;
			expect(highRadio.checked).toBe(true);
		});
	});

	// -----------------------------------------------------------------------
	// Submit
	// -----------------------------------------------------------------------

	describe("submit", () => {
		it("PATCHes persona with form data and calls next()", async () => {
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);

			const user = await renderFormWithUser();

			// Add a target role
			const roleInput = screen.getByPlaceholderText(
				/e\.g\., Engineering Manager/i,
			);
			await user.type(roleInput, "Tech Lead{Enter}");

			// Add a target skill
			const skillInput = screen.getByPlaceholderText(/e\.g\., Kubernetes/i);
			await user.type(skillInput, "System Design{Enter}");

			// Select High stretch appetite
			const group = screen.getByRole("radiogroup", {
				name: /stretch appetite/i,
			});
			const highRadio = group.querySelector(
				'input[value="High"]',
			) as HTMLInputElement;
			await user.click(highRadio);

			// Submit
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}`,
					{
						target_roles: ["Tech Lead"],
						target_skills: ["System Design"],
						stretch_appetite: "High",
					},
				);
			});

			expect(mocks.mockNext).toHaveBeenCalledTimes(1);
		});

		it("shows error on failed PATCH", async () => {
			mocks.mockApiPatch.mockRejectedValueOnce(new Error("Network error"));

			const user = await renderFormWithUser();
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(screen.getByText(GENERIC_ERROR_TEXT)).toBeInTheDocument();
			});
			expect(mocks.mockNext).not.toHaveBeenCalled();
		});

		it("disables submit button and shows Saving text while submitting", async () => {
			mocks.mockApiPatch.mockReturnValue(new Promise(() => {}));

			const user = await renderFormWithUser();
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				const btn = screen.getByTestId(SUBMIT_BUTTON_TESTID);
				expect(btn).toBeDisabled();
				expect(btn).toHaveTextContent("Saving...");
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

		it("shows friendly error for validation failure", async () => {
			mocks.mockApiPatch.mockRejectedValueOnce(
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

		it("submits with default Medium when stretch appetite unchanged", async () => {
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);

			const user = await renderFormWithUser();
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}`,
					expect.objectContaining({
						stretch_appetite: "Medium",
					}),
				);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Navigation
	// -----------------------------------------------------------------------

	describe("navigation", () => {
		it("calls back() when Back is clicked", async () => {
			const user = await renderFormWithUser();

			await user.click(screen.getByTestId(BACK_BUTTON_TESTID));

			expect(mocks.mockBack).toHaveBeenCalledTimes(1);
		});

		it("does not render a Skip button", async () => {
			await renderFormWithUser();

			expect(
				screen.queryByRole("button", { name: /skip/i }),
			).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Tag interaction (basic — FormTagField is tested separately)
	// -----------------------------------------------------------------------

	describe("tag interaction", () => {
		it("adds a target role tag on Enter", async () => {
			const user = await renderFormWithUser();

			const roleInput = screen.getByPlaceholderText(
				/e\.g\., Engineering Manager/i,
			);
			await user.type(roleInput, "VP of Engineering{Enter}");

			expect(screen.getByText("VP of Engineering")).toBeInTheDocument();
		});

		it("adds a target skill tag on Enter", async () => {
			const user = await renderFormWithUser();

			const skillInput = screen.getByPlaceholderText(/e\.g\., Kubernetes/i);
			await user.type(skillInput, "Machine Learning{Enter}");

			expect(screen.getByText("Machine Learning")).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Fetch failure
	// -----------------------------------------------------------------------

	describe("fetch failure", () => {
		it("renders form with defaults when fetch fails", async () => {
			mocks.mockApiGet.mockRejectedValueOnce(new Error("Network error"));

			await renderFormWithUser();

			// Form should still render with defaults
			expect(screen.getByText("Target Roles")).toBeInTheDocument();
			expect(screen.getByText("Target Skills")).toBeInTheDocument();
		});
	});
});
