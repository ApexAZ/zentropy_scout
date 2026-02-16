/**
 * Settings page layout component.
 *
 * REQ-012 §12.1: Settings page with three sections —
 * Job Sources, Agent Configuration, and About.
 * Child sections filled by §11.2 (JobSourcesSection), §11.3 (AgentConfigurationSection),
 * and §11.4 (About — inline, see comment below).
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AgentConfigurationSection } from "./agent-configuration-section";
import { JobSourcesSection } from "./job-sources-section";

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
			<h1 className="text-2xl font-bold">Settings</h1>

			{/* Job Sources */}
			<Card data-testid="settings-job-sources">
				<CardHeader>
					<CardTitle>Job Sources</CardTitle>
				</CardHeader>
				<CardContent>
					<JobSourcesSection personaId={personaId} />
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
						Single-user mode &mdash; no configuration needed.
					</p>
				</CardContent>
			</Card>
		</div>
	);
}
