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
 *
 * Called by / Used by:
 * - Next.js framework: route / (public landing page)
 */

import { HeroSection } from "./components/hero-section";
import { HowItWorks } from "./components/how-it-works";
import { LandingFooter } from "./components/landing-footer";

export default function LandingPage() {
	return (
		<div data-testid="landing-page">
			<HeroSection />
			<HowItWorks />
			<LandingFooter />
		</div>
	);
}
