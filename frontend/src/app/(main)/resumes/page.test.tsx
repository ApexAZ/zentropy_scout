/**
 * Tests for the ResumesPage route component.
 *
 * Verifies guard clause: only renders ResumeList for onboarded users.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ResumesPage from "./page";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
	mockUsePersonaStatus: vi.fn(),
}));

vi.mock("@/hooks/use-persona-status", () => ({
	usePersonaStatus: mocks.mockUsePersonaStatus,
}));

vi.mock("@/components/resume/resume-list", () => ({
	ResumeList: () => <div data-testid="resume-list">Resume List</div>,
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ResumesPage", () => {
	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	it("renders nothing when status is loading", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({ status: "loading" });
		const { container } = render(<ResumesPage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders nothing when status is needs-onboarding", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "needs-onboarding",
		});
		const { container } = render(<ResumesPage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders ResumeList when status is onboarded", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona: { id: "p-1" },
		});
		render(<ResumesPage />);

		expect(screen.getByTestId("resume-list")).toBeInTheDocument();
	});
});
