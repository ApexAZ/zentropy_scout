/**
 * @fileoverview Usage records table for the usage dashboard.
 *
 * Layer: component
 * Feature: usage
 *
 * REQ-020 §9.2: Recent activity — paginated table showing
 * provider, model, task type, tokens, cost, and date.
 *
 * Coordinates with:
 * - lib/format-utils.ts: formatCost, formatDate, formatNumber for display formatting
 * - components/ui/card.tsx: Card, CardContent, CardHeader, CardTitle for layout
 * - components/ui/skeleton.tsx: Skeleton for loading state
 * - components/ui/table-pagination.tsx: TablePagination for page navigation
 * - types/usage.ts: UsageRecordResponse type
 *
 * Called by / Used by:
 * - components/usage/usage-page.tsx: usage records table on usage dashboard
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { TablePagination } from "@/components/ui/table-pagination";
import { formatCost, formatDate, formatNumber } from "@/lib/format-utils";
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
				<CardTitle>Recent Activity</CardTitle>
			</CardHeader>
			<CardContent>{renderContent()}</CardContent>
		</Card>
	);
}
