/**
 * Usage records table for the usage dashboard.
 *
 * REQ-020 §9.2: Recent activity — paginated table showing
 * provider, model, task type, tokens, cost, and date.
 */

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCost, formatDate, formatNumber } from "@/lib/format-utils";
import { Skeleton } from "@/components/ui/skeleton";
import type { UsageRecordResponse } from "@/types/usage";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UsageTableProps {
	records: UsageRecordResponse[];
	isLoading: boolean;
	page: number;
	totalPages: number;
	onPageChange: (page: number) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function UsageTable({
	records,
	isLoading,
	page,
	totalPages,
	onPageChange,
}: Readonly<UsageTableProps>) {
	function renderContent() {
		if (isLoading) {
			return (
				<div data-testid="usage-table-loading" className="space-y-3">
					<Skeleton className="h-6 w-full" />
					<Skeleton className="h-6 w-full" />
					<Skeleton className="h-6 w-full" />
				</div>
			);
		}

		if (records.length === 0) {
			return (
				<p className="text-muted-foreground text-sm">No usage records yet.</p>
			);
		}

		return (
			<>
				<table className="w-full text-sm">
					<thead>
						<tr className="text-muted-foreground border-b text-left">
							<th className="pb-2">Provider</th>
							<th className="pb-2">Model</th>
							<th className="pb-2">Task</th>
							<th className="pb-2 text-right">Tokens</th>
							<th className="pb-2 text-right">Cost</th>
							<th className="pb-2 text-right">Date</th>
						</tr>
					</thead>
					<tbody>
						{records.map((record) => (
							<tr key={record.id} className="border-b">
								<td className="py-2">{record.provider}</td>
								<td className="py-2">{record.model}</td>
								<td className="py-2">{record.task_type}</td>
								<td className="py-2 text-right">
									{formatNumber(record.input_tokens + record.output_tokens)}
								</td>
								<td className="py-2 text-right">
									{formatCost(record.billed_cost_usd, true)}
								</td>
								<td className="py-2 text-right">
									{formatDate(record.created_at)}
								</td>
							</tr>
						))}
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
		);
	}

	return (
		<Card>
			<CardHeader>
				<CardTitle>Recent Activity</CardTitle>
			</CardHeader>
			<CardContent>{renderContent()}</CardContent>
		</Card>
	);
}
