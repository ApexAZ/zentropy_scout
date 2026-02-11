/**
 * Tests for the ReorderableList component.
 *
 * REQ-012 §7.4: Drag-and-drop reorder for persona collections.
 * REQ-012 §9.2: Resume bullet ordering.
 * REQ-012 §12.2: Job source preferences ordering.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ReorderableList } from "./reorderable-list";

// ---------------------------------------------------------------------------
// Mock useIsMobile to control desktop vs mobile rendering
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
	useIsMobile: vi.fn(() => false),
}));

vi.mock("@/hooks/use-is-mobile", () => ({
	useIsMobile: mocks.useIsMobile,
}));

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TEST_LABEL = "Test list";
const DRAG_HANDLE_LABEL = "Drag to reorder";
const MOVE_UP_LABEL = "Move up";
const MOVE_DOWN_LABEL = "Move down";
const ITEM_SELECTOR = "[data-slot='reorderable-item']";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

interface TestItem {
	id: string;
	name: string;
}

const items: TestItem[] = [
	{ id: "1", name: "First" },
	{ id: "2", name: "Second" },
	{ id: "3", name: "Third" },
];

function defaultRenderItem(item: TestItem, dragHandle: React.ReactNode | null) {
	return (
		<div data-testid={`item-${item.id}`}>
			{dragHandle}
			<span>{item.name}</span>
		</div>
	);
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
	mocks.useIsMobile.mockReturnValue(false);
});

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe("ReorderableList", () => {
	describe("rendering", () => {
		it("renders all items", () => {
			render(
				<ReorderableList
					items={items}
					onReorder={vi.fn()}
					renderItem={defaultRenderItem}
					label={TEST_LABEL}
				/>,
			);

			expect(screen.getByText("First")).toBeInTheDocument();
			expect(screen.getByText("Second")).toBeInTheDocument();
			expect(screen.getByText("Third")).toBeInTheDocument();
		});

		it("renders items in correct order", () => {
			render(
				<ReorderableList
					items={items}
					onReorder={vi.fn()}
					renderItem={defaultRenderItem}
					label={TEST_LABEL}
				/>,
			);

			const listItems = screen.getAllByTestId(/^item-/);
			expect(listItems).toHaveLength(3);
			expect(listItems[0]).toHaveTextContent("First");
			expect(listItems[1]).toHaveTextContent("Second");
			expect(listItems[2]).toHaveTextContent("Third");
		});

		it("has data-slot attribute", () => {
			const { container } = render(
				<ReorderableList
					items={items}
					onReorder={vi.fn()}
					renderItem={defaultRenderItem}
					label={TEST_LABEL}
				/>,
			);

			expect(
				container.querySelector('[data-slot="reorderable-list"]'),
			).toBeInTheDocument();
		});

		it("applies custom className", () => {
			const { container } = render(
				<ReorderableList
					items={items}
					onReorder={vi.fn()}
					renderItem={defaultRenderItem}
					label={TEST_LABEL}
					className="custom-class"
				/>,
			);

			expect(
				container.querySelector('[data-slot="reorderable-list"]'),
			).toHaveClass("custom-class");
		});

		it("has role and aria-label on the list", () => {
			render(
				<ReorderableList
					items={items}
					onReorder={vi.fn()}
					renderItem={defaultRenderItem}
					label="Work history"
				/>,
			);

			const list = screen.getByRole("list", { name: "Work history" });
			expect(list).toBeInTheDocument();
		});
	});

	// ---------------------------------------------------------------------------
	// Desktop drag handle
	// ---------------------------------------------------------------------------

	describe("desktop drag handle", () => {
		it("renders drag handle for each item", () => {
			mocks.useIsMobile.mockReturnValue(false);

			render(
				<ReorderableList
					items={items}
					onReorder={vi.fn()}
					renderItem={defaultRenderItem}
					label={TEST_LABEL}
				/>,
			);

			const handles = screen.getAllByLabelText(DRAG_HANDLE_LABEL);
			expect(handles).toHaveLength(3);
		});

		it("passes non-null dragHandle to renderItem", () => {
			mocks.useIsMobile.mockReturnValue(false);
			const renderItem = vi.fn(
				(item: TestItem, dragHandle: React.ReactNode | null) => (
					<div>
						{dragHandle}
						<span>{item.name}</span>
					</div>
				),
			);

			render(
				<ReorderableList
					items={items}
					onReorder={vi.fn()}
					renderItem={renderItem}
					label={TEST_LABEL}
				/>,
			);

			expect(renderItem).toHaveBeenCalledTimes(3);
			for (const call of renderItem.mock.calls) {
				expect(call[1]).not.toBeNull();
			}
		});
	});

	// ---------------------------------------------------------------------------
	// Mobile arrows
	// ---------------------------------------------------------------------------

	describe("mobile arrows", () => {
		beforeEach(() => {
			mocks.useIsMobile.mockReturnValue(true);
		});

		it("shows arrow buttons and no drag handles on mobile", () => {
			render(
				<ReorderableList
					items={items}
					onReorder={vi.fn()}
					renderItem={defaultRenderItem}
					label={TEST_LABEL}
				/>,
			);

			expect(screen.queryAllByLabelText(DRAG_HANDLE_LABEL)).toHaveLength(0);
			expect(screen.getAllByLabelText(MOVE_UP_LABEL)).toHaveLength(3);
			expect(screen.getAllByLabelText(MOVE_DOWN_LABEL)).toHaveLength(3);
		});

		it("disables up arrow on first item", () => {
			render(
				<ReorderableList
					items={items}
					onReorder={vi.fn()}
					renderItem={defaultRenderItem}
					label={TEST_LABEL}
				/>,
			);

			const firstItem = screen.getByTestId("item-1").closest(ITEM_SELECTOR)!;
			const upButton = within(firstItem as HTMLElement).getByLabelText(
				MOVE_UP_LABEL,
			);
			expect(upButton).toBeDisabled();
		});

		it("disables down arrow on last item", () => {
			render(
				<ReorderableList
					items={items}
					onReorder={vi.fn()}
					renderItem={defaultRenderItem}
					label={TEST_LABEL}
				/>,
			);

			const lastItem = screen.getByTestId("item-3").closest(ITEM_SELECTOR)!;
			const downButton = within(lastItem as HTMLElement).getByLabelText(
				MOVE_DOWN_LABEL,
			);
			expect(downButton).toBeDisabled();
		});

		it("moves item up when up arrow is clicked", async () => {
			const user = userEvent.setup();
			const onReorder = vi.fn();

			render(
				<ReorderableList
					items={items}
					onReorder={onReorder}
					renderItem={defaultRenderItem}
					label={TEST_LABEL}
				/>,
			);

			const secondItem = screen.getByTestId("item-2").closest(ITEM_SELECTOR)!;
			const upButton = within(secondItem as HTMLElement).getByLabelText(
				MOVE_UP_LABEL,
			);
			await user.click(upButton);

			expect(onReorder).toHaveBeenCalledWith([
				{ id: "2", name: "Second" },
				{ id: "1", name: "First" },
				{ id: "3", name: "Third" },
			]);
		});

		it("moves item down when down arrow is clicked", async () => {
			const user = userEvent.setup();
			const onReorder = vi.fn();

			render(
				<ReorderableList
					items={items}
					onReorder={onReorder}
					renderItem={defaultRenderItem}
					label={TEST_LABEL}
				/>,
			);

			const firstItem = screen.getByTestId("item-1").closest(ITEM_SELECTOR)!;
			const downButton = within(firstItem as HTMLElement).getByLabelText(
				MOVE_DOWN_LABEL,
			);
			await user.click(downButton);

			expect(onReorder).toHaveBeenCalledWith([
				{ id: "2", name: "Second" },
				{ id: "1", name: "First" },
				{ id: "3", name: "Third" },
			]);
		});

		it("passes null dragHandle to renderItem on mobile", () => {
			const renderItem = vi.fn(
				(item: TestItem, dragHandle: React.ReactNode | null) => (
					<div>
						{dragHandle}
						<span>{item.name}</span>
					</div>
				),
			);

			render(
				<ReorderableList
					items={items}
					onReorder={vi.fn()}
					renderItem={renderItem}
					label={TEST_LABEL}
				/>,
			);

			for (const call of renderItem.mock.calls) {
				expect(call[1]).toBeNull();
			}
		});
	});

	// ---------------------------------------------------------------------------
	// Edge cases
	// ---------------------------------------------------------------------------

	describe("edge cases", () => {
		it("renders gracefully with empty list", () => {
			const { container } = render(
				<ReorderableList
					items={[]}
					onReorder={vi.fn()}
					renderItem={defaultRenderItem}
					label="Empty list"
				/>,
			);

			expect(
				container.querySelector('[data-slot="reorderable-list"]'),
			).toBeInTheDocument();
			expect(screen.queryAllByTestId(/^item-/)).toHaveLength(0);
		});

		it("disables both arrows on single item", () => {
			mocks.useIsMobile.mockReturnValue(true);
			const singleItem = [{ id: "1", name: "Only" }];

			render(
				<ReorderableList
					items={singleItem}
					onReorder={vi.fn()}
					renderItem={defaultRenderItem}
					label="Single list"
				/>,
			);

			const upButton = screen.getByLabelText(MOVE_UP_LABEL);
			const downButton = screen.getByLabelText(MOVE_DOWN_LABEL);
			expect(upButton).toBeDisabled();
			expect(downButton).toBeDisabled();
		});
	});
});
