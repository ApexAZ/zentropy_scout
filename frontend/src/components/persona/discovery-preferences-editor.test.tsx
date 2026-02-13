/**
 * Tests for the DiscoveryPreferencesEditor component (§6.11).
 *
 * REQ-012 §7.2.9: Two threshold sliders (0-100), polling frequency
 * select, behavioral explanations, and cross-field validation warning.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Persona } from "@/types/persona";

import { DiscoveryPreferencesEditor } from "./discovery-preferences-editor";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const PERSONA_PATCH_URL = `/personas/${DEFAULT_PERSONA_ID}`;
const GENERIC_ERROR_TEXT = "Failed to save. Please try again.";
const FORM_TESTID = "discovery-preferences-editor-form";
const MOCK_PATCH_RESPONSE = { data: {} };

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
	remote_preference: "No Preference",
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
	polling_frequency: "Weekly",
	onboarding_complete: true,
	onboarding_step: null,
	created_at: "2026-01-01T00:00:00Z",
	updated_at: "2026-01-01T00:00:00Z",
};

const MOCK_PERSONA_DEFAULTS: Persona = {
	...MOCK_PERSONA,
	minimum_fit_threshold: 50,
	auto_draft_threshold: 90,
	polling_frequency: "Daily",
};

const MOCK_PERSONA_THRESHOLD_WARNING: Persona = {
	...MOCK_PERSONA,
	minimum_fit_threshold: 80,
	auto_draft_threshold: 60,
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
			<DiscoveryPreferencesEditor persona={persona} />
		</Wrapper>,
	);
	return user;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DiscoveryPreferencesEditor", () => {
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
				screen.getByRole("heading", { name: /discovery preferences/i }),
			).toBeInTheDocument();
		});

		it("renders minimum fit threshold slider", () => {
			renderEditor();

			expect(
				screen.getByLabelText(/minimum fit threshold/i),
			).toBeInTheDocument();
		});

		it("renders auto-draft threshold slider", () => {
			renderEditor();

			expect(
				screen.getByLabelText(/auto-draft threshold/i),
			).toBeInTheDocument();
		});

		it("renders polling frequency select", () => {
			renderEditor();

			expect(screen.getByLabelText(/polling frequency/i)).toBeInTheDocument();
		});

		it("renders behavioral explanation for fit threshold", () => {
			renderEditor();

			expect(
				screen.getByText("Jobs scoring below 70 will be hidden from your feed"),
			).toBeInTheDocument();
		});

		it("renders behavioral explanation for auto-draft threshold", () => {
			renderEditor();

			expect(
				screen.getByText(
					"I'll automatically draft materials for jobs scoring 85 or above",
				),
			).toBeInTheDocument();
		});

		it("renders polling frequency explanation", () => {
			renderEditor();

			expect(
				screen.getByText("How often should I check for new jobs?"),
			).toBeInTheDocument();
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
		it("pre-fills minimum fit threshold slider value", () => {
			renderEditor();

			const slider = screen.getByLabelText(
				/minimum fit threshold/i,
			) as HTMLInputElement;
			expect(slider.value).toBe("70");
		});

		it("pre-fills auto-draft threshold slider value", () => {
			renderEditor();

			const slider = screen.getByLabelText(
				/auto-draft threshold/i,
			) as HTMLInputElement;
			expect(slider.value).toBe("85");
		});

		it("pre-fills polling frequency select", () => {
			renderEditor();

			expect(screen.getByLabelText(/polling frequency/i)).toHaveValue("Weekly");
		});

		it("shows default values for default persona", () => {
			renderEditor(MOCK_PERSONA_DEFAULTS);

			const fitSlider = screen.getByLabelText(
				/minimum fit threshold/i,
			) as HTMLInputElement;
			const draftSlider = screen.getByLabelText(
				/auto-draft threshold/i,
			) as HTMLInputElement;

			expect(fitSlider.value).toBe("50");
			expect(draftSlider.value).toBe("90");
			expect(screen.getByLabelText(/polling frequency/i)).toHaveValue("Daily");
		});
	});

	// -----------------------------------------------------------------------
	// Cross-field validation warning
	// -----------------------------------------------------------------------

	describe("cross-field validation warning", () => {
		it("shows warning when auto_draft < minimum_fit", () => {
			renderEditor(MOCK_PERSONA_THRESHOLD_WARNING);

			expect(
				screen.getByText(/auto-draft threshold is below your fit threshold/i),
			).toBeInTheDocument();
		});

		it("does not show warning when auto_draft >= minimum_fit", () => {
			renderEditor();

			expect(
				screen.queryByText(/auto-draft threshold is below your fit threshold/i),
			).not.toBeInTheDocument();
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
					minimum_fit_threshold: 70,
					auto_draft_threshold: 85,
					polling_frequency: "Weekly",
				});
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
