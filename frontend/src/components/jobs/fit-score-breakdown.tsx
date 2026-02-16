"use client";

/**
 * Expandable fit score breakdown for the job detail page.
 *
 * REQ-012 §8.3: Fit score section showing total with tier badge.
 * REQ-012 §8.4: Drill-down with 5 component rows displaying
 * individual scores, weights, and weighted contributions.
 */

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import type { FitScoreResult } from "@/types/job";
import {
	FIT_COMPONENT_ORDER,
	formatComponentLabel,
} from "@/lib/score-formatters";
import { cn } from "@/lib/utils";
import { ScoreTierBadge } from "@/components/ui/score-tier-badge";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface FitScoreBreakdownProps {
	/** Fit score data. Undefined when job has not been scored. */
	fit: FitScoreResult | undefined;
	/** Additional CSS classes. */
	className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Renders the fit score total with tier badge, expandable to reveal
 * component-level breakdown with scores, weights, and weighted contributions.
 */
function FitScoreBreakdown({ fit, className }: FitScoreBreakdownProps) {
	const [expanded, setExpanded] = useState(false);

	// Not scored state — no toggle, no chevron
	if (!fit) {
		return (
			<div
				data-testid="fit-score-breakdown"
				className={cn("flex items-center gap-2", className)}
			>
				<span className="text-sm font-semibold">Fit Score:</span>
				<span
					data-testid="fit-score-not-scored"
					className="border-border text-muted-foreground inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium"
				>
					Not scored
				</span>
			</div>
		);
	}

	return (
		<div
			data-testid="fit-score-breakdown"
			className={cn("flex flex-col gap-2", className)}
		>
			{/* Toggle row: chevron + label + badge */}
			<button
				type="button"
				data-testid="fit-score-toggle"
				aria-expanded={expanded}
				aria-controls="fit-score-panel"
				onClick={() => setExpanded((prev) => !prev)}
				className="flex items-center gap-2"
			>
				{expanded ? (
					<ChevronDown data-testid="chevron-down" className="h-4 w-4" />
				) : (
					<ChevronRight data-testid="chevron-right" className="h-4 w-4" />
				)}
				<span className="text-sm font-semibold">Fit Score:</span>
				<ScoreTierBadge score={fit.total} scoreType="fit" />
			</button>

			{/* Expanded panel: component rows */}
			{expanded && (
				<div
					id="fit-score-panel"
					data-testid="fit-score-panel"
					role="region"
					aria-label="Fit score component breakdown"
				>
					<ul className="ml-6 space-y-1">
						{FIT_COMPONENT_ORDER.map((key) => {
							const score = fit.components[key];
							const weight = fit.weights[key];
							const weighted = Math.round(score * weight);
							const pct = Math.round(weight * 100);

							return (
								<li
									key={key}
									data-testid={`fit-component-${key}`}
									className="text-muted-foreground flex items-center justify-between text-sm"
								>
									<span className="min-w-[140px]">
										{formatComponentLabel(key)}
									</span>
									<span className="min-w-[32px] text-right font-medium">
										{score}
									</span>
									<span className="text-muted-foreground/60 min-w-[40px] text-right">
										{pct}%
									</span>
									<span className="min-w-[32px] text-right font-medium">
										{weighted}
									</span>
								</li>
							);
						})}
					</ul>
				</div>
			)}
		</div>
	);
}

export { FitScoreBreakdown };
export type { FitScoreBreakdownProps };
