/**
 * SSE client wrapper with reconnection and tab visibility management.
 *
 * REQ-012 §4.4: Custom EventSource wrapper with exponential backoff
 * reconnection and tab inactive detection.
 */

import { parseSSEEvent } from "../types/sse";

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export interface SSEClientConfig {
	/** SSE endpoint URL (e.g., /api/v1/chat/stream). */
	url: string;
	/** Called on each streaming LLM token. */
	onChatToken: (text: string) => void;
	/** Called when a chat message is complete. */
	onChatDone: (messageId: string) => void;
	/** Called when an agent starts a tool call. */
	onToolStart: (tool: string, args: Record<string, unknown>) => void;
	/** Called when an agent tool call completes. */
	onToolResult: (tool: string, success: boolean) => void;
	/** Called when backend data changes (for cache invalidation). */
	onDataChanged: (resource: string, id: string, action: string) => void;
	/** Called when the SSE connection is lost. */
	onDisconnect: () => void;
	/** Called when the SSE connection is re-established. */
	onReconnect: () => void;
	/** Called whenever the connection status changes. */
	onStatusChange?: (status: ConnectionStatus) => void;
}

export type ConnectionStatus = "connected" | "reconnecting" | "disconnected";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const INITIAL_BACKOFF_MS = 1_000;
const MAX_BACKOFF_MS = 30_000;
const MAX_RECONNECT_ATTEMPTS = 20;
const INACTIVITY_TIMEOUT_MS = 5 * 60 * 1_000;
const MAX_MESSAGE_SIZE = 65_536; // 64 KB

// ---------------------------------------------------------------------------
// SSEClient
// ---------------------------------------------------------------------------

export class SSEClient {
	private readonly config: SSEClientConfig;
	private eventSource: EventSource | null = null;
	private status: ConnectionStatus = "disconnected";
	private reconnectAttempt = 0;
	private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
	private inactivityTimer: ReturnType<typeof setTimeout> | null = null;
	private closedByInactivity = false;
	private isReconnecting = false;
	private destroyed = false;

	constructor(config: SSEClientConfig) {
		if (!config.url.startsWith("/")) {
			throw new Error("SSEClient: url must be a relative path");
		}
		this.config = config;
		document.addEventListener("visibilitychange", this.handleVisibilityChange);
	}

	/** Open an SSE connection to the configured URL. */
	connect(): void {
		if (this.destroyed) return;

		if (this.eventSource) {
			this.eventSource.close();
		}

		this.eventSource = new EventSource(this.config.url);

		this.eventSource.onopen = () => {
			this.updateStatus("connected");
			this.reconnectAttempt = 0;

			if (this.isReconnecting) {
				this.config.onReconnect();
				this.isReconnecting = false;
			}
		};

		this.eventSource.onmessage = (event: MessageEvent) => {
			this.handleMessage(event);
		};

		this.eventSource.onerror = () => {
			this.eventSource?.close();
			this.eventSource = null;
			this.updateStatus("reconnecting");
			this.isReconnecting = true;
			this.config.onDisconnect();
			this.scheduleReconnect();
		};
	}

	/** Explicitly close the SSE connection (no auto-reconnect). */
	disconnect(): void {
		this.clearReconnectTimer();
		this.eventSource?.close();
		this.eventSource = null;
		this.updateStatus("disconnected");
		this.isReconnecting = false;
	}

	/** Get the current connection status. */
	getStatus(): ConnectionStatus {
		return this.status;
	}

	/** Clean up all resources (EventSource, timers, event listeners). */
	destroy(): void {
		if (this.destroyed) return;
		this.destroyed = true;
		this.disconnect();
		this.clearInactivityTimer();
		document.removeEventListener(
			"visibilitychange",
			this.handleVisibilityChange,
		);
	}

	// -----------------------------------------------------------------------
	// Private methods
	// -----------------------------------------------------------------------

	private updateStatus(newStatus: ConnectionStatus): void {
		this.status = newStatus;
		this.config.onStatusChange?.(newStatus);
	}

	private handleMessage(event: MessageEvent): void {
		const data = event.data as string;
		if (data.length > MAX_MESSAGE_SIZE) return;

		const parsed = parseSSEEvent(data);
		if (!parsed) return;

		switch (parsed.type) {
			case "chat_token":
				this.config.onChatToken(parsed.text);
				break;
			case "chat_done":
				this.config.onChatDone(parsed.message_id);
				break;
			case "tool_start":
				this.config.onToolStart(parsed.tool, parsed.args);
				break;
			case "tool_result":
				this.config.onToolResult(parsed.tool, parsed.success);
				break;
			case "data_changed":
				this.config.onDataChanged(parsed.resource, parsed.id, parsed.action);
				break;
			case "heartbeat":
				// No-op — connection keepalive.
				break;
		}
	}

	private scheduleReconnect(): void {
		if (this.reconnectAttempt >= MAX_RECONNECT_ATTEMPTS) {
			this.updateStatus("disconnected");
			return;
		}
		this.clearReconnectTimer();
		const baseDelay = Math.min(
			INITIAL_BACKOFF_MS * 2 ** this.reconnectAttempt,
			MAX_BACKOFF_MS,
		);
		const jitter = 0.5 + Math.random() * 0.5;
		const delay = Math.floor(baseDelay * jitter);
		this.reconnectAttempt += 1;
		this.reconnectTimer = setTimeout(() => {
			this.connect();
		}, delay);
	}

	private clearReconnectTimer(): void {
		if (this.reconnectTimer !== null) {
			clearTimeout(this.reconnectTimer);
			this.reconnectTimer = null;
		}
	}

	private readonly handleVisibilityChange = (): void => {
		if (document.visibilityState === "hidden") {
			if (this.status === "connected") {
				this.startInactivityTimer();
			}
		} else {
			this.clearInactivityTimer();
			if (this.closedByInactivity) {
				this.closedByInactivity = false;
				this.isReconnecting = true;
				this.connect();
			}
		}
	};

	private startInactivityTimer(): void {
		this.clearInactivityTimer();
		this.inactivityTimer = setTimeout(() => {
			this.eventSource?.close();
			this.eventSource = null;
			this.closedByInactivity = true;
			this.updateStatus("disconnected");
		}, INACTIVITY_TIMEOUT_MS);
	}

	private clearInactivityTimer(): void {
		if (this.inactivityTimer !== null) {
			clearTimeout(this.inactivityTimer);
			this.inactivityTimer = null;
		}
	}
}
