/**
 * Chat message types for the chat interface.
 *
 * REQ-012 §5.2: Message types include user, agent, system notices,
 * and inline tool execution indicators.
 * REQ-012 §5.3: Structured chat cards (job card, score summary).
 */

import type { WorkModel } from "./persona";
import type {
	FitScoreResult,
	ScoreExplanation,
	StretchScoreResult,
} from "./job";

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
// Structured chat cards (REQ-012 §5.3)
// ---------------------------------------------------------------------------

/** Data for a compact job card displayed inline in chat. */
export interface JobCardData {
	/** Job posting ID (for action callbacks). */
	jobId: string;
	/** Job title. */
	jobTitle: string;
	/** Company name. */
	companyName: string;
	/** Location (e.g., "Austin, TX"). Null when not specified. */
	location: string | null;
	/** Work arrangement. Null when not specified. */
	workModel: WorkModel | null;
	/** Fit score (0–100). Null when not scored. */
	fitScore: number | null;
	/** Stretch score (0–100). Null when not scored. */
	stretchScore: number | null;
	/** Minimum salary. Null when not disclosed. */
	salaryMin: number | null;
	/** Maximum salary. Null when not disclosed. */
	salaryMax: number | null;
	/** ISO 4217 currency code (e.g., "USD"). Null when not disclosed. */
	salaryCurrency: string | null;
	/** Whether the user has favorited this posting. */
	isFavorite: boolean;
}

/** Data for a score summary card displayed inline in chat. */
export interface ScoreCardData {
	/** Job posting ID (for context). */
	jobId: string;
	/** Job title (display context for the card header). */
	jobTitle: string;
	/** Fit score breakdown. */
	fit: FitScoreResult;
	/** Stretch score breakdown. */
	stretch: StretchScoreResult;
	/** Human-readable score explanation. */
	explanation: ScoreExplanation;
}

// ---------------------------------------------------------------------------
// Ambiguity resolution cards (REQ-012 §5.6)
// ---------------------------------------------------------------------------

/** A single selectable option in an ambiguity resolution list. */
export interface OptionItem {
	/** Display label (e.g., "Scrum Master at Acme Corp"). */
	label: string;
	/** Value sent as a user message when selected (e.g., "1"). */
	value: string;
}

/** Data for the clickable option list card. */
export interface OptionListData {
	/** Selectable options. */
	options: OptionItem[];
}

/** Data for the destructive confirmation card. */
export interface ConfirmCardData {
	/** Description of what will happen if the user proceeds. */
	message: string;
	/** Label for the proceed button. Defaults to "Proceed" if omitted. */
	proceedLabel?: string;
	/** Label for the cancel button. Defaults to "Cancel" if omitted. */
	cancelLabel?: string;
	/** Whether this is a destructive action (red proceed button). */
	isDestructive: boolean;
}

// ---------------------------------------------------------------------------
// Chat card union
// ---------------------------------------------------------------------------

/** Discriminated union for structured chat card types. */
export type ChatCard =
	| { type: "job"; data: JobCardData }
	| { type: "score"; data: ScoreCardData }
	| { type: "options"; data: OptionListData }
	| { type: "confirm"; data: ConfirmCardData };

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
	/** Structured cards embedded in this message (REQ-012 §5.3). */
	cards: ChatCard[];
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
