"use client";

/**
 * Responsive chat sidebar.
 *
 * REQ-012 §3.2, §5.1: Persistent collapsible chat sidebar with three
 * responsive modes:
 * - Desktop (lg+, >=1024px): Inline right sidebar, 400px. CSS collapse
 *   preserves scroll position when minimized.
 * - Tablet (md, 768-1023px): Slide-over sheet from right edge, 400px max.
 * - Mobile (<768px): Full-screen sheet with back button.
 *
 * Chat content (message list, typing indicator, input) is wired via
 * the ChatProvider / useChat hook.
 */

import { useEffect } from "react";

import { ArrowLeft, Minus, X } from "lucide-react";

import { useIsMobile } from "@/hooks/use-is-mobile";
import { useMediaQuery } from "@/hooks/use-media-query";
import { useChatPanel } from "@/lib/chat-panel-provider";
import { useChat } from "@/lib/chat-provider";
import { cn } from "@/lib/utils";

import { ChatInput } from "../chat/chat-input";
import { ChatMessageList } from "../chat/chat-message-list";
import { TypingIndicator } from "../chat/typing-indicator";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "../ui/sheet";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DESKTOP_QUERY = "(min-width: 1024px)";

const ICON_BUTTON_CLASSES =
	"text-muted-foreground hover:bg-secondary/50 hover:text-foreground rounded-md p-1 transition-colors";

// ---------------------------------------------------------------------------
// Shared inner content — wired to chat provider
// ---------------------------------------------------------------------------

function ChatContent() {
	const { messages, isStreaming, isLoadingHistory, sendMessage, loadHistory } =
		useChat();

	useEffect(() => {
		loadHistory();
	}, [loadHistory]);

	return (
		<div className="flex flex-1 flex-col overflow-hidden">
			<ChatMessageList messages={messages} isLoading={isLoadingHistory} />
			{isStreaming && <TypingIndicator className="px-4 pb-1" />}
			<ChatInput onSend={sendMessage} disabled={isStreaming} />
		</div>
	);
}

// ---------------------------------------------------------------------------
// Desktop sidebar (inline, CSS-collapsed when closed)
// ---------------------------------------------------------------------------

function DesktopSidebar({
	isOpen,
	onClose,
}: {
	isOpen: boolean;
	onClose: () => void;
}) {
	return (
		<aside
			className={cn(
				"bg-background shrink-0 border-l transition-all duration-300",
				isOpen ? "w-[400px]" : "w-0 overflow-hidden border-l-0",
			)}
			aria-label="Chat panel"
		>
			<div className="flex h-14 items-center justify-between border-b px-4">
				<h2 className="text-sm font-semibold">Chat</h2>
				<div className="flex items-center gap-1">
					<button
						type="button"
						onClick={onClose}
						aria-label="Minimize chat"
						className={ICON_BUTTON_CLASSES}
					>
						<Minus className="h-4 w-4" />
					</button>
					<button
						type="button"
						onClick={onClose}
						aria-label="Close chat"
						className={ICON_BUTTON_CLASSES}
					>
						<X className="h-4 w-4" />
					</button>
				</div>
			</div>
			<ChatContent />
		</aside>
	);
}

// ---------------------------------------------------------------------------
// Sheet sidebar (tablet + mobile overlay)
// ---------------------------------------------------------------------------

function SheetSidebar({
	isOpen,
	isMobile,
	onClose,
}: {
	isOpen: boolean;
	isMobile: boolean;
	onClose: () => void;
}) {
	return (
		<Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
			<SheetContent
				side="right"
				className={cn(isMobile ? "w-full" : "max-w-[400px]")}
				aria-label="Chat panel"
				aria-describedby={undefined}
			>
				<SheetHeader className="flex-row items-center justify-between border-b px-4 py-3">
					{isMobile ? (
						<button
							type="button"
							onClick={onClose}
							aria-label="Back"
							className={ICON_BUTTON_CLASSES}
						>
							<ArrowLeft className="h-4 w-4" />
						</button>
					) : null}
					<SheetTitle className="text-sm">Chat</SheetTitle>
					<button
						type="button"
						onClick={onClose}
						aria-label="Close chat"
						className={ICON_BUTTON_CLASSES}
					>
						<X className="h-4 w-4" />
					</button>
				</SheetHeader>
				<ChatContent />
			</SheetContent>
		</Sheet>
	);
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ChatSidebar() {
	const { isOpen, close } = useChatPanel();
	const isDesktop = useMediaQuery(DESKTOP_QUERY);
	const isMobile = useIsMobile();

	if (isDesktop) {
		return (
			<div data-slot="chat-sidebar">
				<DesktopSidebar isOpen={isOpen} onClose={close} />
			</div>
		);
	}

	// Tablet or mobile — use Sheet overlay
	return (
		<div data-slot="chat-sidebar">
			<SheetSidebar isOpen={isOpen} isMobile={isMobile} onClose={close} />
		</div>
	);
}
