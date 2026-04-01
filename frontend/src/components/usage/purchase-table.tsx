/**
 * @fileoverview Purchase history table for the usage dashboard.
 *
 * Layer: component
 * Feature: usage
 *
 * REQ-029 §8.3: Paginated table of purchases, grants, and refunds
 * with color-coded signed amounts.
 *
 * Coordinates with:
 * - lib/format-utils.ts: formatDate for date display
 * - lib/utils.ts: cn class-name helper
 * - components/ui/card.tsx: Card, CardContent, CardHeader, CardTitle for layout
 * - components/ui/skeleton.tsx: Skeleton for loading state
 * - components/ui/table-pagination.tsx: TablePagination for page navigation
 * - types/usage.ts: PurchaseItem type
 *
 * Called by / Used by:
 * - components/usage/usage-page.tsx: purchase history table on usage dashboard
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { TablePagination } from "@/components/ui/table-pagination";
import { formatDate } from "@/lib/format-utils";
import { cn } from "@/lib/utils";
import type { PurchaseItem } from "@/types/usage";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PurchaseTableProps {
	purchases: PurchaseItem[];
	isLoading: boolean;
	page: number;
	totalPages: number;
	onPageChange: (page: number) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PurchaseTable({
	purchases,
	isLoading,
	page,
	totalPages,
	onPageChange,
}: Readonly<PurchaseTableProps>) {
	function renderContent() {
		if (isLoading) {
			return (
				<div data-testid="purchase-table-loading" className="space-y-3">
					<Skeleton className="h-6 w-full" />
					<Skeleton className="h-6 w-full" />
					<Skeleton className="h-6 w-full" />
				</div>
			);
		}

		if (purchases.length === 0) {
			return <p className="text-muted-foreground text-sm">No purchases yet.</p>;
		}

		return (
			<>
				<table className="w-full text-sm">
					<thead>
						<tr className="text-muted-foreground border-b text-left">
							<th className="pb-2">Amount</th>
							<th className="pb-2">Type</th>
							<th className="pb-2">Description</th>
							<th className="pb-2 text-right">Date</th>
						</tr>
					</thead>
					<tbody>
						{purchases.map((item) => {
							const num = Number.parseFloat(item.amount_usd);
							const isPositive = num >= 0;

							return (
								<tr key={item.id} className="border-b">
									<td className="py-2">
										<span
											data-testid={`purchase-amount-${item.id}`}
											className={cn(
												"font-medium",
												isPositive ? "text-success" : "text-destructive",
											)}
										>
											{item.amount_display}
										</span>
									</td>
									<td className="py-2">{item.transaction_type}</td>
									<td className="text-muted-foreground py-2">
										{item.description}
									</td>
									<td className="py-2 text-right">
										{formatDate(item.created_at)}
									</td>
								</tr>
							);
						})}
					</tbody>
				</table>

				<TablePagination
					page={page}
					totalPages={totalPages}
					onPageChange={onPageChange}
				/>
			</>
		);
	}

	return (
		<Card>
			<CardHeader>
				<CardTitle>Purchase History</CardTitle>
			</CardHeader>
			<CardContent>{renderContent()}</CardContent>
		</Card>
	);
}
