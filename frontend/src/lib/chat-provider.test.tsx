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
const SEND_BUTTON_TEST_ID = "send-btn";
const SYSTEM_BUTTON_TEST_ID = "system-btn";
const CLEAR_BUTTON_TEST_ID = "clear-btn";
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
vi.mock("./api-client", () => ({
	apiPost: (...args: unknown[]) => mockApiPost(...args),
}));

let uuidCounter = 0;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function TestConsumer() {
	const {
		messages,
		isStreaming,
		sendMessage,
		addSystemMessage,
		clearMessages,
	} = useChat();
	return (
		<div>
			<div data-testid={MESSAGES_TEST_ID}>{JSON.stringify(messages)}</div>
			<div data-testid={STREAMING_TEST_ID}>{String(isStreaming)}</div>
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
