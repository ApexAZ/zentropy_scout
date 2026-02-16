/**
 * E2E tests for the chat interaction flow.
 *
 * REQ-012 §5: Chat sidebar, message sending, SSE streaming, tool execution,
 * structured cards, and typing indicator.
 * All API calls are mocked via Playwright's page.route() — no real backend.
 * SSE is mocked via page.addInitScript() replacing EventSource.
 */

import { expect, test } from "@playwright/test";

import {
	sendChatDone,
	sendChatTokens,
	sendToolResult,
	sendToolStart,
	setupChatMocks,
	setupChatWithCardsMocks,
	setupChatWithHistoryMocks,
	setupChatWithOptionsMocks,
} from "../utils/chat-api-mocks";

// ---------------------------------------------------------------------------
// Shared selectors & text
// ---------------------------------------------------------------------------

const TOGGLE_CHAT = "Toggle chat";
const SEND_MESSAGE = "Send message";
const MESSAGE_INPUT = "Message";
const USER_BUBBLE = '[data-slot="message-bubble"][data-role="user"]';
const AGENT_BUBBLE = '[data-slot="message-bubble"][data-role="agent"]';

// ---------------------------------------------------------------------------
// A. Chat Panel Toggle
// ---------------------------------------------------------------------------

test.describe("Chat Panel Toggle", () => {
	test("opens and closes chat panel", async ({ page }) => {
		await setupChatMocks(page);
		await page.goto("/");

		// Panel should not be visible initially (desktop: w-0 overflow-hidden)
		const messageList = page.locator('[data-slot="chat-message-list"]');
		await expect(messageList).not.toBeVisible();

		// Open the panel
		const toggleButton = page.getByRole("button", { name: TOGGLE_CHAT });
		await toggleButton.click();
		await expect(messageList).toBeVisible();

		// Close the panel
		await toggleButton.click();
		await expect(messageList).not.toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// B. Send Message
// ---------------------------------------------------------------------------

test.describe("Send Message", () => {
	test("sends message via POST and shows user bubble", async ({ page }) => {
		await setupChatMocks(page);
		await page.goto("/");

		// Open chat panel
		await page.getByRole("button", { name: TOGGLE_CHAT }).click();

		// Type and send a message
		const textarea = page.getByRole("textbox", { name: MESSAGE_INPUT });
		await textarea.fill("Hello Scout");

		const postPromise = page.waitForResponse(
			(res) =>
				res.url().includes("/chat/messages") &&
				res.request().method() === "POST",
		);

		await page.getByRole("button", { name: SEND_MESSAGE }).click();
		await postPromise;

		// Verify user bubble appears
		const userBubble = page.locator(USER_BUBBLE);
		await expect(userBubble).toBeVisible();
		await expect(userBubble).toContainText("Hello Scout");

		// Verify textarea is cleared
		await expect(textarea).toHaveValue("");
	});
});

// ---------------------------------------------------------------------------
// C. Streaming Response
// ---------------------------------------------------------------------------

test.describe("Streaming Response", () => {
	test("displays agent bubble with streamed tokens", async ({ page }) => {
		await setupChatMocks(page);
		await page.goto("/");

		// Open panel and send message
		await page.getByRole("button", { name: TOGGLE_CHAT }).click();
		await page.getByRole("textbox", { name: MESSAGE_INPUT }).fill("Hi");
		await page.getByRole("button", { name: SEND_MESSAGE }).click();

		// Stream tokens from "agent"
		await sendChatTokens(page, "Hello! I can help you");

		// Verify agent bubble appears with streamed text
		const agentBubble = page.locator(AGENT_BUBBLE);
		await expect(agentBubble).toBeVisible();
		await expect(agentBubble).toContainText("Hello! I can help you");

		// Streaming cursor should be visible while streaming
		await expect(page.locator('[data-slot="streaming-cursor"]')).toBeVisible();

		// End streaming
		await sendChatDone(page);

		// Streaming cursor should disappear
		await expect(
			page.locator('[data-slot="streaming-cursor"]'),
		).not.toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// D. Tool Execution
// ---------------------------------------------------------------------------

test.describe("Tool Execution", () => {
	test("shows spinner then success badge", async ({ page }) => {
		await setupChatMocks(page);
		await page.goto("/");

		// Open panel and send message
		await page.getByRole("button", { name: TOGGLE_CHAT }).click();
		await page
			.getByRole("textbox", { name: MESSAGE_INPUT })
			.fill("Search jobs");
		await page.getByRole("button", { name: SEND_MESSAGE }).click();

		// Stream some tokens first to create the agent message
		await sendChatTokens(page, "Searching for you");

		// Start tool execution
		await sendToolStart(page, "search_jobs", { query: "React" });

		// Verify running badge
		const toolBadge = page.locator('[data-slot="tool-execution"]');
		await expect(toolBadge).toBeVisible();
		await expect(toolBadge).toHaveAttribute("data-status", "running");
		await expect(toolBadge).toContainText("Search jobs");

		// Complete tool execution
		await sendToolResult(page, "search_jobs", true);

		// Verify success badge
		await expect(toolBadge).toHaveAttribute("data-status", "success");

		// End streaming
		await sendChatDone(page);
	});
});

// ---------------------------------------------------------------------------
// E. Typing Indicator
// ---------------------------------------------------------------------------

test.describe("Typing Indicator", () => {
	test("appears during streaming, disappears after done", async ({ page }) => {
		await setupChatMocks(page);
		await page.goto("/");

		// Open panel and send message
		await page.getByRole("button", { name: TOGGLE_CHAT }).click();
		await page.getByRole("textbox", { name: MESSAGE_INPUT }).fill("Hello");
		await page.getByRole("button", { name: SEND_MESSAGE }).click();

		// Typing indicator should appear (isStreaming becomes true on send)
		const typingIndicator = page.locator('[data-slot="typing-indicator"]');
		await expect(typingIndicator).toBeVisible();
		await expect(typingIndicator).toContainText("Scout is typing");

		// Stream tokens — indicator should still be visible
		await sendChatTokens(page, "Working on it");
		await expect(typingIndicator).toBeVisible();

		// End streaming
		await sendChatDone(page);

		// Typing indicator should disappear
		await expect(typingIndicator).not.toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// F. Chat History
// ---------------------------------------------------------------------------

test.describe("Chat History", () => {
	test("loads and displays persisted messages", async ({ page }) => {
		await setupChatWithHistoryMocks(page);
		await page.goto("/");

		// Open chat panel
		await page.getByRole("button", { name: TOGGLE_CHAT }).click();

		// Verify 2 user bubbles and 2 agent bubbles from history
		const userBubbles = page.locator(USER_BUBBLE);
		const agentBubbles = page.locator(AGENT_BUBBLE);
		await expect(userBubbles).toHaveCount(2);
		await expect(agentBubbles).toHaveCount(2);
	});
});

// ---------------------------------------------------------------------------
// G. Structured Cards & Option List
// ---------------------------------------------------------------------------

test.describe("Structured Cards", () => {
	test("renders job card and score card", async ({ page }) => {
		await setupChatWithCardsMocks(page);
		await page.goto("/");

		// Open chat panel
		await page.getByRole("button", { name: TOGGLE_CHAT }).click();

		// Verify job card renders
		const jobCard = page.locator('[data-slot="chat-job-card"]');
		await expect(jobCard).toBeVisible();
		await expect(jobCard).toContainText("Senior React Developer");
		await expect(jobCard).toContainText("TechCorp");

		// Verify score card renders
		const scoreCard = page.locator('[data-slot="chat-score-card"]');
		await expect(scoreCard).toBeVisible();
	});

	test("renders option list with clickable items", async ({ page }) => {
		await setupChatWithOptionsMocks(page);
		await page.goto("/");

		// Open chat panel
		await page.getByRole("button", { name: TOGGLE_CHAT }).click();

		// Verify option list renders
		const optionList = page.locator('[data-slot="chat-option-list"]');
		await expect(optionList).toBeVisible();

		// Verify 3 option items
		const optionItems = page.locator('[data-slot="option-item"]');
		await expect(optionItems).toHaveCount(3);

		// Verify hint text
		await expect(optionList).toContainText("Or type to describe");
	});
});

// ---------------------------------------------------------------------------
// H. Input Disabled During Streaming
// ---------------------------------------------------------------------------

test.describe("Input Disabled During Streaming", () => {
	test("textarea and send button disabled while streaming", async ({
		page,
	}) => {
		await setupChatMocks(page);
		await page.goto("/");

		// Open panel and send message
		await page.getByRole("button", { name: TOGGLE_CHAT }).click();
		await page.getByRole("textbox", { name: MESSAGE_INPUT }).fill("Hello");
		await page.getByRole("button", { name: SEND_MESSAGE }).click();

		// Verify textarea and send button are disabled during streaming
		await expect(
			page.getByRole("textbox", { name: MESSAGE_INPUT }),
		).toBeDisabled();
		await expect(
			page.getByRole("button", { name: SEND_MESSAGE }),
		).toBeDisabled();

		// Stream tokens and end
		await sendChatTokens(page, "Response text");
		await sendChatDone(page);

		// Verify textarea is re-enabled after streaming completes
		await expect(
			page.getByRole("textbox", { name: MESSAGE_INPUT }),
		).toBeEnabled();
	});
});
