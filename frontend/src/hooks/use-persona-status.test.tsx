/**
 * Tests for the usePersonaStatus hook.
 *
 * REQ-012 §3.3: Persona status check determines routing —
 * no persona or incomplete onboarding redirects to /onboarding.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ApiListResponse } from "@/types/api";
import type { Persona } from "@/types/persona";

import { usePersonaStatus } from "./use-persona-status";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	const mockApiGet = vi.fn();
	return { mockApiGet };
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createWrapper() {
	const queryClient = new QueryClient({
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

function makePersona(overrides: Partial<Persona> = {}): Persona {
	return {
		id: "test-persona-id",
		user_id: "test-user-id",
		full_name: "Test User",
		email: "test@example.com",
		phone: "555-0100",
		home_city: "Austin",
		home_state: "TX",
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
		minimum_fit_threshold: 60,
		auto_draft_threshold: 80,
		polling_frequency: "Daily",
		onboarding_complete: true,
		onboarding_step: null,
		created_at: "2026-01-01T00:00:00Z",
		updated_at: "2026-01-01T00:00:00Z",
		...overrides,
	};
}

function makeListResponse(personas: Persona[]): ApiListResponse<Persona> {
	return {
		data: personas,
		meta: {
			total: personas.length,
			page: 1,
			per_page: 20,
			total_pages: personas.length > 0 ? 1 : 0,
		},
	};
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("usePersonaStatus", () => {
	it("returns loading while query is fetching", () => {
		mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
		const { result } = renderHook(() => usePersonaStatus(), {
			wrapper: createWrapper(),
		});
		expect(result.current.status).toBe("loading");
	});

	it("returns needs-onboarding when persona list is empty", async () => {
		mocks.mockApiGet.mockResolvedValue(makeListResponse([]));

		const { result } = renderHook(() => usePersonaStatus(), {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(result.current.status).toBe("needs-onboarding");
		});
	});

	it("returns needs-onboarding when persona has onboarding_complete = false", async () => {
		const persona = makePersona({
			onboarding_complete: false,
			onboarding_step: "basic_info",
		});
		mocks.mockApiGet.mockResolvedValue(makeListResponse([persona]));

		const { result } = renderHook(() => usePersonaStatus(), {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(result.current.status).toBe("needs-onboarding");
		});
	});

	it("returns onboarded with persona when onboarding_complete = true", async () => {
		const persona = makePersona({ onboarding_complete: true });
		mocks.mockApiGet.mockResolvedValue(makeListResponse([persona]));

		const { result } = renderHook(() => usePersonaStatus(), {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(result.current.status).toBe("onboarded");
		});
		if (result.current.status === "onboarded") {
			expect(result.current.persona.id).toBe("test-persona-id");
		}
	});

	it("returns error when API call fails", async () => {
		mocks.mockApiGet.mockRejectedValue(new Error("Network error"));

		const { result } = renderHook(() => usePersonaStatus(), {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(result.current.status).toBe("error");
		});
		if (result.current.status === "error") {
			expect(result.current.error).toBeInstanceOf(Error);
		}
	});

	it("calls apiGet with /personas path", async () => {
		mocks.mockApiGet.mockResolvedValue(makeListResponse([]));

		renderHook(() => usePersonaStatus(), {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(mocks.mockApiGet).toHaveBeenCalledWith("/personas");
		});
	});
});
