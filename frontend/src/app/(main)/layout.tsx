"use client";

/**
 * Main route group layout.
 *
 * REQ-012 §3.2: Protected routes use AppShell (top nav + chat sidebar).
 * REQ-012 §3.3: OnboardingGate checks persona status before rendering.
 */

import type { ReactNode } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { OnboardingGate } from "@/components/layout/onboarding-gate";

export default function MainLayout({ children }: { children: ReactNode }) {
	return (
		<OnboardingGate>
			<AppShell>{children}</AppShell>
		</OnboardingGate>
	);
}
