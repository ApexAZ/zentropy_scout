/**
 * Tests for the clickable option list card displayed inline in chat.
 *
 * REQ-012 §5.6: Ambiguity resolution UI — numbered options as
 * clickable list items. Clicking sends the selection as a user message.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";

import type { OptionListData } from "@/types/chat";

import { ChatOptionList } from "./chat-option-list";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const FULL_OPTIONS: OptionListData = {
	options: [
		{ label: "Scrum Master at Acme Corp", value: "1" },
		{ label: "Product Owner at TechCo", value: "2" },
		{ label: "Agile Coach at StartupX", value: "3" },
	],
};

const SINGLE_OPTION: OptionListData = {
	options: [{ label: "Senior Developer at BigCo", value: "1" }],
};

// ---------------------------------------------------------------------------
// Selectors
// ---------------------------------------------------------------------------

const CARD_SELECTOR = '[data-slot="chat-option-list"]';
const OPTION_SELECTOR = '[data-slot="option-item"]';
const HINT_SELECTOR = '[data-slot="option-hint"]';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderCard(
	props: Partial<ComponentProps<typeof ChatOptionList>> = {},
) {
	return render(<ChatOptionList data={FULL_OPTIONS} {...props} />);
}

// ---------------------------------------------------------------------------
// Content display
// ---------------------------------------------------------------------------

describe("ChatOptionList", () => {
	describe("content display", () => {
		it("renders all option labels with numbers", () => {
			renderCard();

			expect(
				screen.getByText(/1\.\s*Scrum Master at Acme Corp/),
			).toBeInTheDocument();
			expect(
				screen.getByText(/2\.\s*Product Owner at TechCo/),
			).toBeInTheDocument();
			expect(
				screen.getByText(/3\.\s*Agile Coach at StartupX/),
			).toBeInTheDocument();
		});

		it("renders a single option", () => {
			renderCard({ data: SINGLE_OPTION });

			expect(
				screen.getByText(/1\.\s*Senior Developer at BigCo/),
			).toBeInTheDocument();
		});

		it("renders the hint text", () => {
			const { container } = renderCard();

			const hint = container.querySelector(HINT_SELECTOR);
			expect(hint?.textContent).toContain("Or type to describe");
		});

		it("renders all option items as buttons", () => {
			renderCard();

			const buttons = screen.getAllByRole("button");
			expect(buttons).toHaveLength(3);
		});
	});

	// -----------------------------------------------------------------------
	// Click interactions
	// -----------------------------------------------------------------------

	describe("click interactions", () => {
		it("calls onSelect with option value when clicked", async () => {
			const user = userEvent.setup();
			const onSelect = vi.fn();
			renderCard({ onSelect });

			await user.click(screen.getByText(/1\.\s*Scrum Master/));

			expect(onSelect).toHaveBeenCalledWith("1");
		});

		it("calls onSelect with correct value for second option", async () => {
			const user = userEvent.setup();
			const onSelect = vi.fn();
			renderCard({ onSelect });

			await user.click(screen.getByText(/2\.\s*Product Owner/));

			expect(onSelect).toHaveBeenCalledWith("2");
		});

		it("calls onSelect with correct value for third option", async () => {
			const user = userEvent.setup();
			const onSelect = vi.fn();
			renderCard({ onSelect });

			await user.click(screen.getByText(/3\.\s*Agile Coach/));

			expect(onSelect).toHaveBeenCalledWith("3");
		});

		it("does not throw when onSelect is not provided", async () => {
			const user = userEvent.setup();
			renderCard();

			await expect(
				user.click(screen.getByText(/1\.\s*Scrum Master/)),
			).resolves.not.toThrow();
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

		it("renders correct number of option items", () => {
			const { container } = renderCard();

			const items = container.querySelectorAll(OPTION_SELECTOR);
			expect(items).toHaveLength(3);
		});

		it("has option buttons with hover styling classes", () => {
			renderCard();

			const firstButton = screen.getAllByRole("button")[0];
			expect(firstButton).toHaveClass("cursor-pointer");
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
				expect.stringContaining("option"),
			);
		});

		it("uses list semantics", () => {
			renderCard();

			const list = screen.getByRole("list");
			expect(list).toBeInTheDocument();
		});

		it("each option is a list item containing a button", () => {
			renderCard();

			const items = screen.getAllByRole("listitem");
			expect(items).toHaveLength(3);

			const buttons = screen.getAllByRole("button");
			expect(buttons).toHaveLength(3);
		});

		it("option buttons have accessible names", () => {
			renderCard();

			expect(
				screen.getByRole("button", { name: /Scrum Master at Acme Corp/ }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: /Product Owner at TechCo/ }),
			).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Security
	// -----------------------------------------------------------------------

	describe("security", () => {
		it("renders HTML-like label as plain text", () => {
			const xssOptions: OptionListData = {
				options: [
					{
						label: '<script>alert("xss")</script>',
						value: "1",
					},
				],
			};
			renderCard({ data: xssOptions });

			expect(
				screen.getByText(/<script>alert\("xss"\)<\/script>/),
			).toBeInTheDocument();
		});

		it("does not render injected HTML elements", () => {
			const xssOptions: OptionListData = {
				options: [
					{
						label: "<img src=x onerror=alert(1)>",
						value: "1",
					},
				],
			};
			const { container } = renderCard({ data: xssOptions });

			expect(container.querySelector("img")).not.toBeInTheDocument();
		});
	});
});
