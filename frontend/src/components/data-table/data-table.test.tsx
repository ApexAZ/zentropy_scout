/**
 * Tests for DataTable component.
 *
 * REQ-012 §13.3: Table/List component with column definitions,
 * row click navigation, and responsive card fallback.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ColumnDef, PaginationState } from "@tanstack/react-table";
import { describe, expect, it, vi } from "vitest";

import { DataTable } from "./data-table";
import { DataTableColumnHeader } from "./data-table-column-header";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const COL_NAME = "Name";
const COL_EMAIL = "Email";
const EMPTY_MESSAGE = "No results.";
const CUSTOM_EMPTY = "No jobs found";
const CURSOR_POINTER = "cursor-pointer";
const MOBILE_SLOT = "[data-slot='data-table-mobile']";
const TEST_PAGINATION: PaginationState = { pageIndex: 0, pageSize: 2 };

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

interface TestRow {
	id: number;
	name: string;
	email: string;
}

const ALICE: TestRow = { id: 1, name: "Alice", email: "alice@example.com" };
const BOB: TestRow = { id: 2, name: "Bob", email: "bob@example.com" };
const CHARLIE: TestRow = {
	id: 3,
	name: "Charlie",
	email: "charlie@example.com",
};
const TEST_DATA: TestRow[] = [ALICE, BOB, CHARLIE];
const UNORDERED_DATA: TestRow[] = [BOB, CHARLIE, ALICE];

const TEST_COLUMNS: ColumnDef<TestRow>[] = [
	{ accessorKey: "name", header: COL_NAME },
	{ accessorKey: "email", header: COL_EMAIL },
];

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

function testRenderCard(row: TestRow) {
	return <div data-testid={`card-${row.id}`}>{row.name}</div>;
}

function testGetRowId(row: TestRow) {
	return String(row.id);
}

const SORTABLE_COLUMNS: ColumnDef<TestRow>[] = [
	{
		accessorKey: "name",
		header: ({ column }) => (
			<DataTableColumnHeader column={column} title={COL_NAME} />
		),
		enableSorting: true,
	},
	{
		accessorKey: "email",
		header: COL_EMAIL,
		enableSorting: false,
	},
];

function getFirstColumnCells(): string[] {
	const table = screen.getByRole("table");
	const rows = within(table).getAllByRole("row");
	return rows
		.slice(1)
		.map((row) => within(row).getAllByRole("cell")[0].textContent ?? "");
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DataTable", () => {
	// -- Rendering -----------------------------------------------------------

	it("renders column headers", () => {
		render(<DataTable columns={TEST_COLUMNS} data={TEST_DATA} />);

		expect(screen.getByText(COL_NAME)).toBeInTheDocument();
		expect(screen.getByText(COL_EMAIL)).toBeInTheDocument();
	});

	it("renders data rows", () => {
		render(<DataTable columns={TEST_COLUMNS} data={TEST_DATA} />);

		const table = screen.getByRole("table");
		const rows = within(table).getAllByRole("row");
		// 1 header row + 3 data rows
		expect(rows).toHaveLength(4);
	});

	it("renders correct cell values from accessorKey columns", () => {
		render(<DataTable columns={TEST_COLUMNS} data={TEST_DATA} />);

		expect(screen.getByText(ALICE.name)).toBeInTheDocument();
		expect(screen.getByText(ALICE.email)).toBeInTheDocument();
		expect(screen.getByText(BOB.name)).toBeInTheDocument();
		expect(screen.getByText(BOB.email)).toBeInTheDocument();
	});

	it("renders custom cell content via column cell function", () => {
		const columns: ColumnDef<TestRow>[] = [
			{
				accessorKey: "name",
				header: COL_NAME,
				cell: ({ row }) => <strong>{row.getValue("name")}</strong>,
			},
			{ accessorKey: "email", header: COL_EMAIL },
		];

		render(<DataTable columns={columns} data={TEST_DATA} />);

		const strong = screen.getByText(ALICE.name).closest("strong");
		expect(strong).toBeInTheDocument();
	});

	it("renders custom header content via column header function", () => {
		const columns: ColumnDef<TestRow>[] = [
			{
				accessorKey: "name",
				header: () => <span data-testid="custom-header">Full Name</span>,
			},
			{ accessorKey: "email", header: COL_EMAIL },
		];

		render(<DataTable columns={columns} data={TEST_DATA} />);

		expect(screen.getByTestId("custom-header")).toBeInTheDocument();
		expect(screen.getByText("Full Name")).toBeInTheDocument();
	});

	// -- Empty state ---------------------------------------------------------

	it("renders empty message when data is empty", () => {
		render(<DataTable columns={TEST_COLUMNS} data={[]} />);

		expect(screen.getByText(EMPTY_MESSAGE)).toBeInTheDocument();
	});

	it("renders custom empty message", () => {
		render(
			<DataTable
				columns={TEST_COLUMNS}
				data={[]}
				emptyMessage={CUSTOM_EMPTY}
			/>,
		);

		expect(screen.getByText(CUSTOM_EMPTY)).toBeInTheDocument();
	});

	// -- Row click -----------------------------------------------------------

	it("calls onRowClick with row data when a row is clicked", async () => {
		const user = userEvent.setup();
		const handleClick = vi.fn();

		render(
			<DataTable
				columns={TEST_COLUMNS}
				data={TEST_DATA}
				onRowClick={handleClick}
			/>,
		);

		const aliceRow = screen.getByText(ALICE.name).closest("tr");
		await user.click(aliceRow as HTMLElement);

		expect(handleClick).toHaveBeenCalledOnce();
		expect(handleClick).toHaveBeenCalledWith(ALICE);
	});

	it("adds cursor-pointer class to rows when onRowClick is provided", () => {
		render(
			<DataTable
				columns={TEST_COLUMNS}
				data={TEST_DATA}
				onRowClick={() => {}}
			/>,
		);

		const aliceRow = screen.getByText(ALICE.name).closest("tr");
		expect(aliceRow).toHaveClass(CURSOR_POINTER);
	});

	it("does not add cursor-pointer when onRowClick is not provided", () => {
		render(<DataTable columns={TEST_COLUMNS} data={TEST_DATA} />);

		const aliceRow = screen.getByText(ALICE.name).closest("tr");
		expect(aliceRow).not.toHaveClass(CURSOR_POINTER);
	});

	it("makes clickable rows keyboard-accessible", async () => {
		const user = userEvent.setup();
		const handleClick = vi.fn();

		render(
			<DataTable
				columns={TEST_COLUMNS}
				data={TEST_DATA}
				onRowClick={handleClick}
			/>,
		);

		const aliceRow = screen.getByText(ALICE.name).closest("tr");
		expect(aliceRow).toHaveAttribute("role", "button");
		expect(aliceRow).toHaveAttribute("tabindex", "0");

		// Enter key activates
		(aliceRow as HTMLElement).focus();
		await user.keyboard("{Enter}");
		expect(handleClick).toHaveBeenCalledWith(ALICE);

		// Space key activates
		handleClick.mockClear();
		await user.keyboard(" ");
		expect(handleClick).toHaveBeenCalledWith(ALICE);
	});

	it("does not add role or tabindex when onRowClick is not provided", () => {
		render(<DataTable columns={TEST_COLUMNS} data={TEST_DATA} />);

		const aliceRow = screen.getByText(ALICE.name).closest("tr");
		expect(aliceRow).not.toHaveAttribute("role");
		expect(aliceRow).not.toHaveAttribute("tabindex");
	});

	// -- Responsive card fallback --------------------------------------------

	it("renders card fallback when renderCard is provided", () => {
		render(
			<DataTable
				columns={TEST_COLUMNS}
				data={TEST_DATA}
				renderCard={testRenderCard}
			/>,
		);

		// Both table and cards should be in the DOM (CSS handles visibility)
		expect(screen.getByRole("table")).toBeInTheDocument();
		expect(screen.getByTestId("card-1")).toBeInTheDocument();
		expect(screen.getByTestId("card-2")).toBeInTheDocument();
		expect(screen.getByTestId("card-3")).toBeInTheDocument();
	});

	it("hides table on mobile when renderCard is provided", () => {
		render(
			<DataTable
				columns={TEST_COLUMNS}
				data={TEST_DATA}
				renderCard={testRenderCard}
			/>,
		);

		const tableContainer = screen
			.getByRole("table")
			.closest("[data-slot='data-table-desktop']");
		expect(tableContainer).toHaveClass("hidden");
		expect(tableContainer).toHaveClass("md:block");
	});

	it("shows cards on mobile when renderCard is provided", () => {
		render(
			<DataTable
				columns={TEST_COLUMNS}
				data={TEST_DATA}
				renderCard={testRenderCard}
			/>,
		);

		const cardContainer = screen.getByTestId("card-1").closest(MOBILE_SLOT);
		expect(cardContainer).toHaveClass("md:hidden");
	});

	it("does not render card container when renderCard is not provided", () => {
		const { container } = render(
			<DataTable columns={TEST_COLUMNS} data={TEST_DATA} />,
		);

		expect(container.querySelector(MOBILE_SLOT)).not.toBeInTheDocument();
	});

	it("renders empty card list when data is empty and renderCard is provided", () => {
		const { container } = render(
			<DataTable
				columns={TEST_COLUMNS}
				data={[]}
				renderCard={testRenderCard}
			/>,
		);

		const mobileContainer = container.querySelector(MOBILE_SLOT);
		expect(mobileContainer).toBeInTheDocument();
	});

	it("uses getRowId for stable card keys", () => {
		const { container } = render(
			<DataTable
				columns={TEST_COLUMNS}
				data={TEST_DATA}
				renderCard={testRenderCard}
				getRowId={testGetRowId}
			/>,
		);

		const mobileContainer = container.querySelector(MOBILE_SLOT);
		expect(mobileContainer).toBeInTheDocument();
		expect(screen.getByTestId("card-1")).toBeInTheDocument();
	});

	it("filters mobile cards when global filter is active", () => {
		render(
			<DataTable
				columns={TEST_COLUMNS}
				data={TEST_DATA}
				renderCard={testRenderCard}
				globalFilter="alice"
			/>,
		);

		expect(screen.getByTestId("card-1")).toBeInTheDocument();
		expect(screen.queryByTestId("card-2")).not.toBeInTheDocument();
		expect(screen.queryByTestId("card-3")).not.toBeInTheDocument();
	});

	it("sorts mobile cards when sorting is active", () => {
		render(
			<DataTable
				columns={SORTABLE_COLUMNS}
				data={UNORDERED_DATA}
				renderCard={testRenderCard}
				getRowId={testGetRowId}
				sorting={[{ id: "name", desc: false }]}
			/>,
		);

		const mobileContainer = document.querySelector(MOBILE_SLOT);
		const cards = mobileContainer?.querySelectorAll("[data-testid]");
		const cardIds = Array.from(cards ?? []).map((el) =>
			el.getAttribute("data-testid"),
		);
		// Sorted by name ascending: Alice (1), Bob (2), Charlie (3)
		expect(cardIds).toEqual(["card-1", "card-2", "card-3"]);
	});

	// -- className pass-through ----------------------------------------------

	it("applies custom className to the root element", () => {
		const { container } = render(
			<DataTable
				columns={TEST_COLUMNS}
				data={TEST_DATA}
				className="my-custom-class"
			/>,
		);

		const root = container.querySelector("[data-slot='data-table']");
		expect(root).toHaveClass("my-custom-class");
	});

	// -- Sorting -------------------------------------------------------------

	describe("Sorting", () => {
		it("sorts rows ascending when clicking sortable column header", async () => {
			const user = userEvent.setup();
			render(<DataTable columns={SORTABLE_COLUMNS} data={UNORDERED_DATA} />);

			// Initially: Bob, Charlie, Alice (insertion order)
			expect(getFirstColumnCells()).toEqual(["Bob", "Charlie", "Alice"]);

			// Click Name header → sort ascending
			await user.click(screen.getByRole("button", { name: /name/i }));

			expect(getFirstColumnCells()).toEqual(["Alice", "Bob", "Charlie"]);
		});

		it("sorts rows descending on second header click", async () => {
			const user = userEvent.setup();
			render(<DataTable columns={SORTABLE_COLUMNS} data={UNORDERED_DATA} />);

			const header = screen.getByRole("button", { name: /name/i });
			await user.click(header); // asc
			await user.click(header); // desc

			expect(getFirstColumnCells()).toEqual(["Charlie", "Bob", "Alice"]);
		});

		it("calls onSortingChange for controlled sorting", async () => {
			const user = userEvent.setup();
			const handleSortingChange = vi.fn();

			render(
				<DataTable
					columns={SORTABLE_COLUMNS}
					data={UNORDERED_DATA}
					sorting={[]}
					onSortingChange={handleSortingChange}
				/>,
			);

			await user.click(screen.getByRole("button", { name: /name/i }));
			expect(handleSortingChange).toHaveBeenCalledOnce();
		});

		it("adds aria-sort to sorted column header", async () => {
			const user = userEvent.setup();
			render(<DataTable columns={SORTABLE_COLUMNS} data={UNORDERED_DATA} />);

			const nameHeader = screen.getByText(COL_NAME).closest("th");
			expect(nameHeader).toHaveAttribute("aria-sort", "none");

			await user.click(screen.getByRole("button", { name: /name/i }));
			expect(nameHeader).toHaveAttribute("aria-sort", "ascending");
		});
	});

	// -- Filtering -----------------------------------------------------------

	describe("Filtering", () => {
		it("filters rows when global filter matches", () => {
			render(
				<DataTable
					columns={TEST_COLUMNS}
					data={TEST_DATA}
					globalFilter="alice"
				/>,
			);

			const table = screen.getByRole("table");
			const rows = within(table).getAllByRole("row");
			// 1 header row + 1 matching row
			expect(rows).toHaveLength(2);
			expect(screen.getByText(ALICE.name)).toBeInTheDocument();
		});

		it("filters rows based on column filter", () => {
			render(
				<DataTable
					columns={TEST_COLUMNS}
					data={TEST_DATA}
					columnFilters={[{ id: "name", value: "Bob" }]}
				/>,
			);

			const table = screen.getByRole("table");
			const rows = within(table).getAllByRole("row");
			expect(rows).toHaveLength(2);
			expect(screen.getByText(BOB.name)).toBeInTheDocument();
		});

		it("shows empty message when all rows are filtered out", () => {
			render(
				<DataTable
					columns={TEST_COLUMNS}
					data={TEST_DATA}
					globalFilter="nonexistent"
				/>,
			);

			expect(screen.getByText(EMPTY_MESSAGE)).toBeInTheDocument();
		});
	});

	// -- Toolbar -------------------------------------------------------------

	describe("Toolbar", () => {
		it("renders toolbar when toolbar prop is provided", () => {
			render(
				<DataTable
					columns={TEST_COLUMNS}
					data={TEST_DATA}
					toolbar={() => <div data-testid="my-toolbar">Toolbar</div>}
				/>,
			);

			expect(screen.getByTestId("my-toolbar")).toBeInTheDocument();
		});

		it("passes table instance to toolbar render prop", () => {
			const toolbarFn = vi.fn().mockReturnValue(null);

			render(
				<DataTable
					columns={TEST_COLUMNS}
					data={TEST_DATA}
					toolbar={toolbarFn}
				/>,
			);

			expect(toolbarFn).toHaveBeenCalledOnce();
			const tableArg = toolbarFn.mock.calls[0][0];
			expect(tableArg).toHaveProperty("getState");
			expect(tableArg).toHaveProperty("setGlobalFilter");
		});

		it("does not render toolbar slot when toolbar is not provided", () => {
			const { container } = render(
				<DataTable columns={TEST_COLUMNS} data={TEST_DATA} />,
			);

			expect(
				container.querySelector("[data-slot='data-table-toolbar']"),
			).not.toBeInTheDocument();
		});
	});

	// -- Pagination ----------------------------------------------------------

	describe("Pagination", () => {
		it("paginates rows when pagination prop is provided", () => {
			render(
				<DataTable
					columns={TEST_COLUMNS}
					data={TEST_DATA}
					pagination={TEST_PAGINATION}
				/>,
			);

			const table = screen.getByRole("table");
			const rows = within(table).getAllByRole("row");
			// 1 header row + 2 data rows (page 1 of 2)
			expect(rows).toHaveLength(3);
		});

		it("shows all rows when no pagination props are provided", () => {
			render(<DataTable columns={TEST_COLUMNS} data={TEST_DATA} />);

			const table = screen.getByRole("table");
			const rows = within(table).getAllByRole("row");
			// 1 header row + 3 data rows (all data visible)
			expect(rows).toHaveLength(4);
		});

		it("calls onPaginationChange for controlled pagination", async () => {
			const user = userEvent.setup();
			const handlePaginationChange = vi.fn();

			render(
				<DataTable
					columns={SORTABLE_COLUMNS}
					data={TEST_DATA}
					pagination={TEST_PAGINATION}
					onPaginationChange={handlePaginationChange}
				/>,
			);

			// Sorting triggers a pagination reset (autoResetPageIndex)
			await user.click(screen.getByRole("button", { name: /name/i }));
			expect(handlePaginationChange).toHaveBeenCalled();
		});

		it("paginates mobile cards when pagination is active", () => {
			render(
				<DataTable
					columns={TEST_COLUMNS}
					data={TEST_DATA}
					renderCard={testRenderCard}
					pagination={TEST_PAGINATION}
				/>,
			);

			const mobileContainer = document.querySelector(MOBILE_SLOT);
			const cards = mobileContainer?.querySelectorAll("[data-testid]");
			expect(cards).toHaveLength(2);
		});

		it("shows second page of data when pageIndex is 1", () => {
			render(
				<DataTable
					columns={TEST_COLUMNS}
					data={TEST_DATA}
					pagination={{ pageIndex: 1, pageSize: 2 }}
				/>,
			);

			const table = screen.getByRole("table");
			const rows = within(table).getAllByRole("row");
			// 1 header row + 1 data row (page 2: only Charlie left)
			expect(rows).toHaveLength(2);
			expect(screen.getByText(CHARLIE.name)).toBeInTheDocument();
		});

		it("supports server-side pagination with pageCount", () => {
			// Server-side: data is already sliced, pageCount tells total pages
			render(
				<DataTable
					columns={TEST_COLUMNS}
					data={[ALICE, BOB]}
					pagination={TEST_PAGINATION}
					pageCount={5}
				/>,
			);

			const table = screen.getByRole("table");
			const rows = within(table).getAllByRole("row");
			// 1 header row + 2 data rows (server already sliced)
			expect(rows).toHaveLength(3);
		});

		it("filters and paginates correctly together", () => {
			render(
				<DataTable
					columns={TEST_COLUMNS}
					data={TEST_DATA}
					globalFilter="alice"
					pagination={TEST_PAGINATION}
				/>,
			);

			const table = screen.getByRole("table");
			const rows = within(table).getAllByRole("row");
			// 1 header row + 1 matching row (filter applied before pagination)
			expect(rows).toHaveLength(2);
			expect(screen.getByText(ALICE.name)).toBeInTheDocument();
		});
	});
});
