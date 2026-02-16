/**
 * Destructive confirmation card for inline chat confirmations.
 *
 * REQ-012 §5.6: Destructive confirmations render as a distinct card
 * with explicit "Proceed" / "Cancel" buttons. The proceed button
 * uses destructive styling when the action is destructive.
 */

import type { ConfirmCardData } from "@/types/chat";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ChatConfirmCardProps {
	/** Confirmation card data. */
	data: ConfirmCardData;
	/** Called when user clicks the proceed button. */
	onProceed?: () => void;
	/** Called when user clicks the cancel button. */
	onCancel?: () => void;
	/** Additional CSS classes for the wrapper element. */
	className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Renders an inline confirmation card with Proceed/Cancel buttons.
 *
 * For destructive actions, the proceed button renders with red styling
 * and the card border highlights in destructive color.
 *
 * @param props.data - The confirmation card data.
 * @param props.onProceed - Callback when user clicks proceed.
 * @param props.onCancel - Callback when user clicks cancel.
 * @param props.className - Optional extra CSS classes on the wrapper.
 */
export function ChatConfirmCard({
	data,
	onProceed,
	onCancel,
	className,
}: Readonly<ChatConfirmCardProps>) {
	const proceedLabel = data.proceedLabel ?? "Proceed";
	const cancelLabel = data.cancelLabel ?? "Cancel";

	return (
		<fieldset
			data-slot="chat-confirm-card"
			data-destructive={String(data.isDestructive)}
			aria-label="Confirmation required"
			className={cn(
				"bg-card m-0 rounded-lg border p-3 text-sm",
				data.isDestructive && "border-destructive/50",
				className,
			)}
		>
			<p data-slot="confirm-message" className="mb-3">
				{data.message}
			</p>
			<div data-slot="confirm-actions" className="flex gap-2">
				<button
					type="button"
					className={cn(
						"rounded px-3 py-1.5 text-xs font-medium transition-colors",
						data.isDestructive
							? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
							: "bg-primary text-primary-foreground hover:bg-primary/90",
					)}
					onClick={() => onProceed?.()}
				>
					{proceedLabel}
				</button>
				<button
					type="button"
					className="hover:bg-muted rounded border px-3 py-1.5 text-xs font-medium transition-colors"
					onClick={() => onCancel?.()}
				>
					{cancelLabel}
				</button>
			</div>
		</fieldset>
	);
}
