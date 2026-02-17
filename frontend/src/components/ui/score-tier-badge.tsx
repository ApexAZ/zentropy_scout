/**
 * Score tier badge displaying a numeric score with tier label and color.
 *
 * REQ-012 §8.4: Fit and Stretch score tiers with color-coded badges.
 * REQ-008 §7.1: Fit tier ranges — High (90-100), Medium (75-89), Low (60-74), Poor (0-59).
 * REQ-008 §7.2: Stretch tier ranges — High Growth (80-100), Moderate Growth (60-79),
 *   Lateral (40-59), Low Growth (0-39).
 *
 * Accepts score and scoreType as props. Derives tier label and color
 * automatically from the numeric score. Renders "Not scored" when score
 * is null.
 */

import type { FitScoreTier, StretchScoreTier } from "@/types/job";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BASE_CLASSES =
	"inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium";

const NOT_SCORED_STYLES = "border border-border text-muted-foreground";

const FIT_TIER_STYLES: Record<FitScoreTier, string> = {
	High: "bg-success text-success-foreground",
	Medium: "bg-primary text-primary-foreground",
	Low: "bg-warning text-warning-foreground",
	Poor: "bg-destructive text-destructive-foreground",
};

const STRETCH_TIER_STYLES: Record<StretchScoreTier, string> = {
	"High Growth": "bg-stretch-high text-stretch-high-foreground",
	"Moderate Growth": "bg-primary text-primary-foreground",
	Lateral: "bg-stretch-lateral text-stretch-lateral-foreground",
	"Low Growth": "bg-muted text-muted-foreground",
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ScoreType = "fit" | "stretch";

interface ScoreTierBadgeProps {
	score: number | null;
	scoreType: ScoreType;
	className?: string;
}

// ---------------------------------------------------------------------------
// Tier derivation
// ---------------------------------------------------------------------------

function getFitTier(score: number): FitScoreTier {
	if (score >= 90) return "High";
	if (score >= 75) return "Medium";
	if (score >= 60) return "Low";
	return "Poor";
}

function getStretchTier(score: number): StretchScoreTier {
	if (score >= 80) return "High Growth";
	if (score >= 60) return "Moderate Growth";
	if (score >= 40) return "Lateral";
	return "Low Growth";
}

function getTierConfig(
	scoreType: ScoreType,
	score: number,
): { tier: string; colorClass: string } {
	if (scoreType === "fit") {
		const tier = getFitTier(score);
		return { tier, colorClass: FIT_TIER_STYLES[tier] };
	}
	const tier = getStretchTier(score);
	return { tier, colorClass: STRETCH_TIER_STYLES[tier] };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function ScoreTierBadge({
	score,
	scoreType,
	className,
}: Readonly<ScoreTierBadgeProps>) {
	const typeLabel = scoreType === "fit" ? "Fit" : "Stretch";

	if (score === null) {
		return (
			<span
				data-slot="score-tier-badge"
				data-score-type={scoreType}
				data-tier="none"
				aria-label={`${typeLabel} score: Not scored`}
				className={cn(BASE_CLASSES, NOT_SCORED_STYLES, className)}
			>
				Not scored
			</span>
		);
	}

	const { tier, colorClass } = getTierConfig(scoreType, score);
	const tierSlug = tier.toLowerCase().replaceAll(/\s+/g, "-");

	return (
		<span
			data-slot="score-tier-badge"
			data-score-type={scoreType}
			data-tier={tierSlug}
			aria-label={`${typeLabel} score: ${score}, ${tier}`}
			className={cn(BASE_CLASSES, "gap-1", colorClass, className)}
		>
			<span>{score}</span>
			<span>{tier}</span>
		</span>
	);
}

export { ScoreTierBadge };
export type { ScoreTierBadgeProps, ScoreType };
