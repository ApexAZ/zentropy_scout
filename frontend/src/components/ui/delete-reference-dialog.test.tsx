/**
 * Tests for the DeleteReferenceDialog component (§6.12).
 *
 * REQ-012 §7.5 / REQ-001 §7b: Dialog variants for checking, mutable-refs,
 * review-each, immutable-block, and deleting states.
 */

import type { ComponentProps } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ReferencingEntity } from "@/types/deletion";

import { DeleteReferenceDialog } from "./delete-reference-dialog";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ITEM_LABEL = "Python";

const MUTABLE_REF: ReferencingEntity = {
	id: "ref-001",
	name: "My Resume",
	type: "base_resume",
	immutable: false,
};

const MUTABLE_REF_2: ReferencingEntity = {
	id: "ref-002",
	name: "Cover Letter Draft",
	type: "cover_letter",
	immutable: false,
};

const IMMUTABLE_REF: ReferencingEntity = {
	id: "ref-003",
	name: "Submitted Resume",
	type: "base_resume",
	immutable: true,
	application_id: "app-001",
	company_name: "Acme Corp",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderDialog(
	props: Partial<ComponentProps<typeof DeleteReferenceDialog>> = {},
) {
	const defaultProps: ComponentProps<typeof DeleteReferenceDialog> = {
		open: true,
		onCancel: vi.fn(),
		flowState: "checking",
		deleteError: null,
		itemLabel: ITEM_LABEL,
		references: [],
		hasImmutableReferences: false,
		reviewSelections: {},
		onRemoveAllAndDelete: vi.fn(),
		onExpandReviewEach: vi.fn(),
		onToggleReviewSelection: vi.fn(),
		onConfirmReviewAndDelete: vi.fn(),
		...props,
	};

	return render(<DeleteReferenceDialog {...defaultProps} />);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DeleteReferenceDialog", () => {
	// -----------------------------------------------------------------------
	// Not rendered when closed
	// -----------------------------------------------------------------------

	it("does not render content when open is false", () => {
		renderDialog({ open: false });

		expect(
			screen.queryByTestId("delete-reference-dialog"),
		).not.toBeInTheDocument();
	});

	// -----------------------------------------------------------------------
	// Checking state
	// -----------------------------------------------------------------------

	describe("checking state", () => {
		it("shows checking title and spinner", () => {
			renderDialog({ flowState: "checking" });

			expect(screen.getByText("Checking references...")).toBeInTheDocument();
			expect(screen.getByTestId("checking-spinner")).toBeInTheDocument();
		});

		it("disables cancel button during checking", () => {
			renderDialog({ flowState: "checking" });

			expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
		});
	});

	// -----------------------------------------------------------------------
	// Mutable refs state
	// -----------------------------------------------------------------------

	describe("mutable-refs state", () => {
		const mutableProps = {
			flowState: "mutable-refs" as const,
			references: [MUTABLE_REF, MUTABLE_REF_2],
		};

		it("shows title with document count", () => {
			renderDialog(mutableProps);

			expect(screen.getByText("Used in 2 documents")).toBeInTheDocument();
		});

		it("shows singular title for one reference", () => {
			renderDialog({
				...mutableProps,
				references: [MUTABLE_REF],
			});

			expect(screen.getByText("Used in 1 document")).toBeInTheDocument();
		});

		it("renders reference names in a list", () => {
			renderDialog(mutableProps);

			const list = screen.getByTestId("reference-list");
			expect(within(list).getByText("My Resume")).toBeInTheDocument();
			expect(within(list).getByText("Cover Letter Draft")).toBeInTheDocument();
		});

		it("renders three action buttons", () => {
			renderDialog(mutableProps);

			expect(screen.getByTestId("remove-all-delete-btn")).toBeInTheDocument();
			expect(screen.getByTestId("review-each-btn")).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: "Cancel" }),
			).toBeInTheDocument();
		});

		it("calls onRemoveAllAndDelete when button clicked", async () => {
			const user = userEvent.setup();
			const onRemoveAllAndDelete = vi.fn();

			renderDialog({ ...mutableProps, onRemoveAllAndDelete });

			await user.click(screen.getByTestId("remove-all-delete-btn"));

			expect(onRemoveAllAndDelete).toHaveBeenCalledOnce();
		});

		it("calls onExpandReviewEach when button clicked", async () => {
			const user = userEvent.setup();
			const onExpandReviewEach = vi.fn();

			renderDialog({ ...mutableProps, onExpandReviewEach });

			await user.click(screen.getByTestId("review-each-btn"));

			expect(onExpandReviewEach).toHaveBeenCalledOnce();
		});

		it("calls onCancel when cancel clicked", async () => {
			const user = userEvent.setup();
			const onCancel = vi.fn();

			renderDialog({ ...mutableProps, onCancel });

			await user.click(screen.getByRole("button", { name: "Cancel" }));

			expect(onCancel).toHaveBeenCalledOnce();
		});
	});

	// -----------------------------------------------------------------------
	// Review each state
	// -----------------------------------------------------------------------

	describe("review-each state", () => {
		const reviewProps = {
			flowState: "review-each" as const,
			references: [MUTABLE_REF, MUTABLE_REF_2],
			reviewSelections: {
				[MUTABLE_REF.id]: true,
				[MUTABLE_REF_2.id]: true,
			},
		};

		it("shows review title", () => {
			renderDialog(reviewProps);

			expect(screen.getByText("Review references")).toBeInTheDocument();
		});

		it("renders checkboxes for each reference", () => {
			renderDialog(reviewProps);

			expect(
				screen.getByTestId(`review-checkbox-${MUTABLE_REF.id}`),
			).toBeInTheDocument();
			expect(
				screen.getByTestId(`review-checkbox-${MUTABLE_REF_2.id}`),
			).toBeInTheDocument();
		});

		it("shows checkboxes as checked by default", () => {
			renderDialog(reviewProps);

			const checkbox1 = screen.getByTestId(`review-checkbox-${MUTABLE_REF.id}`);
			expect(checkbox1).toHaveAttribute("data-state", "checked");
		});

		it("calls onToggleReviewSelection when checkbox clicked", async () => {
			const user = userEvent.setup();
			const onToggleReviewSelection = vi.fn();

			renderDialog({ ...reviewProps, onToggleReviewSelection });

			await user.click(screen.getByTestId(`review-checkbox-${MUTABLE_REF.id}`));

			expect(onToggleReviewSelection).toHaveBeenCalledWith(MUTABLE_REF.id);
		});

		it("calls onConfirmReviewAndDelete when confirm clicked", async () => {
			const user = userEvent.setup();
			const onConfirmReviewAndDelete = vi.fn();

			renderDialog({ ...reviewProps, onConfirmReviewAndDelete });

			await user.click(screen.getByTestId("confirm-review-delete-btn"));

			expect(onConfirmReviewAndDelete).toHaveBeenCalledOnce();
		});
	});

	// -----------------------------------------------------------------------
	// Immutable block state
	// -----------------------------------------------------------------------

	describe("immutable-block state", () => {
		const immutableProps = {
			flowState: "immutable-block" as const,
			references: [IMMUTABLE_REF],
			hasImmutableReferences: true,
		};

		it("shows cannot delete title with warning icon", () => {
			renderDialog(immutableProps);

			expect(screen.getByText("Cannot delete")).toBeInTheDocument();
		});

		it("shows company name in description", () => {
			renderDialog(immutableProps);

			expect(
				screen.getByText(/submitted application.*to Acme Corp/i),
			).toBeInTheDocument();
		});

		it("shows Go to Application link", () => {
			renderDialog(immutableProps);

			const link = screen.getByTestId("go-to-application-link");
			expect(link).toHaveAttribute("href", "/applications/app-001");
		});
	});

	// -----------------------------------------------------------------------
	// Deleting state
	// -----------------------------------------------------------------------

	describe("deleting state", () => {
		it("shows deleting title and spinner with disabled cancel", () => {
			renderDialog({ flowState: "deleting" });

			expect(screen.getByText("Deleting...")).toBeInTheDocument();
			expect(screen.getByTestId("deleting-spinner")).toBeInTheDocument();
			expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
		});
	});

	// -----------------------------------------------------------------------
	// Error display
	// -----------------------------------------------------------------------

	describe("error display", () => {
		it("shows error text in mutable-refs state", () => {
			renderDialog({
				flowState: "mutable-refs",
				references: [MUTABLE_REF],
				deleteError: "Failed to save. Please try again.",
			});

			expect(screen.getByTestId("delete-error")).toHaveTextContent(
				"Failed to save. Please try again.",
			);
		});

		it("shows error text in review-each state", () => {
			renderDialog({
				flowState: "review-each",
				references: [MUTABLE_REF],
				reviewSelections: { [MUTABLE_REF.id]: true },
				deleteError: "Failed to save. Please try again.",
			});

			expect(screen.getByTestId("delete-error")).toHaveTextContent(
				"Failed to save. Please try again.",
			);
		});
	});
});
