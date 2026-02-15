/**
 * Tests for the RejectionDetailsDialog component (§10.6).
 *
 * REQ-012 §11.6: Rejection details capture form with pre-populated stage.
 * Modal dialog triggered when user transitions to Rejected status.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { RejectionDetails } from "@/types/application";
import { RejectionDetailsDialog } from "./rejection-details-dialog";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DIALOG_TITLE = "Rejection Details";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderDialog(
	props?: Partial<{
		open: boolean;
		onConfirm: (details: RejectionDetails) => void;
		onCancel: () => void;
		loading: boolean;
		initialData: RejectionDetails | null;
		initialStage: string | null;
	}>,
) {
	const defaultProps = {
		open: true,
		onConfirm: vi.fn(),
		onCancel: vi.fn(),
		loading: false,
		initialData: null,
		initialStage: null,
		...props,
	};
	return {
		...render(<RejectionDetailsDialog {...defaultProps} />),
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

describe("RejectionDetailsDialog", () => {
	// -----------------------------------------------------------------------
	// Rendering
	// -----------------------------------------------------------------------

	describe("rendering", () => {
		it("renders dialog title", () => {
			renderDialog();
			expect(screen.getByText(DIALOG_TITLE)).toBeInTheDocument();
		});

		it("renders stage select", () => {
			renderDialog();
			expect(screen.getByTestId("rejection-stage-select")).toBeInTheDocument();
		});

		it("renders reason input", () => {
			renderDialog();
			expect(screen.getByLabelText("Reason")).toBeInTheDocument();
		});

		it("renders feedback textarea", () => {
			renderDialog();
			expect(screen.getByLabelText("Feedback")).toBeInTheDocument();
		});

		it("renders when datetime input", () => {
			renderDialog();
			expect(screen.getByLabelText("When")).toBeInTheDocument();
		});

		it("shows all interview stages in stage select", async () => {
			const user = userEvent.setup();
			renderDialog();

			const trigger = screen.getByTestId("rejection-stage-select");
			await user.click(trigger);

			await waitFor(() => {
				expect(
					screen.getByRole("option", { name: "Phone Screen" }),
				).toBeInTheDocument();
				expect(
					screen.getByRole("option", { name: "Onsite" }),
				).toBeInTheDocument();
				expect(
					screen.getByRole("option", { name: "Final Round" }),
				).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Interaction
	// -----------------------------------------------------------------------

	describe("interaction", () => {
		it("calls onConfirm with empty object when submitting empty form", async () => {
			const user = userEvent.setup();
			const { onConfirm } = renderDialog();

			await user.click(screen.getByRole("button", { name: "Save" }));

			expect(onConfirm).toHaveBeenCalledWith({});
		});

		it("calls onConfirm with filled fields", async () => {
			const user = userEvent.setup();
			const { onConfirm } = renderDialog();

			// Fill reason
			await user.type(screen.getByLabelText("Reason"), "Culture fit concerns");
			// Fill feedback
			await user.type(
				screen.getByLabelText("Feedback"),
				"Looking for more senior candidate",
			);
			// Fill when
			await user.type(screen.getByLabelText("When"), "2026-01-15T10:30");

			await user.click(screen.getByRole("button", { name: "Save" }));

			expect(onConfirm).toHaveBeenCalledWith(
				expect.objectContaining({
					reason: "Culture fit concerns",
					feedback: "Looking for more senior candidate",
					rejected_at: "2026-01-15T10:30",
				}),
			);
		});

		it("pre-populates stage from initialStage prop", () => {
			renderDialog({ initialStage: "Onsite" });
			expect(screen.getByText("Onsite")).toBeInTheDocument();
		});

		it("pre-populates all fields from initialData prop", () => {
			const initialData: RejectionDetails = {
				stage: "Final Round",
				reason: "Over-qualified",
				feedback: "Great candidate but too senior",
				rejected_at: "2026-02-10T14:00",
			};
			renderDialog({ initialData });

			expect(screen.getByText("Final Round")).toBeInTheDocument();
			expect(screen.getByLabelText("Reason")).toHaveValue("Over-qualified");
			expect(screen.getByLabelText("Feedback")).toHaveValue(
				"Great candidate but too senior",
			);
			expect(screen.getByLabelText("When")).toHaveValue("2026-02-10T14:00");
		});

		it("prefers initialData over initialStage when both provided", () => {
			renderDialog({
				initialData: { stage: "Final Round", reason: "Budget cut" },
				initialStage: "Phone Screen",
			});
			expect(screen.getByText("Final Round")).toBeInTheDocument();
			expect(screen.getByLabelText("Reason")).toHaveValue("Budget cut");
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

		it("resets form when dialog reopens", async () => {
			const user = userEvent.setup();
			const { rerender, onConfirm } = renderDialog();

			// Fill reason
			await user.type(screen.getByLabelText("Reason"), "Some reason");

			// Close and reopen
			rerender(
				<RejectionDetailsDialog
					open={false}
					onConfirm={onConfirm}
					onCancel={vi.fn()}
				/>,
			);
			rerender(
				<RejectionDetailsDialog
					open={true}
					onConfirm={onConfirm}
					onCancel={vi.fn()}
				/>,
			);

			// Reason should be cleared
			expect(screen.getByLabelText("Reason")).toHaveValue("");
		});
	});
});
