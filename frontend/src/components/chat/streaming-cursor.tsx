/**
 * Blinking cursor for streaming chat messages.
 *
 * REQ-012 §5.4: Show a blinking cursor at the end of the message
 * bubble during streaming. Removed on chat_done.
 */

import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface StreamingCursorProps {
	/** Additional CSS classes. */
	className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Inline blinking cursor displayed at the end of a streaming message.
 *
 * Renders a block cursor character (`▍`) with a blink animation.
 * Decorative only — hidden from screen readers via `aria-hidden`.
 *
 * @param props.className - Optional extra CSS classes.
 */
export function StreamingCursor({ className }: Readonly<StreamingCursorProps>) {
	return (
		<span
			data-slot="streaming-cursor"
			aria-hidden="true"
			className={cn("motion-safe:animate-blink-caret", className)}
		>
			▍
		</span>
	);
}
