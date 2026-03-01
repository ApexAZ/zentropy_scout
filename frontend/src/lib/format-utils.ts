/**
 * Shared formatting utilities for financial and numeric display.
 *
 * REQ-020 §2.5: All monetary values displayed with 2 decimal places.
 * Backend returns 6 decimal places; frontend formats for display.
 */

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
