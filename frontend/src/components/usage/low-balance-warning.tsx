/**
 * @fileoverview Low-balance warning banner for the usage page.
 *
 * Layer: component
 * Feature: usage
 *
 * REQ-029 §9.5: Threshold-based color coding with CTA to
 * scroll to funding packs section.
 *
 * Coordinates with:
 * - lib/format-utils.ts: BALANCE_THRESHOLD_HIGH, BALANCE_THRESHOLD_LOW for threshold constants
 * - lib/utils.ts: cn class-name helper
 *
 * Called by / Used by:
 * - components/usage/usage-page.tsx: low-balance warning on usage dashboard
 */

import {
	BALANCE_THRESHOLD_HIGH,
	BALANCE_THRESHOLD_LOW,
} from "@/lib/format-utils";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface LowBalanceWarningProps {
	balance: number;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function LowBalanceWarning({
	balance,
}: Readonly<LowBalanceWarningProps>) {
	if (balance >= BALANCE_THRESHOLD_HIGH) {
		return null;
	}

	const isCritical = balance < BALANCE_THRESHOLD_LOW;

	return (
		<div
			data-testid="low-balance-warning"
			role="alert"
			className={cn(
				"rounded-xl border px-4 py-3 text-sm",
				isCritical
					? "border-destructive bg-destructive/10 text-destructive"
					: "border-primary bg-primary/10 text-primary",
			)}
		>
			<p>
				{isCritical
					? "Your balance is nearly empty. Add funds to continue using Zentropy Scout."
					: "Your balance is running low. Add funds to continue."}
			</p>
			<a
				href="#funding-packs"
				className={cn(
					"mt-1 inline-block rounded-sm font-medium underline focus-visible:ring-2 focus-visible:outline-none",
					isCritical
						? "text-destructive hover:text-destructive/80 focus-visible:ring-destructive/50"
						: "text-primary hover:text-primary/80 focus-visible:ring-primary/50",
				)}
			>
				Add Funds
			</a>
		</div>
	);
}
