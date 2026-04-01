/**
 * @fileoverview Landing page hero section with headline and CTA.
 *
 * Layer: component
 * Feature: shared
 *
 * REQ-024 §4.2: Headline, subtitle, CTA button, sign-in link,
 * and gradient placeholder graphic.
 *
 * Coordinates with:
 * - components/ui/button.tsx: Button component for CTA
 *
 * Called by / Used by:
 * - app/(public)/page.tsx: landing page composition
 */

import Link from "next/link";

import { Button } from "@/components/ui/button";

export function HeroSection() {
	return (
		<section
			data-testid="hero-section"
			aria-label="Hero"
			className="flex flex-col items-center gap-12 px-6 py-16 lg:flex-row lg:justify-between lg:px-16 lg:py-24"
		>
			<div className="max-w-xl text-center lg:text-left">
				<h1 className="text-foreground text-4xl font-bold tracking-tight sm:text-5xl">
					Your AI-Powered Job Search Assistant
				</h1>
				<p className="text-muted-foreground mt-4 text-lg">
					Build your professional persona, find matching jobs, and generate
					tailored resumes and cover letters — all powered by AI.
				</p>
				<div className="mt-8 flex flex-col items-center gap-4 sm:flex-row lg:items-start">
					<Button asChild size="lg">
						<Link data-testid="hero-cta" href="/register">
							Get Started Free
						</Link>
					</Button>
					<Link
						data-testid="hero-sign-in"
						href="/login"
						className="text-muted-foreground hover:text-foreground text-sm transition-colors"
					>
						Already have an account? Sign in
					</Link>
				</div>
			</div>

			<div
				data-testid="hero-graphic"
				className="from-primary/20 via-card to-primary/10 h-64 w-full max-w-md rounded-2xl bg-gradient-to-br lg:h-72 lg:w-96"
				aria-hidden="true"
			/>
		</section>
	);
}
