/**
 * Tests for the chat panel React context provider.
 *
 * REQ-012 §4.2: Chat panel open/closed state is global React Context.
 */

import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChatPanelProvider, useChatPanel } from "./chat-panel-provider";

// ---------------------------------------------------------------------------
// Test constants
// ---------------------------------------------------------------------------

const PANEL_STATE_TEST_ID = "panel-state";
const TOGGLE_BUTTON_TEST_ID = "toggle-btn";
const OPEN_BUTTON_TEST_ID = "open-btn";
const CLOSE_BUTTON_TEST_ID = "close-btn";
const CHILD_TEST_ID = "child";

// ---------------------------------------------------------------------------
// Test consumer
// ---------------------------------------------------------------------------

function TestConsumer() {
	const { isOpen, toggle, open, close } = useChatPanel();
	return (
		<div>
			<span data-testid={PANEL_STATE_TEST_ID}>{String(isOpen)}</span>
			<button data-testid={TOGGLE_BUTTON_TEST_ID} onClick={toggle}>
				Toggle
			</button>
			<button data-testid={OPEN_BUTTON_TEST_ID} onClick={open}>
				Open
			</button>
			<button data-testid={CLOSE_BUTTON_TEST_ID} onClick={close}>
				Close
			</button>
		</div>
	);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ChatPanelProvider", () => {
	it("renders children", () => {
		render(
			<ChatPanelProvider>
				<div data-testid={CHILD_TEST_ID}>Hello</div>
			</ChatPanelProvider>,
		);

		expect(screen.getByTestId(CHILD_TEST_ID)).toHaveTextContent("Hello");
	});

	it("provides initial state as closed", () => {
		render(
			<ChatPanelProvider>
				<TestConsumer />
			</ChatPanelProvider>,
		);

		expect(screen.getByTestId(PANEL_STATE_TEST_ID)).toHaveTextContent("false");
	});

	it("toggle opens panel when closed", () => {
		render(
			<ChatPanelProvider>
				<TestConsumer />
			</ChatPanelProvider>,
		);

		act(() => {
			screen.getByTestId(TOGGLE_BUTTON_TEST_ID).click();
		});

		expect(screen.getByTestId(PANEL_STATE_TEST_ID)).toHaveTextContent("true");
	});

	it("toggle closes panel when open", () => {
		render(
			<ChatPanelProvider>
				<TestConsumer />
			</ChatPanelProvider>,
		);

		act(() => {
			screen.getByTestId(TOGGLE_BUTTON_TEST_ID).click();
		});
		expect(screen.getByTestId(PANEL_STATE_TEST_ID)).toHaveTextContent("true");

		act(() => {
			screen.getByTestId(TOGGLE_BUTTON_TEST_ID).click();
		});
		expect(screen.getByTestId(PANEL_STATE_TEST_ID)).toHaveTextContent("false");
	});

	it("open sets panel to open", () => {
		render(
			<ChatPanelProvider>
				<TestConsumer />
			</ChatPanelProvider>,
		);

		act(() => {
			screen.getByTestId(OPEN_BUTTON_TEST_ID).click();
		});

		expect(screen.getByTestId(PANEL_STATE_TEST_ID)).toHaveTextContent("true");
	});

	it("close sets panel to closed from open", () => {
		render(
			<ChatPanelProvider>
				<TestConsumer />
			</ChatPanelProvider>,
		);

		act(() => {
			screen.getByTestId(OPEN_BUTTON_TEST_ID).click();
		});
		expect(screen.getByTestId(PANEL_STATE_TEST_ID)).toHaveTextContent("true");

		act(() => {
			screen.getByTestId(CLOSE_BUTTON_TEST_ID).click();
		});
		expect(screen.getByTestId(PANEL_STATE_TEST_ID)).toHaveTextContent("false");
	});

	it("open is idempotent when already open", () => {
		render(
			<ChatPanelProvider>
				<TestConsumer />
			</ChatPanelProvider>,
		);

		act(() => {
			screen.getByTestId(OPEN_BUTTON_TEST_ID).click();
		});
		act(() => {
			screen.getByTestId(OPEN_BUTTON_TEST_ID).click();
		});

		expect(screen.getByTestId(PANEL_STATE_TEST_ID)).toHaveTextContent("true");
	});

	it("close is idempotent when already closed", () => {
		render(
			<ChatPanelProvider>
				<TestConsumer />
			</ChatPanelProvider>,
		);

		act(() => {
			screen.getByTestId(CLOSE_BUTTON_TEST_ID).click();
		});

		expect(screen.getByTestId(PANEL_STATE_TEST_ID)).toHaveTextContent("false");
	});
});

describe("useChatPanel", () => {
	it("throws when used outside ChatPanelProvider", () => {
		const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

		expect(() => render(<TestConsumer />)).toThrow(
			"useChatPanel must be used within a ChatPanelProvider",
		);

		consoleSpy.mockRestore();
	});
});
