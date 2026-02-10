/**
 * Tests for DataTablePagination component.
 *
 * REQ-012 §13.3: Page selector with per-page options 20/50/100.
 *
 * Note: Radix Select uses portals, which limits what jsdom can test
 * for the page-size dropdown. We focus on rendering, button state,
 * and navigation callbacks.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Table } from "@tanstack/react-table";
import { describe, expect, it, vi } from "vitest";

import { DataTablePagination } from "./data-table-pagination";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PREVIOUS_LABEL = "Previous";
const NEXT_LABEL = "Next";
const ROWS_PER_PAGE_LABEL = "Rows per page";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

interface MockTableOpts {
	pageIndex?: number;
	pageSize?: number;
	pageCount?: number;
	canPreviousPage?: boolean;
	canNextPage?: boolean;
}

function createMockTable({
	pageIndex = 0,
	pageSize = 20,
	pageCount = 5,
	canPreviousPage = false,
	canNextPage = true,
}: MockTableOpts = {}) {
	return {
		getState: vi.fn().mockReturnValue({
			pagination: { pageIndex, pageSize },
		}),
		getCanPreviousPage: vi.fn().mockReturnValue(canPreviousPage),
		getCanNextPage: vi.fn().mockReturnValue(canNextPage),
		previousPage: vi.fn(),
		nextPage: vi.fn(),
		setPageSize: vi.fn(),
		getPageCount: vi.fn().mockReturnValue(pageCount),
	} as unknown as Table<unknown>;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DataTablePagination", () => {
	// -- Rendering -----------------------------------------------------------

	it("renders page info text", () => {
		const table = createMockTable({ pageIndex: 0, pageCount: 5 });
		render(<DataTablePagination table={table} />);

		expect(screen.getByText("Page 1 of 5")).toBeInTheDocument();
	});

	it("displays correct page number (1-indexed)", () => {
		const table = createMockTable({ pageIndex: 2, pageCount: 10 });
		render(<DataTablePagination table={table} />);

		expect(screen.getByText("Page 3 of 10")).toBeInTheDocument();
	});

	it("renders page size selector with aria-label", () => {
		const table = createMockTable({ pageSize: 20 });
		render(<DataTablePagination table={table} />);

		const trigger = screen.getByRole("combobox", { name: ROWS_PER_PAGE_LABEL });
		expect(trigger).toBeInTheDocument();
	});

	it("wraps controls in a nav landmark", () => {
		const table = createMockTable();
		render(<DataTablePagination table={table} />);

		expect(
			screen.getByRole("navigation", { name: "Table pagination" }),
		).toBeInTheDocument();
	});

	it("renders previous and next buttons", () => {
		const table = createMockTable();
		render(<DataTablePagination table={table} />);

		expect(
			screen.getByRole("button", { name: PREVIOUS_LABEL }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("button", { name: NEXT_LABEL }),
		).toBeInTheDocument();
	});

	// -- Button states -------------------------------------------------------

	it("disables Previous button on first page", () => {
		const table = createMockTable({ canPreviousPage: false });
		render(<DataTablePagination table={table} />);

		expect(screen.getByRole("button", { name: PREVIOUS_LABEL })).toBeDisabled();
	});

	it("disables Next button on last page", () => {
		const table = createMockTable({ canNextPage: false });
		render(<DataTablePagination table={table} />);

		expect(screen.getByRole("button", { name: NEXT_LABEL })).toBeDisabled();
	});

	it("enables Previous button when not on first page", () => {
		const table = createMockTable({ canPreviousPage: true });
		render(<DataTablePagination table={table} />);

		expect(screen.getByRole("button", { name: PREVIOUS_LABEL })).toBeEnabled();
	});

	it("enables Next button when not on last page", () => {
		const table = createMockTable({ canNextPage: true });
		render(<DataTablePagination table={table} />);

		expect(screen.getByRole("button", { name: NEXT_LABEL })).toBeEnabled();
	});

	// -- Navigation callbacks ------------------------------------------------

	it("calls previousPage on Previous click", async () => {
		const user = userEvent.setup();
		const table = createMockTable({ canPreviousPage: true });
		render(<DataTablePagination table={table} />);

		await user.click(screen.getByRole("button", { name: PREVIOUS_LABEL }));
		expect(table.previousPage).toHaveBeenCalledOnce();
	});

	it("calls nextPage on Next click", async () => {
		const user = userEvent.setup();
		const table = createMockTable({ canNextPage: true });
		render(<DataTablePagination table={table} />);

		await user.click(screen.getByRole("button", { name: NEXT_LABEL }));
		expect(table.nextPage).toHaveBeenCalledOnce();
	});

	// -- className pass-through ----------------------------------------------

	it("applies custom className to the root element", () => {
		const table = createMockTable();
		const { container } = render(
			<DataTablePagination table={table} className="my-pagination" />,
		);

		expect(container.firstChild).toHaveClass("my-pagination");
	});

	// -- Page info edge cases ------------------------------------------------

	it("shows 'Page 0 of 0' when there are no pages", () => {
		const table = createMockTable({ pageIndex: 0, pageCount: 0 });
		render(<DataTablePagination table={table} />);

		expect(screen.getByText("Page 0 of 0")).toBeInTheDocument();
	});

	// -- Custom page size options --------------------------------------------

	it("accepts custom pageSizeOptions without error", () => {
		const table = createMockTable({ pageSize: 10 });
		render(
			<DataTablePagination table={table} pageSizeOptions={[10, 25, 50]} />,
		);

		// Verify component renders correctly with custom options
		expect(
			screen.getByRole("combobox", { name: ROWS_PER_PAGE_LABEL }),
		).toBeInTheDocument();
		expect(screen.getByText("Page 1 of 5")).toBeInTheDocument();
	});

	// -- Single page ---------------------------------------------------------

	it("disables both buttons on single page", () => {
		const table = createMockTable({
			pageCount: 1,
			canPreviousPage: false,
			canNextPage: false,
		});
		render(<DataTablePagination table={table} />);

		expect(screen.getByRole("button", { name: PREVIOUS_LABEL })).toBeDisabled();
		expect(screen.getByRole("button", { name: NEXT_LABEL })).toBeDisabled();
	});
});
