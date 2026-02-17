"use client";

/**
 * Generic expandable score breakdown for the job detail page.
 *
 * REQ-012 §8.3: Score section showing total with tier badge.
 * REQ-012 §8.4: Drill-down with component rows displaying
 * individual scores, weights, and weighted contributions.
 *
 * Replaces the former FitScoreBreakdown and StretchScoreBreakdown
 * components with a single parameterized implementation.
 */

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import type { FitScoreResult, StretchScoreResult } from "@/types/job";
import {
	FIT_COMPONENT_ORDER,
	STRETCH_COMPONENT_ORDER,
	formatComponentLabel,
} from "@/lib/score-formatters";
import { cn } from "@/lib/utils";
import { ScoreTierBadge } from "@/components/ui/score-tier-badge";

// ---------------------------------------------------------------------------
// Config per score type
// ---------------------------------------------------------------------------

const SCORE_CONFIG = {
	fit: {
		label: "Fit Score",
		componentOrder: FIT_COMPONENT_ORDER,
	},
	stretch: {
		label: "Stretch Score",
		componentOrder: STRETCH_COMPONENT_ORDER,
	},
} as const;

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ScoreBreakdownProps {
	/** Score data. Undefined when job has not been scored. */
	score: FitScoreResult | StretchScoreResult | undefined;
	/** Which score type to render — drives labels, testids, and component order. */
	scoreType: "fit" | "stretch";
	/** Additional CSS classes. */
	className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Renders a score total with tier badge, expandable to reveal
 * component-level breakdown with scores, weights, and weighted contributions.
 */
function ScoreBreakdown({
	score,
	scoreType,
	className,
}: Readonly<ScoreBreakdownProps>) {
	const [expanded, setExpanded] = useState(false);
	const config = SCORE_CONFIG[scoreType];

	// Not scored state — no toggle, no chevron
	if (!score) {
		return (
			<div
				data-testid={`${scoreType}-score-breakdown`}
				className={cn("flex items-center gap-2", className)}
			>
				<span className="text-sm font-semibold">{config.label}:</span>
				<span
					data-testid={`${scoreType}-score-not-scored`}
					className="border-border text-muted-foreground inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium"
				>
					Not scored
				</span>
			</div>
		);
	}

	return (
		<div
			data-testid={`${scoreType}-score-breakdown`}
			className={cn("flex flex-col gap-2", className)}
		>
			{/* Toggle row: chevron + label + badge */}
			<button
				type="button"
				data-testid={`${scoreType}-score-toggle`}
				aria-expanded={expanded}
				aria-controls={`${scoreType}-score-panel`}
				onClick={() => setExpanded((prev) => !prev)}
				className="flex items-center gap-2"
			>
				{expanded ? (
					<ChevronDown data-testid="chevron-down" className="h-4 w-4" />
				) : (
					<ChevronRight data-testid="chevron-right" className="h-4 w-4" />
				)}
				<span className="text-sm font-semibold">{config.label}:</span>
				<ScoreTierBadge score={score.total} scoreType={scoreType} />
			</button>

			{/* Expanded panel: component rows */}
			{expanded && (
				<section
					id={`${scoreType}-score-panel`}
					data-testid={`${scoreType}-score-panel`}
					aria-label={`${config.label} component breakdown`}
				>
					<ul className="ml-6 space-y-1">
						{config.componentOrder.map((key) => {
							const componentScore =
								score.components[key as keyof typeof score.components];
							const weight = score.weights[key as keyof typeof score.weights];
							const weighted = Math.round(componentScore * weight);
							const pct = Math.round(weight * 100);

							return (
								<li
									key={key}
									data-testid={`${scoreType}-component-${key}`}
									className="text-muted-foreground flex items-center justify-between text-sm"
								>
									<span className="min-w-[140px]">
										{formatComponentLabel(key)}
									</span>
									<span className="min-w-[32px] text-right font-medium">
										{componentScore}
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
				</section>
			)}
		</div>
	);
}

export { ScoreBreakdown };
export type { ScoreBreakdownProps };
