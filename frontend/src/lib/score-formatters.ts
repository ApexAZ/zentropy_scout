/**
 * Shared formatting utilities for fit and stretch score component display.
 *
 * Extracted from chat-score-card.tsx for reuse across score display
 * components (ChatScoreCard, FitScoreBreakdown, StretchScoreBreakdown).
 *
 * REQ-008 §4.1: Fit score component keys and weight order.
 * REQ-008 §5.1: Stretch score component keys and weight order.
 * REQ-012 §8.3: Score display formatting.
 */

import type {
	FitScoreComponentKey,
	StretchScoreComponentKey,
} from "@/types/job";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/**
 * Display order for fit score components (matches REQ-008 §4.1 weight order).
 *
 * Same keys as FIT_SCORE_COMPONENT_KEYS in types/job.ts, but reordered by
 * weight precedence (40%, 25%, 15%, 10%, 10%) for display purposes.
 */
export const FIT_COMPONENT_ORDER: readonly FitScoreComponentKey[] = [
	"hard_skills",
	"experience_level",
	"soft_skills",
	"role_title",
	"location_logistics",
] as const;

/**
 * Display order for stretch score components (matches REQ-008 §5.1 weight order).
 *
 * Same keys as STRETCH_SCORE_COMPONENT_KEYS in types/job.ts, but reordered by
 * weight precedence (50%, 40%, 10%) for display purposes.
 */
export const STRETCH_COMPONENT_ORDER: readonly StretchScoreComponentKey[] = [
	"target_role",
	"target_skills",
	"growth_trajectory",
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
