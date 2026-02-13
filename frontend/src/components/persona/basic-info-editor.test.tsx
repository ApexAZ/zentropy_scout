/**
 * Tests for the BasicInfoEditor component (§6.3).
 *
 * REQ-012 §7.2.1: Two-column form (desktop) / stacked (mobile) for all
 * 12 basic info and professional overview fields. Pre-filled from persona
 * prop, validates on submit, PATCHes /personas/{id}, invalidates cache,
 * and navigates back to /persona.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Persona } from "@/types/persona";

import { BasicInfoEditor } from "./basic-info-editor";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const GENERIC_ERROR_TEXT = "Failed to save. Please try again.";
const FORM_TESTID = "basic-info-editor-form";
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
	"Professional Summary",
	"Years of Experience",
	"Current Role",
	"Current Company",
] as const;

const MOCK_PERSONA: Persona = {
	id: DEFAULT_PERSONA_ID,
	user_id: "00000000-0000-4000-a000-000000000002",
	full_name: "Jane Doe",
	email: "jane@example.com",
	phone: "+1-555-0123",
	home_city: "San Francisco",
	home_state: "CA",
	home_country: "USA",
	linkedin_url: "https://linkedin.com/in/janedoe",
	portfolio_url: "https://janedoe.com",
	professional_summary: "Senior engineer with 8 years of experience",
	years_experience: 8,
	current_role: "Staff Engineer",
	current_company: "TechCorp",
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
		mockApiPatch: vi.fn(),
		MockApiError,
		mockRouterPush: vi.fn(),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiPatch: mocks.mockApiPatch,
	ApiError: mocks.MockApiError,
}));

vi.mock("next/navigation", () => ({
	useRouter: () => ({
		push: mocks.mockRouterPush,
	}),
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
			<BasicInfoEditor persona={persona} />
		</Wrapper>,
	);
	return user;
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

describe("BasicInfoEditor", () => {
	beforeEach(() => {
		mocks.mockApiPatch.mockReset();
		mocks.mockRouterPush.mockReset();
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	// -----------------------------------------------------------------------
	// Rendering
	// -----------------------------------------------------------------------

	describe("rendering", () => {
		it("shows all 12 form field labels", () => {
			renderEditor();

			for (const label of FIELD_LABELS) {
				expect(screen.getByLabelText(label)).toBeInTheDocument();
			}
		});

		it("renders a Save button", () => {
			renderEditor();

			expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
		});

		it("renders a Back to Profile link to /persona", () => {
			renderEditor();

			const link = screen.getByRole("link", { name: /back to profile/i });
			expect(link).toHaveAttribute("href", "/persona");
		});

		it("renders heading", () => {
			renderEditor();

			expect(
				screen.getByRole("heading", { name: /edit basic info/i }),
			).toBeInTheDocument();
		});

		it("has correct form testid", () => {
			renderEditor();

			expect(screen.getByTestId(FORM_TESTID)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Pre-fill
	// -----------------------------------------------------------------------

	describe("pre-fill", () => {
		it("pre-fills 8 basic info fields from persona", () => {
			renderEditor();

			expect(screen.getByLabelText("Full Name")).toHaveValue("Jane Doe");
			expect(screen.getByLabelText("Email")).toHaveValue("jane@example.com");
			expect(screen.getByLabelText("Phone")).toHaveValue("+1-555-0123");
			expect(screen.getByLabelText("LinkedIn URL")).toHaveValue(
				"https://linkedin.com/in/janedoe",
			);
			expect(screen.getByLabelText("Portfolio URL")).toHaveValue(
				"https://janedoe.com",
			);
			expect(screen.getByLabelText("City")).toHaveValue("San Francisco");
			expect(screen.getByLabelText("State")).toHaveValue("CA");
			expect(screen.getByLabelText("Country")).toHaveValue("USA");
		});

		it("pre-fills 4 professional overview fields from persona", () => {
			renderEditor();

			expect(screen.getByLabelText("Professional Summary")).toHaveValue(
				"Senior engineer with 8 years of experience",
			);
			expect(screen.getByLabelText("Years of Experience")).toHaveValue(8);
			expect(screen.getByLabelText("Current Role")).toHaveValue(
				"Staff Engineer",
			);
			expect(screen.getByLabelText("Current Company")).toHaveValue("TechCorp");
		});

		it("shows empty string for null optional fields", () => {
			const personaNoOptionals = {
				...MOCK_PERSONA,
				linkedin_url: null,
				portfolio_url: null,
				professional_summary: null,
				years_experience: null,
				current_role: null,
				current_company: null,
			};
			renderEditor(personaNoOptionals);

			expect(screen.getByLabelText("LinkedIn URL")).toHaveValue("");
			expect(screen.getByLabelText("Portfolio URL")).toHaveValue("");
			expect(screen.getByLabelText("Professional Summary")).toHaveValue("");
			expect(screen.getByLabelText("Years of Experience")).toHaveValue(null);
			expect(screen.getByLabelText("Current Role")).toHaveValue("");
			expect(screen.getByLabelText("Current Company")).toHaveValue("");
		});
	});

	// -----------------------------------------------------------------------
	// Validation
	// -----------------------------------------------------------------------

	describe("validation", () => {
		it("shows error when full name is empty on submit", async () => {
			const personaEmpty = { ...MOCK_PERSONA, full_name: "" };
			const user = renderEditor(personaEmpty);

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(
					screen.getAllByText("Full name is required").length,
				).toBeGreaterThanOrEqual(1);
			});
			expect(mocks.mockApiPatch).not.toHaveBeenCalled();
		});

		it("shows error when email is empty on submit", async () => {
			const personaEmpty = { ...MOCK_PERSONA, email: "" };
			const user = renderEditor(personaEmpty);

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(
					screen.getAllByText("Email is required").length,
				).toBeGreaterThanOrEqual(1);
			});
		});

		it("shows error for invalid email format", async () => {
			const user = renderEditor();

			const emailInput = screen.getByLabelText("Email");
			await user.clear(emailInput);
			await user.type(emailInput, "not-an-email");
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(
					screen.getAllByText("Invalid email format").length,
				).toBeGreaterThanOrEqual(1);
			});
		});

		it("shows error when phone is empty on submit", async () => {
			const personaEmpty = { ...MOCK_PERSONA, phone: "" };
			const user = renderEditor(personaEmpty);

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(
					screen.getAllByText("Phone number is required").length,
				).toBeGreaterThanOrEqual(1);
			});
		});

		it("shows error for invalid URL format", async () => {
			const user = renderEditor();

			const linkedinInput = screen.getByLabelText("LinkedIn URL");
			await user.clear(linkedinInput);
			await user.type(linkedinInput, "not-a-url");
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(
					screen.getAllByText("Invalid URL format").length,
				).toBeGreaterThanOrEqual(1);
			});
		});

		it("rejects javascript: URL scheme", async () => {
			const user = renderEditor();

			const linkedinInput = screen.getByLabelText("LinkedIn URL");
			await user.clear(linkedinInput);
			await user.type(linkedinInput, "javascript:alert(1)");
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(
					screen.getAllByText("URL must start with http:// or https://").length,
				).toBeGreaterThanOrEqual(1);
			});
		});

		it("allows empty optional URL fields", async () => {
			const personaNoUrls = {
				...MOCK_PERSONA,
				linkedin_url: null,
				portfolio_url: null,
				professional_summary: null,
				years_experience: null,
				current_role: null,
				current_company: null,
			};
			const user = renderEditor(personaNoUrls);
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledTimes(1);
			});
		});

		it("shows error when location fields are empty on submit", async () => {
			const personaEmpty = {
				...MOCK_PERSONA,
				home_city: "",
				home_state: "",
				home_country: "",
			};
			const user = renderEditor(personaEmpty);

			await user.click(screen.getByRole("button", { name: /save/i }));

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

		it("validates years of experience is 0-99 integer", async () => {
			const user = renderEditor();

			const yearsInput = screen.getByLabelText("Years of Experience");
			await user.clear(yearsInput);
			await user.type(yearsInput, "100");
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(
					screen.getAllByText("Must be between 0 and 99").length,
				).toBeGreaterThanOrEqual(1);
			});
		});

		it("allows empty years of experience", async () => {
			const personaNoYears = {
				...MOCK_PERSONA,
				years_experience: null,
				linkedin_url: null,
				portfolio_url: null,
				professional_summary: null,
				current_role: null,
				current_company: null,
			};
			const user = renderEditor(personaNoYears);
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledTimes(1);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Submission
	// -----------------------------------------------------------------------

	describe("submission", () => {
		it("calls apiPatch with correct 12-field payload", async () => {
			const user = renderEditor();
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}`,
					{
						full_name: "Jane Doe",
						email: "jane@example.com",
						phone: "+1-555-0123",
						linkedin_url: "https://linkedin.com/in/janedoe",
						portfolio_url: "https://janedoe.com",
						home_city: "San Francisco",
						home_state: "CA",
						home_country: "USA",
						professional_summary: "Senior engineer with 8 years of experience",
						years_experience: 8,
						current_role: "Staff Engineer",
						current_company: "TechCorp",
					},
				);
			});
		});

		it("converts empty optional strings to null in payload", async () => {
			const personaNoOptionals = {
				...MOCK_PERSONA,
				linkedin_url: null,
				portfolio_url: null,
				professional_summary: null,
				years_experience: null,
				current_role: null,
				current_company: null,
			};
			const user = renderEditor(personaNoOptionals);
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}`,
					expect.objectContaining({
						linkedin_url: null,
						portfolio_url: null,
						professional_summary: null,
						years_experience: null,
						current_role: null,
						current_company: null,
					}),
				);
			});
		});

		it("invalidates personas query cache after success", async () => {
			const user = renderEditor();
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);
			const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(invalidateSpy).toHaveBeenCalledWith({
					queryKey: ["personas"],
				});
			});
		});

		it("navigates to /persona after successful save", async () => {
			const user = renderEditor();
			mocks.mockApiPatch.mockResolvedValueOnce(MOCK_PATCH_RESPONSE);

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockRouterPush).toHaveBeenCalledWith("/persona");
			});
		});

		it("shows friendly error for VALIDATION_ERROR", async () => {
			const user = renderEditor();
			mocks.mockApiPatch.mockRejectedValueOnce(
				new mocks.MockApiError(
					"VALIDATION_ERROR",
					"Server validation failed",
					422,
				),
			);

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(
					screen.getByText("Please check your input and try again."),
				).toBeInTheDocument();
			});
			expect(mocks.mockRouterPush).not.toHaveBeenCalled();
		});

		it("shows friendly error for DUPLICATE_EMAIL", async () => {
			const user = renderEditor();
			mocks.mockApiPatch.mockRejectedValueOnce(
				new mocks.MockApiError("DUPLICATE_EMAIL", "Email already exists", 409),
			);

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(
					screen.getByText("This email address is already in use."),
				).toBeInTheDocument();
			});
		});

		it("shows generic error for non-API errors", async () => {
			const user = renderEditor();
			mocks.mockApiPatch.mockRejectedValueOnce(new Error("Network failure"));

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(screen.getByText(GENERIC_ERROR_TEXT)).toBeInTheDocument();
			});
		});

		it("shows saving state during submission", async () => {
			const user = renderEditor();
			mocks.mockApiPatch.mockReturnValue(new Promise(() => {}));

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				const btn = screen.getByRole("button", { name: /saving/i });
				expect(btn).toBeDisabled();
			});
		});

		it("re-enables save button after failed submission", async () => {
			const user = renderEditor();
			mocks.mockApiPatch.mockRejectedValueOnce(new Error("fail"));

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				const btn = screen.getByRole("button", { name: /save/i });
				expect(btn).not.toBeDisabled();
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
