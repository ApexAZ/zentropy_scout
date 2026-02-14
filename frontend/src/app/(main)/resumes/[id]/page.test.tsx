/**
 * Tests for the ResumeDetailPage route component.
 *
 * Verifies guard clause: only renders ResumeDetail for onboarded users,
 * and passes correct resumeId and personaId props.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ResumeDetailPage from "./page";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MOCK_RESUME_ID = "r-1";
const MOCK_PERSONA_ID = "p-1";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
	mockUsePersonaStatus: vi.fn(),
	mockUseParams: vi.fn(),
}));

vi.mock("@/hooks/use-persona-status", () => ({
	usePersonaStatus: mocks.mockUsePersonaStatus,
}));

vi.mock("next/navigation", () => ({
	useParams: mocks.mockUseParams,
}));

vi.mock("@/components/resume/resume-detail", () => ({
	ResumeDetail: ({
		resumeId,
		personaId,
	}: {
		resumeId: string;
		personaId: string;
	}) => (
		<div
			data-testid="resume-detail"
			data-resume-id={resumeId}
			data-persona-id={personaId}
		>
			Resume Detail
		</div>
	),
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ResumeDetailPage", () => {
	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	it("renders nothing when status is loading", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({ status: "loading" });
		mocks.mockUseParams.mockReturnValue({ id: MOCK_RESUME_ID });
		const { container } = render(<ResumeDetailPage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders nothing when status is needs-onboarding", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "needs-onboarding",
		});
		mocks.mockUseParams.mockReturnValue({ id: MOCK_RESUME_ID });
		const { container } = render(<ResumeDetailPage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders ResumeDetail with correct props when onboarded", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona: { id: MOCK_PERSONA_ID },
		});
		mocks.mockUseParams.mockReturnValue({ id: MOCK_RESUME_ID });
		render(<ResumeDetailPage />);

		const detail = screen.getByTestId("resume-detail");
		expect(detail).toBeInTheDocument();
		expect(detail).toHaveAttribute("data-resume-id", MOCK_RESUME_ID);
		expect(detail).toHaveAttribute("data-persona-id", MOCK_PERSONA_ID);
	});
});
