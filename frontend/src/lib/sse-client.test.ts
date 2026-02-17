import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
	SSEClient,
	type ConnectionStatus,
	type SSEClientConfig,
} from "./sse-client";

// ---------------------------------------------------------------------------
// Test constants
// ---------------------------------------------------------------------------

const TEST_URL = "/api/v1/chat/stream";
const TEST_TOOL_NAME = "search_jobs";
const INITIAL_BACKOFF_MS = 1_000;
const MAX_BACKOFF_MS = 30_000;
const MAX_RECONNECT_ATTEMPTS = 20;
const INACTIVITY_TIMEOUT_MS = 5 * 60 * 1_000;
const MAX_MESSAGE_SIZE = 65_536;

// ---------------------------------------------------------------------------
// Mock EventSource — only implements properties used by SSEClient
// (onopen, onmessage, onerror, close). Does not implement addEventListener
// or other EventTarget methods.
// ---------------------------------------------------------------------------

class MockEventSource {
	static instances: MockEventSource[] = [];
	static readonly CONNECTING = 0;
	static readonly OPEN = 1;
	static readonly CLOSED = 2;

	readonly CONNECTING = 0;
	readonly OPEN = 1;
	readonly CLOSED = 2;

	url: string;
	readyState = MockEventSource.CONNECTING;
	onopen: ((event: Event) => void) | null = null;
	onmessage: ((event: MessageEvent) => void) | null = null;
	onerror: ((event: Event) => void) | null = null;

	constructor(url: string) {
		this.url = url;
		MockEventSource.instances.push(this);
	}

	close = vi.fn(() => {
		this.readyState = MockEventSource.CLOSED;
	});

	simulateOpen(): void {
		this.readyState = MockEventSource.OPEN;
		this.onopen?.(new Event("open"));
	}

	simulateMessage(data: string): void {
		this.onmessage?.(new MessageEvent("message", { data }));
	}

	simulateError(): void {
		this.readyState = MockEventSource.CLOSED;
		this.onerror?.(new Event("error"));
	}
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createConfig(overrides?: Partial<SSEClientConfig>): SSEClientConfig {
	return {
		url: TEST_URL,
		onChatToken: vi.fn(),
		onChatDone: vi.fn(),
		onToolStart: vi.fn(),
		onToolResult: vi.fn(),
		onDataChanged: vi.fn(),
		onDisconnect: vi.fn(),
		onReconnect: vi.fn(),
		...overrides,
	};
}

function latestES(): MockEventSource {
	return MockEventSource.instances[MockEventSource.instances.length - 1];
}

function setTabHidden(hidden: boolean): void {
	Object.defineProperty(document, "visibilityState", {
		value: hidden ? "hidden" : "visible",
		configurable: true,
	});
	document.dispatchEvent(new Event("visibilitychange"));
}

// ---------------------------------------------------------------------------
// SSEClient
// ---------------------------------------------------------------------------

describe("SSEClient", () => {
	const clients: SSEClient[] = [];

	function createClient(config: SSEClientConfig): SSEClient {
		const c = new SSEClient(config);
		clients.push(c);
		return c;
	}

	beforeEach(() => {
		vi.useFakeTimers();
		MockEventSource.instances = [];
		vi.stubGlobal("EventSource", MockEventSource);
		// Jitter factor = 0.5 + (0xffffffff / 0xffffffff) * 0.5 = 1.0 → no effective jitter.
		// Individual tests override this to verify jitter behavior.
		vi.spyOn(crypto, "getRandomValues").mockImplementation((arr) => {
			(arr as Uint32Array)[0] = 0xffffffff;
			return arr;
		});
	});

	afterEach(() => {
		for (const c of clients) c.destroy();
		clients.length = 0;
		Object.defineProperty(document, "visibilityState", {
			value: "visible",
			configurable: true,
		});
		vi.useRealTimers();
		vi.restoreAllMocks();
	});

	// --- construction ---

	describe("construction", () => {
		it("throws if URL is not a relative path", () => {
			const config = createConfig({ url: "https://evil.com/sse" });
			expect(() => createClient(config)).toThrow(
				"SSEClient: url must be a relative path",
			);
		});

		it("accepts a relative path URL", () => {
			const config = createConfig({ url: "/api/v1/chat/stream" });
			expect(() => createClient(config)).not.toThrow();
		});
	});

	// --- connection lifecycle ---

	describe("connection lifecycle", () => {
		it("creates an EventSource with the configured URL on connect", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();

			expect(MockEventSource.instances).toHaveLength(1);
			expect(latestES().url).toBe(TEST_URL);
		});

		it("transitions to connected on EventSource open", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();

			expect(client.getStatus()).toBe<ConnectionStatus>("connected");
		});

		it("starts with disconnected status", () => {
			const config = createConfig();
			const client = createClient(config);

			expect(client.getStatus()).toBe<ConnectionStatus>("disconnected");
		});

		it("closes EventSource and sets disconnected on disconnect", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();
			client.disconnect();

			expect(latestES().close).toHaveBeenCalled();
			expect(client.getStatus()).toBe<ConnectionStatus>("disconnected");
		});

		it("does not fire onDisconnect for explicit disconnect", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();
			client.disconnect();

			expect(config.onDisconnect).not.toHaveBeenCalled();
		});

