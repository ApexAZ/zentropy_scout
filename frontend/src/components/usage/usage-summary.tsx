/**
 * Usage summary component for the usage dashboard.
 *
 * REQ-020 §9.2: Period summary showing total cost, call count,
 * token usage, and breakdowns by task type and provider.
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCost, formatNumber } from "@/lib/format-utils";
import { Skeleton } from "@/components/ui/skeleton";
import type { UsageSummaryResponse } from "@/types/usage";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UsageSummaryProps {
	data: UsageSummaryResponse | undefined;
	isLoading: boolean;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SECTION_TITLE = "Period Summary";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function UsageSummary({ data, isLoading }: Readonly<UsageSummaryProps>) {
	if (isLoading) {
		return (
			<Card>
				<CardHeader>
					<CardTitle>{SECTION_TITLE}</CardTitle>
				</CardHeader>
				<CardContent data-testid="summary-loading">
					<div className="space-y-3">
						<Skeleton className="h-6 w-48" />
						<Skeleton className="h-6 w-36" />
						<Skeleton className="h-6 w-40" />
					</div>
				</CardContent>
			</Card>
		);
	}

	if (!data) {
		return (
			<Card>
				<CardHeader>
					<CardTitle>{SECTION_TITLE}</CardTitle>
				</CardHeader>
				<CardContent>
					<p className="text-muted-foreground text-sm">
						No usage data for this period.
					</p>
				</CardContent>
			</Card>
		);
	}

	return (
		<Card>
			<CardHeader>
				<CardTitle>{SECTION_TITLE}</CardTitle>
			</CardHeader>
			<CardContent className="space-y-6">
				{/* Summary stats */}
				<div className="grid grid-cols-3 gap-4">
					<div>
						<p className="text-muted-foreground text-sm">Total Calls</p>
						<p data-testid="total-calls" className="text-2xl font-bold">
							{formatNumber(data.total_calls)}
						</p>
					</div>
					<div>
						<p className="text-muted-foreground text-sm">Total Cost</p>
						<p data-testid="total-cost" className="text-2xl font-bold">
							{formatCost(data.total_billed_cost_usd)}
						</p>
					</div>
					<div>
						<p className="text-muted-foreground text-sm">Total Tokens</p>
						<p data-testid="total-tokens" className="text-2xl font-bold">
							{formatNumber(data.total_input_tokens + data.total_output_tokens)}
						</p>
					</div>
				</div>

				{/* Task type breakdown */}
				{data.by_task_type.length > 0 && (
					<div>
						<h3 className="mb-2 text-sm font-medium">By Task Type</h3>
						<table className="w-full text-sm">
							<thead>
								<tr className="text-muted-foreground border-b text-left">
									<th className="pb-2">Task</th>
									<th className="pb-2 text-right">Calls</th>
									<th className="pb-2 text-right">Cost</th>
								</tr>
							</thead>
							<tbody>
								{data.by_task_type.map((row) => (
									<tr key={row.task_type} className="border-b">
										<td className="py-2">{row.task_type}</td>
										<td className="py-2 text-right">
											{formatNumber(row.call_count)}
										</td>
										<td className="py-2 text-right">
											{formatCost(row.billed_cost_usd)}
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				)}

				{/* Provider breakdown */}
				{data.by_provider.length > 0 && (
					<div>
						<h3 className="mb-2 text-sm font-medium">By Provider</h3>
						<table className="w-full text-sm">
							<thead>
								<tr className="text-muted-foreground border-b text-left">
									<th className="pb-2">Provider</th>
									<th className="pb-2 text-right">Calls</th>
									<th className="pb-2 text-right">Cost</th>
								</tr>
							</thead>
							<tbody>
								{data.by_provider.map((row) => (
									<tr key={row.provider} className="border-b">
										<td className="py-2">{row.provider}</td>
										<td className="py-2 text-right">
											{formatNumber(row.call_count)}
										</td>
										<td className="py-2 text-right">
											{formatCost(row.billed_cost_usd)}
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				)}
			</CardContent>
		</Card>
	);
}
