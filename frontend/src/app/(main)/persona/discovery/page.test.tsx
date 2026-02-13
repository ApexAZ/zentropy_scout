/**
 * Tests for the DiscoveryPreferencesPage route component.
 *
 * Verifies guard clause: only renders DiscoveryPreferencesEditor
 * for onboarded users.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import DiscoveryPreferencesPage from "./page";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
	mockUsePersonaStatus: vi.fn(),
}));

vi.mock("@/hooks/use-persona-status", () => ({
	usePersonaStatus: mocks.mockUsePersonaStatus,
}));

vi.mock("@/components/persona/discovery-preferences-editor", () => ({
	DiscoveryPreferencesEditor: ({
		persona,
	}: {
		persona: { full_name: string };
	}) => (
		<div data-testid="discovery-preferences-editor">{persona.full_name}</div>
	),
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DiscoveryPreferencesPage", () => {
	beforeEach(() => {
		mocks.mockUsePersonaStatus.mockReset();
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	it("renders nothing when status is loading", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({ status: "loading" });
		const { container } = render(<DiscoveryPreferencesPage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders nothing when status is needs-onboarding", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "needs-onboarding",
		});
		const { container } = render(<DiscoveryPreferencesPage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders DiscoveryPreferencesEditor when status is onboarded", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona: { full_name: "Jane Doe" },
		});
		render(<DiscoveryPreferencesPage />);

		expect(
			screen.getByTestId("discovery-preferences-editor"),
		).toBeInTheDocument();
		expect(screen.getByText("Jane Doe")).toBeInTheDocument();
	});
});
