/**
 * Chat message bubble components.
 *
 * REQ-012 §5.2: Renders chat messages with role-based alignment
 * and styling. User messages right-aligned with primary color,
 * agent messages left-aligned with muted background, system
 * notices centered with small muted text.
 * REQ-012 §5.3: Renders structured chat cards (job, score) for
 * agent messages.
 * REQ-012 §5.6: Renders ambiguity resolution cards (options, confirm).
 */

import type { ChatCard, ChatMessage } from "@/types/chat";
import { cn } from "@/lib/utils";

import { ChatConfirmCard } from "./chat-confirm-card";
import { ChatJobCard } from "./chat-job-card";
import { ChatOptionList } from "./chat-option-list";
import { ChatScoreCard } from "./chat-score-card";
import { StreamingCursor } from "./streaming-cursor";
import { ToolExecutionBadge } from "./tool-execution-badge";

// ---------------------------------------------------------------------------
// Timestamp formatting
// ---------------------------------------------------------------------------

const timeFormatter = new Intl.DateTimeFormat(undefined, {
	hour: "numeric",
	minute: "2-digit",
});

function formatTimestamp(iso: string): string {
	const date = new Date(iso);
	if (Number.isNaN(date.getTime())) return iso;
	return timeFormatter.format(date);
}

// ---------------------------------------------------------------------------
// Card rendering
// ---------------------------------------------------------------------------

function renderCard(card: ChatCard, index: number) {
	switch (card.type) {
		case "job":
			return (
				<ChatJobCard key={`job-${card.data.jobId}-${index}`} data={card.data} />
			);
		case "score":
			return (
				<ChatScoreCard
					key={`score-${card.data.jobId}-${index}`}
					data={card.data}
				/>
			);
		case "options":
			return <ChatOptionList key={`options-${index}`} data={card.data} />;
		case "confirm":
			return <ChatConfirmCard key={`confirm-${index}`} data={card.data} />;
		default: {
			const _exhaustive: never = card;
			return _exhaustive;
		}
	}
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
				{!isUser && message.cards.length > 0 && (
					<div data-slot="chat-cards" className="flex flex-col gap-2">
						{message.cards.map((card, index) => renderCard(card, index))}
					</div>
				)}
				{!isUser && message.tools.length > 0 && (
					<div
						data-slot="tool-executions"
						aria-live="polite"
						className="flex flex-wrap gap-1"
					>
						{message.tools.map((tool, index) => (
							<ToolExecutionBadge
								key={`${tool.tool}-${index}`}
								execution={tool}
							/>
						))}
					</div>
				)}
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
