/**
 * Agent configuration section for the settings page.
 *
 * REQ-012 §12.1: Read-only display of model routing categories
 * and provider info. Simplified view of backend DEFAULT_CLAUDE_ROUTING.
 */

import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";

// ---------------------------------------------------------------------------
// Static routing data (simplified view of backend DEFAULT_CLAUDE_ROUTING)
// ---------------------------------------------------------------------------

interface RoutingEntry {
	category: string;
	model: string;
	slug: string;
}

const MODEL_ROUTING: RoutingEntry[] = [
	{
		category: "Chat / Onboarding",
		model: "Claude 3.5 Sonnet",
		slug: "chat-onboarding",
	},
	{
		category: "Scouter / Ghost Detection",
		model: "Claude 3.5 Haiku",
		slug: "scouter-ghost-detection",
	},
	{
		category: "Scoring / Generation",
		model: "Claude 3.5 Sonnet",
		slug: "scoring-generation",
	},
];

const PROVIDER_INFO = "Local (Claude SDK)";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Read-only display of agent model routing and provider info. */
export function AgentConfigurationSection() {
	return (
		<div data-testid="agent-configuration-section">
			<p className="text-muted-foreground mb-3 text-xs">
				<span>Model Routing</span> · read-only
			</p>
			<Table>
				<TableHeader>
					<TableRow>
						<TableHead>Category</TableHead>
						<TableHead>Model</TableHead>
					</TableRow>
				</TableHeader>
				<TableBody>
					{MODEL_ROUTING.map((route) => (
						<TableRow
							key={route.slug}
							data-testid={`routing-row-${route.slug}`}
						>
							<TableCell>{route.category}</TableCell>
							<TableCell>{route.model}</TableCell>
						</TableRow>
					))}
				</TableBody>
			</Table>
			<p className="text-muted-foreground mt-4 text-sm">
				Provider: {PROVIDER_INFO}
			</p>
		</div>
	);
}
