/**
 * Landing page navigation bar.
 *
 * REQ-024 §4.1: Logo, sign-in link, and amber CTA button.
 * Minimal nav — no hamburger menu, all items fit on mobile.
 */

import Image from "next/image";
import Link from "next/link";

import { Button } from "@/components/ui/button";

export function LandingNav() {
	return (
		<header
			data-testid="landing-nav"
			className="flex items-center justify-between px-6 py-4"
		>
			<Link href="/" aria-label="Zentropy Scout home">
				<Image
					data-testid="landing-logo"
					src="/zentropy_logo.png"
					alt="Zentropy Scout"
					width={150}
					height={36}
					priority
				/>
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
