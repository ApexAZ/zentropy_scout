/**
 * TanStack Query client factory.
 *
 * REQ-012 §4.2.1: Server state managed by TanStack Query v5.
 * REQ-012 §13.9: Retry behaviour — 1 retry for queries, 0 for mutations.
 *
 * Configuration rationale:
 * - staleTime 30s: SSE `data_changed` events handle real-time invalidation,
 *   so aggressive background refetching is unnecessary.
 * - refetchOnWindowFocus off: Tab visibility reconnection is handled by the
 *   SSE client (§4.4), which triggers full invalidation on return.
 * - retry 1 for queries: The API client already retries 429s (3 attempts),
 *   so one additional retry at the query layer covers transient failures.
 * - retry 0 for mutations: Mutations should not auto-retry — side effects
 *   could be duplicated.
 */

import { QueryClient } from "@tanstack/react-query";

export function createQueryClient(): QueryClient {
	return new QueryClient({
		defaultOptions: {
			queries: {
				retry: 1,
				staleTime: 30_000,
				refetchOnWindowFocus: false,
			},
			mutations: {
				retry: 0,
			},
		},
	});
}
