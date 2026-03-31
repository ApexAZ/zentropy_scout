"use client";

/**
 * @fileoverview Chat panel open/closed state provider.
 *
 * Layer: context-provider
 * Feature: chat
 *
 * REQ-012 §4.2: Chat panel open/closed state is global React Context.
 *
 * Provides `isOpen`, `toggle`, `open`, and `close` to the component tree
 * via the `useChatPanel` hook.
 *
 * Coordinates with:
 * - components/layout/app-shell.tsx: mounts the provider in the layout tree
 * - components/layout/top-nav.tsx: toggle button triggers open/close
 * - components/layout/chat-sidebar.tsx: reads isOpen state for panel visibility
 *
 * Called by / Used by:
 * - components/layout/app-shell.tsx: wraps the main layout with this provider
 * - components/layout/top-nav.tsx: useChatPanel() for toggle
 * - components/layout/chat-sidebar.tsx: useChatPanel() for visibility
 */

import {
	createContext,
	useCallback,
	useContext,
	useMemo,
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
export function ChatPanelProvider({
	children,
}: Readonly<ChatPanelProviderProps>) {
	const [isOpen, setIsOpen] = useState(false);

	const toggle = useCallback(() => setIsOpen((prev) => !prev), []);
	const open = useCallback(() => setIsOpen(true), []);
	const close = useCallback(() => setIsOpen(false), []);

	const contextValue = useMemo(
		() => ({ isOpen, toggle, open, close }),
		[isOpen, toggle, open, close],
	);

	return <ChatPanelContext value={contextValue}>{children}</ChatPanelContext>;
}
