/**
 * Chat message types for the chat interface.
 *
 * REQ-012 §5.2: Message types include user, agent, system notices,
 * and inline tool execution indicators.
 */

// ---------------------------------------------------------------------------
// Tool execution
// ---------------------------------------------------------------------------

/** Status of a tool execution within a chat message. */
export type ToolExecutionStatus = "running" | "success" | "error";

/** Tool execution that occurred inline during an agent message. */
export interface ToolExecution {
	/** Tool name (e.g., "favorite_job", "search_jobs"). */
	tool: string;
	/** Arguments passed to the tool. */
	args: Record<string, unknown>;
	/** Current execution status. */
	status: ToolExecutionStatus;
}

// ---------------------------------------------------------------------------
// Chat message
// ---------------------------------------------------------------------------

/** Chat message sender role. */
export type ChatMessageRole = "user" | "agent" | "system";

/**
 * Single chat message in the conversation.
 *
 * Messages are added to the list by:
 * - User: via sendMessage
 * - Agent: via SSE chat_token/chat_done events
 * - System: via addSystemMessage (connection status, errors)
 */
export interface ChatMessage {
	/** Unique message identifier. */
	id: string;
	/** Who sent the message. */
	role: ChatMessageRole;
	/** Text content (may contain markdown for agent messages). */
	content: string;
	/** ISO 8601 timestamp. */
	timestamp: string;
	/** True while agent is still streaming tokens for this message. */
	isStreaming: boolean;
	/** Tool executions that occurred inline during this message. */
	tools: ToolExecution[];
}

// ---------------------------------------------------------------------------
// Chat handlers (SSE callback registration)
// ---------------------------------------------------------------------------

/**
 * Callbacks for handling SSE chat events.
 *
 * Registered by ChatProvider with the SSE provider to receive
 * real-time chat events from the backend.
 */
export interface ChatHandlers {
	/** Called for each streaming LLM token. */
	onChatToken: (text: string) => void;
	/** Called when a chat message is complete. */
	onChatDone: (messageId: string) => void;
	/** Called when an agent starts a tool call. */
	onToolStart: (tool: string, args: Record<string, unknown>) => void;
	/** Called when an agent tool call completes. */
	onToolResult: (tool: string, success: boolean) => void;
}
