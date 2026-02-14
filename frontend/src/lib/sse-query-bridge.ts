/**
 * SSE-to-TanStack-Query bridge.
 *
 * REQ-012 §4.2.1: Maps SSE `data_changed` events to TanStack Query
 * cache invalidation. On reconnect, invalidates all active queries
 * to ensure stale data is refreshed.
 *
 * The bridge provides callback functions suitable for SSEClientConfig's
 * `onDataChanged` and `onReconnect` fields.
 */

import type { QueryClient } from "@tanstack/react-query";

import { queryKeys } from "./query-keys";

// ---------------------------------------------------------------------------
// Resource → query key mapping
// ---------------------------------------------------------------------------

/**
 * Maps SSE resource names to their corresponding TanStack Query list keys.
 *
 * Uses a Map (not a plain object) to avoid prototype chain lookups —
 * prevents prototype pollution if an attacker sends resource names like
 * "__proto__" or "constructor" via a compromised SSE stream.
 *
 * List keys act as prefixes — invalidating `['jobs']` also invalidates
 * detail keys like `['jobs', 'abc-123']` via TanStack Query prefix matching.
 */
export const RESOURCE_QUERY_KEY_MAP = new Map<string, readonly string[]>([
	["persona", queryKeys.personas],
	["job-posting", queryKeys.jobs],
	["application", queryKeys.applications],
	["resume", queryKeys.resumes],
	["variant", queryKeys.variants],
	["cover-letter", queryKeys.coverLetters],
	["change-flag", queryKeys.changeFlags],
	["embedding", queryKeys.jobs],
]);

// ---------------------------------------------------------------------------
// Invalidation handlers
// ---------------------------------------------------------------------------

/**
 * Invalidate the TanStack Query cache for a changed resource.
 *
 * Called by the SSE client's `onDataChanged` callback. Maps the resource
 * name to the corresponding query list key and invalidates all matching
 * queries (list + detail via prefix matching).
 *
 * Unknown resources are silently ignored.
 *
 * @param queryClient - TanStack QueryClient instance.
 * @param resource - SSE resource name (e.g., "job-posting").
 * @param id - Resource identifier.
 * @param action - Change action ("created" | "updated" | "deleted").
 */
export function handleDataChanged(
	queryClient: QueryClient,
	resource: string,
	_id: string,
	_action: string,
): void {
	const listKey = RESOURCE_QUERY_KEY_MAP.get(resource);
	if (!listKey) return;

	queryClient.invalidateQueries({ queryKey: listKey });
}

/**
 * Invalidate ALL queries in the cache.
 *
 * Called after SSE reconnection or tab return from extended inactivity
 * to ensure stale data is refreshed (REQ-012 §4.4).
 *
 * @param queryClient - TanStack QueryClient instance.
 */
export function handleReconnect(queryClient: QueryClient): void {
	queryClient.invalidateQueries();
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

/**
 * Options for the SSE query bridge factory.
 */
export interface SSEQueryBridgeOptions {
	/**
	 * Called when embedding regeneration completes (SSE `data_changed`
	 * with resource "embedding"). Used to show user notifications.
	 *
	 * REQ-012 §7.7: "Match profile updated. Job scores may have changed."
	 */
	onEmbeddingUpdated?: () => void;
}

/**
 * Create SSE callback handlers wired to a QueryClient.
 *
 * Returns `onDataChanged` and `onReconnect` callbacks suitable for
 * use in an SSEClientConfig.
 *
 * @param queryClient - TanStack QueryClient instance.
 * @param options - Optional callbacks for specific resource events.
 * @returns Object with `onDataChanged` and `onReconnect` callbacks.
 */
export function createSSEQueryBridge(
	queryClient: QueryClient,
	options?: SSEQueryBridgeOptions,
): {
	onDataChanged: (resource: string, id: string, action: string) => void;
	onReconnect: () => void;
} {
	return {
		onDataChanged: (resource: string, id: string, action: string) => {
			handleDataChanged(queryClient, resource, id, action);
			if (resource === "embedding" && options?.onEmbeddingUpdated) {
				options.onEmbeddingUpdated();
			}
		},
		onReconnect: () => {
			handleReconnect(queryClient);
		},
	};
}
