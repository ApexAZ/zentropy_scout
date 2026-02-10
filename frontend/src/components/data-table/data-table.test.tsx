/**
 * Tests for DataTable component.
 *
 * REQ-012 §13.3: Table/List component with column definitions,
 * row click navigation, and responsive card fallback.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ColumnDef } from "@tanstack/react-table";
import { describe, expect, it, vi } from "vitest";

import { DataTable } from "./data-table";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const COL_NAME = "Name";
const COL_EMAIL = "Email";
const EMPTY_MESSAGE = "No results.";
const CUSTOM_EMPTY = "No jobs found";
const CURSOR_POINTER = "cursor-pointer";

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

		const cardContainer = screen
			.getByTestId("card-1")
			.closest("[data-slot='data-table-mobile']");
		expect(cardContainer).toHaveClass("md:hidden");
	});

	it("does not render card container when renderCard is not provided", () => {
		const { container } = render(
			<DataTable columns={TEST_COLUMNS} data={TEST_DATA} />,
		);

		expect(
			container.querySelector("[data-slot='data-table-mobile']"),
		).not.toBeInTheDocument();
	});

	it("renders empty card list when data is empty and renderCard is provided", () => {
		const { container } = render(
			<DataTable
				columns={TEST_COLUMNS}
				data={[]}
				renderCard={testRenderCard}
			/>,
		);

		const mobileContainer = container.querySelector(
			"[data-slot='data-table-mobile']",
		);
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

		const mobileContainer = container.querySelector(
			"[data-slot='data-table-mobile']",
		);
		expect(mobileContainer).toBeInTheDocument();
		expect(screen.getByTestId("card-1")).toBeInTheDocument();
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
});
