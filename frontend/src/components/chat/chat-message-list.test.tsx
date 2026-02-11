/**
 * Tests for the chat message list container.
 *
 * REQ-012 §5.8: Scrollable message list with auto-scroll to bottom,
 * "Jump to latest" floating button, loading state for history fetch,
 * and empty state.
 */

import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ChatMessage } from "@/types/chat";

import { ChatMessageList } from "./chat-message-list";

// ---------------------------------------------------------------------------
// IntersectionObserver mock
// ---------------------------------------------------------------------------

type IntersectionCallback = (entries: IntersectionObserverEntry[]) => void;

let observerCallback: IntersectionCallback | null = null;
const mockObserve = vi.fn();
const mockDisconnect = vi.fn();

class MockIntersectionObserver {
	constructor(callback: IntersectionCallback) {
		observerCallback = callback;
	}
	observe = mockObserve;
	unobserve = vi.fn();
	disconnect = mockDisconnect;
}

// ---------------------------------------------------------------------------
// Mock MessageBubble (isolate from complex card dependencies)
// ---------------------------------------------------------------------------

vi.mock("./message-bubble", () => ({
	MessageBubble: ({ message }: { message: ChatMessage }) => (
		<div data-testid={`msg-${message.id}`} data-role={message.role}>
			{message.content}
		</div>
	),
}));

// ---------------------------------------------------------------------------
// Selectors
// ---------------------------------------------------------------------------

const LIST_SELECTOR = '[data-slot="chat-message-list"]';
const SCROLL_CONTAINER_SELECTOR = '[data-slot="chat-scroll-container"]';
const BOTTOM_SENTINEL_SELECTOR = '[data-slot="chat-scroll-sentinel"]';
const JUMP_BUTTON_SELECTOR = '[data-slot="jump-to-latest"]';
const EMPTY_STATE_SELECTOR = '[data-slot="chat-empty-state"]';
const LOADING_SELECTOR = '[data-slot="chat-loading"]';

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

function makeMessage(overrides: Partial<ChatMessage> = {}): ChatMessage {
	return {
		id: "msg-1",
		role: "user",
		content: "Hello",
		timestamp: "2026-01-01T12:00:00Z",
		isStreaming: false,
		tools: [],
		cards: [],
		...overrides,
	};
}

