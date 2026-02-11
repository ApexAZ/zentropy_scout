/**
 * Chat message bubble components.
 *
 * REQ-012 §5.2: Renders chat messages with role-based alignment
 * and styling. User messages right-aligned with primary color,
 * agent messages left-aligned with muted background, system
 * notices centered with small muted text.
 */

import type { ChatMessage } from "@/types/chat";
import { cn } from "@/lib/utils";

import { StreamingCursor } from "./streaming-cursor";

// ---------------------------------------------------------------------------
// Timestamp formatting
// ---------------------------------------------------------------------------

const timeFormatter = new Intl.DateTimeFormat(undefined, {
	hour: "numeric",
	minute: "2-digit",
});

function formatTimestamp(iso: string): string {
	return timeFormatter.format(new Date(iso));
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface MessageBubbleProps {
	/** The chat message to render. */
	message: ChatMessage;
	/** Additional CSS classes for the wrapper element. */
	className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Renders a single chat message with role-appropriate alignment and styling.
 *
 * - **user**: Right-aligned, primary color background.
 * - **agent**: Left-aligned, muted background.
 * - **system**: Centered, small muted text (no bubble or timestamp).
 *
 * @param props.message - The ChatMessage to display.
 * @param props.className - Optional extra CSS classes on the wrapper.
 */
export function MessageBubble({ message, className }: MessageBubbleProps) {
	if (message.role === "system") {
		return (
			<div
				data-slot="system-notice"
				data-role="system"
				role="status"
				className={cn(
					"text-muted-foreground py-1 text-center text-xs",
					className,
				)}
			>
				{message.content}
			</div>
		);
	}

	const isUser = message.role === "user";

	return (
		<div
			data-slot="message-bubble"
			data-role={message.role}
			data-streaming={String(message.isStreaming)}
			aria-label={isUser ? "You said" : "Scout said"}
			className={cn(
				"flex w-full",
				isUser ? "justify-end" : "justify-start",
				className,
			)}
		>
			<div
				className={cn(
					"flex max-w-[85%] flex-col gap-1",
					isUser ? "items-end" : "items-start",
				)}
			>
				<div
					data-slot="message-content"
					className={cn(
						"rounded-lg px-3 py-2 break-words",
						isUser
							? "bg-primary text-primary-foreground"
							: "bg-muted text-foreground",
					)}
				>
					{message.content}
					{!isUser && message.isStreaming && <StreamingCursor />}
				</div>
				<time
					data-slot="message-timestamp"
					dateTime={message.timestamp}
					className="text-muted-foreground text-[0.65rem]"
				>
					{formatTimestamp(message.timestamp)}
				</time>
			</div>
		</div>
	);
}
