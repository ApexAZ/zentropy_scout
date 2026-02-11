/**
 * Chat scroll management hook.
 *
 * REQ-012 §5.8: Auto-scroll to bottom on new messages (unless user
 * has scrolled up). "Jump to latest" button appears when scrolled
 * up and new messages arrive.
 *
 * Uses IntersectionObserver on a bottom sentinel element to detect
 * whether the user is at the bottom of the scroll container.
 */

import { useCallback, useEffect, useRef, useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface UseChatScrollOptions {
	/** Number of messages — triggers scroll/jump logic on change. */
	messageCount: number;
}

interface UseChatScrollReturn {
	/** Ref to attach to the scrollable container element. */
	containerRef: React.RefObject<HTMLDivElement | null>;
	/** Ref to attach to the bottom sentinel element. */
	bottomRef: React.RefObject<HTMLDivElement | null>;
	/** Whether the scroll position is at the bottom. */
	isAtBottom: boolean;
	/** Whether the "Jump to latest" button should be visible. */
	showJumpToLatest: boolean;
	/** Scrolls the sentinel into view (smooth scroll). */
	scrollToBottom: () => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Manages chat scroll behavior with IntersectionObserver.
 *
 * Tracks whether the user is at the bottom of the scroll container
 * and determines when to show the "Jump to latest" button.
 *
 * @param options.messageCount - Current message count; changes trigger
 *   auto-scroll (if at bottom) or "Jump to latest" (if scrolled up).
 * @returns Refs, state, and a scrollToBottom function.
 */
export function useChatScroll({
	messageCount,
}: UseChatScrollOptions): UseChatScrollReturn {
	const containerRef = useRef<HTMLDivElement | null>(null);
	const bottomRef = useRef<HTMLDivElement | null>(null);
	const [isAtBottom, setIsAtBottom] = useState(true);
	const [showJumpToLatest, setShowJumpToLatest] = useState(false);

	// Track previous message count to detect new messages
	const prevMessageCountRef = useRef(messageCount);

	// Track isAtBottom in a ref for the message count effect
	const isAtBottomRef = useRef(isAtBottom);
	useEffect(() => {
		isAtBottomRef.current = isAtBottom;
	}, [isAtBottom]);

	// Shared scroll helper — guards against environments without scrollIntoView
	const doScroll = useCallback(() => {
		const el = bottomRef.current;
		if (el && typeof el.scrollIntoView === "function") {
			el.scrollIntoView({ behavior: "smooth" });
		}
	}, []);

	// -----------------------------------------------------------------------
	// IntersectionObserver: detect scroll position
	// -----------------------------------------------------------------------

	useEffect(() => {
		const sentinel = bottomRef.current;
		if (!sentinel) return;

		const observer = new IntersectionObserver(
			(entries) => {
				const entry = entries[0];
				const intersecting = entry.isIntersecting;
				setIsAtBottom(intersecting);
				if (intersecting) {
					setShowJumpToLatest(false);
				}
			},
			{ root: containerRef.current },
		);

		observer.observe(sentinel);

		return () => {
			observer.disconnect();
		};
	}, []);

	// -----------------------------------------------------------------------
	// React to message count changes
	// -----------------------------------------------------------------------

	useEffect(() => {
		if (messageCount === prevMessageCountRef.current) return;
		prevMessageCountRef.current = messageCount;

		if (isAtBottomRef.current) {
			doScroll();
		} else {
			// Show "Jump to latest" — this is a legitimate prop-change
			// response; the effect reacts to messageCount changes and
			// conditionally updates derived UI state.
			// eslint-disable-next-line react-hooks/set-state-in-effect
			setShowJumpToLatest(true);
		}
	}, [messageCount, doScroll]);

	// -----------------------------------------------------------------------
	// scrollToBottom
	// -----------------------------------------------------------------------

	const scrollToBottom = useCallback(() => {
		setShowJumpToLatest(false);
		setIsAtBottom(true);
		doScroll();
	}, [doScroll]);

	return {
		containerRef,
		bottomRef,
		isAtBottom,
		showJumpToLatest,
		scrollToBottom,
	};
}
