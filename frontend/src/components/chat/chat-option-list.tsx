/**
 * Clickable option list card for ambiguity resolution.
 *
 * REQ-012 §5.6: When the agent presents numbered options, they render
 * as clickable list items within a chat card. Clicking sends the
 * selection as a user message. Users can also type free-text instead.
 */

import type { OptionListData } from "@/types/chat";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ChatOptionListProps {
	/** Option list data to display. */
	data: OptionListData;
	/** Called with the option value when a user clicks an option. */
	onSelect?: (value: string) => void;
	/** Additional CSS classes for the wrapper element. */
	className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Renders a numbered list of clickable options for ambiguity resolution.
 *
 * Each option is a button that triggers `onSelect` with the option's value.
 * A hint below the list reminds users they can type a free-text response.
 *
 * @param props.data - The option list data containing selectable options.
 * @param props.onSelect - Callback when a user clicks an option.
 * @param props.className - Optional extra CSS classes on the wrapper.
 */
export function ChatOptionList({
	data,
	onSelect,
	className,
}: Readonly<ChatOptionListProps>) {
	return (
		<div
			data-slot="chat-option-list"
			role="group"
			aria-label="Select an option"
			className={cn("bg-card rounded-lg border p-3 text-sm", className)}
		>
			<ul className="flex flex-col gap-1">
				{data.options.map((option, index) => (
					<li key={`${option.value}-${index}`} data-slot="option-item">
						<button
							type="button"
							className="hover:bg-muted w-full cursor-pointer rounded px-2 py-1.5 text-left transition-colors"
							onClick={() => onSelect?.(option.value)}
						>
							{index + 1}. {option.label}
						</button>
					</li>
				))}
			</ul>
			<p data-slot="option-hint" className="text-muted-foreground mt-2 text-xs">
				Or type to describe...
			</p>
		</div>
	);
}
