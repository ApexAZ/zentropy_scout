/**
 * Hook to fetch the user's current balance.
 *
 * REQ-020 §9.1: Balance display in the navigation bar. Fetches from
 * GET /api/v1/usage/balance and auto-refetches every 60 seconds.
 */

import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { ApiResponse } from "@/types/api";
import type { BalanceResponse } from "@/types/usage";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Refetch balance every 60 seconds. */
const REFETCH_INTERVAL_MS = 60_000;

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export interface UseBalanceResult {
	/** Balance string with 6 decimal places, or undefined while loading. */
	balance: string | undefined;
	isLoading: boolean;
	error: Error | null;
}

export function useBalance(): UseBalanceResult {
	const { data, isLoading, error } = useQuery({
		queryKey: queryKeys.balance,
		queryFn: () => apiGet<ApiResponse<BalanceResponse>>("/usage/balance"),
		refetchInterval: REFETCH_INTERVAL_MS,
	});

	return {
		balance: data?.data.balance_usd,
		isLoading,
		error: error instanceof Error ? error : null,
	};
}
