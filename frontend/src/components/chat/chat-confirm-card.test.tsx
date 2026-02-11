/**
 * Tests for the destructive confirmation card displayed inline in chat.
 *
 * REQ-012 §5.6: Destructive confirmations render as a distinct card
 * with explicit "Proceed" / "Cancel" buttons.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";

import type { ConfirmCardData } from "@/types/chat";

import { ChatConfirmCard } from "./chat-confirm-card";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const DESTRUCTIVE_CONFIRM: ConfirmCardData = {
	message: "Are you sure you want to dismiss this job posting?",
	isDestructive: true,
};

const NON_DESTRUCTIVE_CONFIRM: ConfirmCardData = {
	message: "Would you like to save this resume as your default?",
	isDestructive: false,
};

const CUSTOM_LABELS: ConfirmCardData = {
	message: "Delete all application history?",
	proceedLabel: "Yes, delete",
	cancelLabel: "Keep it",
	isDestructive: true,
};

// ---------------------------------------------------------------------------
// Selectors
// ---------------------------------------------------------------------------

const CARD_SELECTOR = '[data-slot="chat-confirm-card"]';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderCard(
	props: Partial<ComponentProps<typeof ChatConfirmCard>> = {},
) {
	return render(<ChatConfirmCard data={DESTRUCTIVE_CONFIRM} {...props} />);
}

// ---------------------------------------------------------------------------
// Content display
// ---------------------------------------------------------------------------

describe("ChatConfirmCard", () => {
	describe("content display", () => {
		it("renders the confirmation message", () => {
			renderCard();

			expect(
				screen.getByText("Are you sure you want to dismiss this job posting?"),
			).toBeInTheDocument();
		});

		it("renders default Proceed button label", () => {
			renderCard();

			expect(
				screen.getByRole("button", { name: "Proceed" }),
			).toBeInTheDocument();
		});

		it("renders default Cancel button label", () => {
			renderCard();

			expect(
				screen.getByRole("button", { name: "Cancel" }),
			).toBeInTheDocument();
		});

		it("renders custom proceed label", () => {
			renderCard({ data: CUSTOM_LABELS });

			expect(
				screen.getByRole("button", { name: "Yes, delete" }),
			).toBeInTheDocument();
		});

		it("renders custom cancel label", () => {
			renderCard({ data: CUSTOM_LABELS });

			expect(
				screen.getByRole("button", { name: "Keep it" }),
			).toBeInTheDocument();
		});

		it("renders non-destructive message", () => {
			renderCard({ data: NON_DESTRUCTIVE_CONFIRM });

			expect(
				screen.getByText("Would you like to save this resume as your default?"),
			).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Click interactions
	// -----------------------------------------------------------------------

	describe("click interactions", () => {
		it("calls onProceed when Proceed is clicked", async () => {
			const user = userEvent.setup();
			const onProceed = vi.fn();
			renderCard({ onProceed });

			await user.click(screen.getByRole("button", { name: "Proceed" }));

			expect(onProceed).toHaveBeenCalledOnce();
		});

		it("calls onCancel when Cancel is clicked", async () => {
			const user = userEvent.setup();
			const onCancel = vi.fn();
			renderCard({ onCancel });

			await user.click(screen.getByRole("button", { name: "Cancel" }));

			expect(onCancel).toHaveBeenCalledOnce();
		});

		it("does not throw when callbacks are not provided", async () => {
			const user = userEvent.setup();
			renderCard();

			await expect(
				user.click(screen.getByRole("button", { name: "Proceed" })),
			).resolves.not.toThrow();
			await expect(
				user.click(screen.getByRole("button", { name: "Cancel" })),
			).resolves.not.toThrow();
		});
	});

	// -----------------------------------------------------------------------
	// Destructive variant styling
	// -----------------------------------------------------------------------

	describe("destructive variant", () => {
		it("marks card as destructive via data attribute", () => {
			const { container } = renderCard();

			const card = container.querySelector(CARD_SELECTOR);
			expect(card).toHaveAttribute("data-destructive", "true");
		});

		it("marks card as non-destructive via data attribute", () => {
			const { container } = renderCard({ data: NON_DESTRUCTIVE_CONFIRM });

			const card = container.querySelector(CARD_SELECTOR);
			expect(card).toHaveAttribute("data-destructive", "false");
		});

		it("applies destructive styling to proceed button", () => {
			renderCard();

			const proceedBtn = screen.getByRole("button", { name: "Proceed" });
			expect(proceedBtn).toHaveClass("bg-destructive");
		});

		it("does not apply destructive styling for non-destructive variant", () => {
			renderCard({ data: NON_DESTRUCTIVE_CONFIRM });

			const proceedBtn = screen.getByRole("button", { name: "Proceed" });
			expect(proceedBtn).not.toHaveClass("bg-destructive");
			expect(proceedBtn).toHaveClass("bg-primary");
		});
	});

	// -----------------------------------------------------------------------
	// Structure & styling
	// -----------------------------------------------------------------------

	describe("structure", () => {
		it("has data-slot attribute", () => {
			const { container } = renderCard();

			expect(container.querySelector(CARD_SELECTOR)).toBeInTheDocument();
		});

		it("renders with card styling", () => {
			const { container } = renderCard();

			const card = container.querySelector(CARD_SELECTOR);
			expect(card).toHaveClass("rounded-lg");
			expect(card).toHaveClass("border");
		});

		it("merges custom className", () => {
			const { container } = renderCard({ className: "mt-2" });

			const card = container.querySelector(CARD_SELECTOR);
			expect(card).toHaveClass("mt-2");
		});

		it("has correct DOM order: message → actions", () => {
			const { container } = renderCard();

			const card = container.querySelector(CARD_SELECTOR);
			const children = Array.from(card?.children ?? []);
			const slots = children.map(
				(el) => el.getAttribute("data-slot") ?? el.tagName,
			);

			const messageIdx = slots.indexOf("confirm-message");
			const actionsIdx = slots.indexOf("confirm-actions");

			expect(messageIdx).toBeLessThan(actionsIdx);
		});

		it("has destructive border styling", () => {
			const { container } = renderCard();

			const card = container.querySelector(CARD_SELECTOR);
			expect(card).toHaveClass("border-destructive/50");
		});

		it("does not have destructive border for non-destructive variant", () => {
			const { container } = renderCard({ data: NON_DESTRUCTIVE_CONFIRM });

			const card = container.querySelector(CARD_SELECTOR);
			expect(card).not.toHaveClass("border-destructive/50");
		});
	});

	// -----------------------------------------------------------------------
	// Accessibility
	// -----------------------------------------------------------------------

	describe("accessibility", () => {
		it("has role and aria-label on the card", () => {
			const { container } = renderCard();

			const card = container.querySelector(CARD_SELECTOR);
			expect(card).toHaveAttribute("role", "group");
			expect(card).toHaveAttribute(
				"aria-label",
				expect.stringContaining("Confirmation"),
			);
		});

		it("proceed button has accessible name", () => {
			renderCard();

			expect(
				screen.getByRole("button", { name: "Proceed" }),
			).toBeInTheDocument();
		});

		it("cancel button has accessible name", () => {
			renderCard();

			expect(
				screen.getByRole("button", { name: "Cancel" }),
			).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Security
	// -----------------------------------------------------------------------

	describe("security", () => {
		it("renders HTML-like message as plain text", () => {
			const xssConfirm: ConfirmCardData = {
				message: '<script>alert("xss")</script>',
				isDestructive: true,
			};
			renderCard({ data: xssConfirm });

			expect(
				screen.getByText('<script>alert("xss")</script>'),
			).toBeInTheDocument();
		});

		it("does not render injected HTML elements", () => {
			const xssConfirm: ConfirmCardData = {
				message: "<img src=x onerror=alert(1)>",
				isDestructive: true,
			};
			const { container } = renderCard({ data: xssConfirm });

			expect(container.querySelector("img")).not.toBeInTheDocument();
		});
	});
});
