/**
 * Tests for the WorkHistoryPage route component.
 *
 * Verifies guard clause: only renders WorkHistoryEditor for onboarded users.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import WorkHistoryPage from "./page";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
	mockUsePersonaStatus: vi.fn(),
}));

vi.mock("@/hooks/use-persona-status", () => ({
	usePersonaStatus: mocks.mockUsePersonaStatus,
}));

vi.mock("@/components/persona/work-history-editor", () => ({
	WorkHistoryEditor: ({ persona }: { persona: { full_name: string } }) => (
		<div data-testid="work-history-editor">{persona.full_name}</div>
	),
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("WorkHistoryPage", () => {
	beforeEach(() => {
		mocks.mockUsePersonaStatus.mockReset();
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	it("renders nothing when status is loading", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({ status: "loading" });
		const { container } = render(<WorkHistoryPage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders nothing when status is needs-onboarding", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "needs-onboarding",
		});
		const { container } = render(<WorkHistoryPage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders WorkHistoryEditor when status is onboarded", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona: { full_name: "Jane Doe" },
		});
		render(<WorkHistoryPage />);

		expect(screen.getByTestId("work-history-editor")).toBeInTheDocument();
		expect(screen.getByText("Jane Doe")).toBeInTheDocument();
	});
});
