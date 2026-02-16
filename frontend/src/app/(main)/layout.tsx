"use client";

/**
 * Main route group layout.
 *
 * REQ-012 §3.2: Protected routes use AppShell (top nav + chat sidebar).
 * REQ-012 §3.3: OnboardingGate checks persona status before rendering.
 * REQ-012 §7.6: Nav badge shows pending PersonaChangeFlags count.
 */

import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { OnboardingGate } from "@/components/layout/onboarding-gate";
import { apiGet } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { ApiListResponse } from "@/types/api";
import type { PersonaChangeFlag } from "@/types/persona";

// ---------------------------------------------------------------------------
// Private wrapper — fetches pending flags count for the nav badge.
// Mounted inside OnboardingGate so persona API calls are safe.
// ---------------------------------------------------------------------------

function MainLayoutContent({ children }: Readonly<{ children: ReactNode }>) {
	const { data } = useQuery({
		queryKey: queryKeys.changeFlags,
		queryFn: () =>
			apiGet<ApiListResponse<PersonaChangeFlag>>("/persona-change-flags", {
				status: "Pending",
			}),
	});

	const pendingFlagsCount = data?.data.length ?? 0;

	return <AppShell pendingFlagsCount={pendingFlagsCount}>{children}</AppShell>;
}

// ---------------------------------------------------------------------------
// Layout
// ---------------------------------------------------------------------------

export default function MainLayout({
	children,
}: Readonly<{ children: ReactNode }>) {
	return (
		<OnboardingGate>
			<MainLayoutContent>{children}</MainLayoutContent>
		</OnboardingGate>
	);
}
