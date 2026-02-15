"use client";

/**
 * Collapsible agent reasoning display.
 *
 * Shared by variant review (§8.7) and cover letter review (§9.1).
 * Shows the LLM's explanation for its decisions in a collapsible panel.
 */

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

interface AgentReasoningProps {
	reasoning: string;
}

function AgentReasoning({ reasoning }: AgentReasoningProps) {
	const [expanded, setExpanded] = useState(true);

	return (
		<div data-testid="agent-reasoning" className="mt-4">
			<button
				type="button"
				data-testid="agent-reasoning-toggle"
				aria-expanded={expanded}
				onClick={() => setExpanded((prev) => !prev)}
				className="flex items-center gap-2"
			>
				{expanded ? (
					<ChevronDown className="h-4 w-4" />
				) : (
					<ChevronRight className="h-4 w-4" />
				)}
				<span className="text-sm font-semibold">Agent Reasoning</span>
			</button>
			{expanded && (
				<div className="text-muted-foreground mt-2 rounded-lg border p-3 text-sm leading-relaxed">
					{reasoning}
				</div>
			)}
		</div>
	);
}

export { AgentReasoning };
export type { AgentReasoningProps };
