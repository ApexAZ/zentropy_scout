/**
 * Tests for the GrowthTargetsEditor component (§6.11).
 *
 * REQ-012 §7.2.8: Simple form matching §6.3.9 — tag inputs for target
 * roles and skills, stretch appetite radio group. Pre-fills from
 * persona prop, PATCHes on save, invalidates cache, shows success.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Persona } from "@/types/persona";

import { GrowthTargetsEditor } from "./growth-targets-editor";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const PERSONA_PATCH_URL = `/personas/${DEFAULT_PERSONA_ID}`;
const GENERIC_ERROR_TEXT = "Failed to save. Please try again.";
const FORM_TESTID = "growth-targets-editor-form";
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
	target_roles: ["Engineering Manager", "Staff Engineer"],
	target_skills: ["Kubernetes", "People Management"],
	stretch_appetite: "High",
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
	minimum_fit_threshold: 50,
	auto_draft_threshold: 90,
	polling_frequency: "Daily",
	onboarding_complete: true,
	onboarding_step: null,
	created_at: "2026-01-01T00:00:00Z",
	updated_at: "2026-01-01T00:00:00Z",
};

const MOCK_PERSONA_DEFAULTS: Persona = {
	...MOCK_PERSONA,
	target_roles: [],
	target_skills: [],
	stretch_appetite: "Medium",
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
			<GrowthTargetsEditor persona={persona} />
		</Wrapper>,
	);
	return user;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("GrowthTargetsEditor", () => {
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
				screen.getByRole("heading", { name: /growth targets/i }),
			).toBeInTheDocument();
		});

		it("renders Target Roles label", () => {
			renderEditor();

			expect(screen.getByText("Target Roles")).toBeInTheDocument();
		});

		it("renders Target Skills label", () => {
			renderEditor();

			expect(screen.getByText("Target Skills")).toBeInTheDocument();
		});

		it("renders Stretch Appetite radio group", () => {
			renderEditor();

			expect(
				screen.getByRole("radiogroup", { name: /stretch appetite/i }),
			).toBeInTheDocument();
		});

		it("renders all 3 stretch appetite options with descriptions", () => {
			renderEditor();

			expect(screen.getByRole("radio", { name: /low/i })).toBeInTheDocument();
			expect(
				screen.getByRole("radio", { name: /medium/i }),
			).toBeInTheDocument();
			expect(screen.getByRole("radio", { name: /high/i })).toBeInTheDocument();
			expect(
				screen.getByText("Show me roles I'm already qualified for"),
			).toBeInTheDocument();
			expect(
				screen.getByText("Mix of comfortable and stretch roles"),
			).toBeInTheDocument();
			expect(
				screen.getByText("Challenge me — I want to grow into new areas"),
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
		it("pre-fills target roles as tag chips", () => {
			renderEditor();

			expect(screen.getByText("Engineering Manager")).toBeInTheDocument();
			expect(screen.getByText("Staff Engineer")).toBeInTheDocument();
		});

		it("pre-fills target skills as tag chips", () => {
			renderEditor();

			expect(screen.getByText("Kubernetes")).toBeInTheDocument();
			expect(screen.getByText("People Management")).toBeInTheDocument();
		});

		it("pre-fills stretch appetite radio selection", () => {
			renderEditor();

			const highRadio = screen.getByRole("radio", { name: /high/i });
			expect(highRadio).toBeChecked();
		});

		it("defaults to Medium when persona has default values", () => {
			renderEditor(MOCK_PERSONA_DEFAULTS);

			const mediumRadio = screen.getByRole("radio", { name: /medium/i });
			expect(mediumRadio).toBeChecked();
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
					target_roles: ["Engineering Manager", "Staff Engineer"],
					target_skills: ["Kubernetes", "People Management"],
					stretch_appetite: "High",
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
