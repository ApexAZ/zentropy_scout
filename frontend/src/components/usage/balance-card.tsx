/**
 * Balance card component for the usage dashboard.
 *
 * REQ-020 §9.2: Large balance display with color coding.
 * REQ-029 §9.1: "Add Funds" button links to funding packs section.
 */

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
	BALANCE_THRESHOLD_HIGH,
	BALANCE_THRESHOLD_LOW,
	formatBalance,
	getBalanceColorClass,
} from "@/lib/format-utils";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface BalanceCardProps {
	balance: string | undefined;
	isLoading: boolean;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Cap for usage bar width scaling (largest default pack = $15). */
const BAR_CAP_DOLLARS = 15;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Get the Tailwind background color class for the usage bar fill. */
function getBarColorClass(amount: number): string {
	if (amount >= BALANCE_THRESHOLD_HIGH) return "bg-success";
	if (amount >= BALANCE_THRESHOLD_LOW) return "bg-primary";
	return "bg-destructive";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function BalanceCard({
	balance,
	isLoading,
}: Readonly<BalanceCardProps>) {
	const raw = balance ? Number.parseFloat(balance) : 0;
	const parsed = Number.isNaN(raw) ? 0 : raw;
	const displayBalance = balance ? formatBalance(balance) : "$0.00";
	const pct = Math.min(100, (parsed / BAR_CAP_DOLLARS) * 100);

	return (
		<Card data-testid="balance-card">
			<CardHeader>
				<CardTitle>Current Balance</CardTitle>
			</CardHeader>
			<CardContent className="space-y-3">
				<div className="flex items-center justify-between">
					{isLoading ? (
						<Skeleton data-testid="balance-skeleton" className="h-10 w-32" />
					) : (
						<span
							data-testid="balance-amount"
							className={cn("text-4xl font-bold", getBalanceColorClass(parsed))}
						>
							{displayBalance}
						</span>
					)}
					<Button asChild>
						<a href="#funding-packs">Add Funds</a>
					</Button>
				</div>
				{!isLoading && (
					<>
						<progress
							className="sr-only"
							aria-label={`Balance: ${displayBalance}`}
							max={100}
							value={Math.round(pct)}
						/>
						<div
							data-testid="usage-bar"
							className="bg-muted h-2 w-full overflow-hidden rounded-full"
							aria-hidden="true"
						>
							<div
								className={cn(
									"h-full rounded-full transition-all",
									getBarColorClass(parsed),
								)}
								style={{ width: `${pct}%` }}
							/>
						</div>
					</>
				)}
			</CardContent>
		</Card>
	);
}
