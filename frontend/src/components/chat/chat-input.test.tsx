/**
 * Tests for the chat input component.
 *
 * REQ-012 §5.7: Textarea with send button, Enter/Shift+Enter
 * behavior, disabled during streaming, contextual placeholder.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";

import { ChatInput } from "./chat-input";

// ---------------------------------------------------------------------------
// Selectors
// ---------------------------------------------------------------------------

const INPUT_SELECTOR = '[data-slot="chat-input"]';
const TEXTAREA_SELECTOR = '[data-slot="chat-textarea"]';
const SEND_BUTTON_SELECTOR = '[data-slot="chat-send-button"]';
const CHAR_COUNTER_SELECTOR = '[data-slot="char-counter"]';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderInput(props: Partial<ComponentProps<typeof ChatInput>> = {}) {
	return render(<ChatInput onSend={vi.fn()} {...props} />);
}

// ---------------------------------------------------------------------------
// Structure
// ---------------------------------------------------------------------------

describe("ChatInput", () => {
	describe("structure", () => {
		it("renders the chat input wrapper", () => {
			const { container } = renderInput();

			expect(container.querySelector(INPUT_SELECTOR)).toBeInTheDocument();
		});

		it("renders a textarea", () => {
			renderInput();

			expect(
				screen.getByRole("textbox", { name: /message/i }),
			).toBeInTheDocument();
		});

		it("renders a send button", () => {
			renderInput();

			expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();
		});

		it("has data-slot on textarea", () => {
			const { container } = renderInput();

			expect(container.querySelector(TEXTAREA_SELECTOR)).toBeInTheDocument();
		});

		it("has data-slot on send button", () => {
			const { container } = renderInput();

			expect(container.querySelector(SEND_BUTTON_SELECTOR)).toBeInTheDocument();
		});

		it("merges custom className", () => {
			const { container } = renderInput({ className: "mt-4" });

			const wrapper = container.querySelector(INPUT_SELECTOR);
			expect(wrapper).toHaveClass("mt-4");
		});
	});

	// -----------------------------------------------------------------------
	// Placeholder
	// -----------------------------------------------------------------------

	describe("placeholder", () => {
		it("shows default placeholder text", () => {
			renderInput();

			expect(
				screen.getByPlaceholderText("Ask Scout anything..."),
			).toBeInTheDocument();
		});

		it("shows custom placeholder when provided", () => {
			renderInput({ placeholder: "Type your answer..." });

			expect(
				screen.getByPlaceholderText("Type your answer..."),
			).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Sending messages
	// -----------------------------------------------------------------------

	describe("sending messages", () => {
		it("calls onSend with trimmed content when send button clicked", async () => {
			const user = userEvent.setup();
			const onSend = vi.fn();
			renderInput({ onSend });

			await user.type(screen.getByRole("textbox"), "  Hello Scout  ");
			await user.click(screen.getByRole("button", { name: /send/i }));

			expect(onSend).toHaveBeenCalledWith("Hello Scout");
		});

		it("clears the textarea after sending", async () => {
			const user = userEvent.setup();
			const onSend = vi.fn();
			renderInput({ onSend });

			const textarea = screen.getByRole("textbox");
			await user.type(textarea, "Hello");
			await user.click(screen.getByRole("button", { name: /send/i }));

			expect(textarea).toHaveValue("");
		});

		it("does not call onSend for empty input", async () => {
			const user = userEvent.setup();
			const onSend = vi.fn();
			renderInput({ onSend });

			await user.click(screen.getByRole("button", { name: /send/i }));

			expect(onSend).not.toHaveBeenCalled();
		});

		it("does not call onSend for whitespace-only input", async () => {
			const user = userEvent.setup();
			const onSend = vi.fn();
			renderInput({ onSend });

			await user.type(screen.getByRole("textbox"), "   ");
			await user.click(screen.getByRole("button", { name: /send/i }));

			expect(onSend).not.toHaveBeenCalled();
		});

		it("sends on Enter key press", async () => {
			const user = userEvent.setup();
			const onSend = vi.fn();
			renderInput({ onSend });

			await user.type(screen.getByRole("textbox"), "Hello{Enter}");

			expect(onSend).toHaveBeenCalledWith("Hello");
		});

		it("does not send on Shift+Enter (allows newline)", async () => {
			const user = userEvent.setup();
			const onSend = vi.fn();
			renderInput({ onSend });

			await user.type(
				screen.getByRole("textbox"),
				"Line 1{Shift>}{Enter}{/Shift}Line 2",
			);

			expect(onSend).not.toHaveBeenCalled();
			expect(screen.getByRole("textbox")).toHaveValue("Line 1\nLine 2");
		});

		it("does not send empty content on Enter", async () => {
			const user = userEvent.setup();
			const onSend = vi.fn();
			renderInput({ onSend });

			await user.type(screen.getByRole("textbox"), "{Enter}");

			expect(onSend).not.toHaveBeenCalled();
		});
	});

	// -----------------------------------------------------------------------
	// Disabled state (streaming)
	// -----------------------------------------------------------------------

	describe("disabled state", () => {
		it("disables textarea when disabled prop is true", () => {
			renderInput({ disabled: true });

			expect(screen.getByRole("textbox")).toBeDisabled();
		});

		it("disables send button when disabled prop is true", () => {
			renderInput({ disabled: true });

			expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
		});

		it("does not disable textarea by default", () => {
			renderInput();

			expect(screen.getByRole("textbox")).not.toBeDisabled();
		});

		it("does not call onSend on render when disabled", () => {
			const onSend = vi.fn();
			renderInput({ onSend, disabled: true });

			expect(onSend).not.toHaveBeenCalled();
		});

		it("marks wrapper with data-disabled true when disabled", () => {
			const { container } = renderInput({ disabled: true });

			const wrapper = container.querySelector(INPUT_SELECTOR);
			expect(wrapper).toHaveAttribute("data-disabled", "true");
		});

		it("marks wrapper with data-disabled false by default", () => {
			const { container } = renderInput();

			const wrapper = container.querySelector(INPUT_SELECTOR);
			expect(wrapper).toHaveAttribute("data-disabled", "false");
		});
	});

	// -----------------------------------------------------------------------
	// Send button state
	// -----------------------------------------------------------------------

	describe("send button state", () => {
		it("disables send button when textarea is empty", () => {
			renderInput();

			expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
		});

		it("enables send button when textarea has content", async () => {
			const user = userEvent.setup();
			renderInput();

			await user.type(screen.getByRole("textbox"), "Hello");

			expect(screen.getByRole("button", { name: /send/i })).not.toBeDisabled();
		});

		it("disables send button when textarea has only whitespace", async () => {
			const user = userEvent.setup();
			renderInput();

			await user.type(screen.getByRole("textbox"), "   ");

			expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
		});
	});

	// -----------------------------------------------------------------------
	// Character limit
	// -----------------------------------------------------------------------

	describe("character limit", () => {
		it("shows character count when maxLength is provided", async () => {
			const user = userEvent.setup();
			renderInput({ maxLength: 500 });

			await user.type(screen.getByRole("textbox"), "Hello");

			expect(screen.getByText("5/500")).toBeInTheDocument();
		});

		it("does not show character count without maxLength", () => {
			renderInput();

			expect(screen.queryByText(/\/\d+/)).not.toBeInTheDocument();
		});

		it("does not show character count at 0 when maxLength is set", () => {
			renderInput({ maxLength: 500 });

			expect(screen.getByText("0/500")).toBeInTheDocument();
		});

		it("does not send content exceeding maxLength", async () => {
			const user = userEvent.setup();
			const onSend = vi.fn();
			renderInput({ onSend, maxLength: 10 });

			await user.type(screen.getByRole("textbox"), "12345678901");
			await user.click(screen.getByRole("button", { name: /send/i }));

			expect(onSend).not.toHaveBeenCalled();
		});

		it("sends content at exactly maxLength", async () => {
			const user = userEvent.setup();
			const onSend = vi.fn();
			renderInput({ onSend, maxLength: 5 });

			await user.type(screen.getByRole("textbox"), "Hello");
			await user.click(screen.getByRole("button", { name: /send/i }));

			expect(onSend).toHaveBeenCalledWith("Hello");
		});

		it("applies warning styling near limit", async () => {
			const user = userEvent.setup();
			const { container } = renderInput({ maxLength: 10 });

			await user.type(screen.getByRole("textbox"), "123456789");

			const counter = container.querySelector(CHAR_COUNTER_SELECTOR);
			expect(counter).toHaveAttribute("data-near-limit", "true");
		});
	});

	// -----------------------------------------------------------------------
	// Accessibility
	// -----------------------------------------------------------------------

	describe("accessibility", () => {
		it("textarea has aria-label", () => {
			renderInput();

			expect(
				screen.getByRole("textbox", { name: /message/i }),
			).toBeInTheDocument();
		});

		it("send button has aria-label", () => {
			renderInput();

			expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();
		});

		it("form has role and aria-label", () => {
			const { container } = renderInput();

			const form = container.querySelector("form");
			expect(form).toHaveAttribute(
				"aria-label",
				expect.stringContaining("message"),
			);
		});
	});

	// -----------------------------------------------------------------------
	// Security
	// -----------------------------------------------------------------------

	describe("security", () => {
		it("sends content as plain text (no HTML interpretation)", async () => {
			const user = userEvent.setup();
			const onSend = vi.fn();
			renderInput({ onSend });

			const xss = '<script>alert("xss")</script>';
			await user.type(screen.getByRole("textbox"), xss);
			await user.click(screen.getByRole("button", { name: /send/i }));

			expect(onSend).toHaveBeenCalledWith(xss);
		});
	});
});
