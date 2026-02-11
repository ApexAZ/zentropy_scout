/**
 * Tests for the chat context provider.
 *
 * REQ-012 §5: Chat interface state management — message list,
 * streaming state, SSE callback wiring, and message sending.
 */

import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ChatHandlers, ChatMessage } from "../types/chat";

import { ChatProvider, useChat } from "./chat-provider";

// ---------------------------------------------------------------------------
// Test constants
// ---------------------------------------------------------------------------

const MESSAGES_TEST_ID = "messages";
const STREAMING_TEST_ID = "streaming";
const LOADING_HISTORY_TEST_ID = "loading-history";
const SEND_BUTTON_TEST_ID = "send-btn";
const SYSTEM_BUTTON_TEST_ID = "system-btn";
const CLEAR_BUTTON_TEST_ID = "clear-btn";
const LOAD_HISTORY_BUTTON_TEST_ID = "load-history-btn";
const CHILD_TEST_ID = "child";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let capturedHandlers: ChatHandlers | null = null;
const mockUnregister = vi.fn();

vi.mock("./sse-provider", () => ({
	useSSE: () => ({
		status: "connected" as const,
		registerChatHandlers: (handlers: ChatHandlers) => {
			capturedHandlers = handlers;
			return mockUnregister;
		},
	}),
}));

const mockApiPost = vi.fn();
const mockApiGet = vi.fn();
vi.mock("./api-client", () => ({
	apiPost: (...args: unknown[]) => mockApiPost(...args),
	apiGet: (...args: unknown[]) => mockApiGet(...args),
}));

let uuidCounter = 0;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function TestConsumer() {
	const {
		messages,
		isStreaming,
		isLoadingHistory,
		sendMessage,
		addSystemMessage,
		clearMessages,
		loadHistory,
	} = useChat();
	return (
		<div>
			<div data-testid={MESSAGES_TEST_ID}>{JSON.stringify(messages)}</div>
			<div data-testid={STREAMING_TEST_ID}>{String(isStreaming)}</div>
			<div data-testid={LOADING_HISTORY_TEST_ID}>
				{String(isLoadingHistory)}
			</div>
			<button
				data-testid={SEND_BUTTON_TEST_ID}
				onClick={() => sendMessage("hello")}
			>
				Send
			</button>
			<button
				data-testid={SYSTEM_BUTTON_TEST_ID}
				onClick={() => addSystemMessage("Connected")}
			>
				System
			</button>
			<button data-testid={CLEAR_BUTTON_TEST_ID} onClick={clearMessages}>
				Clear
			</button>
			<button data-testid={LOAD_HISTORY_BUTTON_TEST_ID} onClick={loadHistory}>
				Load History
			</button>
		</div>
	);
}

function getMessages(): ChatMessage[] {
	return JSON.parse(
		screen.getByTestId(MESSAGES_TEST_ID).textContent ?? "[]",
	) as ChatMessage[];
}

function getIsStreaming(): boolean {
	return screen.getByTestId(STREAMING_TEST_ID).textContent === "true";
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
	capturedHandlers = null;
	uuidCounter = 0;
	mockApiPost.mockResolvedValue({ data: { id: "backend-msg-1" } });
	mockApiGet.mockResolvedValue([]);

	// Deterministic UUID generation
	vi.spyOn(crypto, "randomUUID").mockImplementation(
		() =>
			`test-uuid-${++uuidCounter}` as `${string}-${string}-${string}-${string}-${string}`,
	);
});

// ---------------------------------------------------------------------------
// Tests: ChatProvider
// ---------------------------------------------------------------------------

