/**
 * Tests for DataTableColumnHeader component.
 *
 * REQ-012 §13.3: Column sorting (click header, toggle asc/desc).
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Column } from "@tanstack/react-table";
import { describe, expect, it, vi } from "vitest";

import { DataTableColumnHeader } from "./data-table-column-header";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TITLE = "Name";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

interface MockColumnOpts {
	isSorted?: false | "asc" | "desc";
	canSort?: boolean;
}

function createMockColumn({
	isSorted = false,
	canSort = true,
}: MockColumnOpts = {}) {
	return {
		getIsSorted: vi.fn().mockReturnValue(isSorted),
		getCanSort: vi.fn().mockReturnValue(canSort),
		toggleSorting: vi.fn(),
	} as unknown as Column<unknown, unknown>;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DataTableColumnHeader", () => {
	it("renders title text", () => {
		const column = createMockColumn();
		render(<DataTableColumnHeader column={column} title={TITLE} />);
		expect(screen.getByText(TITLE)).toBeInTheDocument();
	});

	it("renders as a button when column is sortable", () => {
		const column = createMockColumn({ canSort: true });
		render(<DataTableColumnHeader column={column} title={TITLE} />);
		expect(screen.getByRole("button")).toBeInTheDocument();
	});

	it("renders as plain text when column is not sortable", () => {
		const column = createMockColumn({ canSort: false });
		render(<DataTableColumnHeader column={column} title={TITLE} />);
		expect(screen.queryByRole("button")).not.toBeInTheDocument();
		expect(screen.getByText(TITLE)).toBeInTheDocument();
	});

	it("shows unsorted indicator when sortable but not sorted", () => {
		const column = createMockColumn({ isSorted: false });
		render(<DataTableColumnHeader column={column} title={TITLE} />);
		expect(screen.getByTestId("sort-unsorted")).toBeInTheDocument();
		expect(screen.queryByTestId("sort-asc")).not.toBeInTheDocument();
		expect(screen.queryByTestId("sort-desc")).not.toBeInTheDocument();
	});

	it("shows ascending indicator when sorted asc", () => {
		const column = createMockColumn({ isSorted: "asc" });
		render(<DataTableColumnHeader column={column} title={TITLE} />);
		expect(screen.getByTestId("sort-asc")).toBeInTheDocument();
		expect(screen.queryByTestId("sort-unsorted")).not.toBeInTheDocument();
	});

	it("shows descending indicator when sorted desc", () => {
		const column = createMockColumn({ isSorted: "desc" });
		render(<DataTableColumnHeader column={column} title={TITLE} />);
		expect(screen.getByTestId("sort-desc")).toBeInTheDocument();
		expect(screen.queryByTestId("sort-unsorted")).not.toBeInTheDocument();
	});

	it("calls toggleSorting on click", async () => {
		const user = userEvent.setup();
		const column = createMockColumn();
		render(<DataTableColumnHeader column={column} title={TITLE} />);

		await user.click(screen.getByRole("button"));
		expect(column.toggleSorting).toHaveBeenCalledOnce();
	});

	it("applies custom className", () => {
		const column = createMockColumn();
		const { container } = render(
			<DataTableColumnHeader
				column={column}
				title={TITLE}
				className="my-class"
			/>,
		);
		expect(container.firstChild).toHaveClass("my-class");
	});
});
