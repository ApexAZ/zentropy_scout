/**
 * Chat input component with textarea and send button.
 *
 * REQ-012 §5.7: Textarea with send button, Enter to send,
 * Shift+Enter for newline, disabled during streaming,
 * contextual placeholder text.
 */

import { SendHorizontal } from "lucide-react";
import {
	useCallback,
	useRef,
	useState,
	type FormEvent,
	type KeyboardEvent,
} from "react";

import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ChatInputProps {
	/** Callback fired with the message content when the user sends. */
	onSend: (content: string) => void;
	/** Placeholder text for the textarea. */
	placeholder?: string;
	/** Whether the input is disabled (e.g., during streaming). */
	disabled?: boolean;
	/** Optional max character length with counter display. */
	maxLength?: number;
	/** Additional CSS classes for the wrapper element. */
	className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Chat message input with textarea, send button, and keyboard shortcuts.
 *
 * - Enter sends the message.
 * - Shift+Enter inserts a newline.
 * - Send button is disabled when textarea is empty or input is disabled.
 * - Optional character counter shown when `maxLength` is provided.
 *
 * @param props.onSend - Callback with trimmed message content.
 * @param props.placeholder - Textarea placeholder text.
 * @param props.disabled - Disables textarea and send button.
 * @param props.maxLength - Shows character counter when set.
 * @param props.className - Optional extra CSS classes on the wrapper.
 */
export function ChatInput({
	onSend,
	placeholder = "Ask Scout anything...",
	disabled = false,
	maxLength,
	className,
}: ChatInputProps) {
	const [value, setValue] = useState("");
	const textareaRef = useRef<HTMLTextAreaElement>(null);

	const trimmed = value.trim();
	const exceedsLimit = maxLength !== undefined && trimmed.length > maxLength;
	const canSend = trimmed.length > 0 && !disabled && !exceedsLimit;
	const nearLimit =
		maxLength !== undefined && trimmed.length >= maxLength * 0.9;

	const handleSend = useCallback(() => {
		if (!canSend) return;
		onSend(trimmed);
		setValue("");
		textareaRef.current?.focus();
	}, [canSend, onSend, trimmed]);

	const handleSubmit = useCallback(
		(e: FormEvent) => {
			e.preventDefault();
			handleSend();
		},
		[handleSend],
	);

	const handleKeyDown = useCallback(
		(e: KeyboardEvent<HTMLTextAreaElement>) => {
			if (e.key === "Enter" && !e.shiftKey) {
				e.preventDefault();
				handleSend();
			}
		},
		[handleSend],
	);

	return (
		<div
			data-slot="chat-input"
			data-disabled={String(disabled)}
			className={cn("border-t p-3", className)}
		>
			<form
				onSubmit={handleSubmit}
				aria-label="Send a message"
				className="flex items-end gap-2"
			>
				<textarea
					ref={textareaRef}
					data-slot="chat-textarea"
					aria-label="Message"
					placeholder={placeholder}
					disabled={disabled}
					value={value}
					onChange={(e) => setValue(e.target.value)}
					onKeyDown={handleKeyDown}
					rows={1}
					className={cn(
						"placeholder:text-muted-foreground field-sizing-content max-h-32 min-h-[2.25rem] flex-1 resize-none rounded-md border bg-transparent px-3 py-2 text-sm transition-colors outline-none",
						"focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]",
						"disabled:cursor-not-allowed disabled:opacity-50",
					)}
				/>
				<button
					type="submit"
					data-slot="chat-send-button"
					aria-label="Send message"
					disabled={!canSend}
					className={cn(
						"bg-primary text-primary-foreground inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md transition-colors",
						"hover:bg-primary/90",
						"disabled:pointer-events-none disabled:opacity-50",
					)}
				>
					<SendHorizontal className="h-4 w-4" />
				</button>
			</form>
			{maxLength !== undefined && (
				<div
					data-slot="char-counter"
					data-near-limit={String(nearLimit)}
					className={cn(
						"mt-1 text-right text-xs",
						nearLimit ? "text-destructive" : "text-muted-foreground",
					)}
				>
					{trimmed.length}/{maxLength}
				</div>
			)}
		</div>
	);
}
