/**
 * Tests for the GrowthTargetsPage route component.
 *
 * Verifies guard clause: only renders GrowthTargetsEditor
 * for onboarded users.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import GrowthTargetsPage from "./page";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
	mockUsePersonaStatus: vi.fn(),
}));

vi.mock("@/hooks/use-persona-status", () => ({
	usePersonaStatus: mocks.mockUsePersonaStatus,
}));

vi.mock("@/components/persona/growth-targets-editor", () => ({
	GrowthTargetsEditor: ({ persona }: { persona: { full_name: string } }) => (
		<div data-testid="growth-targets-editor">{persona.full_name}</div>
	),
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("GrowthTargetsPage", () => {
	beforeEach(() => {
		mocks.mockUsePersonaStatus.mockReset();
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	it("renders nothing when status is loading", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({ status: "loading" });
		const { container } = render(<GrowthTargetsPage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders nothing when status is needs-onboarding", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "needs-onboarding",
		});
		const { container } = render(<GrowthTargetsPage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders GrowthTargetsEditor when status is onboarded", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona: { full_name: "Jane Doe" },
		});
		render(<GrowthTargetsPage />);

		expect(screen.getByTestId("growth-targets-editor")).toBeInTheDocument();
		expect(screen.getByText("Jane Doe")).toBeInTheDocument();
	});
});
