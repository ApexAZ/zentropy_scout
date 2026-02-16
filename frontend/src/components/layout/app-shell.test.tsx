/**
 * Tests for the app shell layout component.
 *
 * REQ-012 §3.2: App shell composes TopNav, page content area,
 * and chat sidebar into the main application layout.
 *
 * Integration test — uses real ChatPanelProvider (not mocked).
 */

import { act, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./app-shell";

// ---------------------------------------------------------------------------
// Mocks (only Next.js modules — real ChatPanelProvider for integration)
// ---------------------------------------------------------------------------

vi.mock("next/navigation", () => ({
	usePathname: () => "/",
}));

vi.mock("next/link", () => ({
	default: function MockLink({
		children,
		href,
		...props
	}: {
		children: ReactNode;
		href: string;
		[key: string]: unknown;
	}) {
		return (
			<a href={href} {...props}>
				{children}
			</a>
		);
	},
}));

vi.mock("@/lib/chat-provider", () => ({
	useChat: () => ({
		messages: [],
		isStreaming: false,
		isLoadingHistory: false,
		sendMessage: vi.fn(),
		addSystemMessage: vi.fn(),
		clearMessages: vi.fn(),
		loadHistory: vi.fn(),
	}),
}));

vi.mock("../chat/chat-message-list", () => ({
	ChatMessageList: () => <div data-slot="chat-message-list" />,
}));

vi.mock("../chat/chat-input", () => ({
	ChatInput: () => <div data-slot="chat-input" />,
}));

vi.mock("../chat/typing-indicator", () => ({
	TypingIndicator: () => <div data-slot="typing-indicator" />,
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AppShell", () => {
	it("renders navigation", () => {
		render(
			<AppShell>
				<div>Content</div>
			</AppShell>,
		);

		expect(screen.getByRole("navigation")).toBeInTheDocument();
	});

	it("renders children in main content area", () => {
		render(
			<AppShell>
				<div data-testid="page-content">Page Content</div>
			</AppShell>,
		);

		const main = screen.getByRole("main");
		expect(main).toContainElement(screen.getByTestId("page-content"));
	});

	it("renders chat toggle button in nav", () => {
		render(
			<AppShell>
				<div>Content</div>
			</AppShell>,
		);

		expect(
			screen.getByRole("button", { name: /toggle chat/i }),
		).toBeInTheDocument();
	});

	it("renders brand text", () => {
		render(
			<AppShell>
				<div>Content</div>
			</AppShell>,
		);

		expect(screen.getByText("Zentropy Scout")).toBeInTheDocument();
	});

	// -------------------------------------------------------------------
	// Integration: chat panel open/close flow
	// -------------------------------------------------------------------

	it("opens chat sidebar when toggle is clicked and closes via sidebar button", () => {
		// In JSDOM, matchMedia is unavailable so ChatSidebar renders in
		// tablet/Sheet mode (dialog role) rather than desktop aside mode.
		render(
			<AppShell>
				<div>Content</div>
			</AppShell>,
		);

		// Initially no sidebar dialog
		expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

		// Click toggle in nav → sidebar Sheet appears
		act(() => {
			screen.getByRole("button", { name: /toggle chat/i }).click();
		});
		expect(screen.getByRole("dialog")).toBeInTheDocument();

		// Click close in sidebar → sidebar Sheet disappears
		act(() => {
			screen.getByRole("button", { name: /close chat/i }).click();
		});
		expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
	});

	it("forwards badge props to TopNav", () => {
		render(
			<AppShell pendingFlagsCount={3}>
				<div>Content</div>
			</AppShell>,
		);

		expect(screen.getByTestId("pending-flags-badge")).toHaveTextContent("3");
	});
});
