/**
 * @fileoverview Typing indicator for streaming chat messages.
 *
 * Layer: component
 * Feature: chat
 *
 * REQ-012 §5.4: While tokens are streaming, show a
 * "Scout is typing..." indicator above the input.
 * Disappear on chat_done.
 *
 * Coordinates with:
 * - lib/utils.ts: cn class-name helper
 *
 * Called by / Used by:
 * - components/layout/chat-sidebar.tsx: typing indicator above chat input
 */

import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface TypingIndicatorProps {
	/** Additional CSS classes. */
	className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Displays a "Scout is typing..." indicator while the agent is streaming.
 *
 * Uses `<output>` (implicit `role="status"` and `aria-live="polite"`)
 * so screen readers announce the typing state without interrupting the user.
 *
 * @param props.className - Optional extra CSS classes.
 */
export function TypingIndicator({ className }: Readonly<TypingIndicatorProps>) {
	return (
		<output
			data-slot="typing-indicator"
			className={cn(
				"block",
				"text-muted-foreground text-xs motion-safe:animate-pulse",
				className,
			)}
		>
			Scout is typing...
		</output>
	);
}
