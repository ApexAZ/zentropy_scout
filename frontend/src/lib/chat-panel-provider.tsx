"use client";

/**
 * Chat panel state provider.
 *
 * REQ-012 §4.2: Chat panel open/closed state is global React Context.
 *
 * Provides `isOpen`, `toggle`, `open`, and `close` to the component tree
 * via the `useChatPanel` hook.
 */

import {
	createContext,
	useCallback,
	useContext,
	useState,
	type ReactNode,
} from "react";

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

interface ChatPanelContextValue {
	/** Whether the chat panel is currently open. */
	isOpen: boolean;
	/** Toggle the chat panel open/closed. */
	toggle: () => void;
	/** Open the chat panel. */
	open: () => void;
	/** Close the chat panel. */
	close: () => void;
}

const ChatPanelContext = createContext<ChatPanelContextValue | null>(null);

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Access the chat panel state and controls.
 *
 * Must be called within a ChatPanelProvider.
 *
 * @returns Object with `isOpen`, `toggle`, `open`, `close`.
 * @throws Error if called outside a ChatPanelProvider.
 */
export function useChatPanel(): ChatPanelContextValue {
	const ctx = useContext(ChatPanelContext);
	if (!ctx) {
		throw new Error("useChatPanel must be used within a ChatPanelProvider");
	}
	return ctx;
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

interface ChatPanelProviderProps {
	children: ReactNode;
}

/**
 * Provides chat panel open/closed state to the component tree.
 *
 * @param props.children - React children to render.
 */
export function ChatPanelProvider({ children }: ChatPanelProviderProps) {
	const [isOpen, setIsOpen] = useState(false);

	const toggle = useCallback(() => setIsOpen((prev) => !prev), []);
	const open = useCallback(() => setIsOpen(true), []);
	const close = useCallback(() => setIsOpen(false), []);

	return (
		<ChatPanelContext value={{ isOpen, toggle, open, close }}>
			{children}
		</ChatPanelContext>
	);
}