const MESSAGES: ChatMessage[] = [
	makeMessage({ id: "msg-1", role: "user", content: "Hello" }),
	makeMessage({ id: "msg-2", role: "agent", content: "Hi there!" }),
	makeMessage({ id: "msg-3", role: "user", content: "How are you?" }),
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fireIntersection(isIntersecting: boolean) {
	act(() => {
		observerCallback?.([{ isIntersecting } as IntersectionObserverEntry]);
	});
}

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

let originalIntersectionObserver: typeof IntersectionObserver;

beforeEach(() => {
	originalIntersectionObserver = globalThis.IntersectionObserver;
	globalThis.IntersectionObserver =
		MockIntersectionObserver as unknown as typeof IntersectionObserver;
	observerCallback = null;
	mockObserve.mockClear();
	mockDisconnect.mockClear();

	// JSDOM does not implement scrollIntoView
	Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
	globalThis.IntersectionObserver = originalIntersectionObserver;
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ChatMessageList", () => {
	// -----------------------------------------------------------------------
	// Structure
	// -----------------------------------------------------------------------

	describe("structure", () => {
		it("renders the message list wrapper", () => {
			const { container } = render(<ChatMessageList messages={MESSAGES} />);

			expect(container.querySelector(LIST_SELECTOR)).toBeInTheDocument();
		});

		it("renders a scroll container", () => {
			const { container } = render(<ChatMessageList messages={MESSAGES} />);

			expect(
				container.querySelector(SCROLL_CONTAINER_SELECTOR),
			).toBeInTheDocument();
		});

		it("renders a bottom sentinel element", () => {
			const { container } = render(<ChatMessageList messages={MESSAGES} />);

			expect(
				container.querySelector(BOTTOM_SENTINEL_SELECTOR),
			).toBeInTheDocument();
		});

		it("renders message bubbles for each message", () => {
			render(<ChatMessageList messages={MESSAGES} />);

			expect(screen.getByTestId("msg-msg-1")).toBeInTheDocument();
			expect(screen.getByTestId("msg-msg-2")).toBeInTheDocument();
			expect(screen.getByTestId("msg-msg-3")).toBeInTheDocument();
		});

		it("renders messages in order", () => {
			const { container } = render(<ChatMessageList messages={MESSAGES} />);

			const scrollContainer = container.querySelector(
				SCROLL_CONTAINER_SELECTOR,
			);
			const bubbles =
				scrollContainer?.querySelectorAll("[data-testid^='msg-']") ?? [];
			const ids = Array.from(bubbles).map((el) =>
				el.getAttribute("data-testid"),
			);

			expect(ids).toEqual(["msg-msg-1", "msg-msg-2", "msg-msg-3"]);
		});

		it("merges custom className", () => {
			const { container } = render(
				<ChatMessageList messages={MESSAGES} className="mt-4" />,
			);

			const wrapper = container.querySelector(LIST_SELECTOR);
			expect(wrapper).toHaveClass("mt-4");
		});
	});

	// -----------------------------------------------------------------------
	// Empty state
	// -----------------------------------------------------------------------

	describe("empty state", () => {
		it("shows empty state when no messages and not loading", () => {
			const { container } = render(<ChatMessageList messages={[]} />);

			expect(container.querySelector(EMPTY_STATE_SELECTOR)).toBeInTheDocument();
		});

		it("does not show empty state when messages exist", () => {
			const { container } = render(<ChatMessageList messages={MESSAGES} />);

			expect(
				container.querySelector(EMPTY_STATE_SELECTOR),
			).not.toBeInTheDocument();
		});

		it("does not show empty state when loading", () => {
			const { container } = render(<ChatMessageList messages={[]} isLoading />);

			expect(
				container.querySelector(EMPTY_STATE_SELECTOR),
			).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Loading state
	// -----------------------------------------------------------------------

	describe("loading state", () => {
		it("shows loading indicator when isLoading is true", () => {
			const { container } = render(<ChatMessageList messages={[]} isLoading />);

			expect(container.querySelector(LOADING_SELECTOR)).toBeInTheDocument();
		});

		it("does not show loading indicator by default", () => {
			const { container } = render(<ChatMessageList messages={[]} />);

			expect(container.querySelector(LOADING_SELECTOR)).not.toBeInTheDocument();
		});

		it("does not show loading indicator when messages exist", () => {
			const { container } = render(
				<ChatMessageList messages={MESSAGES} isLoading />,
			);

			expect(container.querySelector(LOADING_SELECTOR)).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Jump to latest button
	// -----------------------------------------------------------------------

	describe("jump to latest", () => {
		it("does not show jump-to-latest button by default", () => {
			const { container } = render(<ChatMessageList messages={MESSAGES} />);

			expect(
				container.querySelector(JUMP_BUTTON_SELECTOR),
			).not.toBeInTheDocument();
		});

		it("shows jump-to-latest when scrolled up and new messages arrive", () => {
			const { container, rerender } = render(
				<ChatMessageList messages={MESSAGES} />,
			);

			fireIntersection(false);
			rerender(
				<ChatMessageList
					messages={[...MESSAGES, makeMessage({ id: "msg-4", content: "New" })]}
				/>,
			);

			expect(container.querySelector(JUMP_BUTTON_SELECTOR)).toBeInTheDocument();
		});

		it("hides jump-to-latest when scrolled back to bottom", () => {
			const { container, rerender } = render(
				<ChatMessageList messages={MESSAGES} />,
			);

			fireIntersection(false);
			rerender(
				<ChatMessageList
					messages={[...MESSAGES, makeMessage({ id: "msg-4", content: "New" })]}
				/>,
			);
			expect(container.querySelector(JUMP_BUTTON_SELECTOR)).toBeInTheDocument();

			fireIntersection(true);
			expect(
				container.querySelector(JUMP_BUTTON_SELECTOR),
			).not.toBeInTheDocument();
		});

		it("jump-to-latest button has accessible label", () => {
			const { rerender } = render(<ChatMessageList messages={MESSAGES} />);

			fireIntersection(false);
			rerender(
				<ChatMessageList
					messages={[...MESSAGES, makeMessage({ id: "msg-4", content: "New" })]}
				/>,
			);

			expect(
				screen.getByRole("button", { name: /jump to latest/i }),
			).toBeInTheDocument();
		});

		it("clicking jump-to-latest hides the button", async () => {
			const user = userEvent.setup();
			const { container, rerender } = render(
				<ChatMessageList messages={MESSAGES} />,
			);

			fireIntersection(false);
			rerender(
				<ChatMessageList
					messages={[...MESSAGES, makeMessage({ id: "msg-4", content: "New" })]}
				/>,
			);

			await user.click(screen.getByRole("button", { name: /jump to latest/i }));

			expect(
				container.querySelector(JUMP_BUTTON_SELECTOR),
			).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Accessibility
	// -----------------------------------------------------------------------

	describe("accessibility", () => {
		it("scroll container has role log", () => {
			const { container } = render(<ChatMessageList messages={MESSAGES} />);

			const scrollContainer = container.querySelector(
				SCROLL_CONTAINER_SELECTOR,
			);
			expect(scrollContainer).toHaveAttribute("role", "log");
		});

		it("scroll container has aria-label", () => {
			const { container } = render(<ChatMessageList messages={MESSAGES} />);

			const scrollContainer = container.querySelector(
				SCROLL_CONTAINER_SELECTOR,
			);
			expect(scrollContainer).toHaveAttribute(
				"aria-label",
				expect.stringContaining("message"),
			);
		});

		it("bottom sentinel is visually hidden", () => {
			const { container } = render(<ChatMessageList messages={MESSAGES} />);

			const sentinel = container.querySelector(BOTTOM_SENTINEL_SELECTOR);
			expect(sentinel).toHaveAttribute("aria-hidden", "true");
		});
	});
});
