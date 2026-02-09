/**
 * SSE event types matching backend/app/schemas/chat.py.
 *
 * REQ-006 §2.5: SSE event types for real-time communication.
 * REQ-012 §4.4: SSE client with typed events.
 */

/** Streaming LLM token — append text to current chat message. */
export interface ChatTokenEvent {
	type: "chat_token";
	text: string;
}

/** Message complete — re-enable user input. */
export interface ChatDoneEvent {
	type: "chat_done";
	message_id: string;
}

/** Agent started a tool call — show spinner with tool label. */
export interface ToolStartEvent {
	type: "tool_start";
	tool: string;
	args: Record<string, unknown>;
}

/** Agent tool call completed — show result badge. */
export interface ToolResultEvent {
	type: "tool_result";
	tool: string;
	success: boolean;
	result: Record<string, unknown> | null;
	error: string | null;
}

/** Data modification — invalidate corresponding TanStack Query cache. */
export interface DataChangedEvent {
	type: "data_changed";
	resource: string;
	id: string;
	action: "created" | "updated" | "deleted";
}

/** Keepalive heartbeat — no action needed. */
export interface HeartbeatEvent {
	type: "heartbeat";
}

/**
 * Discriminated union of all SSE event types.
 *
 * Use the `type` field to narrow:
 * ```ts
 * if (event.type === "chat_token") {
 *   console.log(event.text); // TypeScript knows this is ChatTokenEvent
 * }
 * ```
 */
export type SSEEvent =
	| ChatTokenEvent
	| ChatDoneEvent
	| ToolStartEvent
	| ToolResultEvent
	| DataChangedEvent
	| HeartbeatEvent;

/** All valid SSE event type strings. Typed to catch drift with the SSEEvent union. */
const SSE_EVENT_TYPES: Set<SSEEvent["type"]> = new Set([
	"chat_token",
	"chat_done",
	"tool_start",
	"tool_result",
	"data_changed",
	"heartbeat",
]);

/**
 * Type guard for SSEEvent — validates the `type` discriminant only,
 * not the full event shape. Consumers should null-check individual
 * fields if handling untrusted data.
 *
 * @param value - Value to check.
 * @returns True if value is an object with a recognized `type` field.
 */
export function isSSEEvent(value: unknown): value is SSEEvent {
	if (typeof value !== "object" || value === null) {
		return false;
	}
	const obj = value as Record<string, unknown>;
	return (
		typeof obj.type === "string" &&
		SSE_EVENT_TYPES.has(obj.type as SSEEvent["type"])
	);
}

/**
 * Parse a JSON string into a typed SSE event.
 *
 * @param json - Raw JSON string from SSE `data:` field.
 * @returns Parsed event, or null if invalid JSON or unknown event type.
 */
export function parseSSEEvent(json: string): SSEEvent | null {
	let parsed: unknown;
	try {
		parsed = JSON.parse(json);
	} catch {
		return null;
	}

	if (isSSEEvent(parsed)) {
		return parsed;
	}
	return null;
}
