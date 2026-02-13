/**
 * Tests for the BasicInfoPage route component.
 *
 * Verifies guard clause: only renders BasicInfoEditor for onboarded users.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import BasicInfoPage from "./page";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
	mockUsePersonaStatus: vi.fn(),
}));

vi.mock("@/hooks/use-persona-status", () => ({
	usePersonaStatus: mocks.mockUsePersonaStatus,
}));

vi.mock("@/components/persona/basic-info-editor", () => ({
	BasicInfoEditor: ({ persona }: { persona: { full_name: string } }) => (
		<div data-testid="basic-info-editor">{persona.full_name}</div>
	),
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("BasicInfoPage", () => {
	beforeEach(() => {
		mocks.mockUsePersonaStatus.mockReset();
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	it("renders nothing when status is loading", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({ status: "loading" });
		const { container } = render(<BasicInfoPage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders nothing when status is needs-onboarding", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "needs-onboarding",
		});
		const { container } = render(<BasicInfoPage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders BasicInfoEditor when status is onboarded", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona: { full_name: "Jane Doe" },
		});
		render(<BasicInfoPage />);

		expect(screen.getByTestId("basic-info-editor")).toBeInTheDocument();
		expect(screen.getByText("Jane Doe")).toBeInTheDocument();
	});
});
