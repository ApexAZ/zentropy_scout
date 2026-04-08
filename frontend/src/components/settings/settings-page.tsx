/**
 * @fileoverview Settings page layout with account, job search, agent config, and about/legal sections.
 *
 * Layer: component
 * Feature: shared
 *
 * REQ-012 §12.1: Settings page with Account, Agent Configuration, and About.
 * REQ-024 §5.4: Legal section with ToS and Privacy placeholder links.
 * REQ-034 §9.2: Job Search section with search criteria, poll schedule, and source toggles.
 *
 * Coordinates with:
 * - components/ui/card.tsx: Card, CardContent, CardHeader, CardTitle for section cards
 * - components/settings/account-section.tsx: AccountSection for account management
 * - components/settings/agent-configuration-section.tsx: AgentConfigurationSection for routing display
 * - components/settings/job-search-section.tsx: JobSearchSection for search criteria, poll schedule, sources
 *
 * Called by / Used by:
 * - app/(main)/settings/page.tsx: settings route page
 */

import Link from "next/link";

import { PageTitle } from "@/components/ui/headings";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { AccountSection } from "./account-section";
import { AgentConfigurationSection } from "./agent-configuration-section";
import { JobSearchSection } from "./job-search-section";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SettingsPageProps {
	personaId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Settings page with section cards for Job Sources, Agent Config, and About. */
export function SettingsPage({ personaId }: Readonly<SettingsPageProps>) {
	return (
		<div data-testid="settings-page" className="space-y-6">
			<PageTitle>Settings</PageTitle>

			{/* Account (REQ-013 §8.3a) */}
			<Card data-testid="settings-account">
				<CardHeader>
					<CardTitle>Account</CardTitle>
				</CardHeader>
				<CardContent>
					<AccountSection />
				</CardContent>
			</Card>

			{/* Job Search (REQ-034 §9.2) */}
			<Card data-testid="settings-job-search">
				<CardHeader>
					<CardTitle>Job Search</CardTitle>
				</CardHeader>
				<CardContent>
					<JobSearchSection personaId={personaId} />
				</CardContent>
			</Card>

			{/* Agent Configuration */}
			<Card data-testid="settings-agent-configuration">
				<CardHeader>
					<CardTitle>Agent Configuration</CardTitle>
				</CardHeader>
				<CardContent>
					<AgentConfigurationSection />
				</CardContent>
			</Card>

			{/* About — §11.4 (REQ-012 §12.1 + §12.4): Implemented inline rather than
			   as a separate component because the content is two static <p> tags with
			   no interactivity. See frontend_implementation_plan.md §11.4 note. */}
			<Card data-testid="settings-about">
				<CardHeader>
					<CardTitle>About</CardTitle>
				</CardHeader>
				<CardContent className="space-y-2">
					<p className="text-sm">Zentropy Scout v0.1.0 &middot; AGPL-3.0</p>
					<p className="text-muted-foreground text-sm">
						AI-Powered Job Application Assistant
					</p>
				</CardContent>
			</Card>

			{/* Legal (REQ-024 §5.4): ToS and Privacy placeholder links until PBI #26 */}
			<Card data-testid="settings-legal">
				<CardHeader>
					<CardTitle>Legal</CardTitle>
				</CardHeader>
				<CardContent className="space-y-2">
					<Link href="#" className="text-primary block text-sm hover:underline">
						Terms of Service
					</Link>
					<Link href="#" className="text-primary block text-sm hover:underline">
						Privacy Policy
					</Link>
				</CardContent>
			</Card>
		</div>
	);
}
