/**
 * @fileoverview Landing page — full composition of all landing sections.
 *
 * Layer: page
 * Feature: shared
 *
 * REQ-024 §4.1-§4.5: Composes hero, how-it-works, and footer
 * sections into the public landing page.
 *
 * Coordinates with:
 * - app/(public)/components/hero-section.tsx: hero with logo, showcase, and CTA
 * - app/(public)/components/how-it-works.tsx: 3-step walkthrough
 * - app/(public)/components/landing-footer.tsx: footer with links
 * - app/(public)/components/star-field-loader.tsx: client-only starfield background
 *
 * Called by / Used by:
 * - Next.js framework: route / (public landing page)
 */

import { HeroSection } from "./components/hero-section";
import { HowItWorks } from "./components/how-it-works";
import { LandingFooter } from "./components/landing-footer";
import { StarFieldLoader } from "./components/star-field-loader";

export default function LandingPage() {
	return (
		<div
			data-testid="landing-page"
			className="mx-auto flex min-h-screen max-w-7xl flex-col"
		>
			<StarFieldLoader />
			<div className="flex-1">
				<HeroSection />
				<HowItWorks />
			</div>
			<LandingFooter />
		</div>
	);
}
