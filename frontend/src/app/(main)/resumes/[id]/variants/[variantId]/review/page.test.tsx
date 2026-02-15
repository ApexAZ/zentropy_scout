/**
 * Tests for the VariantReviewPage route component.
 *
 * Verifies guard clause: only renders VariantReview for onboarded users,
 * and passes correct baseResumeId, variantId, and personaId props.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import VariantReviewPage from "./page";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MOCK_RESUME_ID = "r-1";
const MOCK_VARIANT_ID = "v-1";
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

vi.mock("@/components/resume/variant-review", () => ({
	VariantReview: ({
		baseResumeId,
		variantId,
		personaId,
	}: {
		baseResumeId: string;
		variantId: string;
		personaId: string;
	}) => (
		<div
			data-testid="variant-review"
			data-base-resume-id={baseResumeId}
			data-variant-id={variantId}
			data-persona-id={personaId}
		>
			Variant Review
		</div>
	),
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("VariantReviewPage", () => {
	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	it("renders nothing when status is loading", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({ status: "loading" });
		mocks.mockUseParams.mockReturnValue({
			id: MOCK_RESUME_ID,
			variantId: MOCK_VARIANT_ID,
		});
		const { container } = render(<VariantReviewPage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders nothing when status is needs-onboarding", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "needs-onboarding",
		});
		mocks.mockUseParams.mockReturnValue({
			id: MOCK_RESUME_ID,
			variantId: MOCK_VARIANT_ID,
		});
		const { container } = render(<VariantReviewPage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders VariantReview with correct props when onboarded", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona: { id: MOCK_PERSONA_ID },
		});
		mocks.mockUseParams.mockReturnValue({
			id: MOCK_RESUME_ID,
			variantId: MOCK_VARIANT_ID,
		});
		render(<VariantReviewPage />);

		const review = screen.getByTestId("variant-review");
		expect(review).toBeInTheDocument();
		expect(review).toHaveAttribute("data-base-resume-id", MOCK_RESUME_ID);
		expect(review).toHaveAttribute("data-variant-id", MOCK_VARIANT_ID);
		expect(review).toHaveAttribute("data-persona-id", MOCK_PERSONA_ID);
	});
});
