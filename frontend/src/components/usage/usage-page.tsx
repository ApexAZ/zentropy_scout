"use client";

/**
 * Usage dashboard page layout component.
 *
 * REQ-020 §9.2: Usage page at /usage with balance card,
 * period summary, cost breakdowns, and paginated tables.
 * REQ-029 §9.1: Funding packs, purchase history, low-balance warning.
 * REQ-029 §9.4; REQ-030 §10.2: Stripe redirect success/cancel handling.
 */

import { Suspense, useEffect, useState } from "react";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";

import { useBalance } from "@/hooks/use-balance";
import { apiGet } from "@/lib/api-client";
import { fetchPurchases } from "@/lib/api/credits";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type {
	CreditTransactionResponse,
	UsageRecordResponse,
	UsageSummaryResponse,
} from "@/types/usage";

import { BalanceCard } from "./balance-card";
import { FundingPacks } from "./funding-packs";
import { LowBalanceWarning } from "./low-balance-warning";
import { PurchaseTable } from "./purchase-table";
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
// Stripe redirect handler (REQ-029 §9.4)
// ---------------------------------------------------------------------------

function StripeRedirectHandler() {
	const searchParams = useSearchParams();
	const router = useRouter();
	const queryClient = useQueryClient();

	useEffect(() => {
		const status = searchParams.get("status");
		if (status === "success") {
			showToast.success("Payment successful! Your balance has been updated.");
			queryClient.invalidateQueries({ queryKey: queryKeys.balance });
			queryClient.invalidateQueries({ queryKey: queryKeys.purchases });
		} else if (status === "cancelled") {
			showToast.info("Purchase cancelled.");
		}
		if (status === "success" || status === "cancelled") {
			router.replace("/usage");
		}
	}, [searchParams, router, queryClient]);

	return null;
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

	const [purchasePage, setPurchasePage] = useState(1);
	const { data: purchaseData, isLoading: purchaseLoading } = useQuery({
		queryKey: [...queryKeys.purchases, purchasePage],
		queryFn: () => fetchPurchases(purchasePage),
	});

	const balanceNum = balance ? Number.parseFloat(balance) : 0;
	const parsedBalance = Number.isNaN(balanceNum) ? 0 : balanceNum;

	return (
		<div data-testid="usage-page" className="space-y-6">
			<Suspense>
				<StripeRedirectHandler />
			</Suspense>

			<h1 className="text-2xl font-bold">Usage &amp; Billing</h1>

			{!balanceLoading && <LowBalanceWarning balance={parsedBalance} />}

			<BalanceCard balance={balance} isLoading={balanceLoading} />

			<FundingPacks />

			<PurchaseTable
				purchases={purchaseData?.data ?? []}
				isLoading={purchaseLoading}
				page={purchasePage}
				totalPages={purchaseData?.meta.total_pages ?? 1}
				onPageChange={setPurchasePage}
			/>

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