describe("ChatProvider", () => {
	// -----------------------------------------------------------------------
	// Rendering
	// -----------------------------------------------------------------------

	it("renders children", () => {
		render(
			<ChatProvider>
				<div data-testid={CHILD_TEST_ID}>Hello</div>
			</ChatProvider>,
		);

		expect(screen.getByTestId(CHILD_TEST_ID)).toHaveTextContent("Hello");
	});

	// -----------------------------------------------------------------------
	// Initial state
	// -----------------------------------------------------------------------

	it("provides empty messages initially", () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		expect(getMessages()).toEqual([]);
	});

	it("provides isStreaming as false initially", () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		expect(getIsStreaming()).toBe(false);
	});

	// -----------------------------------------------------------------------
	// SSE handler registration
	// -----------------------------------------------------------------------

	it("registers chat handlers with SSE provider on mount", () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		expect(capturedHandlers).not.toBeNull();
		expect(typeof capturedHandlers!.onChatToken).toBe("function");
		expect(typeof capturedHandlers!.onChatDone).toBe("function");
		expect(typeof capturedHandlers!.onToolStart).toBe("function");
		expect(typeof capturedHandlers!.onToolResult).toBe("function");
	});

	it("unregisters chat handlers on unmount", () => {
		const { unmount } = render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		unmount();

		expect(mockUnregister).toHaveBeenCalledTimes(1);
	});

	// -----------------------------------------------------------------------
	// sendMessage
	// -----------------------------------------------------------------------

	it("adds user message to list on sendMessage", async () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		await act(async () => {
			screen.getByTestId(SEND_BUTTON_TEST_ID).click();
		});

		const messages = getMessages();
		expect(messages).toHaveLength(1);
		expect(messages[0].role).toBe("user");
		expect(messages[0].content).toBe("hello");
		expect(messages[0].isStreaming).toBe(false);
		expect(messages[0].tools).toEqual([]);
	});

	it("sets isStreaming to true after sendMessage", async () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		await act(async () => {
			screen.getByTestId(SEND_BUTTON_TEST_ID).click();
		});

		expect(getIsStreaming()).toBe(true);
	});

	it("POSTs to /chat/messages endpoint", async () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		await act(async () => {
			screen.getByTestId(SEND_BUTTON_TEST_ID).click();
		});

		expect(mockApiPost).toHaveBeenCalledWith("/chat/messages", {
			content: "hello",
		});
	});

	it("prevents sending while streaming", async () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		// First send
		await act(async () => {
			screen.getByTestId(SEND_BUTTON_TEST_ID).click();
		});

		// Second send while still streaming
		await act(async () => {
			screen.getByTestId(SEND_BUTTON_TEST_ID).click();
		});

		expect(mockApiPost).toHaveBeenCalledTimes(1);
		expect(getMessages()).toHaveLength(1);
	});

	it("adds error system message on send failure", async () => {
		mockApiPost.mockRejectedValueOnce(new Error("Network error"));

		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		await act(async () => {
			screen.getByTestId(SEND_BUTTON_TEST_ID).click();
		});

		const messages = getMessages();
		expect(messages).toHaveLength(2);
		expect(messages[0].role).toBe("user");
		expect(messages[1].role).toBe("system");
		expect(messages[1].content).toBe(
			"Failed to send message. Please try again.",
		);
	});

	it("resets isStreaming on send failure", async () => {
		mockApiPost.mockRejectedValueOnce(new Error("Network error"));

		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		await act(async () => {
			screen.getByTestId(SEND_BUTTON_TEST_ID).click();
		});

		expect(getIsStreaming()).toBe(false);
	});

	// -----------------------------------------------------------------------
	// SSE: chat_token
	// -----------------------------------------------------------------------

	it("creates agent message on first chat_token", () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		act(() => {
			capturedHandlers!.onChatToken("Hello ");
		});

		const messages = getMessages();
		expect(messages).toHaveLength(1);
		expect(messages[0].role).toBe("agent");
		expect(messages[0].content).toBe("Hello ");
		expect(messages[0].isStreaming).toBe(true);
	});

	it("appends to existing agent message on subsequent chat_token", () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		act(() => {
			capturedHandlers!.onChatToken("Hello ");
		});
		act(() => {
			capturedHandlers!.onChatToken("world!");
		});

		const messages = getMessages();
		expect(messages).toHaveLength(1);
		expect(messages[0].content).toBe("Hello world!");
	});

	it("sets isStreaming to true on chat_token", () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		act(() => {
			capturedHandlers!.onChatToken("Hi");
		});

		expect(getIsStreaming()).toBe(true);
	});

	// -----------------------------------------------------------------------
	// SSE: chat_done
	// -----------------------------------------------------------------------

	it("marks streaming message as complete on chat_done", () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		act(() => {
			capturedHandlers!.onChatToken("Hello");
		});
		act(() => {
			capturedHandlers!.onChatDone("backend-msg-1");
		});

		const messages = getMessages();
		expect(messages[0].isStreaming).toBe(false);
	});

	it("sets isStreaming to false on chat_done", () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		act(() => {
			capturedHandlers!.onChatToken("Hello");
		});
		act(() => {
			capturedHandlers!.onChatDone("backend-msg-1");
		});

		expect(getIsStreaming()).toBe(false);
	});

	it("updates message id with backend id on chat_done", () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		act(() => {
			capturedHandlers!.onChatToken("Hello");
		});
		act(() => {
			capturedHandlers!.onChatDone("server-id-42");
		});

		const messages = getMessages();
		expect(messages[0].id).toBe("server-id-42");
	});

	// -----------------------------------------------------------------------
	// SSE: tool_start
	// -----------------------------------------------------------------------

	it("adds tool execution to current agent message", () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		act(() => {
			capturedHandlers!.onChatToken("Let me check...");
		});
		act(() => {
			capturedHandlers!.onToolStart("favorite_job", { job_id: "j1" });
		});

		const messages = getMessages();
		expect(messages[0].tools).toHaveLength(1);
		expect(messages[0].tools[0]).toEqual({
			tool: "favorite_job",
			args: { job_id: "j1" },
			status: "running",
		});
	});

	it("ignores tool_start when no agent message exists", () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		act(() => {
			capturedHandlers!.onToolStart("search", {});
		});

		expect(getMessages()).toEqual([]);
	});

	// -----------------------------------------------------------------------
	// SSE: tool_result
	// -----------------------------------------------------------------------

	it("updates tool execution status to success", () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		act(() => {
			capturedHandlers!.onChatToken("Working...");
		});
		act(() => {
			capturedHandlers!.onToolStart("favorite_job", { job_id: "j1" });
		});
		act(() => {
			capturedHandlers!.onToolResult("favorite_job", true);
		});

		expect(getMessages()[0].tools[0].status).toBe("success");
	});

	it("updates tool execution status to error on failure", () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		act(() => {
			capturedHandlers!.onChatToken("Working...");
		});
		act(() => {
			capturedHandlers!.onToolStart("favorite_job", { job_id: "j1" });
		});
		act(() => {
			capturedHandlers!.onToolResult("favorite_job", false);
		});

		expect(getMessages()[0].tools[0].status).toBe("error");
	});

	it("ignores tool_result when no agent message exists", () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		act(() => {
			capturedHandlers!.onToolResult("search", true);
		});

		expect(getMessages()).toEqual([]);
	});

	// -----------------------------------------------------------------------
	// addSystemMessage
	// -----------------------------------------------------------------------

	it("adds system message to list", () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		act(() => {
			screen.getByTestId(SYSTEM_BUTTON_TEST_ID).click();
		});

		const messages = getMessages();
		expect(messages).toHaveLength(1);
		expect(messages[0].role).toBe("system");
		expect(messages[0].content).toBe("Connected");
		expect(messages[0].isStreaming).toBe(false);
	});

	// -----------------------------------------------------------------------
	// clearMessages
	// -----------------------------------------------------------------------

	it("removes all messages and resets streaming", () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		// Add some messages first
		act(() => {
			capturedHandlers!.onChatToken("Hello");
		});

		expect(getMessages()).toHaveLength(1);
		expect(getIsStreaming()).toBe(true);

		act(() => {
			screen.getByTestId(CLEAR_BUTTON_TEST_ID).click();
		});

		expect(getMessages()).toEqual([]);
		expect(getIsStreaming()).toBe(false);
	});

	// -----------------------------------------------------------------------
	// Full conversation flow
	// -----------------------------------------------------------------------

	it("handles a complete send-receive cycle", async () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		// User sends message
		await act(async () => {
			screen.getByTestId(SEND_BUTTON_TEST_ID).click();
		});

		expect(getMessages()).toHaveLength(1);
		expect(getMessages()[0].role).toBe("user");
		expect(getIsStreaming()).toBe(true);

		// Agent starts responding
		act(() => {
			capturedHandlers!.onChatToken("Hi ");
		});
		act(() => {
			capturedHandlers!.onChatToken("there!");
		});

		expect(getMessages()).toHaveLength(2);
		expect(getMessages()[1].content).toBe("Hi there!");

		// Agent uses a tool
		act(() => {
			capturedHandlers!.onToolStart("search_jobs", { query: "react" });
		});
		act(() => {
			capturedHandlers!.onToolResult("search_jobs", true);
		});

		expect(getMessages()[1].tools).toHaveLength(1);
		expect(getMessages()[1].tools[0].status).toBe("success");

		// Agent finishes
		act(() => {
			capturedHandlers!.onChatDone("msg-42");
		});

		expect(getIsStreaming()).toBe(false);
		expect(getMessages()[1].isStreaming).toBe(false);
		expect(getMessages()[1].id).toBe("msg-42");
	});

	// -----------------------------------------------------------------------
	// Token after sendMessage (agent response to user message)
	// -----------------------------------------------------------------------

	it("allows sending after previous stream completes", async () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		// First send
		await act(async () => {
			screen.getByTestId(SEND_BUTTON_TEST_ID).click();
		});

		// Agent responds and finishes
		act(() => {
			capturedHandlers!.onChatToken("Reply");
		});
		act(() => {
			capturedHandlers!.onChatDone("msg-1");
		});

		expect(getIsStreaming()).toBe(false);

		// Second send should work
		await act(async () => {
			screen.getByTestId(SEND_BUTTON_TEST_ID).click();
		});

		expect(mockApiPost).toHaveBeenCalledTimes(2);
		expect(getMessages()).toHaveLength(3); // user, agent, user
	});

	// -----------------------------------------------------------------------
	// UUID assertion (Finding #6: verify deterministic UUIDs are used)
	// -----------------------------------------------------------------------

	it("assigns client-generated UUID to agent message before chat_done", () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		act(() => {
			capturedHandlers!.onChatToken("Hello");
		});

		// Before chat_done, the ID is the client-generated UUID
		const messages = getMessages();
		expect(messages[0].id).toMatch(/^test-uuid-\d+$/);
	});

	// -----------------------------------------------------------------------
	// Input validation (Finding #3)
	// -----------------------------------------------------------------------

	it("ignores empty string in sendMessage", async () => {
		function EmptySender() {
			const { messages, sendMessage } = useChat();
			return (
				<div>
					<div data-testid={MESSAGES_TEST_ID}>{JSON.stringify(messages)}</div>
					<button data-testid="send" onClick={() => sendMessage("")}>
						Send
					</button>
				</div>
			);
		}

		render(
			<ChatProvider>
				<EmptySender />
			</ChatProvider>,
		);

		await act(async () => {
			screen.getByTestId("send").click();
		});

		expect(mockApiPost).not.toHaveBeenCalled();
		expect(getMessages()).toEqual([]);
	});

	it("ignores whitespace-only string in sendMessage", async () => {
		function WhitespaceSender() {
			const { messages, sendMessage } = useChat();
			return (
				<div>
					<div data-testid={MESSAGES_TEST_ID}>{JSON.stringify(messages)}</div>
					<button data-testid="send" onClick={() => sendMessage("   \n\t  ")}>
						Send
					</button>
				</div>
			);
		}

		render(
			<ChatProvider>
				<WhitespaceSender />
			</ChatProvider>,
		);

		await act(async () => {
			screen.getByTestId("send").click();
		});

		expect(mockApiPost).not.toHaveBeenCalled();
		expect(getMessages()).toEqual([]);
	});

	it("trims content before sending", async () => {
		function TrimSender() {
			const { messages, sendMessage } = useChat();
			return (
				<div>
					<div data-testid={MESSAGES_TEST_ID}>{JSON.stringify(messages)}</div>
					<button data-testid="send" onClick={() => sendMessage("  hello  ")}>
						Send
					</button>
				</div>
			);
		}

		render(
			<ChatProvider>
				<TrimSender />
			</ChatProvider>,
		);

		await act(async () => {
			screen.getByTestId("send").click();
		});

		expect(mockApiPost).toHaveBeenCalledWith("/chat/messages", {
			content: "hello",
		});
		expect(getMessages()[0].content).toBe("hello");
	});

	it("rejects content exceeding max length", async () => {
		const longContent = "a".repeat(10_001);

		function LongSender() {
			const { messages, sendMessage } = useChat();
			return (
				<div>
					<div data-testid={MESSAGES_TEST_ID}>{JSON.stringify(messages)}</div>
					<button data-testid="send" onClick={() => sendMessage(longContent)}>
						Send
					</button>
				</div>
			);
		}

		render(
			<ChatProvider>
				<LongSender />
			</ChatProvider>,
		);

		await act(async () => {
			screen.getByTestId("send").click();
		});

		expect(mockApiPost).not.toHaveBeenCalled();
		expect(getMessages()).toEqual([]);
	});

	// -----------------------------------------------------------------------
	// Bounds: message list cap (Finding #1)
	// -----------------------------------------------------------------------

	it("evicts oldest messages when exceeding max message count", () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		// Add 501 system messages (over the 500 cap)
		for (let i = 0; i < 501; i++) {
			act(() => {
				screen.getByTestId(SYSTEM_BUTTON_TEST_ID).click();
			});
		}

		const messages = getMessages();
		expect(messages.length).toBeLessThanOrEqual(500);
	});

	// -----------------------------------------------------------------------
	// Bounds: message content cap (Finding #2)
	// -----------------------------------------------------------------------

	it("stops appending tokens when message content exceeds max length", () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		// Send a large initial token
		const largeToken = "x".repeat(50_000);
		act(() => {
			capturedHandlers!.onChatToken(largeToken);
		});
		act(() => {
			capturedHandlers!.onChatToken(largeToken);
		});

		// Third token should be dropped (content would exceed 100K)
		act(() => {
			capturedHandlers!.onChatToken(largeToken);
		});

		const messages = getMessages();
		expect(messages[0].content.length).toBeLessThanOrEqual(100_000);
	});

	// -----------------------------------------------------------------------
	// Bounds: tool execution cap (Finding #4)
	// -----------------------------------------------------------------------

	it("caps tool executions per message at limit", () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		act(() => {
			capturedHandlers!.onChatToken("Working...");
		});

		// Add 51 tool_start events (over the 50 cap)
		for (let i = 0; i < 51; i++) {
			act(() => {
				capturedHandlers!.onToolStart(`tool_${i}`, {});
			});
		}

		const messages = getMessages();
		expect(messages[0].tools.length).toBeLessThanOrEqual(50);
	});

	// -----------------------------------------------------------------------
	// Bounds: tool args size cap (Finding #5)
	// -----------------------------------------------------------------------

	it("truncates oversized tool args", () => {
		render(
			<ChatProvider>
				<TestConsumer />
			</ChatProvider>,
		);

		act(() => {
			capturedHandlers!.onChatToken("Working...");
		});

		const largeArgs: Record<string, unknown> = {
			data: "x".repeat(20_000),
		};
		act(() => {
			capturedHandlers!.onToolStart("big_tool", largeArgs);
		});

		const tools = getMessages()[0].tools;
		expect(tools).toHaveLength(1);
		expect(tools[0].args).toHaveProperty("_truncated", true);
	});

	// -----------------------------------------------------------------------
	// loadHistory
	// -----------------------------------------------------------------------

	describe("loadHistory", () => {
		it("provides isLoadingHistory as false initially", () => {
			render(
				<ChatProvider>
					<TestConsumer />
				</ChatProvider>,
			);

			expect(screen.getByTestId(LOADING_HISTORY_TEST_ID).textContent).toBe(
				"false",
			);
		});

		it("fetches from /chat/messages when called", async () => {
			render(
				<ChatProvider>
					<TestConsumer />
				</ChatProvider>,
			);

			await act(async () => {
				screen.getByTestId(LOAD_HISTORY_BUTTON_TEST_ID).click();
			});

			expect(mockApiGet).toHaveBeenCalledWith("/chat/messages");
		});

		it("populates messages from REST response", async () => {
			const history: ChatMessage[] = [
				{
					id: "hist-1",
					role: "user",
					content: "Previous message",
					timestamp: "2026-01-01T10:00:00Z",
					isStreaming: false,
					tools: [],
					cards: [],
				},
				{
					id: "hist-2",
					role: "agent",
					content: "Previous reply",
					timestamp: "2026-01-01T10:01:00Z",
					isStreaming: false,
					tools: [],
					cards: [],
				},
			];
			mockApiGet.mockResolvedValueOnce(history);

			render(
				<ChatProvider>
					<TestConsumer />
				</ChatProvider>,
			);

			await act(async () => {
				screen.getByTestId(LOAD_HISTORY_BUTTON_TEST_ID).click();
			});

			const messages = getMessages();
			expect(messages).toHaveLength(2);
			expect(messages[0].id).toBe("hist-1");
			expect(messages[0].content).toBe("Previous message");
			expect(messages[1].id).toBe("hist-2");
			expect(messages[1].content).toBe("Previous reply");
		});

		it("sets isLoadingHistory to true during fetch", async () => {
			let resolveApiGet!: (value: ChatMessage[]) => void;
			mockApiGet.mockReturnValueOnce(
				new Promise<ChatMessage[]>((resolve) => {
					resolveApiGet = resolve;
				}),
			);

			render(
				<ChatProvider>
					<TestConsumer />
				</ChatProvider>,
			);

			act(() => {
				screen.getByTestId(LOAD_HISTORY_BUTTON_TEST_ID).click();
			});

			expect(screen.getByTestId(LOADING_HISTORY_TEST_ID).textContent).toBe(
				"true",
			);

			await act(async () => {
				resolveApiGet([]);
			});

			expect(screen.getByTestId(LOADING_HISTORY_TEST_ID).textContent).toBe(
				"false",
			);
		});

		it("sets isLoadingHistory to false after fetch completes", async () => {
			render(
				<ChatProvider>
					<TestConsumer />
				</ChatProvider>,
			);

			await act(async () => {
				screen.getByTestId(LOAD_HISTORY_BUTTON_TEST_ID).click();
			});

			expect(screen.getByTestId(LOADING_HISTORY_TEST_ID).textContent).toBe(
				"false",
			);
		});

		it("handles fetch error gracefully", async () => {
			mockApiGet.mockRejectedValueOnce(new Error("Network error"));

			render(
				<ChatProvider>
					<TestConsumer />
				</ChatProvider>,
			);

			await act(async () => {
				screen.getByTestId(LOAD_HISTORY_BUTTON_TEST_ID).click();
			});

			expect(screen.getByTestId(LOADING_HISTORY_TEST_ID).textContent).toBe(
				"false",
			);
			expect(getMessages()).toEqual([]);
		});

		it("replaces existing messages with history on reload", async () => {
			render(
				<ChatProvider>
					<TestConsumer />
				</ChatProvider>,
			);

			// First: add a message via SSE
			act(() => {
				capturedHandlers!.onChatToken("Live message");
			});
			act(() => {
				capturedHandlers!.onChatDone("live-1");
			});
			expect(getMessages()).toHaveLength(1);

			// Then: load history (replaces)
			const history: ChatMessage[] = [
				{
					id: "hist-1",
					role: "user",
					content: "Old message",
					timestamp: "2026-01-01T10:00:00Z",
					isStreaming: false,
					tools: [],
					cards: [],
				},
			];
			mockApiGet.mockResolvedValueOnce(history);

			await act(async () => {
				screen.getByTestId(LOAD_HISTORY_BUTTON_TEST_ID).click();
			});

			const messages = getMessages();
			expect(messages).toHaveLength(1);
			expect(messages[0].id).toBe("hist-1");
		});

		it("resets isStreaming when loading history", async () => {
			render(
				<ChatProvider>
					<TestConsumer />
				</ChatProvider>,
			);

			// Start streaming
			act(() => {
				capturedHandlers!.onChatToken("Streaming...");
			});
			expect(getIsStreaming()).toBe(true);

			// Load history should reset streaming
			await act(async () => {
				screen.getByTestId(LOAD_HISTORY_BUTTON_TEST_ID).click();
			});

			expect(getIsStreaming()).toBe(false);
		});

		it("trims history to max message limit", async () => {
			const largeHistory: ChatMessage[] = Array.from(
				{ length: 510 },
				(_, i) => ({
					id: `hist-${i}`,
					role: "user" as const,
					content: `Message ${i}`,
					timestamp: "2026-01-01T10:00:00Z",
					isStreaming: false,
					tools: [],
					cards: [],
				}),
			);
			mockApiGet.mockResolvedValueOnce(largeHistory);

			render(
				<ChatProvider>
					<TestConsumer />
				</ChatProvider>,
			);

			await act(async () => {
				screen.getByTestId(LOAD_HISTORY_BUTTON_TEST_ID).click();
			});

			expect(getMessages().length).toBeLessThanOrEqual(500);
		});

		it("filters out messages with missing id from history response", async () => {
			const history = [
				{ role: "user", content: "No id", timestamp: "2026-01-01T10:00:00Z" },
				{
					id: "valid-1",
					role: "user",
					content: "Valid",
					timestamp: "2026-01-01T10:00:00Z",
					isStreaming: false,
					tools: [],
					cards: [],
				},
			];
			mockApiGet.mockResolvedValueOnce(history);

			render(
				<ChatProvider>
					<TestConsumer />
				</ChatProvider>,
			);

			await act(async () => {
				screen.getByTestId(LOAD_HISTORY_BUTTON_TEST_ID).click();
			});

			const messages = getMessages();
			expect(messages).toHaveLength(1);
			expect(messages[0].id).toBe("valid-1");
		});

		it("filters out messages with invalid role from history response", async () => {
			const history = [
				{
					id: "bad-1",
					role: "admin",
					content: "Invalid role",
					timestamp: "2026-01-01T10:00:00Z",
					isStreaming: false,
					tools: [],
					cards: [],
				},
				{
					id: "valid-1",
					role: "agent",
					content: "Valid",
					timestamp: "2026-01-01T10:00:00Z",
					isStreaming: false,
					tools: [],
					cards: [],
				},
			];
			mockApiGet.mockResolvedValueOnce(history);

			render(
				<ChatProvider>
					<TestConsumer />
				</ChatProvider>,
			);

			await act(async () => {
				screen.getByTestId(LOAD_HISTORY_BUTTON_TEST_ID).click();
			});

			const messages = getMessages();
			expect(messages).toHaveLength(1);
			expect(messages[0].id).toBe("valid-1");
		});

		it("truncates oversized content in history messages", async () => {
			const history: ChatMessage[] = [
				{
					id: "big-1",
					role: "agent",
					content: "x".repeat(200_000),
					timestamp: "2026-01-01T10:00:00Z",
					isStreaming: false,
					tools: [],
					cards: [],
				},
			];
			mockApiGet.mockResolvedValueOnce(history);

			render(
				<ChatProvider>
					<TestConsumer />
				</ChatProvider>,
			);

			await act(async () => {
				screen.getByTestId(LOAD_HISTORY_BUTTON_TEST_ID).click();
			});

			const messages = getMessages();
			expect(messages).toHaveLength(1);
			expect(messages[0].content.length).toBeLessThanOrEqual(100_000);
		});

		it("treats non-array response as empty history", async () => {
			mockApiGet.mockResolvedValueOnce("not an array");

			render(
				<ChatProvider>
					<TestConsumer />
				</ChatProvider>,
			);

			await act(async () => {
				screen.getByTestId(LOAD_HISTORY_BUTTON_TEST_ID).click();
			});

			expect(getMessages()).toEqual([]);
		});

		it("filters out invalid tool entries from history response", async () => {
			const history = [
				{
					id: "hist-1",
					role: "agent",
					content: "Working",
					timestamp: "2026-01-01T10:00:00Z",
					isStreaming: false,
					tools: [
						{ tool: "search_jobs", args: {}, status: "success" },
						{ tool: 123, args: {}, status: "running" },
						{ tool: "bad_status", args: {}, status: "unknown" },
						"not-an-object",
					],
					cards: [],
				},
			];
			mockApiGet.mockResolvedValueOnce(history);

			render(
				<ChatProvider>
					<TestConsumer />
				</ChatProvider>,
			);

			await act(async () => {
				screen.getByTestId(LOAD_HISTORY_BUTTON_TEST_ID).click();
			});

			const messages = getMessages();
			expect(messages[0].tools).toHaveLength(1);
			expect(messages[0].tools[0].tool).toBe("search_jobs");
		});

		it("filters out invalid card entries from history response", async () => {
			const history = [
				{
					id: "hist-1",
					role: "agent",
					content: "Here are results",
					timestamp: "2026-01-01T10:00:00Z",
					isStreaming: false,
					tools: [],
					cards: [
						{
							type: "job",
							data: {
								jobId: "j1",
								jobTitle: "Dev",
								companyName: "Acme",
								location: null,
								workModel: null,
								fitScore: null,
								stretchScore: null,
								salaryMin: null,
								salaryMax: null,
								salaryCurrency: null,
								isFavorite: false,
							},
						},
						{ type: "invalid_type", data: {} },
						{ type: "job", data: null },
						"not-an-object",
					],
				},
			];
			mockApiGet.mockResolvedValueOnce(history);

			render(
				<ChatProvider>
					<TestConsumer />
				</ChatProvider>,
			);

			await act(async () => {
				screen.getByTestId(LOAD_HISTORY_BUTTON_TEST_ID).click();
			});

			const messages = getMessages();
			expect(messages[0].cards).toHaveLength(1);
			expect(messages[0].cards[0].type).toBe("job");
		});

		it("caps tools per message from history response", async () => {
			const tools = Array.from({ length: 60 }, (_, i) => ({
				tool: `tool_${i}`,
				args: {},
				status: "success" as const,
			}));
			const history: ChatMessage[] = [
				{
					id: "hist-1",
					role: "agent",
					content: "Done",
					timestamp: "2026-01-01T10:00:00Z",
					isStreaming: false,
					tools,
					cards: [],
				},
			];
			mockApiGet.mockResolvedValueOnce(history);

			render(
				<ChatProvider>
					<TestConsumer />
				</ChatProvider>,
			);

			await act(async () => {
				screen.getByTestId(LOAD_HISTORY_BUTTON_TEST_ID).click();
			});

			expect(getMessages()[0].tools.length).toBeLessThanOrEqual(50);
		});

		it("caps cards per message from history response", async () => {
			const cards = Array.from({ length: 25 }, (_, i) => ({
				type: "job" as const,
				data: {
					jobId: `j-${i}`,
					jobTitle: "Dev",
					companyName: "Co",
					location: null,
					workModel: null,
					fitScore: null,
					stretchScore: null,
					salaryMin: null,
					salaryMax: null,
					salaryCurrency: null,
					isFavorite: false,
				},
			}));
			const history: ChatMessage[] = [
				{
					id: "hist-1",
					role: "agent",
					content: "Jobs",
					timestamp: "2026-01-01T10:00:00Z",
					isStreaming: false,
					tools: [],
					cards,
				},
			];
			mockApiGet.mockResolvedValueOnce(history);

			render(
				<ChatProvider>
					<TestConsumer />
				</ChatProvider>,
			);

			await act(async () => {
				screen.getByTestId(LOAD_HISTORY_BUTTON_TEST_ID).click();
			});

			expect(getMessages()[0].cards.length).toBeLessThanOrEqual(20);
		});

		it("ignores duplicate loadHistory calls while one is in-flight", async () => {
			let resolveApiGet!: (value: ChatMessage[]) => void;
			mockApiGet.mockReturnValueOnce(
				new Promise<ChatMessage[]>((resolve) => {
					resolveApiGet = resolve;
				}),
			);

			render(
				<ChatProvider>
					<TestConsumer />
				</ChatProvider>,
			);

			// First call
			act(() => {
				screen.getByTestId(LOAD_HISTORY_BUTTON_TEST_ID).click();
			});

			// Second call while first is in-flight
			act(() => {
				screen.getByTestId(LOAD_HISTORY_BUTTON_TEST_ID).click();
			});

			expect(mockApiGet).toHaveBeenCalledTimes(1);

			await act(async () => {
				resolveApiGet([]);
			});
		});
	});
});

// ---------------------------------------------------------------------------
// useChat hook
// ---------------------------------------------------------------------------

describe("useChat", () => {
	it("throws when used outside ChatProvider", () => {
		const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

		expect(() => render(<TestConsumer />)).toThrow(
			"useChat must be used within a ChatProvider",
		);

		consoleSpy.mockRestore();
	});
});
