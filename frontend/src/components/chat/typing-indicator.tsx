/**
 * Typing indicator for streaming chat messages.
 *
 * REQ-012 §5.4: While tokens are streaming, show a
 * "Scout is typing..." indicator above the input.
 * Disappear on chat_done.
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
