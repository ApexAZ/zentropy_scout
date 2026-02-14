/**
 * Tests for the DashboardTabs component (§7.1).
 *
 * REQ-012 §8.1: Three-tab dashboard layout with URL-persisted
 * tab state: Opportunities, In Progress, History.
 */

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CONTAINER_TESTID = "dashboard-tabs";
const LABEL_OPPORTUNITIES = "Opportunities";
const LABEL_IN_PROGRESS = "In Progress";
const LABEL_HISTORY = "History";
const ARIA_SELECTED = "aria-selected";

const TAB_PARAM = "tab";
const TAB_VALUE_IN_PROGRESS = "in-progress";
const TAB_VALUE_HISTORY = "history";

function mockTabParam(value: string) {
	return (key: string) => (key === TAB_PARAM ? value : null);
}

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
	mockReplace: vi.fn(),
	mockGet: vi.fn(),
	mockToString: vi.fn(),
}));

vi.mock("next/navigation", () => ({
	useRouter: () => ({ replace: mocks.mockReplace }),
	useSearchParams: () => ({
		get: mocks.mockGet,
		toString: mocks.mockToString,
	}),
}));

vi.mock("./applications-table", () => ({
	ApplicationsTable: ({ variant }: { variant: string }) => (
		<div data-testid={`applications-table-${variant}`}>
			Applications ({variant})
		</div>
	),
}));

vi.mock("./opportunities-table", () => ({
	OpportunitiesTable: () => (
		<div data-testid="opportunities-table">Opportunities</div>
	),
}));

import { DashboardTabs } from "./dashboard-tabs";

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
	mocks.mockReplace.mockReset();
	mocks.mockGet.mockReset().mockReturnValue(null);
	mocks.mockToString.mockReset().mockReturnValue("");
});

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DashboardTabs", () => {
	describe("rendering", () => {
		it("renders dashboard heading", () => {
			render(<DashboardTabs />);

			expect(
				screen.getByRole("heading", { name: "Dashboard" }),
			).toBeInTheDocument();
		});

		it("renders container with testid", () => {
			render(<DashboardTabs />);

			expect(screen.getByTestId(CONTAINER_TESTID)).toBeInTheDocument();
		});

		it("renders tablist", () => {
			render(<DashboardTabs />);

			expect(screen.getByRole("tablist")).toBeInTheDocument();
		});

		it("renders three tab triggers", () => {
			render(<DashboardTabs />);

			const tabs = screen.getAllByRole("tab");
			expect(tabs).toHaveLength(3);
		});

		it("renders Opportunities tab trigger", () => {
			render(<DashboardTabs />);

			expect(
				screen.getByRole("tab", { name: LABEL_OPPORTUNITIES }),
			).toBeInTheDocument();
		});

		it("renders In Progress tab trigger", () => {
			render(<DashboardTabs />);

			expect(
				screen.getByRole("tab", { name: LABEL_IN_PROGRESS }),
			).toBeInTheDocument();
		});

		it("renders History tab trigger", () => {
			render(<DashboardTabs />);

			expect(
				screen.getByRole("tab", { name: LABEL_HISTORY }),
			).toBeInTheDocument();
		});
	});

	describe("default tab", () => {
		it("activates Opportunities tab by default when no URL param", () => {
			render(<DashboardTabs />);

			const tab = screen.getByRole("tab", {
				name: LABEL_OPPORTUNITIES,
			});
			expect(tab).toHaveAttribute(ARIA_SELECTED, "true");
		});

		it("does not activate In Progress by default", () => {
			render(<DashboardTabs />);

			const tab = screen.getByRole("tab", { name: LABEL_IN_PROGRESS });
			expect(tab).toHaveAttribute(ARIA_SELECTED, "false");
		});

		it("defaults to Opportunities for invalid tab param", () => {
			mocks.mockGet.mockReturnValue("invalid-tab");

			render(<DashboardTabs />);

			const tab = screen.getByRole("tab", {
				name: LABEL_OPPORTUNITIES,
			});
			expect(tab).toHaveAttribute(ARIA_SELECTED, "true");
		});
	});

	describe("URL-driven tab state", () => {
		it("activates In Progress tab when URL has tab=in-progress", () => {
			mocks.mockGet.mockImplementation(mockTabParam(TAB_VALUE_IN_PROGRESS));

			render(<DashboardTabs />);

			const tab = screen.getByRole("tab", { name: LABEL_IN_PROGRESS });
			expect(tab).toHaveAttribute(ARIA_SELECTED, "true");
		});

		it("activates History tab when URL has tab=history", () => {
			mocks.mockGet.mockImplementation(mockTabParam(TAB_VALUE_HISTORY));

			render(<DashboardTabs />);

			const tab = screen.getByRole("tab", { name: LABEL_HISTORY });
			expect(tab).toHaveAttribute(ARIA_SELECTED, "true");
		});
	});

	describe("tab switching updates URL", () => {
		it("calls router.replace with tab=in-progress when clicking In Progress", async () => {
			const user = userEvent.setup();

			render(<DashboardTabs />);

			await user.click(screen.getByRole("tab", { name: LABEL_IN_PROGRESS }));

			expect(mocks.mockReplace).toHaveBeenCalledWith("/?tab=in-progress");
		});

		it("calls router.replace with tab=history when clicking History", async () => {
			const user = userEvent.setup();

			render(<DashboardTabs />);

			await user.click(screen.getByRole("tab", { name: LABEL_HISTORY }));

			expect(mocks.mockReplace).toHaveBeenCalledWith("/?tab=history");
		});

		it("calls router.replace with clean URL when clicking Opportunities from another tab", async () => {
			const user = userEvent.setup();
			mocks.mockGet.mockImplementation(mockTabParam(TAB_VALUE_IN_PROGRESS));
			mocks.mockToString.mockReturnValue("tab=in-progress");

			render(<DashboardTabs />);

			await user.click(screen.getByRole("tab", { name: LABEL_OPPORTUNITIES }));

			expect(mocks.mockReplace).toHaveBeenCalledWith("/");
		});

		it("does not call router.replace when clicking the already-active tab", async () => {
			const user = userEvent.setup();

			render(<DashboardTabs />);

			// Opportunities is already active by default
			await user.click(screen.getByRole("tab", { name: LABEL_OPPORTUNITIES }));

			expect(mocks.mockReplace).not.toHaveBeenCalled();
		});
	});

	describe("tab content", () => {
		it("renders ApplicationsTable with variant='in-progress' in In Progress tab", () => {
			mocks.mockGet.mockImplementation(mockTabParam(TAB_VALUE_IN_PROGRESS));

			render(<DashboardTabs />);

			expect(
				screen.getByTestId("applications-table-in-progress"),
			).toBeInTheDocument();
		});

		it("renders ApplicationsTable with variant='history' in History tab", () => {
			mocks.mockGet.mockImplementation(mockTabParam(TAB_VALUE_HISTORY));

			render(<DashboardTabs />);

			expect(
				screen.getByTestId("applications-table-history"),
			).toBeInTheDocument();
		});
	});
});
