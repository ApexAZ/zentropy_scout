/**
 * Landing page — full composition of all landing sections.
 *
 * REQ-024 §4.1–§4.5: Nav, hero, features, how-it-works, footer.
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
