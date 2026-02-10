/**
 * Onboarding page placeholder.
 *
 * REQ-012 §6: Full onboarding UI implemented in a later phase.
 * This placeholder exists so the onboarding gate redirect has a target.
 */

export default function OnboardingPage() {
	return (
		<main className="flex min-h-screen items-center justify-center">
			<div className="text-center">
				<h1 className="text-2xl font-semibold">Welcome to Zentropy Scout</h1>
				<p className="text-muted-foreground mt-2">
					Onboarding will be available here.
				</p>
			</div>
		</main>
	);
}
