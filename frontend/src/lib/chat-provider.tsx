"use client";

/**
 * Chat state provider.
 *
 * REQ-012 §5: Manages the chat message list, streaming state, and
 * SSE callback wiring. Provides `useChat` hook for components to
 * access messages, send messages, and manage chat state.
 *
 * Must be rendered inside an SSEProvider so that `useSSE()` is
 * available for registering chat event handlers.
 */

import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useReducer,
	useRef,
	type ReactNode,
} from "react";

import type { ChatMessage } from "../types/chat";

import { apiPost } from "./api-client";
import { useSSE } from "./sse-provider";

// ---------------------------------------------------------------------------
// Constants (security bounds)
// ---------------------------------------------------------------------------

/** Maximum number of messages retained in the chat list. */
const MAX_MESSAGES = 500;

/** Maximum length (chars) of a single message's content. */
const MAX_MESSAGE_CONTENT_LENGTH = 100_000;

/** Maximum length (chars) of user-submitted message content. */
const MAX_USER_MESSAGE_LENGTH = 10_000;

/** Maximum tool executions tracked per agent message. */
const MAX_TOOLS_PER_MESSAGE = 50;

/** Maximum serialized size (chars) of tool args before truncation. */
const MAX_TOOL_ARGS_SIZE = 10_000;

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

interface ChatState {
	messages: ChatMessage[];
	isStreaming: boolean;
}

const initialState: ChatState = {
	messages: [],
	isStreaming: false,
};

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

type ChatAction =
	| {
			type: "ADD_USER_MESSAGE";
			id: string;
			content: string;
			timestamp: string;
	  }
	| {
			type: "ADD_SYSTEM_MESSAGE";
			id: string;
			content: string;
			timestamp: string;
	  }
	| { type: "APPEND_TOKEN"; text: string; id: string; timestamp: string }
	| { type: "TOOL_START"; tool: string; args: Record<string, unknown> }
	| { type: "TOOL_RESULT"; tool: string; success: boolean }
	| { type: "STREAM_DONE"; messageId: string }
	| { type: "CLEAR_MESSAGES" };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Trim messages array to MAX_MESSAGES, keeping the newest. */
function trimMessages(messages: ChatMessage[]): ChatMessage[] {
	if (messages.length <= MAX_MESSAGES) return messages;
	return messages.slice(messages.length - MAX_MESSAGES);
}

/** Sanitize tool args — truncate if serialized size exceeds limit. */
function sanitizeToolArgs(
	args: Record<string, unknown>,
): Record<string, unknown> {
	const serialized = JSON.stringify(args);
	if (serialized.length > MAX_TOOL_ARGS_SIZE) {
		return { _truncated: true, _message: "Args too large to display" };
	}
	return args;
}

// ---------------------------------------------------------------------------
// Reducer
// ---------------------------------------------------------------------------

