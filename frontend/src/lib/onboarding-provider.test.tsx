/**
 * Tests for the OnboardingProvider state management.
 *
 * REQ-019 §7: 11-step wizard with checkpoint/resume behavior.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ApiListResponse } from "@/types/api";
import type { Persona } from "@/types/persona";

import {
	CHECKPOINT_TTL_MS,
	OnboardingProvider,
	useOnboarding,
} from "./onboarding-provider";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
	mockApiGet: vi.fn(),
	mockApiPatch: vi.fn(),
	mockApiPost: vi.fn(),
}));

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPatch: mocks.mockApiPatch,
	apiPost: mocks.mockApiPost,
}));

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const ALTERNATE_PERSONA_ID = "00000000-0000-4000-a000-000000000002";
const PERSONA_PATCH_URL = `/personas/${DEFAULT_PERSONA_ID}`;
const BASIC_INFO_CHECKPOINT = { onboarding_step: "basic-info" };
const RESUME_UPLOAD_CHECKPOINT = { onboarding_step: "resume-upload" };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makePersona(overrides: Partial<Persona> = {}): Persona {
	return {
		id: DEFAULT_PERSONA_ID,
		user_id: "user-1",
		full_name: "Test User",
		email: "test@example.com",
		phone: "",
		home_city: "",
		home_state: "",
		home_country: "",
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
		polling_frequency: "Daily",
		onboarding_complete: false,
		onboarding_step: null,
		created_at: new Date().toISOString(),
		updated_at: new Date().toISOString(),
		...overrides,
	};
}

function makeListResponse(personas: Persona[] = []): ApiListResponse<Persona> {
	return {
		data: personas,
		meta: {
			total: personas.length,
			page: 1,
			per_page: 20,
			total_pages: Math.max(1, Math.ceil(personas.length / 20)),
		},
	};
}

function createWrapper(): ({
	children,
}: {
	children: ReactNode;
}) => React.JSX.Element {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	return function Wrapper({ children }: { children: ReactNode }) {
		return (
			<QueryClientProvider client={queryClient}>
				<OnboardingProvider>{children}</OnboardingProvider>
			</QueryClientProvider>
		);
	};
}

function renderUseOnboarding() {
	return renderHook(() => useOnboarding(), { wrapper: createWrapper() });
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
	mocks.mockApiPatch.mockResolvedValue({});
	mocks.mockApiPost.mockResolvedValue({});
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useOnboarding", () => {
	it("throws when used outside OnboardingProvider", () => {
		const queryClient = new QueryClient();
		expect(() =>
			renderHook(() => useOnboarding(), {
				wrapper: ({ children }: { children: ReactNode }) => (
					<QueryClientProvider client={queryClient}>
						{children}
					</QueryClientProvider>
				),
			}),
		).toThrow("useOnboarding must be used within an OnboardingProvider");
	});
});

describe("OnboardingProvider", () => {
	// -----------------------------------------------------------------------
	// Initialization
	// -----------------------------------------------------------------------

	describe("initialization", () => {
		it("starts in loading state", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
			const { result } = renderUseOnboarding();
			expect(result.current.isLoadingCheckpoint).toBe(true);
		});

		it("starts at step 1 when no persona exists", async () => {
			mocks.mockApiGet.mockResolvedValue(makeListResponse([]));
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			expect(result.current.currentStep).toBe(1);
			expect(result.current.personaId).toBeNull();
			expect(result.current.resumePrompt).toBeNull();
		});

		it("starts at step 1 when persona has no onboarding_step", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makeListResponse([makePersona({ onboarding_step: null })]),
			);
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			expect(result.current.currentStep).toBe(1);
			expect(result.current.personaId).toBe(DEFAULT_PERSONA_ID);
			expect(result.current.resumePrompt).toBeNull();
		});

		it("resumes at saved step when onboarding_step is set", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makeListResponse([
					makePersona({
						onboarding_step: "skills",
						updated_at: new Date().toISOString(),
					}),
				]),
			);
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			expect(result.current.currentStep).toBe(5);
			expect(result.current.stepName).toBe("Skills");
		});

		it("shows welcome-back prompt when resuming within 24h", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makeListResponse([
					makePersona({
						onboarding_step: "work-history",
						updated_at: new Date().toISOString(),
					}),
				]),
			);
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			expect(result.current.resumePrompt).toBe("welcome-back");
		});

		it("shows expired prompt when checkpoint is older than 24h", async () => {
			const oldDate = new Date(Date.now() - CHECKPOINT_TTL_MS - 1000);
			mocks.mockApiGet.mockResolvedValue(
				makeListResponse([
					makePersona({
						onboarding_step: "education",
						updated_at: oldDate.toISOString(),
					}),
				]),
			);
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			expect(result.current.resumePrompt).toBe("expired");
			expect(result.current.currentStep).toBe(4);
		});

		it("defaults to step 1 for unknown onboarding_step key", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makeListResponse([
					makePersona({
						onboarding_step: "unknown-step",
						updated_at: new Date().toISOString(),
					}),
				]),
			);
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			expect(result.current.currentStep).toBe(1);
		});
	});

	// -----------------------------------------------------------------------
	// Navigation
	// -----------------------------------------------------------------------

	describe("navigation", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(
				makeListResponse([makePersona({ onboarding_step: null })]),
			);
		});

		it("next() advances to the next step", async () => {
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			expect(result.current.currentStep).toBe(1);

			act(() => {
				result.current.next();
			});

			expect(result.current.currentStep).toBe(2);
		});

		it("next() saves checkpoint to server", async () => {
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			act(() => {
				result.current.next();
			});

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					PERSONA_PATCH_URL,
					BASIC_INFO_CHECKPOINT,
				);
			});
		});

		it("next() is a no-op at the last step", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makeListResponse([
					makePersona({
						onboarding_step: "review",
						updated_at: new Date().toISOString(),
					}),
				]),
			);
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.currentStep).toBe(11);
			});

			act(() => {
				result.current.next();
			});

			expect(result.current.currentStep).toBe(11);
		});

		it("back() goes to the previous step", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makeListResponse([
					makePersona({
						onboarding_step: "work-history",
						updated_at: new Date().toISOString(),
					}),
				]),
			);
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.currentStep).toBe(3);
			});

			act(() => {
				result.current.back();
			});

			expect(result.current.currentStep).toBe(2);
		});

		it("back() is a no-op at step 1", async () => {
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			act(() => {
				result.current.back();
			});

			expect(result.current.currentStep).toBe(1);
		});

		it("back() saves checkpoint to server", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makeListResponse([
					makePersona({
						onboarding_step: "work-history",
						updated_at: new Date().toISOString(),
					}),
				]),
			);
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.currentStep).toBe(3);
			});

			act(() => {
				result.current.back();
			});

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					PERSONA_PATCH_URL,
					BASIC_INFO_CHECKPOINT,
				);
			});
		});

		it("skip() advances to the next step", async () => {
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			act(() => {
				result.current.skip();
			});

			expect(result.current.currentStep).toBe(2);
		});

		it("skip() saves checkpoint to server", async () => {
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			act(() => {
				result.current.skip();
			});

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					PERSONA_PATCH_URL,
					BASIC_INFO_CHECKPOINT,
				);
			});
		});

		it("goToStep() navigates to a specific step", async () => {
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			act(() => {
				result.current.goToStep(7);
			});

			expect(result.current.currentStep).toBe(7);
		});

		it("goToStep() clamps to valid range", async () => {
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			act(() => {
				result.current.goToStep(99);
			});

			expect(result.current.currentStep).toBe(11);

			act(() => {
				result.current.goToStep(-5);
			});

			expect(result.current.currentStep).toBe(1);
		});

		it("restart() resets to step 1", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makeListResponse([
					makePersona({
						onboarding_step: "skills",
						updated_at: new Date().toISOString(),
					}),
				]),
			);
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.currentStep).toBe(5);
			});

			act(() => {
				result.current.restart();
			});

			expect(result.current.currentStep).toBe(1);
		});

		it("restart() saves checkpoint to server", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makeListResponse([
					makePersona({
						onboarding_step: "skills",
						updated_at: new Date().toISOString(),
					}),
				]),
			);
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.currentStep).toBe(5);
			});

			act(() => {
				result.current.restart();
			});

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					PERSONA_PATCH_URL,
					RESUME_UPLOAD_CHECKPOINT,
				);
			});
		});

		it("dismissResumePrompt() clears the prompt", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makeListResponse([
					makePersona({
						onboarding_step: "skills",
						updated_at: new Date().toISOString(),
					}),
				]),
			);
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.resumePrompt).toBe("welcome-back");
			});

			act(() => {
				result.current.dismissResumePrompt();
			});

			expect(result.current.resumePrompt).toBeNull();
		});
	});

	// -----------------------------------------------------------------------
	// Persona tracking
	// -----------------------------------------------------------------------

	describe("persona tracking", () => {
		it("exposes personaId from fetched persona", async () => {
			mocks.mockApiGet.mockResolvedValue(makeListResponse([makePersona()]));
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			expect(result.current.personaId).toBe(DEFAULT_PERSONA_ID);
		});

		it("setPersonaId() updates the persona ID", async () => {
			mocks.mockApiGet.mockResolvedValue(makeListResponse([]));
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			expect(result.current.personaId).toBeNull();

			act(() => {
				result.current.setPersonaId(ALTERNATE_PERSONA_ID);
			});

			expect(result.current.personaId).toBe(ALTERNATE_PERSONA_ID);
		});

		it("setPersonaId() rejects non-UUID values", async () => {
			mocks.mockApiGet.mockResolvedValue(makeListResponse([]));
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			act(() => {
				result.current.setPersonaId("not-a-uuid");
			});

			expect(result.current.personaId).toBeNull();
		});

		it("does not save checkpoint when no persona exists", async () => {
			mocks.mockApiGet.mockResolvedValue(makeListResponse([]));
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			act(() => {
				result.current.next();
			});

			expect(result.current.currentStep).toBe(2);

			// Give time for any async save to fire
			await act(async () => {
				await new Promise((r) => setTimeout(r, 50));
			});

			expect(mocks.mockApiPatch).not.toHaveBeenCalled();
		});

		it("saves checkpoint after setPersonaId is called", async () => {
			mocks.mockApiGet.mockResolvedValue(makeListResponse([]));
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			act(() => {
				result.current.setPersonaId(ALTERNATE_PERSONA_ID);
			});

			act(() => {
				result.current.next();
			});

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${ALTERNATE_PERSONA_ID}`,
					BASIC_INFO_CHECKPOINT,
				);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Derived values
	// -----------------------------------------------------------------------

	describe("derived values", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(makeListResponse([makePersona()]));
		});

		it("totalSteps is always 11", async () => {
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			expect(result.current.totalSteps).toBe(11);
		});

		it("stepName matches current step definition", async () => {
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			expect(result.current.stepName).toBe("Resume Upload");

			act(() => {
				result.current.next();
			});

			expect(result.current.stepName).toBe("Basic Info");
		});

		it("resumeParseData is initially null", async () => {
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			expect(result.current.resumeParseData).toBeNull();
		});

		it("setResumeParseData stores parsed resume data", async () => {
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			const mockParseData = {
				basic_info: { full_name: "Test User", email: "test@example.com" },
				work_history: [{ job_title: "Engineer", company_name: "Acme" }],
				education: [],
				skills: [{ name: "TypeScript", type: "Hard", proficiency: "Expert" }],
				certifications: [],
				voice_suggestions: {
					writing_style: "technical",
					vocabulary_level: "technical",
					personality_markers: "analytical",
					confidence: 0.85,
				},
				raw_text: "Resume text content",
			};

			act(() => {
				result.current.setResumeParseData(mockParseData);
			});

			expect(result.current.resumeParseData).toEqual(mockParseData);
		});

		it("isStepSkippable reflects current step", async () => {
			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			// Step 1 (Resume Upload) is skippable
			expect(result.current.isStepSkippable).toBe(true);

			act(() => {
				result.current.next();
			});

			// Step 2 (Basic Info) is not skippable
			expect(result.current.isStepSkippable).toBe(false);
		});
	});

	// -----------------------------------------------------------------------
	// Error handling
	// -----------------------------------------------------------------------

	describe("error handling", () => {
		it("handles checkpoint save failure silently", async () => {
			mocks.mockApiGet.mockResolvedValue(makeListResponse([makePersona()]));
			mocks.mockApiPatch.mockRejectedValue(new Error("Network error"));

			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			// Should not throw
			act(() => {
				result.current.next();
			});

			expect(result.current.currentStep).toBe(2);

			await waitFor(() => {
				expect(result.current.isSavingCheckpoint).toBe(false);
			});
		});

		it("sets isSavingCheckpoint during save", async () => {
			let resolvePatch!: () => void;
			mocks.mockApiGet.mockResolvedValue(makeListResponse([makePersona()]));
			mocks.mockApiPatch.mockReturnValue(
				new Promise<void>((resolve) => {
					resolvePatch = resolve;
				}),
			);

			const { result } = renderUseOnboarding();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			act(() => {
				result.current.next();
			});

			await waitFor(() => {
				expect(result.current.isSavingCheckpoint).toBe(true);
			});

			await act(async () => {
				resolvePatch();
			});

			await waitFor(() => {
				expect(result.current.isSavingCheckpoint).toBe(false);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Completion
	// -----------------------------------------------------------------------

	describe("completion", () => {
		let queryClient: QueryClient;

		function createCompletionWrapper(): ({
			children,
		}: {
			children: ReactNode;
		}) => React.JSX.Element {
			queryClient = new QueryClient({
				defaultOptions: { queries: { retry: false } },
			});
			return function Wrapper({ children }: { children: ReactNode }) {
				return (
					<QueryClientProvider client={queryClient}>
						<OnboardingProvider>{children}</OnboardingProvider>
					</QueryClientProvider>
				);
			};
		}

		function renderForCompletion() {
			return renderHook(() => useOnboarding(), {
				wrapper: createCompletionWrapper(),
			});
		}

		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(makeListResponse([makePersona()]));
			mocks.mockApiPatch.mockResolvedValue({});
			mocks.mockApiPost.mockResolvedValue({});
		});

		it("PATCHes persona with onboarding_complete: true", async () => {
			const { result } = renderForCompletion();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			await act(async () => {
				await result.current.completeOnboarding();
			});

			expect(mocks.mockApiPatch).toHaveBeenCalledWith(PERSONA_PATCH_URL, {
				onboarding_complete: true,
			});
		});

		it("POSTs to /refresh to trigger Scouter", async () => {
			const { result } = renderForCompletion();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			await act(async () => {
				await result.current.completeOnboarding();
			});

			expect(mocks.mockApiPost).toHaveBeenCalledWith(
				`/personas/${DEFAULT_PERSONA_ID}/refresh`,
			);
		});

		it("invalidates personas query cache", async () => {
			const { result } = renderForCompletion();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			const spy = vi.spyOn(queryClient, "invalidateQueries");

			await act(async () => {
				await result.current.completeOnboarding();
			});

			expect(spy).toHaveBeenCalledWith({
				queryKey: ["personas"],
			});
		});

		it("sets isCompleting to true during execution", async () => {
			let resolvePatch!: () => void;
			mocks.mockApiPatch.mockReturnValue(
				new Promise<void>((resolve) => {
					resolvePatch = resolve;
				}),
			);

			const { result } = renderForCompletion();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			expect(result.current.isCompleting).toBe(false);

			let completionPromise: Promise<void>;
			act(() => {
				completionPromise = result.current.completeOnboarding();
			});

			await waitFor(() => {
				expect(result.current.isCompleting).toBe(true);
			});

			await act(async () => {
				resolvePatch();
				await completionPromise;
			});

			expect(result.current.isCompleting).toBe(false);
		});

		it("resets isCompleting on PATCH failure", async () => {
			mocks.mockApiPatch.mockRejectedValue(new Error("Network error"));

			const { result } = renderForCompletion();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			await expect(
				act(async () => {
					await result.current.completeOnboarding();
				}),
			).rejects.toThrow("Network error");

			expect(result.current.isCompleting).toBe(false);
		});

		it("throws when no persona ID exists", async () => {
			mocks.mockApiGet.mockResolvedValue(makeListResponse([]));

			const { result } = renderForCompletion();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			await expect(
				act(async () => {
					await result.current.completeOnboarding();
				}),
			).rejects.toThrow("Cannot complete onboarding without a valid persona");
		});

		it("succeeds even if refresh POST fails", async () => {
			mocks.mockApiPost.mockRejectedValue(new Error("Refresh failed"));

			const { result } = renderForCompletion();

			await waitFor(() => {
				expect(result.current.isLoadingCheckpoint).toBe(false);
			});

			// Should not throw
			await act(async () => {
				await result.current.completeOnboarding();
			});

			// PATCH still happened
			expect(mocks.mockApiPatch).toHaveBeenCalledWith(PERSONA_PATCH_URL, {
				onboarding_complete: true,
			});
		});
	});
});
