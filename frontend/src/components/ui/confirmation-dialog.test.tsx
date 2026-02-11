/**
 * Tests for the ConfirmationDialog component.
 *
 * REQ-012 §7.5: Deletion confirmation dialogs with destructive variant.
 * REQ-012 §11.3: Confirmation dialogs for status transitions.
 */

import type { ComponentProps } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConfirmationDialog } from "./confirmation-dialog";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TEST_TITLE = "Delete item?";
const TEST_DESCRIPTION = "This action cannot be undone.";
const DEFAULT_CONFIRM = "Confirm";
const DEFAULT_CANCEL = "Cancel";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderDialog(
	props: Partial<ComponentProps<typeof ConfirmationDialog>> = {},
) {
	return render(
		<ConfirmationDialog
			open
			onOpenChange={vi.fn()}
			title={TEST_TITLE}
			description={TEST_DESCRIPTION}
			onConfirm={vi.fn()}
			{...props}
		/>,
	);
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe("ConfirmationDialog", () => {
	describe("rendering", () => {
		it("renders title and description when open", () => {
			renderDialog();

			expect(screen.getByText(TEST_TITLE)).toBeInTheDocument();
			expect(screen.getByText(TEST_DESCRIPTION)).toBeInTheDocument();
		});

		it("does not render content when closed", () => {
			renderDialog({ open: false });

			expect(screen.queryByText(TEST_TITLE)).not.toBeInTheDocument();
			expect(screen.queryByText(TEST_DESCRIPTION)).not.toBeInTheDocument();
		});

		it("renders default confirm and cancel button labels", () => {
			renderDialog();

			expect(
				screen.getByRole("button", { name: DEFAULT_CONFIRM }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: DEFAULT_CANCEL }),
			).toBeInTheDocument();
		});

		it("renders custom button labels", () => {
			renderDialog({
				confirmLabel: "Remove from all & delete",
				cancelLabel: "Keep it",
			});

			expect(
				screen.getByRole("button", { name: "Remove from all & delete" }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: "Keep it" }),
			).toBeInTheDocument();
		});

		it("has data-slot attribute", () => {
			renderDialog();

			// AlertDialog renders through a Portal — query document directly
			expect(
				document.querySelector('[data-slot="confirmation-dialog"]'),
			).toBeInTheDocument();
		});

		it("merges custom className onto content", () => {
			renderDialog({ className: "custom-width" });

			const content = document.querySelector(
				'[data-slot="confirmation-dialog"]',
			);
			expect(content).toHaveClass("custom-width");
		});

		it("has alertdialog role", () => {
			renderDialog();

			expect(screen.getByRole("alertdialog")).toBeInTheDocument();
		});
	});

	// ---------------------------------------------------------------------------
	// Interactions
	// ---------------------------------------------------------------------------

	describe("interactions", () => {
		it("calls onConfirm when confirm button is clicked", async () => {
			const user = userEvent.setup();
			const onConfirm = vi.fn();

			renderDialog({ onConfirm });

			await user.click(screen.getByRole("button", { name: DEFAULT_CONFIRM }));

			expect(onConfirm).toHaveBeenCalledOnce();
		});

		it("calls onOpenChange with false when cancel button is clicked", async () => {
			const user = userEvent.setup();
			const onOpenChange = vi.fn();

			renderDialog({ onOpenChange });

			await user.click(screen.getByRole("button", { name: DEFAULT_CANCEL }));

			expect(onOpenChange).toHaveBeenCalledWith(false);
		});
	});

	// ---------------------------------------------------------------------------
	// Variants
	// ---------------------------------------------------------------------------

	describe("variants", () => {
		it("uses default button variant by default", () => {
			renderDialog();

			const confirmButton = screen.getByRole("button", {
				name: DEFAULT_CONFIRM,
			});
			expect(confirmButton).not.toHaveAttribute("data-variant", "destructive");
		});

		it("uses destructive button variant when variant is destructive", () => {
			renderDialog({ variant: "destructive" });

			const confirmButton = screen.getByRole("button", {
				name: DEFAULT_CONFIRM,
			});
			expect(confirmButton).toHaveAttribute("data-variant", "destructive");
		});
	});

	// ---------------------------------------------------------------------------
	// Loading state
	// ---------------------------------------------------------------------------

	describe("loading state", () => {
		it("disables both buttons when loading", () => {
			renderDialog({ loading: true });

			expect(
				screen.getByRole("button", { name: DEFAULT_CONFIRM }),
			).toBeDisabled();
			expect(
				screen.getByRole("button", { name: DEFAULT_CANCEL }),
			).toBeDisabled();
		});

		it("does not call onConfirm when loading", async () => {
			const user = userEvent.setup();
			const onConfirm = vi.fn();

			renderDialog({ onConfirm, loading: true });

			await user.click(screen.getByRole("button", { name: DEFAULT_CONFIRM }));

			expect(onConfirm).not.toHaveBeenCalled();
		});
	});
});
