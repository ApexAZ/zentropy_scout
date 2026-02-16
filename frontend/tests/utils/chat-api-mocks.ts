/**
 * Stateful Playwright route mock controller for chat E2E tests.
 *
 * Uses page.route() for REST endpoints and page.addInitScript() to replace
 * the native EventSource with a controllable mock. SSE events are injected
 * from test code via page.evaluate().
 *
 * All API routes use a single regex to avoid Playwright glob matching
 * edge cases with cross-origin URLs.
 */

import type { Page, Route } from "@playwright/test";

import type { ChatMessage } from "@/types/chat";

import {
	chatHistoryResponse,
	chatHistoryWithCards,
	chatHistoryWithOptions,
	onboardedPersonaList,
} from "../fixtures/chat-mock-data";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChatMockState {
	/** Messages to return from GET /chat/messages. */
	chatHistory: ChatMessage[];
	/** Number of POST /chat/messages calls received. */
	postCount: number;
}

// ---------------------------------------------------------------------------
// MockEventSource init script
// ---------------------------------------------------------------------------

const MOCK_EVENT_SOURCE_SCRIPT = `
class MockEventSource {
	static CONNECTING = 0;
	static OPEN = 1;
	static CLOSED = 2;

	readyState = 0;
	url;
	onopen = null;
	onmessage = null;
	onerror = null;

	constructor(url) {
		this.url = url;
		window.__mockSSE = this;
		queueMicrotask(() => {
			this.readyState = 1;
			if (this.onopen) this.onopen({});
		});
	}

	close() {
		this.readyState = 2;
	}

	addEventListener() {}
	removeEventListener() {}
	dispatchEvent() { return true; }
}

window.EventSource = MockEventSource;
`;

// ---------------------------------------------------------------------------
// SSE injection helpers (called from test via page.evaluate)
// ---------------------------------------------------------------------------

/** Dispatch a single SSE event via the MockEventSource. */
async function dispatchSSEEvent(
	page: Page,
	payload: Record<string, unknown>,
): Promise<void> {
	await page.evaluate((data) => {
		const sse = (window as unknown as Record<string, unknown>).__mockSSE as {
			onmessage: ((event: { data: string }) => void) | null;
		};
		if (sse?.onmessage) {
			sse.onmessage({ data: JSON.stringify(data) });
		}
	}, payload);
}

/**
 * Send chat tokens as individual SSE `chat_token` events.
 * Splits text into words and sends each as a separate token.
 */
export async function sendChatTokens(
	page: Page,
	text: string,
	delayMs = 0,
): Promise<void> {
	const words = text.split(" ");
	for (let i = 0; i < words.length; i++) {
		const token = i === 0 ? words[i] : ` ${words[i]}`;
		await dispatchSSEEvent(page, { type: "chat_token", text: token });
		if (delayMs > 0) {
			await page.waitForTimeout(delayMs);
		}
	}
}

/** Send a `chat_done` SSE event to mark the end of streaming. */
export async function sendChatDone(
	page: Page,
	messageId = "agent-msg-final",
): Promise<void> {
	await dispatchSSEEvent(page, { type: "chat_done", message_id: messageId });
}

/** Send a `tool_start` SSE event. */
export async function sendToolStart(
	page: Page,
	tool: string,
	args: Record<string, unknown> = {},
): Promise<void> {
	await dispatchSSEEvent(page, { type: "tool_start", tool, args });
}

/** Send a `tool_result` SSE event. */
export async function sendToolResult(
	page: Page,
	tool: string,
	success: boolean,
): Promise<void> {
	await dispatchSSEEvent(page, { type: "tool_result", tool, success });
}

// ---------------------------------------------------------------------------
// Controller
// ---------------------------------------------------------------------------

export class ChatMockController {
	state: ChatMockState;

	constructor(initialState?: Partial<ChatMockState>) {
		this.state = {
			chatHistory: [],
			postCount: 0,
			...initialState,
		};
	}

	async setupRoutes(page: Page): Promise<void> {
		// Install MockEventSource before any page code runs
		await page.addInitScript(MOCK_EVENT_SOURCE_SCRIPT);

		// Abort SSE / events endpoints to prevent hanging connections
		await page.route("**/api/v1/events/**", (route) => route.abort());
		await page.route("**/api/v1/events", (route) => route.abort());
		await page.route("**/api/v1/chat/stream", (route) => route.abort());

		// Single regex intercepts all /api/v1/ endpoints we need to mock
		await page.route(
			/\/api\/v1\/(chat|personas|persona-change-flags)/,
			async (route) => this.handleRoute(route),
		);
	}

	// -----------------------------------------------------------------------
	// Main router
	// -----------------------------------------------------------------------

	private async handleRoute(route: Route): Promise<void> {
		const url = route.request().url();
		const method = route.request().method();
		const path = new URL(url).pathname;

		// ---- Persona change flags — always empty ----
		if (path.endsWith("/persona-change-flags")) {
			return this.json(route, this.emptyList());
		}

		// ---- Personas — onboarded ----
		if (path.endsWith("/personas")) {
			return this.json(route, onboardedPersonaList());
		}

		// ---- Chat messages ----
		if (path.includes("/chat/messages")) {
			return this.handleChatMessages(route, method);
		}

		// ---- Chat stream (fallback — should be caught by abort above) ----
		if (path.includes("/chat/stream")) {
			return route.abort();
		}

		return route.continue();
	}

	// -----------------------------------------------------------------------
	// Chat messages handler
	// -----------------------------------------------------------------------

	private async handleChatMessages(
		route: Route,
		method: string,
	): Promise<void> {
		// loadHistory() passes the raw response to sanitizeHistoryMessages(),
		// which expects a plain array — NOT an API envelope.
		if (method === "GET") {
			return this.json(route, this.state.chatHistory);
		}

		if (method === "POST") {
			this.state.postCount++;
			return this.json(route, { data: { id: "msg-ack" } }, 201);
		}

		return route.abort();
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	private emptyList(): {
		data: never[];
		meta: { total: 0; page: 1; per_page: 100; total_pages: 1 };
	} {
		return {
			data: [],
			meta: { total: 0, page: 1, per_page: 100, total_pages: 1 },
		};
	}

	private async json(route: Route, body: unknown, status = 200): Promise<void> {
		await route.fulfill({
			status,
			contentType: "application/json",
			body: JSON.stringify(body),
		});
	}
}

// ---------------------------------------------------------------------------
// Convenience factories
// ---------------------------------------------------------------------------

/** Set up mocks with empty chat history. */
export async function setupChatMocks(page: Page): Promise<ChatMockController> {
	const controller = new ChatMockController();
	await controller.setupRoutes(page);
	return controller;
}

/** Set up mocks with 4-message chat history. */
export async function setupChatWithHistoryMocks(
	page: Page,
): Promise<ChatMockController> {
	const controller = new ChatMockController({
		chatHistory: chatHistoryResponse(),
	});
	await controller.setupRoutes(page);
	return controller;
}

/** Set up mocks with history including job + score cards. */
export async function setupChatWithCardsMocks(
	page: Page,
): Promise<ChatMockController> {
	const controller = new ChatMockController({
		chatHistory: chatHistoryWithCards(),
	});
	await controller.setupRoutes(page);
	return controller;
}

/** Set up mocks with history including option list. */
export async function setupChatWithOptionsMocks(
	page: Page,
): Promise<ChatMockController> {
	const controller = new ChatMockController({
		chatHistory: chatHistoryWithOptions(),
	});
	await controller.setupRoutes(page);
	return controller;
}
