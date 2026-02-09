import { describe, expect, it } from "vitest";

import type {
	ChatDoneEvent,
	ChatTokenEvent,
	DataChangedEvent,
	HeartbeatEvent,
	SSEEvent,
	ToolResultEvent,
	ToolStartEvent,
} from "./sse";
import { isSSEEvent, parseSSEEvent } from "./sse";

describe("SSE Event Types", () => {
	describe("ChatTokenEvent", () => {
		it("represents a streaming token", () => {
			const event: ChatTokenEvent = {
				type: "chat_token",
				text: " the",
			};

			expect(event.type).toBe("chat_token");
			expect(event.text).toBe(" the");
		});
	});

	describe("ChatDoneEvent", () => {
		it("represents message completion", () => {
			const event: ChatDoneEvent = {
				type: "chat_done",
				message_id: "550e8400-e29b-41d4-a716-446655440000",
			};

			expect(event.type).toBe("chat_done");
			expect(event.message_id).toBe("550e8400-e29b-41d4-a716-446655440000");
		});
	});

	describe("ToolStartEvent", () => {
		it("represents a tool call starting", () => {
			const event: ToolStartEvent = {
				type: "tool_start",
				tool: "search_jobs",
				args: { query: "python developer" },
			};

			expect(event.type).toBe("tool_start");
			expect(event.tool).toBe("search_jobs");
			expect(event.args).toEqual({ query: "python developer" });
		});

		it("accepts empty args", () => {
			const event: ToolStartEvent = {
				type: "tool_start",
				tool: "list_favorites",
				args: {},
			};

			expect(event.args).toEqual({});
		});
	});

	describe("ToolResultEvent", () => {
		it("represents a successful tool result", () => {
			const event: ToolResultEvent = {
				type: "tool_result",
				tool: "favorite_job",
				success: true,
				result: { job_id: "123" },
				error: null,
			};

			expect(event.success).toBe(true);
			expect(event.result).toEqual({ job_id: "123" });
			expect(event.error).toBeNull();
		});

		it("represents a failed tool result", () => {
			const event: ToolResultEvent = {
				type: "tool_result",
				tool: "favorite_job",
				success: false,
				result: null,
				error: "Job not found",
			};

			expect(event.success).toBe(false);
			expect(event.result).toBeNull();
			expect(event.error).toBe("Job not found");
		});
	});

	describe("DataChangedEvent", () => {
		it("represents a resource creation", () => {
			const event: DataChangedEvent = {
				type: "data_changed",
				resource: "job-posting",
				id: "abc-123",
				action: "created",
			};

			expect(event.type).toBe("data_changed");
			expect(event.action).toBe("created");
		});

		it("represents a resource update", () => {
			const event: DataChangedEvent = {
				type: "data_changed",
				resource: "application",
				id: "def-456",
				action: "updated",
			};

			expect(event.action).toBe("updated");
		});

		it("represents a resource deletion", () => {
			const event: DataChangedEvent = {
				type: "data_changed",
				resource: "persona",
				id: "ghi-789",
				action: "deleted",
			};

			expect(event.action).toBe("deleted");
		});
	});

	describe("HeartbeatEvent", () => {
		it("represents a keepalive", () => {
			const event: HeartbeatEvent = {
				type: "heartbeat",
			};

			expect(event.type).toBe("heartbeat");
		});
	});

	describe("SSEEvent discriminated union", () => {
		it("narrows type via the type field", () => {
			const event: SSEEvent = {
				type: "chat_token",
				text: "hello",
			};

			if (event.type === "chat_token") {
				expect(event.text).toBe("hello");
			}
		});

		it("narrows to tool_result with success/error", () => {
			const event: SSEEvent = {
				type: "tool_result",
				tool: "test",
				success: true,
				result: { ok: true },
				error: null,
			};

			if (event.type === "tool_result") {
				expect(event.success).toBe(true);
				expect(event.result).toEqual({ ok: true });
			}
		});
	});

	describe("parseSSEEvent", () => {
		it("parses a valid chat_token event", () => {
			const json = '{"type":"chat_token","text":" world"}';
			const event = parseSSEEvent(json);

			expect(event).not.toBeNull();
			expect(event?.type).toBe("chat_token");
			if (event?.type === "chat_token") {
				expect(event.text).toBe(" world");
			}
		});

		it("parses a valid data_changed event", () => {
			const json =
				'{"type":"data_changed","resource":"job-posting","id":"abc","action":"updated"}';
			const event = parseSSEEvent(json);

			expect(event).not.toBeNull();
			expect(event?.type).toBe("data_changed");
		});

		it("parses a heartbeat event", () => {
			const json = '{"type":"heartbeat"}';
			const event = parseSSEEvent(json);

			expect(event).not.toBeNull();
			expect(event?.type).toBe("heartbeat");
		});

		it("returns null for invalid JSON", () => {
			const event = parseSSEEvent("not json");
			expect(event).toBeNull();
		});

		it("returns null for unknown event type", () => {
			const event = parseSSEEvent('{"type":"unknown_event"}');
			expect(event).toBeNull();
		});

		it("returns null for missing type field", () => {
			const event = parseSSEEvent('{"text":"no type"}');
			expect(event).toBeNull();
		});
	});

	describe("isSSEEvent", () => {
		it("returns true for valid event objects", () => {
			expect(isSSEEvent({ type: "chat_token", text: "hi" })).toBe(true);
			expect(isSSEEvent({ type: "heartbeat" })).toBe(true);
		});

		it("returns false for non-objects", () => {
			expect(isSSEEvent(null)).toBe(false);
			expect(isSSEEvent("string")).toBe(false);
			expect(isSSEEvent(42)).toBe(false);
		});

		it("returns false for objects without type", () => {
			expect(isSSEEvent({ text: "no type" })).toBe(false);
		});

		it("returns false for unknown event types", () => {
			expect(isSSEEvent({ type: "unknown" })).toBe(false);
		});
	});
});
