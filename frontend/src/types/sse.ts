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

/**
 * Type guard for SSEEvent — validates the `type` discriminant and all
 * required fields for each event type at runtime.
 *
 * @param value - Value to check.
 * @returns True if value is a fully valid SSE event object.
 */
export function isSSEEvent(value: unknown): value is SSEEvent {
	if (typeof value !== "object" || value === null) {
		return false;
	}
	const obj = value as Record<string, unknown>;
	if (typeof obj.type !== "string") return false;

	switch (obj.type) {
		case "chat_token":
			return typeof obj.text === "string";
		case "chat_done":
			return typeof obj.message_id === "string";
		case "tool_start":
			return (
				typeof obj.tool === "string" &&
				typeof obj.args === "object" &&
				obj.args !== null
			);
		case "tool_result":
			return typeof obj.tool === "string" && typeof obj.success === "boolean";
		case "data_changed":
			return (
				typeof obj.resource === "string" &&
				typeof obj.id === "string" &&
				typeof obj.action === "string"
			);
		case "heartbeat":
			return true;
		default:
			return false;
	}
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
