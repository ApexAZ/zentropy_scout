/**
 * @fileoverview Compact job card displayed inline in chat messages.
 *
 * Layer: component
 * Feature: chat
 *
 * REQ-012 §5.3: Structured chat card showing job title,
 * company/location/work model, scores, salary range,
 * and action buttons (View, Favorite, Dismiss).
 * REQ-034 §9.3: Fit/stretch visual treatment — Growth Role amber
 * chip for stretch jobs, contextual score label (% match / % stretch).
 *
 * Coordinates with:
 * - types/chat.ts: JobCardData, SearchBucketType types
 * - lib/utils.ts: cn class-name helper
 * - components/ui/score-tier-badge.tsx: ScoreTierBadge for fit/stretch scores
 *
 * Called by / Used by:
 * - components/chat/message-bubble.tsx: inline job card rendering
 */

import { Eye, Heart, X } from "lucide-react";

import type { JobCardData, SearchBucketType } from "@/types/chat";
import { cn } from "@/lib/utils";

import { ScoreTierBadge } from "@/components/ui/score-tier-badge";

// ---------------------------------------------------------------------------
// Salary formatting
// ---------------------------------------------------------------------------

const CURRENCY_SYMBOLS: Record<string, string> = {
	USD: "$",
	GBP: "£",
	EUR: "€",
	CAD: "CA$",
	AUD: "A$",
};

function formatAmount(amount: number, symbol: string): string {
	if (amount >= 1000) {
		return `${symbol}${Math.round(amount / 1000)}k`;
	}
	return `${symbol}${amount}`;
}

/**
 * Formats a salary range for compact display.
 *
 * @returns Formatted string like "$140k–$160k", or null if no salary info.
 */
export function formatSalary(
	min: number | null,
	max: number | null,
	currency: string | null,
): string | null {
	if (min === null && max === null) return null;

	const symbol = currency ? (CURRENCY_SYMBOLS[currency] ?? "") : "";
	const useCode = currency !== null && !(currency in CURRENCY_SYMBOLS);

	if (min !== null && max !== null) {
		const minStr = formatAmount(min, symbol);
		const maxStr = formatAmount(max, symbol);
		return useCode
			? `${currency} ${minStr.replace(symbol, "")}–${maxStr.replace(symbol, "")}`
			: `${minStr}–${maxStr}`;
	}

	if (min !== null) {
		const minStr = formatAmount(min, symbol);
		return useCode
			? `${currency} ${minStr.replace(symbol, "")}+`
			: `${minStr}+`;
	}

	// At this point min is null and max is non-null (prior guards handled other cases)
	const maxVal = max as number;
	const maxStr = formatAmount(maxVal, symbol);
	return useCode
		? `Up to ${currency} ${maxStr.replace(symbol, "")}`
		: `Up to ${maxStr}`;
}

// ---------------------------------------------------------------------------
// Fit/stretch decision (REQ-034 §9.3)
// ---------------------------------------------------------------------------

/**
 * Determines whether a job should display as a stretch/growth role.
 *
 * Priority: explicit searchBucket prop > score-based decision rule.
 * Score rule: stretch when stretchScore > fitScore + 10 (avoids flicker
 * on near-equal scores).
 */
