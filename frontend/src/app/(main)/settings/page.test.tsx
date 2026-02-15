/**
 * Tests for the SettingsPage route component.
 *
 * Verifies guard clause: only renders SettingsPage for onboarded users.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import SettingsRoute from "./page";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
	mockUsePersonaStatus: vi.fn(),
}));

vi.mock("@/hooks/use-persona-status", () => ({
	usePersonaStatus: mocks.mockUsePersonaStatus,
}));

vi.mock("@/components/settings/settings-page", () => ({
	SettingsPage: () => <div data-testid="settings-page">Settings Page</div>,
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SettingsRoute", () => {
	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	it("renders nothing when status is loading", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({ status: "loading" });
		const { container } = render(<SettingsRoute />);
		expect(container.innerHTML).toBe("");
	});

	it("renders nothing when status is needs-onboarding", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "needs-onboarding",
		});
		const { container } = render(<SettingsRoute />);
		expect(container.innerHTML).toBe("");
	});

	it("renders SettingsPage when status is onboarded", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona: { id: "p-1" },
		});
		render(<SettingsRoute />);
		expect(screen.getByTestId("settings-page")).toBeInTheDocument();
	});
});
