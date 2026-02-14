"use client";

/**
 * SSE React context provider.
 *
 * REQ-012 §4.4: Wraps the SSEClient in a React context and wires
 * the SSE-to-TanStack-Query bridge for cache invalidation.
 *
 * Exposes connection status and chat handler registration to the
 * component tree via the `useSSE` hook.
 *
 * Must be rendered inside a QueryClientProvider so that `useQueryClient()`
 * is available — the bridge needs the QueryClient to invalidate queries.
 *
 * Chat-related callbacks are forwarded through refs so that the ChatProvider
 * (mounted later in the tree) can register its handlers without requiring
 * the SSE client to be recreated.
 */

import { useQueryClient } from "@tanstack/react-query";
import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useRef,
	useState,
	type ReactNode,
} from "react";

import type { ChatHandlers } from "../types/chat";

import { notifyEmbeddingComplete } from "./embedding-staleness";
import { SSEClient, type ConnectionStatus } from "./sse-client";
import { createSSEQueryBridge } from "./sse-query-bridge";

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

interface SSEContextValue {
	/** Current SSE connection status. */
	status: ConnectionStatus;
	/**
	 * Register callbacks for SSE chat events.
	 *
	 * Returns a cleanup function that resets handlers to no-ops.
	 * Only one set of handlers can be registered at a time — calling
	 * again replaces the previous handlers.
	 */
	registerChatHandlers: (handlers: ChatHandlers) => () => void;
}

const SSEContext = createContext<SSEContextValue | null>(null);

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Access the SSE connection status and chat handler registration.
 *
 * Must be called within an SSEProvider.
 *
 * @returns Object with `status` and `registerChatHandlers`.
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
// No-op defaults
// ---------------------------------------------------------------------------

const noop = () => {};
const noopToolStart = (_tool: string, _args: Record<string, unknown>) => {};
const noopToolResult = (_tool: string, _success: boolean) => {};

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
 * Provides SSE connectivity, connection status, and chat handler
 * registration to the component tree.
 *
 * Creates an SSEClient on mount, connects to the configured URL, and
 * cleans up (destroy) on unmount. The SSE-to-TanStack-Query bridge
 * is wired automatically — `data_changed` events invalidate the
 * corresponding query cache entries, and reconnection triggers a
 * full cache refresh.
 *
 * Chat callbacks are stored in refs and forwarded to the SSE client.
 * The ChatProvider registers its handlers via `registerChatHandlers`.
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

	// Refs for chat callbacks — start as no-ops, updated via registerChatHandlers
	const chatTokenRef = useRef<(text: string) => void>(noop);
	const chatDoneRef = useRef<(messageId: string) => void>(noop);
	const toolStartRef =
		useRef<(tool: string, args: Record<string, unknown>) => void>(
			noopToolStart,
		);
	const toolResultRef =
		useRef<(tool: string, success: boolean) => void>(noopToolResult);

	const registerChatHandlers = useCallback((handlers: ChatHandlers) => {
		chatTokenRef.current = handlers.onChatToken;
		chatDoneRef.current = handlers.onChatDone;
		toolStartRef.current = handlers.onToolStart;
		toolResultRef.current = handlers.onToolResult;

		return () => {
			chatTokenRef.current = noop;
			chatDoneRef.current = noop;
			toolStartRef.current = noopToolStart;
			toolResultRef.current = noopToolResult;
		};
	}, []);

	useEffect(() => {
		const bridge = createSSEQueryBridge(queryClient, {
			onEmbeddingUpdated: notifyEmbeddingComplete,
		});

		const client = new SSEClient({
			url,
			onChatToken: (text) => chatTokenRef.current(text),
			onChatDone: (messageId) => chatDoneRef.current(messageId),
			onToolStart: (tool, args) => toolStartRef.current(tool, args),
			onToolResult: (tool, success) => toolResultRef.current(tool, success),
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

	return (
		<SSEContext value={{ status, registerChatHandlers }}>{children}</SSEContext>
	);
}
