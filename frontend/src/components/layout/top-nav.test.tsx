/**
 * Tests for the top navigation bar component.
 *
 * REQ-012 §3.2: Primary navigation with links to major sections,
 * chat toggle, and critical info badge indicators.
 */

import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TopNav } from "./top-nav";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	const mockUsePathname = vi.fn<() => string>();
	const mockToggle = vi.fn();
	const mockUseBalance = vi.fn<
		() => {
			balance: string | undefined;
			isLoading: boolean;
			error: Error | null;
		}
	>();
	const mockUseSession = vi.fn<
		() => {
			session: { isAdmin: boolean } | null;
			status: string;
			logout: () => Promise<void>;
			logoutAllDevices: () => Promise<void>;
		}
	>();
	return { mockUsePathname, mockToggle, mockUseBalance, mockUseSession };
});

vi.mock("next/navigation", () => ({
	usePathname: mocks.mockUsePathname,
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

vi.mock("@/hooks/use-balance", () => ({
	useBalance: mocks.mockUseBalance,
}));

vi.mock("@/lib/auth-provider", () => ({
	useSession: mocks.mockUseSession,
}));

vi.mock("@/lib/chat-panel-provider", () => ({
	useChatPanel: () => ({
		isOpen: false,
		toggle: mocks.mockToggle,
		open: vi.fn(),
		close: vi.fn(),
	}),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function balanceState(
	overrides?: Partial<{
		balance: string | undefined;
		isLoading: boolean;
		error: Error | null;
	}>,
) {
	return {
		balance: "10.500000" as string | undefined,
		isLoading: false,
		error: null as Error | null,
		...overrides,
	};
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

function sessionState(
	overrides?: Partial<{
		session: { isAdmin: boolean } | null;
		status: string;
	}>,
) {
	return {
		session: { isAdmin: false } as { isAdmin: boolean } | null,
		status: "authenticated",
		logout: vi.fn(),
		logoutAllDevices: vi.fn(),
		...overrides,
	};
}

beforeEach(() => {
	vi.clearAllMocks();
	mocks.mockUsePathname.mockReturnValue("/");
	mocks.mockUseBalance.mockReturnValue(balanceState());
	mocks.mockUseSession.mockReturnValue(sessionState());
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("TopNav", () => {
	// -------------------------------------------------------------------
	// Rendering
	// -------------------------------------------------------------------

	it("renders brand text", () => {
		render(<TopNav />);
		expect(screen.getByText("Zentropy Scout")).toBeInTheDocument();
	});

	it("renders navigation landmark", () => {
		render(<TopNav />);
		expect(screen.getByRole("navigation")).toBeInTheDocument();
	});

	// -------------------------------------------------------------------
	// Navigation links
	// -------------------------------------------------------------------

	it("renders Dashboard link pointing to /", () => {
		render(<TopNav />);
		const link = screen.getByRole("link", { name: /dashboard/i });
		expect(link).toHaveAttribute("href", "/");
	});

	it("renders Persona link pointing to /persona", () => {
		render(<TopNav />);
		const link = screen.getByRole("link", { name: /persona/i });
		expect(link).toHaveAttribute("href", "/persona");
	});

	it("renders Resumes link pointing to /resumes", () => {
		render(<TopNav />);
		const link = screen.getByRole("link", { name: /resumes/i });
		expect(link).toHaveAttribute("href", "/resumes");
	});

	it("renders Applications link pointing to /applications", () => {
		render(<TopNav />);
		const link = screen.getByRole("link", { name: /applications/i });
		expect(link).toHaveAttribute("href", "/applications");
	});

	it("renders Settings link pointing to /settings", () => {
		render(<TopNav />);
		const link = screen.getByRole("link", { name: /settings/i });
		expect(link).toHaveAttribute("href", "/settings");
	});

	// -------------------------------------------------------------------
	// Chat toggle
	// -------------------------------------------------------------------

	it("renders chat toggle button", () => {
		render(<TopNav />);
		expect(
			screen.getByRole("button", { name: /toggle chat/i }),
		).toBeInTheDocument();
	});

	it("calls toggle when chat button is clicked", () => {
		render(<TopNav />);
		screen.getByRole("button", { name: /toggle chat/i }).click();
		expect(mocks.mockToggle).toHaveBeenCalledTimes(1);
	});

	// -------------------------------------------------------------------
	// Active link
	// -------------------------------------------------------------------

	it("marks active link with aria-current for current path", () => {
		mocks.mockUsePathname.mockReturnValue("/persona");
		render(<TopNav />);
		const personaLink = screen.getByRole("link", { name: /persona/i });
		expect(personaLink).toHaveAttribute("aria-current", "page");
	});

	it("does not mark inactive links with aria-current", () => {
		mocks.mockUsePathname.mockReturnValue("/persona");
		render(<TopNav />);
		const dashboardLink = screen.getByRole("link", { name: /dashboard/i });
		expect(dashboardLink).not.toHaveAttribute("aria-current");
	});

	it("highlights nested route under parent nav item", () => {
		mocks.mockUsePathname.mockReturnValue("/resumes/abc-123");
		render(<TopNav />);
		const resumesLink = screen.getByRole("link", { name: /resumes/i });
		expect(resumesLink).toHaveAttribute("aria-current", "page");
	});

	// -------------------------------------------------------------------
	// Badge indicators
	// -------------------------------------------------------------------

	it("renders pending flags badge when count > 0", () => {
		render(<TopNav pendingFlagsCount={3} />);
		expect(screen.getByTestId("pending-flags-badge")).toHaveTextContent("3");
	});

	it("renders pending reviews badge when count > 0", () => {
		render(<TopNav pendingReviewsCount={2} />);
		expect(screen.getByTestId("pending-reviews-badge")).toHaveTextContent("2");
	});

	it("renders active applications badge when count > 0", () => {
		render(<TopNav activeApplicationsCount={5} />);
		expect(screen.getByTestId("active-applications-badge")).toHaveTextContent(
			"5",
		);
	});

	it("hides badges when counts are 0", () => {
		render(
			<TopNav
				pendingFlagsCount={0}
				pendingReviewsCount={0}
				activeApplicationsCount={0}
			/>,
		);
		expect(screen.queryByTestId("pending-flags-badge")).not.toBeInTheDocument();
		expect(
			screen.queryByTestId("pending-reviews-badge"),
		).not.toBeInTheDocument();
		expect(
			screen.queryByTestId("active-applications-badge"),
		).not.toBeInTheDocument();
	});

	it("hides badges when counts are not provided", () => {
		render(<TopNav />);
		expect(screen.queryByTestId("pending-flags-badge")).not.toBeInTheDocument();
		expect(
			screen.queryByTestId("pending-reviews-badge"),
		).not.toBeInTheDocument();
		expect(
			screen.queryByTestId("active-applications-badge"),
		).not.toBeInTheDocument();
	});

	// -------------------------------------------------------------------
	// Balance indicator (REQ-020 §9.1)
	// -------------------------------------------------------------------

	it("renders balance indicator with formatted amount", () => {
		mocks.mockUseBalance.mockReturnValue(
			balanceState({ balance: "10.500000" }),
		);
		render(<TopNav />);
		expect(screen.getByTestId("balance-indicator")).toHaveTextContent("$10.50");
	});

	it("renders balance link pointing to /usage", () => {
		render(<TopNav />);
		const link = screen.getByTestId("balance-indicator").closest("a");
		expect(link).toHaveAttribute("href", "/usage");
	});

	it("shows green text when balance > $1.00", () => {
		mocks.mockUseBalance.mockReturnValue(balanceState({ balance: "5.000000" }));
		render(<TopNav />);
		const indicator = screen.getByTestId("balance-indicator");
		expect(indicator.className).toContain("text-green");
	});

	it("shows amber text when balance is between $0.10 and $1.00", () => {
		mocks.mockUseBalance.mockReturnValue(balanceState({ balance: "0.500000" }));
		render(<TopNav />);
		const indicator = screen.getByTestId("balance-indicator");
		expect(indicator.className).toContain("text-amber");
	});

	it("shows red text when balance < $0.10", () => {
		mocks.mockUseBalance.mockReturnValue(balanceState({ balance: "0.050000" }));
		render(<TopNav />);
		const indicator = screen.getByTestId("balance-indicator");
		expect(indicator.className).toContain("text-red");
	});

	it("shows zero balance correctly", () => {
		mocks.mockUseBalance.mockReturnValue(balanceState({ balance: "0.000000" }));
		render(<TopNav />);
		const indicator = screen.getByTestId("balance-indicator");
		expect(indicator).toHaveTextContent("$0.00");
		expect(indicator.className).toContain("text-red");
	});

	it("hides balance indicator while loading", () => {
		mocks.mockUseBalance.mockReturnValue(
			balanceState({ balance: undefined, isLoading: true }),
		);
		render(<TopNav />);
		expect(screen.queryByTestId("balance-indicator")).not.toBeInTheDocument();
	});

	it("hides balance indicator on error", () => {
		mocks.mockUseBalance.mockReturnValue(
			balanceState({ balance: undefined, error: new Error("Failed") }),
		);
		render(<TopNav />);
		expect(screen.queryByTestId("balance-indicator")).not.toBeInTheDocument();
	});

	// -------------------------------------------------------------------
	// Admin link (REQ-022 §11.4)
	// -------------------------------------------------------------------

	it("renders admin link when session.isAdmin is true", () => {
		mocks.mockUseSession.mockReturnValue(
			sessionState({ session: { isAdmin: true } }),
		);
		render(<TopNav />);
		const link = screen.getByRole("link", { name: /admin/i });
		expect(link).toHaveAttribute("href", "/admin/config");
	});

	it("hides admin link when session.isAdmin is false", () => {
		mocks.mockUseSession.mockReturnValue(
			sessionState({ session: { isAdmin: false } }),
		);
		render(<TopNav />);
		expect(
			screen.queryByRole("link", { name: /admin/i }),
		).not.toBeInTheDocument();
	});

	it("hides admin link when session is null", () => {
		mocks.mockUseSession.mockReturnValue(sessionState({ session: null }));
		render(<TopNav />);
		expect(
			screen.queryByRole("link", { name: /admin/i }),
		).not.toBeInTheDocument();
	});

	it("marks admin link as active on /admin path", () => {
		mocks.mockUsePathname.mockReturnValue("/admin/config");
		mocks.mockUseSession.mockReturnValue(
			sessionState({ session: { isAdmin: true } }),
		);
		render(<TopNav />);
		const link = screen.getByRole("link", { name: /admin/i });
		expect(link).toHaveAttribute("aria-current", "page");
	});
});
