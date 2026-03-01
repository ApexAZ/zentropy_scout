/**
 * Balance card component for the usage dashboard.
 *
 * REQ-020 §9.2: Large balance display with color coding.
 * "Add Funds" button disabled until REQ-021 (Credits & Billing).
 */

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
// Helpers
// ---------------------------------------------------------------------------

const BALANCE_THRESHOLD_HIGH = 1.0;
const BALANCE_THRESHOLD_LOW = 0.1;

function getBalanceColor(balance: number): string {
	if (balance >= BALANCE_THRESHOLD_HIGH) return "text-green-600";
	if (balance >= BALANCE_THRESHOLD_LOW) return "text-amber-500";
	return "text-red-500";
}

function formatBalance(raw: string): string {
	const num = Number.parseFloat(raw);
	if (Number.isNaN(num)) return "$0.00";
	return `$${num.toFixed(2)}`;
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

	return (
		<Card data-testid="balance-card">
			<CardHeader>
				<CardTitle>Current Balance</CardTitle>
			</CardHeader>
			<CardContent className="flex items-center justify-between">
				{isLoading ? (
					<Skeleton data-testid="balance-skeleton" className="h-10 w-32" />
				) : (
					<span
						data-testid="balance-amount"
						className={cn("text-4xl font-bold", getBalanceColor(parsed))}
					>
						{balance ? formatBalance(balance) : "$0.00"}
					</span>
				)}
				<Button disabled title="Coming soon — REQ-021">
					Add Funds
				</Button>
			</CardContent>
		</Card>
	);
}
