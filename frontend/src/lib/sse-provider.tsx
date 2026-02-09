"use client";

/**
 * SSE React context provider.
 *
 * REQ-012 §4.4: Wraps the SSEClient in a React context and wires
 * the SSE-to-TanStack-Query bridge for cache invalidation.
 *
 * Exposes connection status to the component tree via the `useSSE` hook.
 *
 * Must be rendered inside a QueryClientProvider so that `useQueryClient()`
 * is available — the bridge needs the QueryClient to invalidate queries.
 *
 * Chat-related callbacks (onChatToken, onChatDone, onToolStart, onToolResult)
 * are no-ops until the chat feature is implemented in a later phase.
 */

import { useQueryClient } from "@tanstack/react-query";
import {
	createContext,
	useContext,
	useEffect,
	useState,
	type ReactNode,
} from "react";

import { SSEClient, type ConnectionStatus } from "./sse-client";
import { createSSEQueryBridge } from "./sse-query-bridge";

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

interface SSEContextValue {
	/** Current SSE connection status. */
	status: ConnectionStatus;
}

const SSEContext = createContext<SSEContextValue | null>(null);

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Access the SSE connection status.
 *
 * Must be called within an SSEProvider.
 *
 * @returns Object with `status` field ("connected" | "reconnecting" | "disconnected").
 * @throws Error if called outside an SSEProvider.
 */
export function useSSE(): SSEContextValue {
	const ctx = useContext(SSEContext);
	if (!ctx) {
		throw new Error("useSSE must be used within an SSEProvider");
	}
	return ctx;
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

const DEFAULT_SSE_URL = "/api/v1/chat/stream";

interface SSEProviderProps {
	children: ReactNode;
	/** SSE endpoint URL. Defaults to /api/v1/chat/stream. */
	url?: string;
}

/**
 * Provides SSE connectivity and connection status to the component tree.
 *
 * Creates an SSEClient on mount, connects to the configured URL, and
 * cleans up (destroy) on unmount. The SSE-to-TanStack-Query bridge
 * is wired automatically — `data_changed` events invalidate the
 * corresponding query cache entries, and reconnection triggers a
 * full cache refresh.
 *
 * @param props.children - React children to render.
 * @param props.url - SSE endpoint URL (defaults to /api/v1/chat/stream).
 */
export function SSEProvider({
	children,
	url = DEFAULT_SSE_URL,
}: SSEProviderProps) {
	const queryClient = useQueryClient();
	const [status, setStatus] = useState<ConnectionStatus>("disconnected");

	useEffect(() => {
		const bridge = createSSEQueryBridge(queryClient);

		const client = new SSEClient({
			url,
			onChatToken: () => {},
			onChatDone: () => {},
			onToolStart: () => {},
			onToolResult: () => {},
			onDataChanged: bridge.onDataChanged,
			onDisconnect: () => {},
			onReconnect: () => {
				bridge.onReconnect();
			},
			onStatusChange: setStatus,
		});

		client.connect();

		return () => {
			client.destroy();
		};
	}, [queryClient, url]);

	return <SSEContext value={{ status }}>{children}</SSEContext>;
}
