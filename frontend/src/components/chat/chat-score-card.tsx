/**
 * Score summary card displayed inline in chat messages.
 *
 * REQ-012 §5.3: Structured chat card showing fit score breakdown
 * (5 components with weights), stretch score with tier,
 * strengths, and gaps.
 */

import type { ScoreCardData } from "@/types/chat";
import type { FitScoreComponentKey } from "@/types/job";
import { cn } from "@/lib/utils";

import { ScoreTierBadge } from "@/components/ui/score-tier-badge";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Display order for fit score components (matches REQ-008 §4.1 weight order). */
const FIT_COMPONENT_ORDER: readonly FitScoreComponentKey[] = [
	"hard_skills",
	"experience_level",
	"soft_skills",
	"role_title",
	"location_logistics",
] as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Converts a snake_case component key to a human-readable label.
 *
 * @example formatComponentLabel("hard_skills") → "Hard Skills"
 */
export function formatComponentLabel(key: string): string {
	return key
		.split("_")
		.map((word) => word.charAt(0).toUpperCase() + word.slice(1))
		.join(" ");
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ChatScoreCardProps {
	/** Score card data to display. */
	data: ScoreCardData;
	/** Additional CSS classes. */
	className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Renders a score summary card for display within chat messages.
 *
 * Shows fit score with component breakdown, stretch score with tier,
 * and strengths/gaps from the score explanation.
 */
export function ChatScoreCard({ data, className }: ChatScoreCardProps) {
	const { fit, stretch, explanation } = data;
	const hasStrengths = explanation.strengths.length > 0;
	const hasGaps = explanation.gaps.length > 0;

	return (
		<div
			data-slot="chat-score-card"
			aria-label="Score summary"
			className={cn(
				"bg-card text-card-foreground flex flex-col gap-3 rounded-lg border p-3",
				className,
			)}
		>
			{/* Fit Score Section */}
			<div data-slot="fit-section" className="flex flex-col gap-1">
				<div className="flex items-center gap-2">
					<span className="text-sm font-semibold">Fit Score:</span>
					<ScoreTierBadge score={fit.total} scoreType="fit" />
				</div>

				<ul
					data-slot="fit-components"
					aria-label="Fit score components"
					className="text-muted-foreground ml-3 space-y-0.5 text-xs"
				>
					{FIT_COMPONENT_ORDER.map((key, index) => (
						<li key={key} className="flex items-center gap-1">
							<span className="text-muted-foreground/60">
								{index === FIT_COMPONENT_ORDER.length - 1 ? "└" : "├"}
							</span>
							<span>{formatComponentLabel(key)}:</span>
							<span className="font-medium">{fit.components[key]}</span>
							<span className="text-muted-foreground/60">
								({Math.round(fit.weights[key] * 100)}%)
							</span>
						</li>
					))}
				</ul>
			</div>

			{/* Stretch Score Section */}
			<div data-slot="stretch-section" className="flex items-center gap-2">
				<span className="text-sm font-semibold">Stretch Score:</span>
				<ScoreTierBadge score={stretch.total} scoreType="stretch" />
			</div>

			{/* Strengths */}
			{hasStrengths && (
				<div data-slot="score-strengths" className="text-xs">
					<span className="font-medium">Strengths: </span>
					<span className="text-muted-foreground">
						{explanation.strengths.join(", ")}
					</span>
				</div>
			)}

			{/* Gaps */}
			{hasGaps && (
				<div data-slot="score-gaps" className="text-xs">
					<span className="font-medium">Gaps: </span>
					<span className="text-muted-foreground">
						{explanation.gaps.join(", ")}
					</span>
				</div>
			)}
		</div>
	);
}