export function isStretchRole(
	searchBucket: SearchBucketType | null | undefined,
	fitScore: number | null,
	stretchScore: number | null,
): boolean {
	if (searchBucket === "stretch") return true;
	if (
		searchBucket === "fit" ||
		searchBucket === "manual" ||
		searchBucket === "pool"
	)
		return false;

	// Fallback: score-based decision
	if (stretchScore !== null && fitScore !== null) {
		return stretchScore > fitScore + 10;
	}
	// Only stretch score present → stretch; only fit or neither → fit
	return stretchScore !== null && fitScore === null;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ICON_SIZE = "h-3 w-3";

const ACTION_BUTTON_BASE =
	"inline-flex items-center gap-1 rounded px-2 py-1 text-xs transition-colors";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ChatJobCardProps {
	/** Job card data to display. */
	data: JobCardData;
	/** Called when View button is clicked. */
	onView?: (jobId: string) => void;
	/** Called when Favorite button is clicked. */
	onFavorite?: (jobId: string) => void;
	/** Called when Dismiss button is clicked. */
	onDismiss?: (jobId: string) => void;
	/** Additional CSS classes. */
	className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Renders a compact job card for display within chat messages.
 *
 * Shows job title, company/location/work model, fit & stretch scores,
 * salary range, and action buttons.
 */
export function ChatJobCard({
	data,
	onView,
	onFavorite,
	onDismiss,
	className,
}: Readonly<ChatJobCardProps>) {
	const {
		jobId,
		jobTitle,
		companyName,
		location,
		workModel,
		fitScore,
		stretchScore,
		salaryMin,
		salaryMax,
		salaryCurrency,
		isFavorite,
		searchBucket,
	} = data;

	const hasScores = fitScore !== null || stretchScore !== null;
	const salary = formatSalary(salaryMin, salaryMax, salaryCurrency);
	const isStretch = isStretchRole(searchBucket, fitScore, stretchScore);

	// Build meta line: "Company · Location · WorkModel"
	const metaParts = [companyName];
	if (location) metaParts.push(location);
	if (workModel) metaParts.push(workModel);

	return (
		<div
			data-slot="chat-job-card"
			data-favorited={String(isFavorite)}
			aria-label={`${jobTitle} at ${companyName}`}
			className={cn(
				"bg-card text-card-foreground flex flex-col gap-1.5 rounded-lg border p-3",
				className,
			)}
		>
			<div data-slot="job-title" className="flex items-center gap-2">
				<span className="min-w-0 truncate text-sm font-semibold">
					{jobTitle}
				</span>
				{isStretch && (
					<span
						data-slot="growth-chip"
						className="bg-logo-accent/15 text-logo-accent inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-medium"
					>
						Growth Role
					</span>
				)}
			</div>

			<div data-slot="job-meta" className="text-muted-foreground text-xs">
				{metaParts.join(" · ")}
			</div>

			{hasScores && (
				<div data-slot="job-scores" className="flex items-center gap-2">
					<ScoreTierBadge score={fitScore} scoreType="fit" />
					<ScoreTierBadge score={stretchScore} scoreType="stretch" />
					<span
						data-slot="score-label"
						className={cn(
							"text-xs font-medium",
							isStretch ? "text-logo-accent" : "text-primary",
						)}
					>
						{isStretch
							? `${stretchScore ?? fitScore}% stretch`
							: `${fitScore ?? stretchScore}% match`}
					</span>
				</div>
			)}

			{salary !== null && (
				<div
					data-slot="job-salary"
					className="text-muted-foreground text-xs font-medium"
				>
					{salary}
				</div>
			)}

			<div data-slot="job-actions" className="flex items-center gap-1 pt-1">
				<button
					type="button"
					aria-label="View job"
					onClick={() => onView?.(jobId)}
					className={cn(
						ACTION_BUTTON_BASE,
						"text-muted-foreground hover:text-foreground",
					)}
				>
					<Eye className={ICON_SIZE} aria-hidden="true" />
					View
				</button>
				<button
					type="button"
					aria-label={isFavorite ? "Unfavorite job" : "Favorite job"}
					onClick={() => onFavorite?.(jobId)}
					className={cn(
						ACTION_BUTTON_BASE,
						isFavorite
							? "text-destructive hover:text-destructive/80"
							: "text-muted-foreground hover:text-foreground",
					)}
				>
					<Heart
						className={cn(ICON_SIZE, isFavorite && "fill-current")}
						aria-hidden="true"
					/>
					{isFavorite ? "Favorited" : "Favorite"}
				</button>
				<button
					type="button"
					aria-label="Dismiss job"
					onClick={() => onDismiss?.(jobId)}
					className={cn(
						ACTION_BUTTON_BASE,
						"text-muted-foreground hover:text-destructive",
					)}
				>
					<X className={ICON_SIZE} aria-hidden="true" />
					Dismiss
				</button>
			</div>
		</div>
	);
}
