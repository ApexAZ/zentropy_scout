"use client";

/**
 * @fileoverview App shell layout with top nav, content area, and chat sidebar.
 *
 * Layer: component
 * Feature: shared
 *
 * REQ-012 §3.2: Composes TopNav, page content area, and chat sidebar
 * into the main application layout. Wraps children in ChatPanelProvider
 * so that TopNav and ChatSidebar share chat panel open/closed state.
 * Not used during onboarding (see REQ-012 §6.2).
 *
 * Coordinates with:
 * - lib/chat-panel-provider.tsx: ChatPanelProvider for chat panel state
 * - components/layout/chat-sidebar.tsx: collapsible chat sidebar
 * - components/layout/top-nav.tsx: horizontal top navigation bar
 *
 * Called by / Used by:
 * - app/(main)/layout.tsx: main route group layout
 */

import type { ReactNode } from "react";

import { ChatPanelProvider } from "@/lib/chat-panel-provider";

import { ChatSidebar } from "./chat-sidebar";
import { TopNav, type TopNavProps } from "./top-nav";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AppShellProps extends TopNavProps {
	children: ReactNode;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AppShell({ children, ...navProps }: Readonly<AppShellProps>) {
	return (
		<ChatPanelProvider>
			<div className="flex h-screen flex-col">
				<TopNav {...navProps} />

				<div className="flex flex-1 overflow-hidden">
					<main className="flex-1 overflow-auto">{children}</main>
					<ChatSidebar />
				</div>
			</div>
		</ChatPanelProvider>
	);
}
