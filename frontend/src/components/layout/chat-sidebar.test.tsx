/**
 * Tests for the responsive ChatSidebar component.
 *
 * REQ-012 §3.2, §5.1: Persistent collapsible chat sidebar with three
 * responsive modes — desktop inline sidebar, tablet sheet, mobile full-screen.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatSidebar } from "./chat-sidebar";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	const mockClose = vi.fn();
	const mockIsOpen = { value: false };
	const mockMediaQueries: Record<string, boolean> = {};
	return { mockClose, mockIsOpen, mockMediaQueries };
});

vi.mock("@/lib/chat-panel-provider", () => ({
	useChatPanel: () => ({
		isOpen: mocks.mockIsOpen.value,
		close: mocks.mockClose,
		toggle: vi.fn(),
		open: vi.fn(),
	}),
}));

vi.mock("@/hooks/use-media-query", () => ({
	useMediaQuery: (query: string) => mocks.mockMediaQueries[query] ?? false,
}));

vi.mock("@/hooks/use-is-mobile", () => ({
	useIsMobile: () => mocks.mockMediaQueries["(max-width: 767px)"] ?? false,
}));

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DESKTOP_QUERY = "(min-width: 1024px)";
const MOBILE_QUERY = "(max-width: 767px)";
const CHAT_SIDEBAR_SELECTOR = '[data-slot="chat-sidebar"]';

// ---------------------------------------------------------------------------
// Breakpoint helpers
// ---------------------------------------------------------------------------

function setDesktop() {
	mocks.mockMediaQueries[DESKTOP_QUERY] = true;
	mocks.mockMediaQueries[MOBILE_QUERY] = false;
}

function setTablet() {
	mocks.mockMediaQueries[DESKTOP_QUERY] = false;
	mocks.mockMediaQueries[MOBILE_QUERY] = false;
}

function setMobile() {
	mocks.mockMediaQueries[DESKTOP_QUERY] = false;
	mocks.mockMediaQueries[MOBILE_QUERY] = true;
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
	mocks.mockIsOpen.value = false;
	mocks.mockMediaQueries[DESKTOP_QUERY] = false;
	mocks.mockMediaQueries[MOBILE_QUERY] = false;
});

// ---------------------------------------------------------------------------
// Desktop tests
// ---------------------------------------------------------------------------

describe("ChatSidebar", () => {
	describe("desktop (>=1024px)", () => {
		beforeEach(() => {
			setDesktop();
		});

		it("renders as aside element when desktop", () => {
			mocks.mockIsOpen.value = true;
			render(<ChatSidebar />);

			expect(screen.getByRole("complementary")).toBeInTheDocument();
		});

		it("has 400px width when open", () => {
			mocks.mockIsOpen.value = true;
			render(<ChatSidebar />);

			const aside = screen.getByRole("complementary");
			expect(aside).toHaveClass("w-[400px]");
		});

		it("has collapse classes when closed", () => {
			mocks.mockIsOpen.value = false;
			render(<ChatSidebar />);

			const wrapper = document.querySelector(CHAT_SIDEBAR_SELECTOR);
			expect(wrapper).toBeInTheDocument();

			const aside = wrapper?.querySelector("aside");
			expect(aside).toBeInTheDocument();
			expect(aside).toHaveClass("w-0");
			expect(aside).toHaveClass("overflow-hidden");
		});

		it("shows minimize and close buttons", () => {
			mocks.mockIsOpen.value = true;
			render(<ChatSidebar />);

			expect(
				screen.getByRole("button", { name: /minimize/i }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: /close chat/i }),
			).toBeInTheDocument();
		});

		it("minimize button calls close", async () => {
			const user = userEvent.setup();
			mocks.mockIsOpen.value = true;
			render(<ChatSidebar />);

			await user.click(screen.getByRole("button", { name: /minimize/i }));
			expect(mocks.mockClose).toHaveBeenCalledOnce();
		});

		it("remains in DOM when closed for scroll preservation", () => {
			mocks.mockIsOpen.value = false;
			render(<ChatSidebar />);

			const wrapper = document.querySelector(CHAT_SIDEBAR_SELECTOR);
			expect(wrapper).toBeInTheDocument();

			const aside = wrapper?.querySelector("aside");
			expect(aside).toBeInTheDocument();
		});
	});

	// ---------------------------------------------------------------------------
	// Tablet tests
	// ---------------------------------------------------------------------------

	describe("tablet (768-1023px)", () => {
		beforeEach(() => {
			setTablet();
		});

		it("renders as Sheet when tablet breakpoint and open", () => {
			mocks.mockIsOpen.value = true;
			render(<ChatSidebar />);

			expect(screen.getByRole("dialog")).toBeInTheDocument();
		});

		it("Sheet has 400px max-width", () => {
			mocks.mockIsOpen.value = true;
			render(<ChatSidebar />);

			const content = document.querySelector('[data-slot="sheet-content"]');
			expect(content).toHaveClass("max-w-[400px]");
		});

		it("shows close button in Sheet header", () => {
			mocks.mockIsOpen.value = true;
			render(<ChatSidebar />);

			expect(
				screen.getByRole("button", { name: /close chat/i }),
			).toBeInTheDocument();
		});

		it("has aria-label on Sheet content", () => {
			mocks.mockIsOpen.value = true;
			render(<ChatSidebar />);

			expect(screen.getByRole("dialog")).toHaveAttribute(
				"aria-label",
				"Chat panel",
			);
		});

		it("does not render dialog when closed", () => {
			mocks.mockIsOpen.value = false;
			render(<ChatSidebar />);

			expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
		});
	});

	// ---------------------------------------------------------------------------
	// Mobile tests
	// ---------------------------------------------------------------------------

	describe("mobile (<768px)", () => {
		beforeEach(() => {
			setMobile();
		});

		it("renders as full-screen Sheet when mobile and open", () => {
			mocks.mockIsOpen.value = true;
			render(<ChatSidebar />);

			expect(screen.getByRole("dialog")).toBeInTheDocument();
		});

		it("shows back button instead of minimize", () => {
			mocks.mockIsOpen.value = true;
			render(<ChatSidebar />);

			expect(screen.getByRole("button", { name: /back/i })).toBeInTheDocument();
			expect(
				screen.queryByRole("button", { name: /minimize/i }),
			).not.toBeInTheDocument();
		});

		it("back button calls close", async () => {
			const user = userEvent.setup();
			mocks.mockIsOpen.value = true;
			render(<ChatSidebar />);

			await user.click(screen.getByRole("button", { name: /back/i }));
			expect(mocks.mockClose).toHaveBeenCalledOnce();
		});

		it("Sheet content is full-width", () => {
			mocks.mockIsOpen.value = true;
			render(<ChatSidebar />);

			const content = document.querySelector('[data-slot="sheet-content"]');
			expect(content).toHaveClass("w-full");
		});

		it("has aria-label on Sheet content", () => {
			mocks.mockIsOpen.value = true;
			render(<ChatSidebar />);

			expect(screen.getByRole("dialog")).toHaveAttribute(
				"aria-label",
				"Chat panel",
			);
		});
	});

	// ---------------------------------------------------------------------------
	// General tests
	// ---------------------------------------------------------------------------

	describe("general", () => {
		it("does not render dialog when tablet/mobile and closed", () => {
			setTablet();
			mocks.mockIsOpen.value = false;
			render(<ChatSidebar />);

			expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
			expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
		});

		it("has data-slot='chat-sidebar' on outermost wrapper", () => {
			setDesktop();
			mocks.mockIsOpen.value = true;
			render(<ChatSidebar />);

			expect(document.querySelector(CHAT_SIDEBAR_SELECTOR)).toBeInTheDocument();
		});
	});
});
