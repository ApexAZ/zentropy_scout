/**
 * @fileoverview Landing page — full composition of all landing sections.
 *
 * Layer: page
 * Feature: shared
 *
 * REQ-024 §4.1-§4.5: Composes nav, hero, features, how-it-works, and footer
 * sections into the public landing page.
 *
 * Coordinates with:
 * - app/(public)/components/feature-cards.tsx: feature highlight grid
 * - app/(public)/components/hero-section.tsx: hero with CTA
 * - app/(public)/components/how-it-works.tsx: 3-step walkthrough
 * - app/(public)/components/landing-footer.tsx: footer with links
 * - app/(public)/components/landing-nav.tsx: navigation bar
 *
 * Called by / Used by:
 * - Next.js framework: route / (public landing page)
 */

import { FeatureCards } from "./components/feature-cards";
import { HeroSection } from "./components/hero-section";
import { HowItWorks } from "./components/how-it-works";
import { LandingFooter } from "./components/landing-footer";
import { LandingNav } from "./components/landing-nav";

export default function LandingPage() {
	return (
		<div data-testid="landing-page">
			<LandingNav />
			<HeroSection />
			<FeatureCards />
			<HowItWorks />
			<LandingFooter />
		</div>
	);
}
