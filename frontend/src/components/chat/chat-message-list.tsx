/**
 * Scrollable chat message list container.
 *
 * REQ-012 §5.8: Renders chat messages in a scrollable container
 * with auto-scroll to bottom on new messages, "Jump to latest"
 * floating button when scrolled up, loading state for history
 * fetch, and empty state.
 */

import { ArrowDown } from "lucide-react";

import { useChatScroll } from "@/hooks/use-chat-scroll";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types/chat";

import { MessageBubble } from "./message-bubble";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ChatMessageListProps {
	/** Chat messages to display. */
	messages: ChatMessage[];
	/** Whether chat history is being loaded from the server. */
	isLoading?: boolean;
	/** Additional CSS classes for the wrapper element. */
	className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Scrollable chat message list with auto-scroll and "Jump to latest".
 *
 * - Auto-scrolls to bottom when new messages arrive (if already at bottom).
 * - Shows a floating "Jump to latest" button when scrolled up and new
 *   messages arrive.
 * - Displays a loading indicator during history fetch.
 * - Shows an empty state when there are no messages.
 *
 * @param props.messages - Array of chat messages to render.
 * @param props.isLoading - Shows loading indicator when true and no messages.
 * @param props.className - Optional extra CSS classes on the wrapper.
 */
export function ChatMessageList({
	messages,
	isLoading = false,
	className,
}: ChatMessageListProps) {
	const { containerRef, bottomRef, showJumpToLatest, scrollToBottom } =
		useChatScroll({ messageCount: messages.length });

	const showEmpty = messages.length === 0 && !isLoading;
	const showLoading = isLoading && messages.length === 0;

	return (
		<div
			data-slot="chat-message-list"
			className={cn("relative flex flex-1 flex-col", className)}
		>
			<div
				ref={containerRef}
				data-slot="chat-scroll-container"
				role="log"
				aria-label="Chat messages"
				className="flex flex-1 flex-col gap-3 overflow-y-auto p-4"
			>
				{showLoading && (
					<div
						data-slot="chat-loading"
						className="text-muted-foreground flex items-center justify-center py-8 text-sm"
					>
						Loading messages...
					</div>
				)}
				{showEmpty && (
					<div
						data-slot="chat-empty-state"
						className="text-muted-foreground flex flex-1 items-center justify-center text-sm"
					>
						No messages yet. Start a conversation!
					</div>
				)}
				{messages.map((message) => (
					<MessageBubble key={message.id} message={message} />
				))}
				<div
					ref={bottomRef}
					data-slot="chat-scroll-sentinel"
					aria-hidden="true"
					className="h-px shrink-0"
				/>
			</div>
			{showJumpToLatest && (
				<button
					type="button"
					data-slot="jump-to-latest"
					aria-label="Jump to latest messages"
					onClick={scrollToBottom}
					className={cn(
						"bg-primary text-primary-foreground absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full px-3 py-1.5 text-xs font-medium shadow-lg transition-opacity",
						"hover:bg-primary/90",
					)}
				>
					<ArrowDown className="mr-1 inline-block h-3 w-3" />
					Jump to latest
				</button>
			)}
		</div>
	);
}
