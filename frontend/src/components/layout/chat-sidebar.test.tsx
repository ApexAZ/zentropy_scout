/**
 * Tests for the chat sidebar slot component.
 *
 * REQ-012 §3.2, §5.1: Persistent collapsible chat sidebar.
 * This is the structural slot — actual chat content comes in Phase 5.
 */

import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatSidebar } from "./chat-sidebar";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	const mockClose = vi.fn();
	const mockIsOpen = { value: false };
	return { mockClose, mockIsOpen };
});

vi.mock("@/lib/chat-panel-provider", () => ({
	useChatPanel: () => ({
		isOpen: mocks.mockIsOpen.value,
		close: mocks.mockClose,
		toggle: vi.fn(),
		open: vi.fn(),
	}),
}));

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
	mocks.mockIsOpen.value = false;
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ChatSidebar", () => {
	it("renders when panel is open", () => {
		mocks.mockIsOpen.value = true;
		render(<ChatSidebar />);
		expect(screen.getByRole("complementary")).toBeInTheDocument();
	});

	it("is not in the document when panel is closed", () => {
		mocks.mockIsOpen.value = false;
		render(<ChatSidebar />);
		expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
	});

	it("displays chat heading", () => {
		mocks.mockIsOpen.value = true;
		render(<ChatSidebar />);
		expect(screen.getByRole("heading", { name: /chat/i })).toBeInTheDocument();
	});

	it("renders close button", () => {
		mocks.mockIsOpen.value = true;
		render(<ChatSidebar />);
		expect(screen.getByRole("button", { name: /close/i })).toBeInTheDocument();
	});

	it("calls close when close button is clicked", () => {
		mocks.mockIsOpen.value = true;
		render(<ChatSidebar />);
		screen.getByRole("button", { name: /close/i }).click();
		expect(mocks.mockClose).toHaveBeenCalledTimes(1);
	});
});