		it("does not fire onReconnect on initial connection", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();

			expect(config.onReconnect).not.toHaveBeenCalled();
		});
	});

	// --- onStatusChange callback ---

	describe("onStatusChange", () => {
		it("fires with connected on initial open", () => {
			const onStatusChange = vi.fn();
			const config = createConfig({ onStatusChange });
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();

			expect(onStatusChange).toHaveBeenCalledWith("connected");
		});

		it("fires with reconnecting on error", () => {
			const onStatusChange = vi.fn();
			const config = createConfig({ onStatusChange });
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();
			onStatusChange.mockClear();

			latestES().simulateError();

			expect(onStatusChange).toHaveBeenCalledWith("reconnecting");
		});

		it("fires with disconnected on explicit disconnect", () => {
			const onStatusChange = vi.fn();
			const config = createConfig({ onStatusChange });
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();
			onStatusChange.mockClear();

			client.disconnect();

			expect(onStatusChange).toHaveBeenCalledWith("disconnected");
		});

		it("is optional — works without it", () => {
			const config = createConfig();
			delete config.onStatusChange;
			const client = createClient(config);

			expect(() => {
				client.connect();
				latestES().simulateOpen();
			}).not.toThrow();
		});
	});

	// --- event dispatching ---

	describe("event dispatching", () => {
		it("dispatches chat_token to onChatToken", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();

			latestES().simulateMessage(
				JSON.stringify({ type: "chat_token", text: "Hello" }),
			);

			expect(config.onChatToken).toHaveBeenCalledWith("Hello");
		});

		it("dispatches chat_done to onChatDone", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();

			latestES().simulateMessage(
				JSON.stringify({ type: "chat_done", message_id: "msg-123" }),
			);

			expect(config.onChatDone).toHaveBeenCalledWith("msg-123");
		});

		it("dispatches tool_start to onToolStart", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();

			latestES().simulateMessage(
				JSON.stringify({
					type: "tool_start",
					tool: TEST_TOOL_NAME,
					args: { query: "react" },
				}),
			);

			expect(config.onToolStart).toHaveBeenCalledWith(TEST_TOOL_NAME, {
				query: "react",
			});
		});

		it("dispatches tool_result to onToolResult", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();

			latestES().simulateMessage(
				JSON.stringify({
					type: "tool_result",
					tool: TEST_TOOL_NAME,
					success: true,
					result: null,
					error: null,
				}),
			);

			expect(config.onToolResult).toHaveBeenCalledWith(TEST_TOOL_NAME, true);
		});

		it("dispatches data_changed to onDataChanged", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();

			latestES().simulateMessage(
				JSON.stringify({
					type: "data_changed",
					resource: "job-posting",
					id: "uuid-1",
					action: "updated",
				}),
			);

			expect(config.onDataChanged).toHaveBeenCalledWith(
				"job-posting",
				"uuid-1",
				"updated",
			);
		});

		it("silently ignores heartbeat events", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();

			latestES().simulateMessage(JSON.stringify({ type: "heartbeat" }));

			expect(config.onChatToken).not.toHaveBeenCalled();
			expect(config.onChatDone).not.toHaveBeenCalled();
			expect(config.onToolStart).not.toHaveBeenCalled();
			expect(config.onToolResult).not.toHaveBeenCalled();
			expect(config.onDataChanged).not.toHaveBeenCalled();
		});

		it("silently ignores invalid JSON", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();

			latestES().simulateMessage("not valid json");

			expect(config.onChatToken).not.toHaveBeenCalled();
		});

		it("silently ignores unknown event types", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();

			latestES().simulateMessage(JSON.stringify({ type: "unknown_type" }));

			expect(config.onChatToken).not.toHaveBeenCalled();
		});

		it("silently ignores messages exceeding size limit", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();

			const hugePayload = "x".repeat(MAX_MESSAGE_SIZE + 1);
			latestES().simulateMessage(hugePayload);

			expect(config.onChatToken).not.toHaveBeenCalled();
		});
	});

	// --- reconnection ---

	describe("reconnection", () => {
		it("transitions to reconnecting on EventSource error", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();
			latestES().simulateError();

			expect(client.getStatus()).toBe<ConnectionStatus>("reconnecting");
		});

		it("fires onDisconnect on EventSource error", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();
			latestES().simulateError();

			expect(config.onDisconnect).toHaveBeenCalledTimes(1);
		});

		it("reconnects after 1 second initial backoff", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateError();

			expect(MockEventSource.instances).toHaveLength(1);

			vi.advanceTimersByTime(INITIAL_BACKOFF_MS);

			expect(MockEventSource.instances).toHaveLength(2);
			expect(latestES().url).toBe(TEST_URL);
		});

		it("doubles backoff on consecutive failures: 1s, 2s, 4s", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();

			// Failure 1 → 1s backoff
			latestES().simulateError();
			vi.advanceTimersByTime(INITIAL_BACKOFF_MS);
			expect(MockEventSource.instances).toHaveLength(2);

			// Failure 2 → 2s backoff
			latestES().simulateError();
			vi.advanceTimersByTime(2 * INITIAL_BACKOFF_MS);
			expect(MockEventSource.instances).toHaveLength(3);

			// Failure 3 → 4s backoff
			latestES().simulateError();
			vi.advanceTimersByTime(4 * INITIAL_BACKOFF_MS);
			expect(MockEventSource.instances).toHaveLength(4);
		});

		it("caps backoff at 30 seconds", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();

			// Burn through 5 failures: 1s, 2s, 4s, 8s, 16s
			const backoffs = [1000, 2000, 4000, 8000, 16000];
			for (const delay of backoffs) {
				latestES().simulateError();
				vi.advanceTimersByTime(delay);
			}

			// 6th failure → backoff should be 30s (capped from 32s)
			const countBefore = MockEventSource.instances.length;
			latestES().simulateError();

			vi.advanceTimersByTime(MAX_BACKOFF_MS - 1);
			expect(MockEventSource.instances).toHaveLength(countBefore);

			vi.advanceTimersByTime(1);
			expect(MockEventSource.instances).toHaveLength(countBefore + 1);
		});

		it("resets backoff after successful reconnection", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();

			// First failure → 1s backoff
			latestES().simulateError();
			vi.advanceTimersByTime(INITIAL_BACKOFF_MS);

			// Successful reconnect → reset
			latestES().simulateOpen();

			// Another failure → should use 1s again (not 2s)
			latestES().simulateError();
			const countBefore = MockEventSource.instances.length;
			vi.advanceTimersByTime(INITIAL_BACKOFF_MS);
			expect(MockEventSource.instances).toHaveLength(countBefore + 1);
		});

		it("fires onReconnect on successful reconnection", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();

			latestES().simulateError();
			vi.advanceTimersByTime(INITIAL_BACKOFF_MS);
			latestES().simulateOpen();

			expect(config.onReconnect).toHaveBeenCalledTimes(1);
		});

		it("applies jitter to backoff delay", () => {
			// crypto value = 0 → jitter = 0.5 + 0 * 0.5 = 0.5 → delay = 500ms
			vi.spyOn(crypto, "getRandomValues").mockImplementation((arr) => {
				(arr as Uint32Array)[0] = 0;
				return arr;
			});
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateError();

			vi.advanceTimersByTime(499);
			expect(MockEventSource.instances).toHaveLength(1);

			vi.advanceTimersByTime(1);
			expect(MockEventSource.instances).toHaveLength(2);
		});

		it("stops reconnecting after maximum attempts", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();

			// Exhaust all reconnect attempts
			for (let i = 0; i < MAX_RECONNECT_ATTEMPTS; i++) {
				latestES().simulateError();
				vi.advanceTimersByTime(MAX_BACKOFF_MS);
			}

			// One more error — should not schedule another reconnect
			const countBefore = MockEventSource.instances.length;
			latestES().simulateError();
			vi.advanceTimersByTime(MAX_BACKOFF_MS * 2);
			expect(MockEventSource.instances).toHaveLength(countBefore);
			expect(client.getStatus()).toBe<ConnectionStatus>("disconnected");
		});

		it("cancels pending reconnect on explicit disconnect", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();
			latestES().simulateError(); // schedules 1s reconnect

			client.disconnect();

			vi.advanceTimersByTime(INITIAL_BACKOFF_MS * 2);
			expect(MockEventSource.instances).toHaveLength(1);
		});
	});

	// --- tab visibility ---

	describe("tab visibility", () => {
		it("does not close SSE before 5 minutes of tab inactivity", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();

			setTabHidden(true);
			vi.advanceTimersByTime(INACTIVITY_TIMEOUT_MS - 1);

			expect(client.getStatus()).toBe<ConnectionStatus>("connected");
		});

		it("closes SSE after 5 minutes of tab inactivity", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();

			setTabHidden(true);
			vi.advanceTimersByTime(INACTIVITY_TIMEOUT_MS);

			expect(latestES().close).toHaveBeenCalled();
		});

		it("reconnects and fires onReconnect when tab returns after 5+ minutes", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();

			setTabHidden(true);
			vi.advanceTimersByTime(INACTIVITY_TIMEOUT_MS);

			const countBefore = MockEventSource.instances.length;

			setTabHidden(false);

			expect(MockEventSource.instances).toHaveLength(countBefore + 1);

			latestES().simulateOpen();
			expect(config.onReconnect).toHaveBeenCalledTimes(1);
		});

		it("does not reconnect when tab returns within 5 minutes", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();

			setTabHidden(true);
			vi.advanceTimersByTime(INACTIVITY_TIMEOUT_MS - 1);

			setTabHidden(false);

			expect(MockEventSource.instances).toHaveLength(1);
			expect(config.onReconnect).not.toHaveBeenCalled();
		});
	});

	// --- cleanup ---

	describe("cleanup", () => {
		it("clears all timers and EventSource on destroy", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();
			latestES().simulateError(); // schedules reconnect

			client.destroy();

			vi.advanceTimersByTime(MAX_BACKOFF_MS * 2);
			// Only the original EventSource should exist
			expect(MockEventSource.instances).toHaveLength(1);
		});

		it("removes visibilitychange listener on destroy", () => {
			const spy = vi.spyOn(document, "removeEventListener");
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();

			client.destroy();

			expect(spy).toHaveBeenCalledWith(
				"visibilitychange",
				expect.any(Function),
			);
		});

		it("is safe to call destroy multiple times", () => {
			const config = createConfig();
			const client = createClient(config);
			client.connect();
			latestES().simulateOpen();

			expect(() => {
				client.destroy();
				client.destroy();
			}).not.toThrow();
		});

		it("ignores connect calls after destroy", () => {
			const config = createConfig();
			const client = createClient(config);
			client.destroy();
			client.connect();

			expect(MockEventSource.instances).toHaveLength(0);
		});
	});
});
