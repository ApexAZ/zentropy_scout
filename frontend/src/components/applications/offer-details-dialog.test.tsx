/**
 * Tests for the OfferDetailsDialog component (§10.5).
 *
 * REQ-012 §11.5: Offer details capture form with all-optional fields.
 * Modal dialog triggered when user transitions to Offer status.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OfferDetails } from "@/types/application";
import { OfferDetailsDialog } from "./offer-details-dialog";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DIALOG_TITLE = "Offer Details";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderDialog(
	props?: Partial<{
		open: boolean;
		onConfirm: (details: OfferDetails) => void;
		onCancel: () => void;
		loading: boolean;
		initialData: OfferDetails | null;
	}>,
) {
	const defaultProps = {
		open: true,
		onConfirm: vi.fn(),
		onCancel: vi.fn(),
		loading: false,
		initialData: null,
		...props,
	};
	return {
		...render(<OfferDetailsDialog {...defaultProps} />),
		onConfirm: defaultProps.onConfirm,
		onCancel: defaultProps.onCancel,
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

describe("OfferDetailsDialog", () => {
	// -----------------------------------------------------------------------
	// Rendering
	// -----------------------------------------------------------------------

	describe("rendering", () => {
		it("renders dialog title", () => {
			renderDialog();
			expect(screen.getByText(DIALOG_TITLE)).toBeInTheDocument();
		});

		it("renders base salary input", () => {
			renderDialog();
			expect(screen.getByLabelText("Base Salary")).toBeInTheDocument();
		});

		it("renders currency select defaulting to USD", () => {
			renderDialog();
			expect(screen.getByTestId("currency-select")).toBeInTheDocument();
			expect(screen.getByText("USD")).toBeInTheDocument();
		});

		it("renders bonus input", () => {
			renderDialog();
			expect(screen.getByLabelText("Bonus (%)")).toBeInTheDocument();
		});

		it("renders equity value input", () => {
			renderDialog();
			expect(screen.getByLabelText("Equity Value")).toBeInTheDocument();
		});

		it("renders equity type select with RSU and Options", async () => {
			const user = userEvent.setup();
			renderDialog();

			const trigger = screen.getByTestId("equity-type-select");
			await user.click(trigger);

			await waitFor(() => {
				expect(screen.getByRole("option", { name: "RSU" })).toBeInTheDocument();
				expect(
					screen.getByRole("option", { name: "Options" }),
				).toBeInTheDocument();
			});
		});

		it("renders vesting years input", () => {
			renderDialog();
			expect(screen.getByLabelText("Vesting Years")).toBeInTheDocument();
		});

		it("renders start date input", () => {
			renderDialog();
			expect(screen.getByLabelText("Start Date")).toBeInTheDocument();
		});

		it("renders response deadline input", () => {
			renderDialog();
			expect(screen.getByLabelText("Response Deadline")).toBeInTheDocument();
		});

		it("renders benefits textarea", () => {
			renderDialog();
			expect(screen.getByLabelText("Benefits")).toBeInTheDocument();
		});

		it("renders notes textarea", () => {
			renderDialog();
			expect(screen.getByLabelText("Notes")).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Interaction
	// -----------------------------------------------------------------------

	describe("interaction", () => {
		it("calls onConfirm with default currency when submitting empty form", async () => {
			const user = userEvent.setup();
			const { onConfirm } = renderDialog();

			await user.click(screen.getByRole("button", { name: "Save" }));

			expect(onConfirm).toHaveBeenCalledWith({ salary_currency: "USD" });
		});

		it("calls onConfirm with filled fields", async () => {
			const user = userEvent.setup();
			const { onConfirm } = renderDialog();

			await user.type(screen.getByLabelText("Base Salary"), "155000");
			await user.type(screen.getByLabelText("Bonus (%)"), "15");
			await user.type(screen.getByLabelText("Equity Value"), "50000");
			await user.type(screen.getByLabelText("Vesting Years"), "4");

			await user.click(screen.getByRole("button", { name: "Save" }));

			expect(onConfirm).toHaveBeenCalledWith(
				expect.objectContaining({
					base_salary: 155000,
					salary_currency: "USD",
					bonus_percent: 15,
					equity_value: 50000,
					equity_vesting_years: 4,
				}),
			);
		});

		it("pre-populates fields from initialData", () => {
			const initialData: OfferDetails = {
				base_salary: 160000,
				salary_currency: "EUR",
				bonus_percent: 20,
				equity_value: 75000,
				equity_type: "RSU",
				equity_vesting_years: 4,
				start_date: "2026-04-01",
				response_deadline: "2026-03-15",
				other_benefits: "401k match, PTO",
				notes: "Negotiated from 140k",
			};
			renderDialog({ initialData });

			expect(screen.getByLabelText("Base Salary")).toHaveValue(160000);
			expect(screen.getByText("EUR")).toBeInTheDocument();
			expect(screen.getByLabelText("Bonus (%)")).toHaveValue(20);
			expect(screen.getByLabelText("Equity Value")).toHaveValue(75000);
			expect(screen.getByLabelText("Vesting Years")).toHaveValue(4);
			expect(screen.getByLabelText("Start Date")).toHaveValue("2026-04-01");
			expect(screen.getByLabelText("Response Deadline")).toHaveValue(
				"2026-03-15",
			);
			expect(screen.getByLabelText("Benefits")).toHaveValue("401k match, PTO");
			expect(screen.getByLabelText("Notes")).toHaveValue(
				"Negotiated from 140k",
			);
		});

		it("calls onCancel when Cancel is clicked", async () => {
			const user = userEvent.setup();
			const { onCancel } = renderDialog();

			await user.click(screen.getByRole("button", { name: "Cancel" }));

			expect(onCancel).toHaveBeenCalled();
		});

		it("disables Save button while loading", () => {
			renderDialog({ loading: true });
			expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
		});

		it("disables Cancel button while loading", () => {
			renderDialog({ loading: true });
			expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
		});

		it("does not render dialog content when open is false", () => {
			renderDialog({ open: false });
			expect(screen.queryByText(DIALOG_TITLE)).not.toBeInTheDocument();
		});
	});
});
