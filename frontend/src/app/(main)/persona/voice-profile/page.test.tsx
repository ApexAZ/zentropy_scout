/**
 * Tests for the VoiceProfilePage route component.
 *
 * Verifies guard clause: only renders VoiceProfileEditor
 * for onboarded users.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import VoiceProfilePage from "./page";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
	mockUsePersonaStatus: vi.fn(),
}));

vi.mock("@/hooks/use-persona-status", () => ({
	usePersonaStatus: mocks.mockUsePersonaStatus,
}));

vi.mock("@/components/persona/voice-profile-editor", () => ({
	VoiceProfileEditor: ({ persona }: { persona: { full_name: string } }) => (
		<div data-testid="voice-profile-editor">{persona.full_name}</div>
	),
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("VoiceProfilePage", () => {
	beforeEach(() => {
		mocks.mockUsePersonaStatus.mockReset();
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	it("renders nothing when status is loading", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({ status: "loading" });
		const { container } = render(<VoiceProfilePage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders nothing when status is needs-onboarding", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "needs-onboarding",
		});
		const { container } = render(<VoiceProfilePage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders VoiceProfileEditor when status is onboarded", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona: { full_name: "Jane Doe" },
		});
		render(<VoiceProfilePage />);

		expect(screen.getByTestId("voice-profile-editor")).toBeInTheDocument();
		expect(screen.getByText("Jane Doe")).toBeInTheDocument();
	});
});
