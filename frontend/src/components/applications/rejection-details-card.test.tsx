/**
 * Tests for the RejectionDetailsCard component (§10.6).
 *
 * REQ-012 §11.6: Read-only display of rejection details with
 * stage, reason, feedback, and date.
 */

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { RejectionDetails } from "@/types/application";
import { RejectionDetailsCard } from "./rejection-details-card";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CARD_TESTID = "rejection-details-card";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeRejectionDetails(
	overrides?: Partial<RejectionDetails>,
): RejectionDetails {
	return {
		stage: "Onsite",
		reason: "Culture fit concerns",
		feedback: "Looking for someone more senior",
		rejected_at: "2026-01-15T10:30:00Z",
		...overrides,
	};
}

function renderCard(
	rejectionDetails: RejectionDetails = makeRejectionDetails(),
	onEdit = vi.fn(),
) {
	return {
		...render(
			<RejectionDetailsCard
				rejectionDetails={rejectionDetails}
				onEdit={onEdit}
			/>,
		),
		onEdit,
	};
}

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("RejectionDetailsCard", () => {
	// -----------------------------------------------------------------------
	// Rendering
	// -----------------------------------------------------------------------

	describe("rendering", () => {
		it("renders the card with testid", () => {
			renderCard();
			expect(screen.getByTestId(CARD_TESTID)).toBeInTheDocument();
		});

		it("renders 'Rejection Details' title", () => {
			renderCard();
			expect(screen.getByText("Rejection Details")).toBeInTheDocument();
		});

		it("renders Edit button", () => {
			renderCard();
			expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
		});

		it("displays stage", () => {
			renderCard();
			expect(screen.getByText("Onsite")).toBeInTheDocument();
		});

		it("displays reason", () => {
			renderCard();
			expect(screen.getByText("Culture fit concerns")).toBeInTheDocument();
		});

		it("displays feedback", () => {
			renderCard();
			expect(
				screen.getByText("Looking for someone more senior"),
			).toBeInTheDocument();
		});

		it("displays formatted rejected at date", () => {
			renderCard();
			expect(screen.getByText(/Jan 15, 2026/)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Partial data
	// -----------------------------------------------------------------------

	describe("partial data", () => {
		it("hides stage row when stage is undefined", () => {
			renderCard(makeRejectionDetails({ stage: undefined }));
			expect(
				screen.queryByTestId("rejection-stage-row"),
			).not.toBeInTheDocument();
		});

		it("hides reason row when reason is undefined", () => {
			renderCard(makeRejectionDetails({ reason: undefined }));
			expect(
				screen.queryByTestId("rejection-reason-row"),
			).not.toBeInTheDocument();
		});

		it("hides feedback row when feedback is undefined", () => {
			renderCard(makeRejectionDetails({ feedback: undefined }));
			expect(
				screen.queryByTestId("rejection-feedback-row"),
			).not.toBeInTheDocument();
		});

		it("hides rejected at row when rejected_at is undefined", () => {
			renderCard(makeRejectionDetails({ rejected_at: undefined }));
			expect(
				screen.queryByTestId("rejection-date-row"),
			).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Interaction
	// -----------------------------------------------------------------------

	describe("interaction", () => {
		it("calls onEdit when Edit button is clicked", async () => {
			const user = userEvent.setup();
			const { onEdit } = renderCard();

			await user.click(screen.getByRole("button", { name: "Edit" }));

			expect(onEdit).toHaveBeenCalledOnce();
		});
	});
});
