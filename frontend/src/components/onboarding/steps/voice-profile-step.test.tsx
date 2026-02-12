/**
 * Tests for the voice profile step component (onboarding Step 10).
 *
 * REQ-012 §6.3.10: Agent-derived voice profile review card with
 * per-field inline editing. Two modes: "review" (read-only card with
 * "Looks good!" and "Let me edit") and "edit" (form with text inputs
 * and tag inputs). Falls back to edit mode when no profile exists.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { VoiceProfileStep } from "./voice-profile-step";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const VOICE_PROFILE_ENDPOINT = `/personas/${DEFAULT_PERSONA_ID}/voice-profile`;
const GENERIC_ERROR_TEXT = "Failed to save. Please try again.";

const MOCK_VOICE_PROFILE = {
	id: "vp-001",
	persona_id: DEFAULT_PERSONA_ID,
	tone: "Direct, confident",
	sentence_style: "Short sentences, active voice",
	vocabulary_level: "Technical when relevant, plain otherwise",
	personality_markers: "Occasional dry humor",
	sample_phrases: ["I led...", "The result was..."],
	things_to_avoid: ["Passionate", "Synergy"],
	writing_sample_text: null,
	created_at: "2026-01-01T00:00:00Z",
	updated_at: "2026-01-01T00:00:00Z",
};

const MOCK_PROFILE_RESPONSE = { data: MOCK_VOICE_PROFILE };

const MOCK_EMPTY_PROFILE_RESPONSE = { data: {} };

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

/** Render step and wait for loading to finish. */
async function renderAndWait() {
	const user = userEvent.setup();
	render(<VoiceProfileStep />);
	await waitFor(() => {
		expect(
			screen.queryByTestId("loading-voice-profile"),
		).not.toBeInTheDocument();
	});
	return user;
}

