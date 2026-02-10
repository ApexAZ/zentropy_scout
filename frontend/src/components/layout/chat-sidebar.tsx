"use client";

/**
 * Chat sidebar slot.
 *
 * REQ-012 §3.2, §5.1: Persistent collapsible chat sidebar.
 *
 * This is the structural shell — actual chat messages, input, and
 * streaming content will be implemented in Phase 5.
 *
 * Desktop (lg+): 400px right sidebar.
 * Smaller screens: behavior refined in later phases.
 */

import { X } from "lucide-react";

import { useChatPanel } from "@/lib/chat-panel-provider";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ChatSidebar() {
	const { isOpen, close } = useChatPanel();

	if (!isOpen) return null;

	return (
		<aside
			className="bg-background w-[400px] shrink-0 border-l"
			aria-label="Chat panel"
		>
			<div className="flex h-14 items-center justify-between border-b px-4">
				<h2 className="text-sm font-semibold">Chat</h2>
				<button
					type="button"
					onClick={close}
					aria-label="Close chat"
					className="text-muted-foreground hover:bg-secondary/50 hover:text-foreground rounded-md p-1 transition-colors"
				>
					<X className="h-4 w-4" />
				</button>
			</div>

			{/* Placeholder — real chat content in Phase 5 */}
			<div className="text-muted-foreground flex flex-1 items-center justify-center p-4 text-sm">
				Chat will be available here.
			</div>
		</aside>
	);
}
