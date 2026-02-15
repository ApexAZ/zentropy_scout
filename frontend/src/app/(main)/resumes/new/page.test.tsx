/**
 * Tests for the NewResumePage route component (§8.8).
 *
 * Verifies guard clause: only renders NewResumeWizard for onboarded users,
 * and passes correct personaId prop.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import NewResumePage from "./page";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MOCK_PERSONA_ID = "p-1";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
	mockUsePersonaStatus: vi.fn(),
}));

vi.mock("@/hooks/use-persona-status", () => ({
	usePersonaStatus: mocks.mockUsePersonaStatus,
}));

vi.mock("@/components/resume/new-resume-wizard", () => ({
	NewResumeWizard: ({ personaId }: { personaId: string }) => (
		<div data-testid="new-resume-wizard" data-persona-id={personaId}>
			New Resume Wizard
		</div>
	),
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("NewResumePage", () => {
	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	it("renders nothing when status is loading", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({ status: "loading" });
		const { container } = render(<NewResumePage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders nothing when status is needs-onboarding", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "needs-onboarding",
		});
		const { container } = render(<NewResumePage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders NewResumeWizard with correct personaId when onboarded", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona: { id: MOCK_PERSONA_ID },
		});
		render(<NewResumePage />);

		const wizard = screen.getByTestId("new-resume-wizard");
		expect(wizard).toBeInTheDocument();
		expect(wizard).toHaveAttribute("data-persona-id", MOCK_PERSONA_ID);
	});
});
