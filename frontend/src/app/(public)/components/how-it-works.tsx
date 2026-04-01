/**
 * @fileoverview Landing page "How It Works" 3-step walkthrough section.
 *
 * Layer: component
 * Feature: shared
 *
 * REQ-024 §4.4: 3-step walkthrough with Lucide icons.
 * Horizontal row on desktop, vertical stack on mobile.
 *
 * Coordinates with:
 * - (no upstream lib imports — self-contained presentational component)
 *
 * Called by / Used by:
 * - app/(public)/page.tsx: landing page composition
 */

import { Radar, Sparkles, UserPlus } from "lucide-react";
import type { LucideIcon } from "lucide-react";

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

interface Step {
	icon: LucideIcon;
	title: string;
	description: string;
}

const STEPS: Step[] = [
	{
		icon: UserPlus,
		title: "Build your persona",
		description:
			"Tell us about your skills, experience, and what you're looking for.",
	},
	{
		icon: Radar,
		title: "Scout finds matches",
		description: "AI analyzes job postings and ranks them by fit.",
	},
	{
		icon: Sparkles,
		title: "Generate & apply",
		description: "Get tailored resumes and cover letters for your top matches.",
	},
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function HowItWorks() {
	return (
		<section
			data-testid="how-it-works"
			aria-label="How it works"
			className="px-6 py-16 lg:px-16"
		>
			<h2 className="text-foreground mb-10 text-center text-2xl font-bold">
				How It Works
			</h2>
			<div className="flex flex-col items-center gap-8 lg:flex-row lg:justify-center lg:gap-16">
				{STEPS.map((step, index) => {
					const Icon = step.icon;
					return (
						<div
							key={step.title}
							data-testid={`how-it-works-step-${index}`}
							className="flex max-w-xs flex-col items-center text-center"
						>
							<div className="bg-primary/10 mb-4 flex h-14 w-14 items-center justify-center rounded-full">
								<Icon className="text-primary h-7 w-7" />
							</div>
							<span className="text-muted-foreground mb-2 text-sm font-medium">
								Step {index + 1}
							</span>
							<h3 className="text-foreground mb-1 font-semibold">
								{step.title}
							</h3>
							<p className="text-muted-foreground text-sm">
								{step.description}
							</p>
						</div>
					);
				})}
			</div>
		</section>
	);
}
