/**
 * Tests for the VoiceProfileEditor component (§6.9).
 *
 * REQ-012 §7.2.6: Single form with text inputs, tag inputs
 * (sample_phrases, things_to_avoid), and optional textarea.
 * Fetches via useQuery, PATCHes on save, invalidates cache,
 * navigates back to /persona.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Persona, VoiceProfile } from "@/types/persona";

import { VoiceProfileEditor } from "./voice-profile-editor";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const VOICE_PROFILE_URL = `/personas/${DEFAULT_PERSONA_ID}/voice-profile`;
const GENERIC_ERROR_TEXT = "Failed to save. Please try again.";
const FORM_TESTID = "voice-profile-editor-form";

const MOCK_TONE = "Direct and confident";
const MOCK_STYLE = "Short sentences, active voice";
const MOCK_VOCAB = "Technical when relevant, plain otherwise";
const MOCK_PERSONALITY = "Occasional dry humor";
const MOCK_PHRASES = ["I led the effort", "The result was"];
const MOCK_AVOID = ["Passionate", "Synergy"];
const MOCK_SAMPLE_TEXT = "Here is how I write professionally...";

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

const MOCK_VOICE_PROFILE: VoiceProfile = {
	id: "00000000-0000-4000-a000-000000000010",
	persona_id: DEFAULT_PERSONA_ID,
	tone: MOCK_TONE,
	sentence_style: MOCK_STYLE,
	vocabulary_level: MOCK_VOCAB,
	personality_markers: MOCK_PERSONALITY,
	sample_phrases: MOCK_PHRASES,
	things_to_avoid: MOCK_AVOID,
	writing_sample_text: MOCK_SAMPLE_TEXT,
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
		mockApiPatch: vi.fn(),
		MockApiError,
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
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

function mockApiGetWithProfile(profile: VoiceProfile = MOCK_VOICE_PROFILE) {
	mocks.mockApiGet.mockResolvedValue({ data: profile });
}

function mockApiGetWithNulls() {
	mocks.mockApiGet.mockResolvedValue({
		data: {
			...MOCK_VOICE_PROFILE,
			personality_markers: null,
			writing_sample_text: null,
			sample_phrases: [],
			things_to_avoid: [],
		},
	});
}

function renderEditor(persona: Persona = MOCK_PERSONA) {
	const user = userEvent.setup();
	const Wrapper = createWrapper();
	render(
		<Wrapper>
			<VoiceProfileEditor persona={persona} />
		</Wrapper>,
	);
	return user;
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

describe("VoiceProfileEditor", () => {
	beforeEach(() => {
		mocks.mockApiGet.mockReset();
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
		it("shows loading spinner while fetching", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
			renderEditor();

			expect(
				screen.getByTestId("loading-voice-profile-editor"),
			).toBeInTheDocument();
		});

		it("renders heading after loading", async () => {
			mockApiGetWithProfile();
			renderEditor();

			await waitFor(() => {
				expect(
					screen.getByRole("heading", { name: /voice profile/i }),
				).toBeInTheDocument();
			});
		});

		it("renders all 4 text input labels", async () => {
			mockApiGetWithProfile();
			renderEditor();

			await waitFor(() => {
				expect(screen.getByLabelText("Tone")).toBeInTheDocument();
			});
			expect(screen.getByLabelText("Style")).toBeInTheDocument();
			expect(screen.getByLabelText("Vocabulary")).toBeInTheDocument();
			expect(screen.getByLabelText("Personality")).toBeInTheDocument();
		});

		it("renders tag input labels and textarea", async () => {
			mockApiGetWithProfile();
			renderEditor();

			await waitFor(() => {
				expect(screen.getByText("Sample Phrases")).toBeInTheDocument();
			});
			expect(screen.getByText("Things to Avoid")).toBeInTheDocument();
			expect(
				screen.getByLabelText("Writing Sample (optional)"),
			).toBeInTheDocument();
		});

		it("renders Save button", async () => {
			mockApiGetWithProfile();
			renderEditor();

			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: /save/i }),
				).toBeInTheDocument();
			});
		});

		it("has correct form testid", async () => {
			mockApiGetWithProfile();
			renderEditor();

			await waitFor(() => {
				expect(screen.getByTestId(FORM_TESTID)).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Fetch
	// -----------------------------------------------------------------------

	describe("fetch", () => {
		it("calls apiGet with correct voice profile URL", async () => {
			mockApiGetWithProfile();
			renderEditor();

			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith(VOICE_PROFILE_URL);
			});
		});

		it("shows form even when fetch fails", async () => {
			mocks.mockApiGet.mockRejectedValue(new Error("Network error"));
			renderEditor();

			await waitFor(() => {
				expect(
					screen.getByRole("heading", { name: /voice profile/i }),
				).toBeInTheDocument();
			});
			expect(screen.getByLabelText("Tone")).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Pre-fill
	// -----------------------------------------------------------------------

	describe("pre-fill", () => {
		it("pre-fills text fields from fetched voice profile", async () => {
			mockApiGetWithProfile();
			renderEditor();

			await waitFor(() => {
				expect(screen.getByLabelText("Tone")).toHaveValue(MOCK_TONE);
			});
			expect(screen.getByLabelText("Style")).toHaveValue(MOCK_STYLE);
			expect(screen.getByLabelText("Vocabulary")).toHaveValue(MOCK_VOCAB);
			expect(screen.getByLabelText("Personality")).toHaveValue(
				MOCK_PERSONALITY,
			);
		});

		it("pre-fills writing sample textarea", async () => {
			mockApiGetWithProfile();
			renderEditor();

			await waitFor(() => {
				expect(screen.getByLabelText("Writing Sample (optional)")).toHaveValue(
					MOCK_SAMPLE_TEXT,
				);
			});
		});

		it("renders tag chips for sample phrases and things to avoid", async () => {
			mockApiGetWithProfile();
			renderEditor();

			await waitFor(() => {
				expect(screen.getByText("I led the effort")).toBeInTheDocument();
			});
			expect(screen.getByText("The result was")).toBeInTheDocument();
			expect(screen.getByText("Passionate")).toBeInTheDocument();
			expect(screen.getByText("Synergy")).toBeInTheDocument();
		});

		it("shows empty fields when profile has null optional values", async () => {
			mockApiGetWithNulls();
			renderEditor();

			await waitFor(() => {
				expect(screen.getByLabelText("Personality")).toHaveValue("");
			});
			expect(screen.getByLabelText("Writing Sample (optional)")).toHaveValue(
				"",
			);
		});
	});

	// -----------------------------------------------------------------------
	// Validation
	// -----------------------------------------------------------------------

	describe("validation", () => {
		it("shows error when tone is empty on submit", async () => {
			mockApiGetWithNulls();
			const user = renderEditor();

			await waitFor(() => {
				expect(screen.getByLabelText("Tone")).toBeInTheDocument();
			});

			// Clear the pre-filled tone field
			await user.clear(screen.getByLabelText("Tone"));
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(
					screen.getAllByText("Tone is required").length,
				).toBeGreaterThanOrEqual(1);
			});
			expect(mocks.mockApiPatch).not.toHaveBeenCalled();
		});

		it("shows error when style is empty on submit", async () => {
			mockApiGetWithNulls();
			const user = renderEditor();

			await waitFor(() => {
				expect(screen.getByLabelText("Style")).toBeInTheDocument();
			});

			await user.clear(screen.getByLabelText("Style"));
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(
					screen.getAllByText("Style is required").length,
				).toBeGreaterThanOrEqual(1);
			});
		});

		it("shows error when vocabulary is empty on submit", async () => {
			mockApiGetWithNulls();
			const user = renderEditor();

			await waitFor(() => {
				expect(screen.getByLabelText("Vocabulary")).toBeInTheDocument();
			});

			await user.clear(screen.getByLabelText("Vocabulary"));
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(
					screen.getAllByText("Vocabulary is required").length,
				).toBeGreaterThanOrEqual(1);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Submission
	// -----------------------------------------------------------------------

	describe("submission", () => {
		it("calls apiPatch with correct URL and request body", async () => {
			mockApiGetWithProfile();
			mocks.mockApiPatch.mockResolvedValueOnce({ data: MOCK_VOICE_PROFILE });
			const user = renderEditor();

			await waitFor(() => {
				expect(screen.getByLabelText("Tone")).toHaveValue(MOCK_TONE);
			});

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(VOICE_PROFILE_URL, {
					tone: MOCK_TONE,
					sentence_style: MOCK_STYLE,
					vocabulary_level: MOCK_VOCAB,
					personality_markers: MOCK_PERSONALITY,
					sample_phrases: MOCK_PHRASES,
					things_to_avoid: MOCK_AVOID,
					writing_sample_text: MOCK_SAMPLE_TEXT,
				});
			});
		});

		it("converts empty optional strings to null in payload", async () => {
			mockApiGetWithNulls();
			mocks.mockApiPatch.mockResolvedValueOnce({
				data: MOCK_VOICE_PROFILE,
			});
			const user = renderEditor();

			await waitFor(() => {
				expect(screen.getByLabelText("Tone")).toBeInTheDocument();
			});

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					VOICE_PROFILE_URL,
					expect.objectContaining({
						personality_markers: null,
						writing_sample_text: null,
					}),
				);
			});
		});

		it("invalidates voiceProfile query cache after success", async () => {
			mockApiGetWithProfile();
			mocks.mockApiPatch.mockResolvedValueOnce({ data: MOCK_VOICE_PROFILE });
			const user = renderEditor();

			await waitFor(() => {
				expect(screen.getByLabelText("Tone")).toHaveValue(MOCK_TONE);
			});

			const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(invalidateSpy).toHaveBeenCalledWith({
					queryKey: ["personas", DEFAULT_PERSONA_ID, "voice-profile"],
				});
			});
		});

		it("shows success message after save", async () => {
			mockApiGetWithProfile();
			mocks.mockApiPatch.mockResolvedValueOnce({ data: MOCK_VOICE_PROFILE });
			const user = renderEditor();

			await waitFor(() => {
				expect(screen.getByLabelText("Tone")).toHaveValue(MOCK_TONE);
			});

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(screen.getByText(/saved/i)).toBeInTheDocument();
			});
		});

		it("shows error message on submission failure", async () => {
			mockApiGetWithProfile();
			mocks.mockApiPatch.mockRejectedValueOnce(new Error("Network failure"));
			const user = renderEditor();

			await waitFor(() => {
				expect(screen.getByLabelText("Tone")).toHaveValue(MOCK_TONE);
			});

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(screen.getByText(GENERIC_ERROR_TEXT)).toBeInTheDocument();
			});
		});

		it("shows saving state during submission", async () => {
			mockApiGetWithProfile();
			mocks.mockApiPatch.mockReturnValue(new Promise(() => {}));
			const user = renderEditor();

			await waitFor(() => {
				expect(screen.getByLabelText("Tone")).toHaveValue(MOCK_TONE);
			});

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				const btn = screen.getByRole("button", { name: /saving/i });
				expect(btn).toBeDisabled();
			});
		});

		it("re-enables save button after failed submission", async () => {
			mockApiGetWithProfile();
			mocks.mockApiPatch.mockRejectedValueOnce(new Error("fail"));
			const user = renderEditor();

			await waitFor(() => {
				expect(screen.getByLabelText("Tone")).toHaveValue(MOCK_TONE);
			});

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
		it("Back to Profile link has href /persona", async () => {
			mockApiGetWithProfile();
			renderEditor();

			await waitFor(() => {
				const link = screen.getByRole("link", {
					name: /back to profile/i,
				});
				expect(link).toHaveAttribute("href", "/persona");
			});
		});
	});
});
