/**
 * Compact job card displayed inline in chat messages.
 *
 * REQ-012 §5.3: Structured chat card showing job title,
 * company/location/work model, scores, salary range,
 * and action buttons (View, Favorite, Dismiss).
 */

import { Eye, Heart, X } from "lucide-react";

import type { JobCardData } from "@/types/chat";
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
}: ChatJobCardProps) {
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
	} = data;

	const hasScores = fitScore !== null || stretchScore !== null;
	const salary = formatSalary(salaryMin, salaryMax, salaryCurrency);

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
			<div data-slot="job-title" className="text-sm font-semibold">
				{jobTitle}
			</div>

			<div data-slot="job-meta" className="text-muted-foreground text-xs">
				{metaParts.join(" · ")}
			</div>

			{hasScores && (
				<div data-slot="job-scores" className="flex items-center gap-2">
					<ScoreTierBadge score={fitScore} scoreType="fit" />
					<ScoreTierBadge score={stretchScore} scoreType="stretch" />
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