function chatReducer(state: ChatState, action: ChatAction): ChatState {
	switch (action.type) {
		case "ADD_USER_MESSAGE":
			return {
				...state,
				isStreaming: true,
				messages: trimMessages([
					...state.messages,
					{
						id: action.id,
						role: "user",
						content: action.content,
						timestamp: action.timestamp,
						isStreaming: false,
						tools: [],
					},
				]),
			};

		case "ADD_SYSTEM_MESSAGE":
			return {
				...state,
				messages: trimMessages([
					...state.messages,
					{
						id: action.id,
						role: "system",
						content: action.content,
						timestamp: action.timestamp,
						isStreaming: false,
						tools: [],
					},
				]),
			};

		case "APPEND_TOKEN": {
			const lastMsg = state.messages[state.messages.length - 1];
			if (lastMsg?.role === "agent" && lastMsg.isStreaming) {
				// Drop tokens if content exceeds max length
				if (lastMsg.content.length >= MAX_MESSAGE_CONTENT_LENGTH) {
					return state;
				}
				// Append to existing streaming agent message
				return {
					...state,
					isStreaming: true,
					messages: state.messages.map((msg, i) =>
						i === state.messages.length - 1
							? { ...msg, content: msg.content + action.text }
							: msg,
					),
				};
			}
			// Create new agent message
			return {
				...state,
				isStreaming: true,
				messages: trimMessages([
					...state.messages,
					{
						id: action.id,
						role: "agent",
						content: action.text,
						timestamp: action.timestamp,
						isStreaming: true,
						tools: [],
					},
				]),
			};
		}

		case "TOOL_START": {
			const lastMsg = state.messages[state.messages.length - 1];
			if (!lastMsg || lastMsg.role !== "agent") return state;
			if (lastMsg.tools.length >= MAX_TOOLS_PER_MESSAGE) return state;
			return {
				...state,
				messages: state.messages.map((msg, i) =>
					i === state.messages.length - 1
						? {
								...msg,
								tools: [
									...msg.tools,
									{
										tool: action.tool,
										args: sanitizeToolArgs(action.args),
										status: "running" as const,
									},
								],
							}
						: msg,
				),
			};
		}

		case "TOOL_RESULT": {
			const lastMsg = state.messages[state.messages.length - 1];
			if (!lastMsg || lastMsg.role !== "agent") return state;
			return {
				...state,
				messages: state.messages.map((msg, i) =>
					i === state.messages.length - 1
						? {
								...msg,
								tools: msg.tools.map((t) =>
									t.tool === action.tool && t.status === "running"
										? {
												...t,
												status: action.success
													? ("success" as const)
													: ("error" as const),
											}
										: t,
								),
							}
						: msg,
				),
			};
		}

		case "STREAM_DONE":
			return {
				...state,
				isStreaming: false,
				messages: state.messages.map((msg) =>
					msg.isStreaming
						? {
								...msg,
								isStreaming: false,
								id: action.messageId || msg.id,
							}
						: msg,
				),
			};

		case "CLEAR_MESSAGES":
			return initialState;

		default:
			return state;
	}
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

interface ChatContextValue {
	/** All chat messages in chronological order. */
	messages: ChatMessage[];
	/** Whether the agent is currently streaming a response. */
	isStreaming: boolean;
	/** Send a user message. Adds to list and POSTs to backend. */
	sendMessage: (content: string) => Promise<void>;
	/** Add a system notice message (e.g., "Reconnecting..."). */
	addSystemMessage: (content: string) => void;
	/** Clear all messages from the list. */
	clearMessages: () => void;
}

const ChatContext = createContext<ChatContextValue | null>(null);

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Access chat state and actions.
 *
 * Must be called within a ChatProvider.
 *
 * @returns Object with `messages`, `isStreaming`, `sendMessage`,
 *          `addSystemMessage`, and `clearMessages`.
 * @throws Error if called outside a ChatProvider.
 */
export function useChat(): ChatContextValue {
	const ctx = useContext(ChatContext);
	if (!ctx) {
		throw new Error("useChat must be used within a ChatProvider");
	}
	return ctx;
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

interface ChatProviderProps {
	children: ReactNode;
}

/**
 * Provides chat state management and SSE event wiring to the component tree.
 *
 * Manages the message list via a reducer and registers SSE chat handlers
 * with the SSEProvider to receive streaming tokens, tool execution events,
 * and message completion signals.
 *
 * @param props.children - React children to render.
 */
export function ChatProvider({ children }: ChatProviderProps) {
	const { registerChatHandlers } = useSSE();
	const [state, dispatch] = useReducer(chatReducer, initialState);

	// Track streaming message ID to avoid generating a new UUID per token
	const streamingIdRef = useRef<string | null>(null);

	// Track isStreaming in a ref for the sendMessage closure
	const isStreamingRef = useRef(state.isStreaming);
	useEffect(() => {
		isStreamingRef.current = state.isStreaming;
	}, [state.isStreaming]);

	// -----------------------------------------------------------------------
	// Register SSE chat handlers
	// -----------------------------------------------------------------------

	useEffect(() => {
		const cleanup = registerChatHandlers({
			onChatToken: (text: string) => {
				if (!streamingIdRef.current) {
					streamingIdRef.current = crypto.randomUUID();
				}
				dispatch({
					type: "APPEND_TOKEN",
					text,
					id: streamingIdRef.current,
					timestamp: new Date().toISOString(),
				});
			},

			onChatDone: (messageId: string) => {
				streamingIdRef.current = null;
				dispatch({ type: "STREAM_DONE", messageId });
			},

			onToolStart: (tool: string, args: Record<string, unknown>) => {
				dispatch({ type: "TOOL_START", tool, args });
			},

			onToolResult: (tool: string, success: boolean) => {
				dispatch({ type: "TOOL_RESULT", tool, success });
			},
		});

		return cleanup;
	}, [registerChatHandlers]);

	// -----------------------------------------------------------------------
	// Actions
	// -----------------------------------------------------------------------

	const sendMessage = useCallback(async (content: string) => {
		const trimmed = content.trim();
		if (!trimmed || trimmed.length > MAX_USER_MESSAGE_LENGTH) return;
		if (isStreamingRef.current) return;

		const id = crypto.randomUUID();
		const timestamp = new Date().toISOString();
		dispatch({ type: "ADD_USER_MESSAGE", id, content: trimmed, timestamp });

		try {
			await apiPost("/chat/messages", { content: trimmed });
		} catch {
			dispatch({ type: "STREAM_DONE", messageId: "" });
			dispatch({
				type: "ADD_SYSTEM_MESSAGE",
				id: crypto.randomUUID(),
				content: "Failed to send message. Please try again.",
				timestamp: new Date().toISOString(),
			});
		}
	}, []);

	const addSystemMessage = useCallback((content: string) => {
		dispatch({
			type: "ADD_SYSTEM_MESSAGE",
			id: crypto.randomUUID(),
			content,
			timestamp: new Date().toISOString(),
		});
	}, []);

	const clearMessages = useCallback(() => {
		streamingIdRef.current = null;
		dispatch({ type: "CLEAR_MESSAGES" });
	}, []);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<ChatContext
			value={{
				messages: state.messages,
				isStreaming: state.isStreaming,
				sendMessage,
				addSystemMessage,
				clearMessages,
			}}
		>
			{children}
		</ChatContext>
	);
}
