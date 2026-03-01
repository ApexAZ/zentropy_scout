/**
 * Shared formatting utilities for financial and numeric display.
 *
 * REQ-020 §2.5: All monetary values displayed with 2 decimal places.
 * Backend returns 6 decimal places; frontend formats for display.
 */

// ---------------------------------------------------------------------------
// Balance thresholds & color coding (REQ-020 §9.1)
// ---------------------------------------------------------------------------

/** Balance at or above this threshold is displayed in green. */
export const BALANCE_THRESHOLD_HIGH = 1;
/** Balance at or above this threshold (but below HIGH) is amber. */
export const BALANCE_THRESHOLD_LOW = 0.1;

/** Get the Tailwind text color class for a balance amount. */
export function getBalanceColorClass(balance: number): string {
	if (balance >= BALANCE_THRESHOLD_HIGH) return "text-green-600";
	if (balance >= BALANCE_THRESHOLD_LOW) return "text-amber-500";
	return "text-red-500";
}

/** Format a balance string (6 decimal places from API) to $X.XX display. */
export function formatBalance(raw: string): string {
	const num = Number.parseFloat(raw);
	if (Number.isNaN(num)) return "$0.00";
	return `$${num.toFixed(2)}`;
}

// ---------------------------------------------------------------------------
// Currency formatting
// ---------------------------------------------------------------------------

/**
 * Format a cost string (6 decimal places from API) for display.
 *
 * @param raw - Cost string from API (e.g., "3.900000").
 * @param showMicroCosts - If true, shows "< $0.01" for sub-cent amounts
 *   instead of rounding to "$0.00". Useful for individual record rows.
 */
export function formatCost(raw: string, showMicroCosts = false): string {
	const num = Number.parseFloat(raw);
	if (Number.isNaN(num)) return "$0.00";
	if (showMicroCosts && num > 0 && num < 0.01) return "< $0.01";
	return `$${num.toFixed(2)}`;
}

// ---------------------------------------------------------------------------
// Number formatting
// ---------------------------------------------------------------------------

/** Format a number with locale-aware thousand separators. */
export function formatNumber(n: number): string {
	return n.toLocaleString("en-US");
}

// ---------------------------------------------------------------------------
// Date formatting
// ---------------------------------------------------------------------------

/** Format an ISO 8601 timestamp for short display. */
export function formatDate(iso: string): string {
	return new Date(iso).toLocaleDateString("en-US", {
		month: "short",
		day: "numeric",
		hour: "2-digit",
		minute: "2-digit",
	});
}