/** Fill required voice profile fields with defaults or overrides. */
async function fillRequiredFields(
	user: ReturnType<typeof userEvent.setup>,
	overrides?: Partial<{
		tone: string;
		style: string;
		vocabulary: string;
	}>,
) {
	const values = {
		tone: "Direct",
		style: "Short",
		vocabulary: "Plain",
		...overrides,
	};
	await user.type(screen.getByLabelText(/^tone$/i), values.tone);
	await user.type(screen.getByLabelText(/^style$/i), values.style);
	await user.type(screen.getByLabelText(/^vocabulary$/i), values.vocabulary);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("VoiceProfileStep", () => {
	beforeEach(() => {
		mocks.mockApiGet.mockReset();
		mocks.mockApiPatch.mockReset();
		mocks.mockNext.mockReset();
		mocks.mockBack.mockReset();
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	// -----------------------------------------------------------------------
	// Rendering & loading
	// -----------------------------------------------------------------------

	describe("rendering", () => {
		it("shows loading spinner while fetching voice profile", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
			render(<VoiceProfileStep />);

			expect(screen.getByTestId("loading-voice-profile")).toBeInTheDocument();
		});

		it("renders title after loading", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_PROFILE_RESPONSE);
			await renderAndWait();

			expect(
				screen.getByRole("heading", { name: /voice profile/i }),
			).toBeInTheDocument();
		});

		it("fetches voice profile from correct endpoint", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_PROFILE_RESPONSE);
			await renderAndWait();

			expect(mocks.mockApiGet).toHaveBeenCalledWith(VOICE_PROFILE_ENDPOINT);
		});
	});

	// -----------------------------------------------------------------------
	// Review mode (profile exists)
	// -----------------------------------------------------------------------

	describe("review mode", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_PROFILE_RESPONSE);
		});

		it("shows review card when voice profile has data", async () => {
			await renderAndWait();

			expect(screen.getByTestId("voice-profile-review")).toBeInTheDocument();
		});

		it("displays all voice profile fields", async () => {
			await renderAndWait();

			expect(screen.getByText("Direct, confident")).toBeInTheDocument();
			expect(
				screen.getByText("Short sentences, active voice"),
			).toBeInTheDocument();
			expect(
				screen.getByText("Technical when relevant, plain otherwise"),
			).toBeInTheDocument();
			expect(screen.getByText("Occasional dry humor")).toBeInTheDocument();
		});

		it("displays sample phrases as chips", async () => {
			await renderAndWait();

			expect(screen.getByText("I led...")).toBeInTheDocument();
			expect(screen.getByText("The result was...")).toBeInTheDocument();
		});

		it("displays things to avoid as chips", async () => {
			await renderAndWait();

			expect(screen.getByText("Passionate")).toBeInTheDocument();
			expect(screen.getByText("Synergy")).toBeInTheDocument();
		});

		it("shows field labels in review card", async () => {
			await renderAndWait();

			expect(screen.getByText("Tone")).toBeInTheDocument();
			expect(screen.getByText("Style")).toBeInTheDocument();
			expect(screen.getByText("Vocabulary")).toBeInTheDocument();
			expect(screen.getByText("Personality")).toBeInTheDocument();
			expect(screen.getByText("Sample Phrases")).toBeInTheDocument();
			expect(screen.getByText("Avoid")).toBeInTheDocument();
		});

		it("shows 'Looks good!' and 'Let me edit' buttons", async () => {
			await renderAndWait();

			expect(
				screen.getByRole("button", { name: /looks good/i }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: /let me edit/i }),
			).toBeInTheDocument();
		});

		it("calls next() when 'Looks good!' is clicked", async () => {
			const user = await renderAndWait();

			await user.click(screen.getByRole("button", { name: /looks good/i }));

			expect(mocks.mockNext).toHaveBeenCalledTimes(1);
		});

		it("switches to edit mode when 'Let me edit' is clicked", async () => {
			const user = await renderAndWait();

			await user.click(screen.getByRole("button", { name: /let me edit/i }));

			expect(
				screen.queryByTestId("voice-profile-review"),
			).not.toBeInTheDocument();
			expect(screen.getByTestId("voice-profile-form")).toBeInTheDocument();
		});

		it("pre-fills form fields when switching to edit mode", async () => {
			const user = await renderAndWait();

			await user.click(screen.getByRole("button", { name: /let me edit/i }));

			expect(screen.getByDisplayValue("Direct, confident")).toBeInTheDocument();
			expect(
				screen.getByDisplayValue("Short sentences, active voice"),
			).toBeInTheDocument();
			expect(
				screen.getByDisplayValue("Technical when relevant, plain otherwise"),
			).toBeInTheDocument();
			expect(
				screen.getByDisplayValue("Occasional dry humor"),
			).toBeInTheDocument();
		});

		it("hides personality row when personality_markers is null", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: { ...MOCK_VOICE_PROFILE, personality_markers: null },
			});
			await renderAndWait();

			// Personality label should not appear in review card
			const review = screen.getByTestId("voice-profile-review");
			expect(
				review.querySelector('[data-field="personality"]'),
			).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Edit mode (no profile or user clicked "Let me edit")
	// -----------------------------------------------------------------------

	describe("edit mode", () => {
		it("starts in edit mode when no profile exists", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_PROFILE_RESPONSE);
			await renderAndWait();

			expect(screen.getByTestId("voice-profile-form")).toBeInTheDocument();
			expect(
				screen.queryByTestId("voice-profile-review"),
			).not.toBeInTheDocument();
		});

		it("renders all form fields", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_PROFILE_RESPONSE);
			await renderAndWait();

			expect(screen.getByLabelText(/^tone$/i)).toBeInTheDocument();
			expect(screen.getByLabelText(/^style$/i)).toBeInTheDocument();
			expect(screen.getByLabelText(/^vocabulary$/i)).toBeInTheDocument();
			expect(screen.getByLabelText(/^personality$/i)).toBeInTheDocument();
			expect(screen.getByText("Sample Phrases")).toBeInTheDocument();
			expect(screen.getByText("Things to Avoid")).toBeInTheDocument();
		});

		it("renders optional writing sample textarea", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_PROFILE_RESPONSE);
			await renderAndWait();

			expect(screen.getByLabelText(/writing sample/i)).toBeInTheDocument();
		});

		it("PATCHes voice profile and calls next() on save", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_PROFILE_RESPONSE);
			mocks.mockApiPatch.mockResolvedValueOnce({ data: {} });

			const user = await renderAndWait();
			await fillRequiredFields(user, {
				tone: "Warm and friendly",
				style: "Conversational",
				vocabulary: "Plain English",
			});

			await user.click(screen.getByTestId("submit-button"));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					VOICE_PROFILE_ENDPOINT,
					expect.objectContaining({
						tone: "Warm and friendly",
						sentence_style: "Conversational",
						vocabulary_level: "Plain English",
					}),
				);
			});

			expect(mocks.mockNext).toHaveBeenCalledTimes(1);
		});

		it("shows error on failed PATCH", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_PROFILE_RESPONSE);
			mocks.mockApiPatch.mockRejectedValueOnce(new Error("Network error"));

			const user = await renderAndWait();
			await fillRequiredFields(user);

			await user.click(screen.getByTestId("submit-button"));

			await waitFor(() => {
				expect(screen.getByText(GENERIC_ERROR_TEXT)).toBeInTheDocument();
			});

			expect(mocks.mockNext).not.toHaveBeenCalled();
		});

		it("shows friendly error for validation failure", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_PROFILE_RESPONSE);
			mocks.mockApiPatch.mockRejectedValueOnce(
				new mocks.MockApiError("VALIDATION_ERROR", "Invalid data", 422),
			);

			const user = await renderAndWait();
			await fillRequiredFields(user);

			await user.click(screen.getByTestId("submit-button"));

			await waitFor(() => {
				expect(screen.getByTestId("submit-error")).toHaveTextContent(
					"Please check your input and try again.",
				);
			});
		});

		it("disables submit button and shows Saving text while submitting", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_PROFILE_RESPONSE);
			mocks.mockApiPatch.mockReturnValue(new Promise(() => {}));

			const user = await renderAndWait();
			await fillRequiredFields(user);

			await user.click(screen.getByTestId("submit-button"));

			await waitFor(() => {
				const btn = screen.getByTestId("submit-button");
				expect(btn).toBeDisabled();
				expect(btn).toHaveTextContent("Saving...");
			});
		});

		it("re-enables submit button after failed submission", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_PROFILE_RESPONSE);
			mocks.mockApiPatch.mockRejectedValueOnce(new Error("fail"));

			const user = await renderAndWait();
			await fillRequiredFields(user);

			await user.click(screen.getByTestId("submit-button"));

			await waitFor(() => {
				const btn = screen.getByTestId("submit-button");
				expect(btn).not.toBeDisabled();
				expect(btn).toHaveTextContent(/save/i);
			});
		});

		it("shows validation errors for empty required fields", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_PROFILE_RESPONSE);

			const user = await renderAndWait();
			await user.click(screen.getByTestId("submit-button"));

			await waitFor(() => {
				expect(
					screen.getAllByText(/is required/i).length,
				).toBeGreaterThanOrEqual(1);
			});

			expect(mocks.mockApiPatch).not.toHaveBeenCalled();
		});

		it("includes tag fields in PATCH body", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_PROFILE_RESPONSE);
			mocks.mockApiPatch.mockResolvedValueOnce({ data: {} });

			const user = await renderAndWait();
			await fillRequiredFields(user);

			// Add a sample phrase
			const phraseInput = screen.getByPlaceholderText(/e\.g\., I led/i);
			await user.type(phraseInput, "I built...{Enter}");

			// Add an avoid word
			const avoidInput = screen.getByPlaceholderText(/e\.g\., Passionate/i);
			await user.type(avoidInput, "Synergy{Enter}");

			await user.click(screen.getByTestId("submit-button"));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					VOICE_PROFILE_ENDPOINT,
					expect.objectContaining({
						sample_phrases: ["I built..."],
						things_to_avoid: ["Synergy"],
					}),
				);
			});
		});

		it("includes writing sample in PATCH body when provided", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_PROFILE_RESPONSE);
			mocks.mockApiPatch.mockResolvedValueOnce({ data: {} });

			const user = await renderAndWait();
			await fillRequiredFields(user);
			await user.type(
				screen.getByLabelText(/writing sample/i),
				"Here is some of my writing...",
			);

			await user.click(screen.getByTestId("submit-button"));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					VOICE_PROFILE_ENDPOINT,
					expect.objectContaining({
						writing_sample_text: "Here is some of my writing...",
					}),
				);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Navigation
	// -----------------------------------------------------------------------

	describe("navigation", () => {
		it("calls back() when Back is clicked in review mode", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_PROFILE_RESPONSE);
			const user = await renderAndWait();

			await user.click(screen.getByTestId("back-button"));

			expect(mocks.mockBack).toHaveBeenCalledTimes(1);
		});

		it("calls back() when Back is clicked in edit mode", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_PROFILE_RESPONSE);
			const user = await renderAndWait();

			await user.click(screen.getByTestId("back-button"));

			expect(mocks.mockBack).toHaveBeenCalledTimes(1);
		});

		it("does not render a Skip button", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_PROFILE_RESPONSE);
			await renderAndWait();

			expect(
				screen.queryByRole("button", { name: /skip/i }),
			).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Fetch failure
	// -----------------------------------------------------------------------

	describe("fetch failure", () => {
		it("falls back to edit mode when fetch fails", async () => {
			mocks.mockApiGet.mockRejectedValueOnce(new Error("Network error"));
			await renderAndWait();

			expect(screen.getByTestId("voice-profile-form")).toBeInTheDocument();
		});
	});
});
