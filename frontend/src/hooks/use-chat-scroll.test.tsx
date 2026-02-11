/**
 * Tests for the chat scroll management hook.
 *
 * REQ-012 §5.8: Scroll to bottom on new messages (unless user has
 * scrolled up). "Jump to latest" button appears when scrolled up
 * and new messages arrive.
 */

import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useChatScroll } from "./use-chat-scroll";

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
// Selectors
// ---------------------------------------------------------------------------

const CONTAINER_TEST_ID = "container";
const BOTTOM_TEST_ID = "bottom";
const AT_BOTTOM_TEST_ID = "is-at-bottom";
const SHOW_JUMP_TEST_ID = "show-jump";
const SCROLL_BUTTON_TEST_ID = "scroll-btn";

// ---------------------------------------------------------------------------
// Wrapper component
// ---------------------------------------------------------------------------

function TestComponent({ messageCount }: { messageCount: number }) {
	const {
		containerRef,
		bottomRef,
		isAtBottom,
		showJumpToLatest,
		scrollToBottom,
	} = useChatScroll({ messageCount });
	return (
		<div ref={containerRef} data-testid={CONTAINER_TEST_ID}>
			<div ref={bottomRef} data-testid={BOTTOM_TEST_ID} />
			<div data-testid={AT_BOTTOM_TEST_ID}>{String(isAtBottom)}</div>
			<div data-testid={SHOW_JUMP_TEST_ID}>{String(showJumpToLatest)}</div>
			<button data-testid={SCROLL_BUTTON_TEST_ID} onClick={scrollToBottom}>
				Scroll
			</button>
		</div>
	);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getIsAtBottom(): boolean {
	return screen.getByTestId(AT_BOTTOM_TEST_ID).textContent === "true";
}

function getShowJump(): boolean {
	return screen.getByTestId(SHOW_JUMP_TEST_ID).textContent === "true";
}

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
});

afterEach(() => {
	globalThis.IntersectionObserver = originalIntersectionObserver;
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useChatScroll", () => {
	// -----------------------------------------------------------------------
	// Initial state
	// -----------------------------------------------------------------------

	describe("initial state", () => {
		it("provides containerRef attached to DOM element", () => {
			render(<TestComponent messageCount={0} />);

			expect(screen.getByTestId(CONTAINER_TEST_ID)).toBeInTheDocument();
		});

		it("provides bottomRef attached to DOM element", () => {
			render(<TestComponent messageCount={0} />);

			expect(screen.getByTestId(BOTTOM_TEST_ID)).toBeInTheDocument();
		});

		it("returns isAtBottom as true initially", () => {
			render(<TestComponent messageCount={0} />);

			expect(getIsAtBottom()).toBe(true);
		});

		it("returns showJumpToLatest as false initially", () => {
			render(<TestComponent messageCount={0} />);

			expect(getShowJump()).toBe(false);
		});

		it("observes the bottom sentinel element", () => {
			render(<TestComponent messageCount={0} />);

			expect(mockObserve).toHaveBeenCalledWith(
				screen.getByTestId(BOTTOM_TEST_ID),
			);
		});
	});

	// -----------------------------------------------------------------------
	// Scroll position tracking
	// -----------------------------------------------------------------------

	describe("scroll position tracking", () => {
		it("sets isAtBottom to false when sentinel leaves viewport", () => {
			render(<TestComponent messageCount={0} />);

			fireIntersection(false);

			expect(getIsAtBottom()).toBe(false);
		});

		it("sets isAtBottom to true when sentinel enters viewport", () => {
			render(<TestComponent messageCount={0} />);

			fireIntersection(false);
			expect(getIsAtBottom()).toBe(false);

			fireIntersection(true);
			expect(getIsAtBottom()).toBe(true);
		});
	});

	// -----------------------------------------------------------------------
	// Jump to latest
	// -----------------------------------------------------------------------

	describe("jump to latest", () => {
		it("shows when not at bottom and messages change", () => {
			const { rerender } = render(<TestComponent messageCount={5} />);

			fireIntersection(false);
			rerender(<TestComponent messageCount={6} />);

			expect(getShowJump()).toBe(true);
		});

		it("does not show when at bottom even if messages change", () => {
			const { rerender } = render(<TestComponent messageCount={5} />);
			screen.getByTestId(BOTTOM_TEST_ID).scrollIntoView = vi.fn();

			fireIntersection(true);
			rerender(<TestComponent messageCount={6} />);

			expect(getShowJump()).toBe(false);
		});

		it("does not show when message count has not changed", () => {
			render(<TestComponent messageCount={5} />);

			fireIntersection(false);

			expect(getShowJump()).toBe(false);
		});

		it("hides after scrollToBottom is called", async () => {
			const user = userEvent.setup();
			const { rerender } = render(<TestComponent messageCount={5} />);
			screen.getByTestId(BOTTOM_TEST_ID).scrollIntoView = vi.fn();

			fireIntersection(false);
			rerender(<TestComponent messageCount={6} />);
			expect(getShowJump()).toBe(true);

			await user.click(screen.getByTestId(SCROLL_BUTTON_TEST_ID));

			expect(getShowJump()).toBe(false);
		});

		it("hides when user scrolls back to bottom", () => {
			const { rerender } = render(<TestComponent messageCount={5} />);
			screen.getByTestId(BOTTOM_TEST_ID).scrollIntoView = vi.fn();

			fireIntersection(false);
			rerender(<TestComponent messageCount={6} />);
			expect(getShowJump()).toBe(true);

			fireIntersection(true);
			expect(getShowJump()).toBe(false);
		});
	});

	// -----------------------------------------------------------------------
	// scrollToBottom
	// -----------------------------------------------------------------------

	describe("scrollToBottom", () => {
		it("calls scrollIntoView on the bottom sentinel", async () => {
			const user = userEvent.setup();
			render(<TestComponent messageCount={0} />);

			const sentinel = screen.getByTestId(BOTTOM_TEST_ID);
			sentinel.scrollIntoView = vi.fn();

			await user.click(screen.getByTestId(SCROLL_BUTTON_TEST_ID));

			expect(sentinel.scrollIntoView).toHaveBeenCalledWith({
				behavior: "smooth",
			});
		});
	});

	// -----------------------------------------------------------------------
	// Auto-scroll on new messages
	// -----------------------------------------------------------------------

	describe("auto-scroll on new messages", () => {
		it("scrolls to bottom when at bottom and messages change", () => {
			const { rerender } = render(<TestComponent messageCount={5} />);
			const sentinel = screen.getByTestId(BOTTOM_TEST_ID);
			sentinel.scrollIntoView = vi.fn();

			fireIntersection(true);
			rerender(<TestComponent messageCount={6} />);

			expect(sentinel.scrollIntoView).toHaveBeenCalledWith({
				behavior: "smooth",
			});
		});

		it("does not auto-scroll when not at bottom", () => {
			const { rerender } = render(<TestComponent messageCount={5} />);
			const sentinel = screen.getByTestId(BOTTOM_TEST_ID);
			sentinel.scrollIntoView = vi.fn();

			fireIntersection(false);
			rerender(<TestComponent messageCount={6} />);

			expect(sentinel.scrollIntoView).not.toHaveBeenCalled();
		});
	});

	// -----------------------------------------------------------------------
	// Cleanup
	// -----------------------------------------------------------------------

	describe("cleanup", () => {
		it("disconnects observer on unmount", () => {
			const { unmount } = render(<TestComponent messageCount={0} />);

			unmount();

			expect(mockDisconnect).toHaveBeenCalled();
		});
	});
});
