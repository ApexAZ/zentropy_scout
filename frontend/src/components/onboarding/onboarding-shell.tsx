"use client";

/**
 * Onboarding shell layout component.
 *
 * REQ-012 §6.2: Full-screen layout (no main navigation bar) with
 * logo, step counter, horizontal progress bar, content area,
 * and Back/Skip/Next navigation buttons.
 */

import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface OnboardingShellProps {
	/** Current step number (1-based). */
	currentStep: number;
	/** Total number of steps. */
	totalSteps: number;
	/** Human-readable name of the current step (shown on hover). */
	stepName: string;
	/** Callback when Next is clicked. Always required. */
	onNext: () => void;
	/** Callback when Back is clicked. If omitted, Back button is hidden. */
	onBack?: () => void;
	/** Callback when Skip is clicked. If omitted, Skip button is hidden. */
	onSkip?: () => void;
	/** Whether the Next button should be disabled (e.g., form invalid). */
	isNextDisabled?: boolean;
	/** Whether the Next button should show a loading spinner. */
	isNextLoading?: boolean;
	/** Step content (form or chat-style conversation). */
	children: ReactNode;
	/** Additional CSS classes for the root element. */
	className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Full-screen onboarding layout with progress tracking and navigation.
 *
 * Renders a minimal chrome layout: header with logo and progress,
 * scrollable content area, and footer with navigation buttons.
 *
 * @param props - See OnboardingShellProps.
 */
export function OnboardingShell({
	currentStep,
	totalSteps,
	stepName,
	onNext,
	onBack,
	onSkip,
	isNextDisabled = false,
	isNextLoading = false,
	children,
	className,
}: OnboardingShellProps) {
	const safeTotal = Math.max(totalSteps, 1);
	const safeStep = Math.min(Math.max(currentStep, 0), safeTotal);
	const progressPercent = Math.round((safeStep / safeTotal) * 100);

	return (
		<div
			data-slot="onboarding-shell"
			className={cn("bg-background flex min-h-screen flex-col", className)}
		>
			{/* Header: Logo + Step counter + Progress bar */}
			<header
				data-slot="onboarding-header"
				className="border-b px-4 py-3 sm:px-6"
			>
				<div className="mx-auto flex max-w-3xl items-center justify-between">
					<span className="text-lg font-semibold">Zentropy Scout</span>
					<span
						className="text-muted-foreground text-sm"
						title={stepName.slice(0, 100)}
					>
						Step {currentStep} of {totalSteps}
					</span>
				</div>
				<div className="mx-auto mt-2 max-w-3xl">
					<Progress value={progressPercent} />
				</div>
			</header>

			{/* Content area */}
			<main
				data-slot="onboarding-content"
				className="mx-auto flex w-full max-w-3xl flex-1 flex-col overflow-auto px-4 py-6 sm:px-6"
			>
				{children}
			</main>

			{/* Footer: Navigation buttons */}
			<nav
				data-slot="onboarding-nav"
				aria-label="Onboarding navigation"
				className="border-t px-4 py-3 sm:px-6"
			>
				<div className="mx-auto flex max-w-3xl items-center justify-between">
					<div>
						{onBack && (
							<Button variant="ghost" onClick={onBack} type="button">
								Back
							</Button>
						)}
					</div>
					<div className="flex gap-2">
						{onSkip && (
							<Button variant="outline" onClick={onSkip} type="button">
								Skip
							</Button>
						)}
						<Button
							onClick={onNext}
							disabled={isNextDisabled || isNextLoading}
							type="button"
						>
							{isNextLoading && <Loader2 className="animate-spin" />}
							Next
						</Button>
					</div>
				</div>
			</nav>
		</div>
	);
}
