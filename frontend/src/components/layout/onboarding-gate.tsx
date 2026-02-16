"use client";

/**
 * Entry gate that redirects unonboarded users to /onboarding.
 *
 * REQ-012 §3.3: All non-onboarding routes redirect to /onboarding
 * until persona exists and onboarding_complete = true.
 */

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { usePersonaStatus } from "@/hooks/use-persona-status";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function Spinner({ label }: Readonly<{ label: string }>) {
	return (
		<output className="flex h-full items-center justify-center">
			<span className="border-primary h-8 w-8 animate-spin rounded-full border-4 border-t-transparent" />
			<span className="sr-only">{label}</span>
		</output>
	);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function OnboardingGate({
	children,
}: Readonly<{ children: ReactNode }>) {
	const personaStatus = usePersonaStatus();
	const router = useRouter();

	useEffect(() => {
		if (personaStatus.status === "needs-onboarding") {
			router.replace("/onboarding");
		}
	}, [personaStatus.status, router]);

	if (personaStatus.status === "loading") {
		return <Spinner label="Loading..." />;
	}

	if (personaStatus.status === "error") {
		return (
			<div role="alert" className="flex h-full items-center justify-center p-4">
				<div className="text-center">
					<p className="text-destructive font-medium">
						Unable to load application
					</p>
					<p className="text-muted-foreground mt-1 text-sm">
						Please try refreshing the page.
					</p>
				</div>
			</div>
		);
	}

	if (personaStatus.status === "needs-onboarding") {
		return <Spinner label="Redirecting..." />;
	}

	return <>{children}</>;
}
