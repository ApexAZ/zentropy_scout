/**
 * Tests for DataTable select column helper and row selection.
 *
 * REQ-012 §13.3: Multi-select with checkbox column.
 * REQ-012 §8.2: Bulk actions toolbar with selected count and cancel.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ColumnDef } from "@tanstack/react-table";
import { describe, expect, it, vi } from "vitest";

import { DataTable } from "./data-table";
import { getSelectColumn } from "./data-table-select-column";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SELECT_ALL_LABEL = "Select all";
const SELECT_ROW_LABEL = "Select row";
const MOBILE_SLOT = "[data-slot='data-table-mobile']";

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

const BASE_COLUMNS: ColumnDef<TestRow>[] = [
	{ accessorKey: "name", header: "Name" },
	{ accessorKey: "email", header: "Email" },
];

// ---------------------------------------------------------------------------
// Tests: getSelectColumn helper
// ---------------------------------------------------------------------------

describe("getSelectColumn", () => {
	it("returns a column definition with id 'select'", () => {
		const col = getSelectColumn<TestRow>();
		expect(col.id).toBe("select");
	});

	it("has sorting and hiding disabled", () => {
		const col = getSelectColumn<TestRow>();
		expect(col.enableSorting).toBe(false);
		expect(col.enableHiding).toBe(false);
	});
});

// ---------------------------------------------------------------------------
// Tests: Row selection in DataTable
// ---------------------------------------------------------------------------

describe("DataTable row selection", () => {
	function getColumnsWithSelect(): ColumnDef<TestRow, unknown>[] {
		return [getSelectColumn<TestRow>(), ...BASE_COLUMNS];
	}

	// -- Checkbox rendering ---------------------------------------------------

	it("renders select-all checkbox in header", () => {
		render(
			<DataTable
				columns={getColumnsWithSelect()}
				data={TEST_DATA}
				enableRowSelection
				rowSelection={{}}
				onRowSelectionChange={vi.fn()}
			/>,
		);

		expect(
			screen.getByRole("checkbox", { name: SELECT_ALL_LABEL }),
		).toBeInTheDocument();
	});

	it("renders per-row checkboxes", () => {
		render(
			<DataTable
				columns={getColumnsWithSelect()}
				data={TEST_DATA}
				enableRowSelection
				rowSelection={{}}
				onRowSelectionChange={vi.fn()}
			/>,
		);

		const rowCheckboxes = screen.getAllByRole("checkbox", {
			name: SELECT_ROW_LABEL,
		});
		expect(rowCheckboxes).toHaveLength(3);
	});

	// -- Selection state ------------------------------------------------------

	it("checks row checkbox when row is in rowSelection state", () => {
		render(
			<DataTable
				columns={getColumnsWithSelect()}
				data={TEST_DATA}
				enableRowSelection
				rowSelection={{ "0": true }}
				onRowSelectionChange={vi.fn()}
			/>,
		);

		const rowCheckboxes = screen.getAllByRole("checkbox", {
			name: SELECT_ROW_LABEL,
		});
		expect(rowCheckboxes[0]).toHaveAttribute("data-state", "checked");
		expect(rowCheckboxes[1]).toHaveAttribute("data-state", "unchecked");
	});

	it("marks select-all as checked when all rows are selected", () => {
		render(
			<DataTable
				columns={getColumnsWithSelect()}
				data={TEST_DATA}
				enableRowSelection
				rowSelection={{ "0": true, "1": true, "2": true }}
				onRowSelectionChange={vi.fn()}
			/>,
		);

		const selectAll = screen.getByRole("checkbox", {
			name: SELECT_ALL_LABEL,
		});
		expect(selectAll).toHaveAttribute("data-state", "checked");
	});

	it("marks select-all as indeterminate when some rows are selected", () => {
		render(
			<DataTable
				columns={getColumnsWithSelect()}
				data={TEST_DATA}
				enableRowSelection
				rowSelection={{ "0": true }}
				onRowSelectionChange={vi.fn()}
			/>,
		);

		const selectAll = screen.getByRole("checkbox", {
			name: SELECT_ALL_LABEL,
		});
		// Radix checkbox uses "indeterminate" data-state
		expect(selectAll).toHaveAttribute("data-state", "indeterminate");
	});

	// -- Interaction ----------------------------------------------------------

	it("calls onRowSelectionChange when clicking a row checkbox", async () => {
		const user = userEvent.setup();
		const handleSelectionChange = vi.fn();

		render(
			<DataTable
				columns={getColumnsWithSelect()}
				data={TEST_DATA}
				enableRowSelection
				rowSelection={{}}
				onRowSelectionChange={handleSelectionChange}
			/>,
		);

		const rowCheckboxes = screen.getAllByRole("checkbox", {
			name: SELECT_ROW_LABEL,
		});
		await user.click(rowCheckboxes[0]);
		expect(handleSelectionChange).toHaveBeenCalledOnce();
	});

	it("calls onRowSelectionChange when clicking select-all", async () => {
		const user = userEvent.setup();
		const handleSelectionChange = vi.fn();

		render(
			<DataTable
				columns={getColumnsWithSelect()}
				data={TEST_DATA}
				enableRowSelection
				rowSelection={{}}
				onRowSelectionChange={handleSelectionChange}
			/>,
		);

		await user.click(screen.getByRole("checkbox", { name: SELECT_ALL_LABEL }));
		expect(handleSelectionChange).toHaveBeenCalledOnce();
	});

	// -- Without enableRowSelection -------------------------------------------

	it("does not show mobile card checkboxes when enableRowSelection is false", () => {
		const { container } = render(
			<DataTable
				columns={getColumnsWithSelect()}
				data={TEST_DATA}
				enableRowSelection={false}
				rowSelection={{}}
				onRowSelectionChange={vi.fn()}
				renderCard={(row) => (
					<div data-testid={`card-${row.id}`}>{row.name}</div>
				)}
				getRowId={(row) => String(row.id)}
			/>,
		);

		// Mobile cards should NOT show checkboxes when selection is disabled
		const mobileContainer = container.querySelector(MOBILE_SLOT);
		expect(mobileContainer).toBeInTheDocument();
		const checkboxes = within(mobileContainer as HTMLElement).queryAllByRole(
			"checkbox",
		);
		expect(checkboxes).toHaveLength(0);
	});

	// -- Selected row styling -------------------------------------------------

	it("applies selected styling to selected rows", () => {
		render(
			<DataTable
				columns={getColumnsWithSelect()}
				data={TEST_DATA}
				enableRowSelection
				rowSelection={{ "0": true }}
				onRowSelectionChange={vi.fn()}
			/>,
		);

		const table = screen.getByRole("table");
		const rows = within(table).getAllByRole("row");
		// Row 0 is header, row 1 is Alice (selected)
		expect(rows[1]).toHaveAttribute("data-state", "selected");
		// Row 2 is Bob (not selected)
		expect(rows[2]).not.toHaveAttribute("data-state", "selected");
	});

	// -- Mobile card checkboxes -----------------------------------------------

	it("renders checkboxes on mobile cards when selection is enabled", () => {
		render(
			<DataTable
				columns={getColumnsWithSelect()}
				data={TEST_DATA}
				enableRowSelection
				rowSelection={{}}
				onRowSelectionChange={vi.fn()}
				renderCard={(row) => (
					<div data-testid={`card-${row.id}`}>{row.name}</div>
				)}
				getRowId={(row) => String(row.id)}
			/>,
		);

		const mobileContainer = document.querySelector(MOBILE_SLOT);
		expect(mobileContainer).toBeInTheDocument();

		const cardCheckboxes = within(mobileContainer as HTMLElement).getAllByRole(
			"checkbox",
		);
		expect(cardCheckboxes).toHaveLength(3);
	});

	it("checks mobile card checkbox for selected rows", () => {
		render(
			<DataTable
				columns={getColumnsWithSelect()}
				data={TEST_DATA}
				enableRowSelection
				rowSelection={{ "1": true }}
				onRowSelectionChange={vi.fn()}
				renderCard={(row) => (
					<div data-testid={`card-${row.id}`}>{row.name}</div>
				)}
				getRowId={(row) => String(row.id)}
			/>,
		);

		const mobileContainer = document.querySelector(MOBILE_SLOT);
		expect(mobileContainer).toBeInTheDocument();
		const checkboxes = within(mobileContainer as HTMLElement).getAllByRole(
			"checkbox",
		);
		expect(checkboxes[0]).toHaveAttribute("data-state", "checked");
		expect(checkboxes[1]).toHaveAttribute("data-state", "unchecked");
	});

	it("calls onRowSelectionChange when clicking a mobile card checkbox", async () => {
		const user = userEvent.setup();
		const handleSelectionChange = vi.fn();

		render(
			<DataTable
				columns={getColumnsWithSelect()}
				data={TEST_DATA}
				enableRowSelection
				rowSelection={{}}
				onRowSelectionChange={handleSelectionChange}
				renderCard={(row) => (
					<div data-testid={`card-${row.id}`}>{row.name}</div>
				)}
				getRowId={(row) => String(row.id)}
			/>,
		);

		const mobileContainer = document.querySelector(MOBILE_SLOT);
		expect(mobileContainer).toBeInTheDocument();
		const checkboxes = within(mobileContainer as HTMLElement).getAllByRole(
			"checkbox",
		);
		await user.click(checkboxes[0]);
		expect(handleSelectionChange).toHaveBeenCalled();
	});

	// -- Pagination interaction -----------------------------------------------

	it("select-all only selects current page rows with pagination", () => {
		render(
			<DataTable
				columns={getColumnsWithSelect()}
				data={TEST_DATA}
				enableRowSelection
				rowSelection={{ "0": true, "1": true }}
				onRowSelectionChange={vi.fn()}
				pagination={{ pageIndex: 0, pageSize: 2 }}
			/>,
		);

		const selectAll = screen.getByRole("checkbox", {
			name: SELECT_ALL_LABEL,
		});
		// All rows on current page selected → checked
		expect(selectAll).toHaveAttribute("data-state", "checked");
	});

	// -- getRowId integration ------------------------------------------------

	it("uses getRowId for selection state keys", () => {
		render(
			<DataTable
				columns={getColumnsWithSelect()}
				data={TEST_DATA}
				enableRowSelection
				rowSelection={{ "1": true }}
				onRowSelectionChange={vi.fn()}
				getRowId={(row) => String(row.id)}
			/>,
		);

		const rowCheckboxes = screen.getAllByRole("checkbox", {
			name: SELECT_ROW_LABEL,
		});
		// With getRowId: id=1 is Alice (first row) → should be checked
		expect(rowCheckboxes[0]).toHaveAttribute("data-state", "checked");
		expect(rowCheckboxes[1]).toHaveAttribute("data-state", "unchecked");
	});
});
