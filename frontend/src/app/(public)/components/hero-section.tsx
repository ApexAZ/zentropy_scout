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
 * - components/ui/zentropy-logo.tsx: shared wordmark
 * - app/(public)/components/hero-showcase.tsx: right-side feature showcase
 *
 * Called by / Used by:
 * - app/(public)/page.tsx: landing page composition
 */

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { ZentropyLogo } from "@/components/ui/zentropy-logo";

import { HeroShowcase } from "./hero-showcase";

export function HeroSection() {
	return (
		<section
			data-testid="hero-section"
			aria-label="Hero"
			className="flex flex-col gap-12 pt-[80px] pr-[110px] pl-[110px] lg:flex-row lg:items-start"
		>
			<div className="flex-[1] text-center lg:text-left">
				<ZentropyLogo data-testid="hero-logo" className="mb-8 block text-9xl" />
				<h1 className="text-foreground text-4xl font-bold tracking-tight sm:text-5xl">
					AI-Powered Job Search Assistant
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

			<div className="mt-[45px] lg:flex-[2]">
				<HeroShowcase />
			</div>
		</section>
	);
}
