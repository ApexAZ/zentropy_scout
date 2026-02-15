/**
 * Settings page layout component.
 *
 * REQ-012 §12.1: Settings page with three sections —
 * Job Sources, Agent Configuration, and About.
 * Child sections are placeholders filled by §11.2–11.4.
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Settings page with section cards for Job Sources, Agent Config, and About. */
export function SettingsPage() {
	return (
		<div data-testid="settings-page" className="space-y-6">
			<h1 className="text-2xl font-bold">Settings</h1>

			{/* Job Sources */}
			<Card data-testid="settings-job-sources">
				<CardHeader>
					<CardTitle>Job Sources</CardTitle>
				</CardHeader>
				<CardContent>
					<p className="text-muted-foreground text-sm">
						Configure which job sources to search and their priority order.
					</p>
				</CardContent>
			</Card>

			{/* Agent Configuration */}
			<Card data-testid="settings-agent-configuration">
				<CardHeader>
					<CardTitle>Agent Configuration</CardTitle>
				</CardHeader>
				<CardContent>
					<p className="text-muted-foreground text-sm">
						Model routing (read-only)
					</p>
				</CardContent>
			</Card>

			{/* About */}
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
