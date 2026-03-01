/**
 * Transaction history table for the usage dashboard.
 *
 * REQ-020 §9.2: Transaction history — paginated table with
 * color-coded amounts (green for credits, red for debits).
 */

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate } from "@/lib/format-utils";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { CreditTransactionResponse } from "@/types/usage";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface TransactionTableProps {
	transactions: CreditTransactionResponse[];
	isLoading: boolean;
	page: number;
	totalPages: number;
	onPageChange: (page: number) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatAmount(raw: string): string {
	const num = Number.parseFloat(raw);
	if (Number.isNaN(num)) return "$0.00";
	const prefix = num >= 0 ? "+" : "";
	return `${prefix}$${Math.abs(num).toFixed(2)}`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TransactionTable({
	transactions,
	isLoading,
	page,
	totalPages,
	onPageChange,
}: Readonly<TransactionTableProps>) {
	return (
		<Card>
			<CardHeader>
				<CardTitle>Transaction History</CardTitle>
			</CardHeader>
			<CardContent>
				{isLoading ? (
					<div data-testid="transaction-table-loading" className="space-y-3">
						<Skeleton className="h-6 w-full" />
						<Skeleton className="h-6 w-full" />
						<Skeleton className="h-6 w-full" />
					</div>
				) : transactions.length === 0 ? (
					<p className="text-muted-foreground text-sm">No transactions yet.</p>
				) : (
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
								{transactions.map((tx) => {
									const num = Number.parseFloat(tx.amount_usd);
									const isPositive = num >= 0;

									return (
										<tr key={tx.id} className="border-b">
											<td className="py-2">
												<span
													data-testid={`tx-amount-${tx.id}`}
													className={cn(
														"font-medium",
														isPositive ? "text-green-600" : "text-red-500",
													)}
												>
													{formatAmount(tx.amount_usd)}
												</span>
											</td>
											<td className="py-2">{tx.transaction_type}</td>
											<td className="text-muted-foreground py-2">
												{tx.description ?? "—"}
											</td>
											<td className="py-2 text-right">
												{formatDate(tx.created_at)}
											</td>
										</tr>
									);
								})}
							</tbody>
						</table>

						{/* Pagination */}
						{totalPages > 1 && (
							<div className="mt-4 flex items-center justify-between">
								<p className="text-muted-foreground text-sm">
									Page {page} of {totalPages}
								</p>
								<div className="flex gap-2">
									<Button
										variant="outline"
										size="sm"
										disabled={page <= 1}
										onClick={() => onPageChange(page - 1)}
									>
										Previous
									</Button>
									<Button
										variant="outline"
										size="sm"
										disabled={page >= totalPages}
										onClick={() => onPageChange(page + 1)}
									>
										Next
									</Button>
								</div>
							</div>
						)}
					</>
				)}
			</CardContent>
		</Card>
	);
}
