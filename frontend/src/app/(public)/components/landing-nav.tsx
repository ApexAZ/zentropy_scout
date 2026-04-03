/**
 * @fileoverview Landing page navigation bar with logo and CTA.
 *
 * Layer: component
 * Feature: shared
 *
 * REQ-024 §4.1: Logo, sign-in link, and amber CTA button.
 * Minimal nav — no hamburger menu, all items fit on mobile.
 *
 * Coordinates with:
 * - components/ui/button.tsx: Button component for CTA
 *
 * Called by / Used by:
 * - app/(public)/page.tsx: landing page composition
 */

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { ZentropyLogo } from "@/components/ui/zentropy-logo";

export function LandingNav() {
	return (
		<header
			data-testid="landing-nav"
			className="flex items-center justify-between px-6 py-4"
		>
			<Link href="/" aria-label="Zentropy Scout home">
				<ZentropyLogo data-testid="landing-logo" className="text-4xl" />
			</Link>

			<nav className="flex items-center gap-4" aria-label="Main">
				<Link
					href="/login"
					className="text-muted-foreground hover:text-foreground text-sm transition-colors"
				>
					Sign In
				</Link>
				<Button asChild>
					<Link href="/register">Get Started</Link>
				</Button>
			</nav>
		</header>
	);
}
