/**
 * Hook to check persona onboarding status.
 *
 * REQ-012 §3.3: Persona check on first load determines routing.
 * - No persona exists → needs onboarding
 * - Persona exists, onboarding_complete = false → needs onboarding
 * - Persona exists, onboarding_complete = true → onboarded
 */

import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { ApiListResponse } from "@/types/api";
import type { Persona } from "@/types/persona";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type PersonaStatus =
	| { status: "loading" }
	| { status: "error"; error: Error }
	| { status: "needs-onboarding" }
	| { status: "onboarded"; persona: Persona };

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function usePersonaStatus(): PersonaStatus {
	const { data, isLoading, error } = useQuery({
		queryKey: queryKeys.personas,
		queryFn: () => apiGet<ApiListResponse<Persona>>("/personas"),
	});

	if (isLoading) return { status: "loading" };

	if (error) {
		return {
			status: "error",
			error: error instanceof Error ? error : new Error(String(error)),
		};
	}

	const persona = data?.data[0];

	if (!persona || !persona.onboarding_complete) {
		return { status: "needs-onboarding" };
	}

	return { status: "onboarded", persona };
}
