/**
 * Usage dashboard page layout component.
 *
 * REQ-020 §9.2: Usage page at /usage with balance card,
 * period summary, cost breakdowns, and paginated tables.
 */

"use client";

import { useState } from "react";

import { useQuery } from "@tanstack/react-query";

import { useBalance } from "@/hooks/use-balance";
import { apiGet } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type {
	CreditTransactionResponse,
	UsageRecordResponse,
	UsageSummaryResponse,
} from "@/types/usage";

import { BalanceCard } from "./balance-card";
import { TransactionTable } from "./transaction-table";
import { UsageSummary } from "./usage-summary";
import { UsageTable } from "./usage-table";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getCurrentMonthRange(): { start: string; end: string } {
	const now = new Date();
	const start = new Date(now.getFullYear(), now.getMonth(), 1);
	const end = new Date(now.getFullYear(), now.getMonth() + 1, 0);
	return {
		start: start.toISOString().slice(0, 10),
		end: end.toISOString().slice(0, 10),
	};
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function UsagePage() {
	const { balance, isLoading: balanceLoading } = useBalance();
	const { start, end } = getCurrentMonthRange();

	const { data: summaryData, isLoading: summaryLoading } = useQuery({
		queryKey: queryKeys.usageSummary(start, end),
		queryFn: () =>
			apiGet<ApiResponse<UsageSummaryResponse>>("/usage/summary", {
				period_start: start,
				period_end: end,
			}),
	});

	const [historyPage, setHistoryPage] = useState(1);
	const { data: historyData, isLoading: historyLoading } = useQuery({
		queryKey: queryKeys.usageHistory(historyPage),
		queryFn: () =>
			apiGet<ApiListResponse<UsageRecordResponse>>("/usage/history", {
				page: historyPage,
			}),
	});

	const [txPage, setTxPage] = useState(1);
	const { data: txData, isLoading: txLoading } = useQuery({
		queryKey: queryKeys.usageTransactions(txPage),
		queryFn: () =>
			apiGet<ApiListResponse<CreditTransactionResponse>>(
				"/usage/transactions",
				{ page: txPage },
			),
	});

	return (
		<div data-testid="usage-page" className="space-y-6">
			<h1 className="text-2xl font-bold">Usage &amp; Billing</h1>

			<BalanceCard balance={balance} isLoading={balanceLoading} />

			<UsageSummary data={summaryData?.data} isLoading={summaryLoading} />

			<UsageTable
				records={historyData?.data ?? []}
				isLoading={historyLoading}
				page={historyPage}
				totalPages={historyData?.meta.total_pages ?? 1}
				onPageChange={setHistoryPage}
			/>

			<TransactionTable
				transactions={txData?.data ?? []}
				isLoading={txLoading}
				page={txPage}
				totalPages={txData?.meta.total_pages ?? 1}
				onPageChange={setTxPage}
			/>
		</div>
	);
}
