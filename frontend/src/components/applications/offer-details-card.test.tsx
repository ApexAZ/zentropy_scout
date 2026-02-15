/**
 * Tests for the OfferDetailsCard component (§10.5).
 *
 * REQ-012 §11.5: Read-only display of offer details with deadline
 * countdown and Edit button.
 */

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OfferDetails } from "@/types/application";
import { OfferDetailsCard } from "./offer-details-card";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CARD_TESTID = "offer-details-card";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeOfferDetails(overrides?: Partial<OfferDetails>): OfferDetails {
	return {
		base_salary: 155000,
		salary_currency: "USD",
		bonus_percent: 15,
		equity_value: 50000,
		equity_type: "RSU",
		equity_vesting_years: 4,
		start_date: "2026-04-01",
		response_deadline: "2026-03-15",
		other_benefits: "401k 6%, unlimited PTO",
		notes: "Negotiated from 140k",
		...overrides,
	};
}

/** Returns a YYYY-MM-DD string for N days from today (UTC). */
function daysFromNow(days: number): string {
	const d = new Date();
	d.setUTCDate(d.getUTCDate() + days);
	return d.toISOString().slice(0, 10);
}

function renderCard(
	offerDetails: OfferDetails = makeOfferDetails(),
	onEdit = vi.fn(),
) {
	return {
		...render(<OfferDetailsCard offerDetails={offerDetails} onEdit={onEdit} />),
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

describe("OfferDetailsCard", () => {
	// -----------------------------------------------------------------------
	// Rendering
	// -----------------------------------------------------------------------

	describe("rendering", () => {
		it("renders the card with testid", () => {
			renderCard();
			expect(screen.getByTestId(CARD_TESTID)).toBeInTheDocument();
		});

		it("renders 'Offer Details' title", () => {
			renderCard();
			expect(screen.getByText("Offer Details")).toBeInTheDocument();
		});

		it("renders Edit button", () => {
			renderCard();
			expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
		});

		it("displays formatted base salary with currency", () => {
			renderCard();
			expect(screen.getByText(/\$155,000/)).toBeInTheDocument();
		});

		it("displays bonus percentage", () => {
			renderCard();
			expect(screen.getByText(/15%/)).toBeInTheDocument();
		});

		it("displays equity details with type and vesting", () => {
			renderCard();
			expect(screen.getByText(/\$50,000/)).toBeInTheDocument();
			expect(screen.getByText(/RSU/)).toBeInTheDocument();
			expect(screen.getByText(/4-year/)).toBeInTheDocument();
		});

		it("displays start date", () => {
			renderCard();
			expect(screen.getByText(/Apr 1, 2026/)).toBeInTheDocument();
		});

		it("displays benefits text", () => {
			renderCard();
			expect(screen.getByText("401k 6%, unlimited PTO")).toBeInTheDocument();
		});

		it("displays notes text", () => {
			renderCard();
			expect(screen.getByText("Negotiated from 140k")).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Deadline countdown
	// -----------------------------------------------------------------------

	describe("deadline countdown", () => {
		it("shows days remaining for future deadline", () => {
			renderCard(
				makeOfferDetails({
					response_deadline: daysFromNow(5),
				}),
			);
			expect(screen.getByText(/5 days remaining/)).toBeInTheDocument();
		});

		it("shows 'Today' for today's deadline", () => {
			renderCard(
				makeOfferDetails({
					response_deadline: daysFromNow(0),
				}),
			);
			expect(screen.getByText(/Today/)).toBeInTheDocument();
		});

		it("shows 'Expired' for past deadline", () => {
			renderCard(
				makeOfferDetails({
					response_deadline: daysFromNow(-3),
				}),
			);
			expect(screen.getByText(/Expired/)).toBeInTheDocument();
		});

		it("shows '1 day remaining' for tomorrow's deadline", () => {
			renderCard(
				makeOfferDetails({
					response_deadline: daysFromNow(1),
				}),
			);
			expect(screen.getByText(/1 day remaining/)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Empty/partial data
	// -----------------------------------------------------------------------

	describe("partial data", () => {
		it("hides salary row when base_salary is undefined", () => {
			renderCard(
				makeOfferDetails({
					base_salary: undefined,
					salary_currency: undefined,
				}),
			);
			expect(screen.queryByText("Base Salary")).not.toBeInTheDocument();
		});

		it("hides bonus row when bonus_percent is undefined", () => {
			renderCard(makeOfferDetails({ bonus_percent: undefined }));
			expect(screen.queryByText("Bonus")).not.toBeInTheDocument();
		});

		it("hides equity row when equity_value is undefined", () => {
			renderCard(
				makeOfferDetails({
					equity_value: undefined,
					equity_type: undefined,
				}),
			);
			expect(screen.queryByText("Equity")).not.toBeInTheDocument();
		});

		it("hides deadline row when response_deadline is undefined", () => {
			renderCard(makeOfferDetails({ response_deadline: undefined }));
			expect(screen.queryByText("Deadline")).not.toBeInTheDocument();
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
