/**
 * @fileoverview Landing page footer with copyright and links.
 *
 * Layer: component
 * Feature: shared
 *
 * REQ-024 §4.5: Copyright, Sign In, ToS, and Privacy links.
 * ToS and Privacy are placeholder links (#) until PBI #26 adds real routes.
 *
 * Coordinates with:
 * - (no upstream lib imports — self-contained presentational component)
 *
 * Called by / Used by:
 * - app/(public)/page.tsx: landing page composition
 */

import Link from "next/link";

const MUTED_LINK =
	"text-muted-foreground hover:text-foreground text-sm transition-colors";

export function LandingFooter() {
	return (
		<footer
			data-testid="landing-footer"
			className="border-t px-6 py-6 lg:px-16"
		>
			<div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
				<p className="text-muted-foreground text-sm">
					&copy; 2026 Zentropy Scout
				</p>
				<nav className="flex items-center gap-4" aria-label="Footer">
					<Link href="/login" className={MUTED_LINK}>
						Sign In
					</Link>
					<Link href="#" data-testid="footer-tos" className={MUTED_LINK}>
						Terms of Service
					</Link>
					<Link href="#" data-testid="footer-privacy" className={MUTED_LINK}>
						Privacy Policy
					</Link>
				</nav>
			</div>
		</footer>
	);
}
