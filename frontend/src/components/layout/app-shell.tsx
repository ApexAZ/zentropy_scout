"use client";

/**
 * App shell layout.
 *
 * REQ-012 §3.2: Composes TopNav, page content area, and chat sidebar
 * into the main application layout.
 *
 * Provides ChatPanelProvider so that TopNav and ChatSidebar can
 * share chat panel open/closed state.
 *
 * Used by route group layouts for pages that show the main navigation
 * (i.e., NOT used during onboarding — see REQ-012 §6.2).
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

export function AppShell({ children, ...navProps }: AppShellProps) {
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
