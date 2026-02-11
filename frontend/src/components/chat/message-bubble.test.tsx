/**
 * Tests for message bubble components.
 *
 * REQ-012 §5.2: Message types with role-based alignment and styling.
 * User messages right-aligned with primary color, agent messages
 * left-aligned with muted background, system notices centered.
 */

import { render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { describe, expect, it } from "vitest";

import type { ChatMessage } from "@/types/chat";

import { MessageBubble } from "./message-bubble";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const USER_MESSAGE: ChatMessage = {
	id: "msg-user-1",
	role: "user",
	content: "Hello, can you help me find a job?",
	timestamp: "2026-02-11T10:30:00.000Z",
	isStreaming: false,
	tools: [],
};

const AGENT_MESSAGE: ChatMessage = {
	id: "msg-agent-1",
	role: "agent",
	content: "Of course! Let me search for matching positions.",
	timestamp: "2026-02-11T10:30:05.000Z",
	isStreaming: false,
	tools: [],
};

const SYSTEM_MESSAGE: ChatMessage = {
	id: "msg-system-1",
	role: "system",
	content: "Connected to Scout",
	timestamp: "2026-02-11T10:29:55.000Z",
	isStreaming: false,
	tools: [],
};

// ---------------------------------------------------------------------------
// Selectors
// ---------------------------------------------------------------------------

const BUBBLE_SELECTOR = '[data-slot="message-bubble"]';
const CONTENT_SELECTOR = '[data-slot="message-content"]';
const TIMESTAMP_SELECTOR = '[data-slot="message-timestamp"]';
const NOTICE_SELECTOR = '[data-slot="system-notice"]';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderBubble(
	props: Partial<ComponentProps<typeof MessageBubble>> = {},
) {
	return render(<MessageBubble message={USER_MESSAGE} {...props} />);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("MessageBubble", () => {
	// -----------------------------------------------------------------------
	// User messages
	// -----------------------------------------------------------------------

	describe("user message", () => {
		it("renders message content", () => {
			renderBubble();

			expect(screen.getByText(USER_MESSAGE.content)).toBeInTheDocument();
		});

		it("has right alignment", () => {
			const { container } = renderBubble();

			const wrapper = container.querySelector(BUBBLE_SELECTOR);
			expect(wrapper).toHaveClass("justify-end");
		});

		it("uses primary color background", () => {
			const { container } = renderBubble();

			const content = container.querySelector(CONTENT_SELECTOR);
			expect(content).toHaveClass("bg-primary");
			expect(content).toHaveClass("text-primary-foreground");
		});

		it("displays timestamp", () => {
			const { container } = renderBubble();

			const timestamp = container.querySelector(TIMESTAMP_SELECTOR);
			expect(timestamp).toBeInTheDocument();
			expect(timestamp?.textContent).toBeTruthy();
		});

		it("has data-role attribute", () => {
			const { container } = renderBubble();

			const wrapper = container.querySelector(BUBBLE_SELECTOR);
			expect(wrapper).toHaveAttribute("data-role", "user");
		});

		it("merges custom className on wrapper", () => {
			const { container } = renderBubble({ className: "my-custom" });

			const wrapper = container.querySelector(BUBBLE_SELECTOR);
			expect(wrapper).toHaveClass("my-custom");
		});
	});

	// -----------------------------------------------------------------------
	// Agent messages
	// -----------------------------------------------------------------------

	describe("agent message", () => {
		it("renders message content", () => {
			renderBubble({ message: AGENT_MESSAGE });

			expect(screen.getByText(AGENT_MESSAGE.content)).toBeInTheDocument();
		});

		it("has left alignment", () => {
			const { container } = renderBubble({ message: AGENT_MESSAGE });

			const wrapper = container.querySelector(BUBBLE_SELECTOR);
			expect(wrapper).toHaveClass("justify-start");
		});

		it("uses muted background", () => {
			const { container } = renderBubble({ message: AGENT_MESSAGE });

			const content = container.querySelector(CONTENT_SELECTOR);
			expect(content).toHaveClass("bg-muted");
			expect(content).toHaveClass("text-foreground");
		});

		it("displays timestamp", () => {
			const { container } = renderBubble({ message: AGENT_MESSAGE });

			const timestamp = container.querySelector(TIMESTAMP_SELECTOR);
			expect(timestamp).toBeInTheDocument();
			expect(timestamp?.textContent).toBeTruthy();
		});

		it("has data-role attribute", () => {
			const { container } = renderBubble({ message: AGENT_MESSAGE });

			const wrapper = container.querySelector(BUBBLE_SELECTOR);
			expect(wrapper).toHaveAttribute("data-role", "agent");
		});
	});

	// -----------------------------------------------------------------------
	// System notices
	// -----------------------------------------------------------------------

	describe("system notice", () => {
		it("renders notice content", () => {
			renderBubble({ message: SYSTEM_MESSAGE });

			expect(screen.getByText(SYSTEM_MESSAGE.content)).toBeInTheDocument();
		});

		it("has center alignment", () => {
			const { container } = renderBubble({ message: SYSTEM_MESSAGE });

			const notice = container.querySelector(NOTICE_SELECTOR);
			expect(notice).toHaveClass("text-center");
		});

		it("uses muted small text styling", () => {
			const { container } = renderBubble({ message: SYSTEM_MESSAGE });

			const notice = container.querySelector(NOTICE_SELECTOR);
			expect(notice).toHaveClass("text-muted-foreground");
			expect(notice).toHaveClass("text-xs");
		});

		it("has data-role attribute", () => {
			const { container } = renderBubble({ message: SYSTEM_MESSAGE });

			const notice = container.querySelector(NOTICE_SELECTOR);
			expect(notice).toHaveAttribute("data-role", "system");
		});

		it("does not render a bubble content wrapper", () => {
			const { container } = renderBubble({ message: SYSTEM_MESSAGE });

			expect(container.querySelector(CONTENT_SELECTOR)).not.toBeInTheDocument();
		});

		it("does not render a timestamp", () => {
			const { container } = renderBubble({ message: SYSTEM_MESSAGE });

			expect(
				container.querySelector(TIMESTAMP_SELECTOR),
			).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Accessibility
	// -----------------------------------------------------------------------

	describe("accessibility", () => {
		it("system notice has status role", () => {
			renderBubble({ message: SYSTEM_MESSAGE });

			expect(screen.getByRole("status")).toBeInTheDocument();
		});

		it("user message timestamp uses time element with dateTime", () => {
			const { container } = renderBubble();

			const time = container.querySelector("time");
			expect(time).toBeInTheDocument();
			expect(time).toHaveAttribute("dateTime", USER_MESSAGE.timestamp);
		});

		it("agent message timestamp uses time element with dateTime", () => {
			const { container } = renderBubble({ message: AGENT_MESSAGE });

			const time = container.querySelector("time");
			expect(time).toBeInTheDocument();
			expect(time).toHaveAttribute("dateTime", AGENT_MESSAGE.timestamp);
		});

		it("user message has aria-label identifying sender", () => {
			const { container } = renderBubble();

			const wrapper = container.querySelector(BUBBLE_SELECTOR);
			expect(wrapper).toHaveAttribute(
				"aria-label",
				expect.stringContaining("You"),
			);
		});

		it("agent message has aria-label identifying sender", () => {
			const { container } = renderBubble({ message: AGENT_MESSAGE });

			const wrapper = container.querySelector(BUBBLE_SELECTOR);
			expect(wrapper).toHaveAttribute(
				"aria-label",
				expect.stringContaining("Scout"),
			);
		});
	});

	// -----------------------------------------------------------------------
	// Security
	// -----------------------------------------------------------------------

	describe("security", () => {
		it("renders HTML-like content as plain text, not as HTML elements", () => {
			const xssContent = '<script>alert("xss")</script>';
			const xssMsg: ChatMessage = {
				...USER_MESSAGE,
				content: xssContent,
			};
			renderBubble({ message: xssMsg });

			expect(screen.getByText(xssContent)).toBeInTheDocument();
		});

		it("renders HTML attributes in content as plain text", () => {
			const imgContent = "<img src=x onerror=alert(1)>";
			const imgMsg: ChatMessage = {
				...AGENT_MESSAGE,
				content: imgContent,
			};
			renderBubble({ message: imgMsg });

			expect(screen.getByText(imgContent)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Edge cases
	// -----------------------------------------------------------------------

	describe("edge cases", () => {
		it("renders empty content gracefully", () => {
			const emptyMsg: ChatMessage = { ...USER_MESSAGE, content: "" };
			const { container } = renderBubble({ message: emptyMsg });

			expect(container.querySelector(BUBBLE_SELECTOR)).toBeInTheDocument();
		});

		it("renders long content without breaking layout", () => {
			const longMsg: ChatMessage = {
				...AGENT_MESSAGE,
				content: "x".repeat(5000),
			};
			const { container } = renderBubble({ message: longMsg });

			const content = container.querySelector(CONTENT_SELECTOR);
			expect(content).toBeInTheDocument();
			expect(content).toHaveClass("break-words");
		});

		it("renders streaming agent message", () => {
			const streamingMsg: ChatMessage = {
				...AGENT_MESSAGE,
				isStreaming: true,
			};
			const { container } = renderBubble({ message: streamingMsg });

			const wrapper = container.querySelector(BUBBLE_SELECTOR);
			expect(wrapper).toHaveAttribute("data-streaming", "true");
		});

		it("non-streaming message has data-streaming false", () => {
			const { container } = renderBubble({ message: AGENT_MESSAGE });

			const wrapper = container.querySelector(BUBBLE_SELECTOR);
			expect(wrapper).toHaveAttribute("data-streaming", "false");
		});
	});
});
