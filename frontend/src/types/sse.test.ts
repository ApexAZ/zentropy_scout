import { describe, expect, it } from "vitest";

import { isSSEEvent, parseSSEEvent } from "./sse";

describe("SSE Event Types", () => {
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

		it("returns true for valid tool_result event", () => {
			expect(
				isSSEEvent({
					type: "tool_result",
					tool: "x",
					success: true,
					result: null,
					error: null,
				}),
			).toBe(true);
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

		it("returns false for chat_token with non-string text", () => {
			expect(isSSEEvent({ type: "chat_token", text: 123 })).toBe(false);
		});

		it("returns false for chat_token with missing text", () => {
			expect(isSSEEvent({ type: "chat_token" })).toBe(false);
		});

		it("returns false for chat_done with missing message_id", () => {
			expect(isSSEEvent({ type: "chat_done" })).toBe(false);
		});

		it("returns false for tool_start with missing args", () => {
			expect(isSSEEvent({ type: "tool_start", tool: "x" })).toBe(false);
		});

		it("returns false for tool_start with null args", () => {
			expect(isSSEEvent({ type: "tool_start", tool: "x", args: null })).toBe(
				false,
			);
		});

		it("returns false for tool_result with non-boolean success", () => {
			expect(
				isSSEEvent({
					type: "tool_result",
					tool: "x",
					success: "yes",
				}),
			).toBe(false);
		});

		it("returns false for data_changed with missing fields", () => {
			expect(isSSEEvent({ type: "data_changed", resource: "x" })).toBe(false);
		});
	});

	describe("parseSSEEvent field validation", () => {
		it("returns null for chat_token with non-string text", () => {
			expect(parseSSEEvent('{"type":"chat_token","text":123}')).toBeNull();
		});

		it("returns null for chat_done with missing message_id", () => {
			expect(parseSSEEvent('{"type":"chat_done"}')).toBeNull();
		});

		it("returns null for tool_start with non-object args", () => {
			expect(
				parseSSEEvent('{"type":"tool_start","tool":"x","args":"string"}'),
			).toBeNull();
		});

		it("returns null for data_changed with non-string id", () => {
			expect(
				parseSSEEvent(
					'{"type":"data_changed","resource":"x","id":1,"action":"updated"}',
				),
			).toBeNull();
		});
	});
});
