/**
 * @fileoverview Landing page feature highlight cards.
 *
 * Layer: component
 * Feature: shared
 *
 * REQ-024 §4.3: 4 cards with Lucide icons, titles, and descriptions.
 * Responsive grid: 1 col mobile, 2 col tablet, 4 col desktop.
 *
 * Coordinates with:
 * - (no upstream lib imports — self-contained presentational component)
 *
 * Called by / Used by:
 * - app/(public)/page.tsx: landing page composition
 */

import { BarChart3, FileText, Search, UserCircle } from "lucide-react";
import type { LucideIcon } from "lucide-react";

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

interface Feature {
	icon: LucideIcon;
	title: string;
	description: string;
}

const FEATURES: Feature[] = [
	{
		icon: UserCircle,
		title: "Build Your Persona",
		description:
			"Create a comprehensive professional profile that AI uses to tailor everything to you.",
	},
	{
		icon: Search,
		title: "Smart Job Matching",
		description:
			"AI analyzes job postings and scores them against your skills, experience, and preferences.",
	},
	{
		icon: FileText,
		title: "Tailored Documents",
		description:
			"Generate customized resumes and cover letters targeted to each specific job posting.",
	},
	{
		icon: BarChart3,
		title: "Track Applications",
		description:
			"Manage your entire job search pipeline from discovery to offer in one place.",
	},
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FeatureCards() {
	return (
		<section
			data-testid="feature-cards"
			aria-label="Features"
			className="px-6 py-16 lg:px-16"
		>
			<div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
				{FEATURES.map((feature, index) => {
					const Icon = feature.icon;
					return (
						<div
							key={feature.title}
							data-testid={`feature-card-${index}`}
							className="bg-card rounded-lg border p-6"
						>
							<Icon className="text-primary mb-3 h-8 w-8" />
							<h3 className="text-foreground mb-1 font-semibold">
								{feature.title}
							</h3>
							<p className="text-muted-foreground text-sm">
								{feature.description}
							</p>
						</div>
					);
				})}
			</div>
		</section>
	);
}
