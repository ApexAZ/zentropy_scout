/**
 * Tests for the DashboardPage route component.
 *
 * Verifies guard clause: only renders DashboardTabs for onboarded users.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "./page";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
	mockUsePersonaStatus: vi.fn(),
}));

vi.mock("@/hooks/use-persona-status", () => ({
	usePersonaStatus: mocks.mockUsePersonaStatus,
}));

vi.mock("@/components/dashboard/dashboard-tabs", () => ({
	DashboardTabs: () => <div data-testid="dashboard-tabs">Dashboard</div>,
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DashboardPage", () => {
	beforeEach(() => {
		mocks.mockUsePersonaStatus.mockReset();
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	it("renders nothing when status is loading", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({ status: "loading" });
		const { container } = render(<DashboardPage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders nothing when status is needs-onboarding", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "needs-onboarding",
		});
		const { container } = render(<DashboardPage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders DashboardTabs when status is onboarded", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona: { id: "p-1" },
		});
		render(<DashboardPage />);

		expect(screen.getByTestId("dashboard-tabs")).toBeInTheDocument();
	});
});
