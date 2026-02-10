/**
 * Tests for DataTableToolbar component.
 *
 * REQ-012 §13.3: Toolbar search and column filter reset.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Table } from "@tanstack/react-table";
import { describe, expect, it, vi } from "vitest";

import { DataTableToolbar } from "./data-table-toolbar";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PLACEHOLDER = "Search...";
const CUSTOM_PLACEHOLDER = "Filter jobs...";
const RESET_LABEL = "Reset";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

interface MockTableOpts {
	globalFilter?: string;
	columnFilters?: { id: string; value: unknown }[];
}

function createMockTable({
	globalFilter = "",
	columnFilters = [],
}: MockTableOpts = {}) {
	return {
		getState: vi.fn().mockReturnValue({ globalFilter, columnFilters }),
		setGlobalFilter: vi.fn(),
		resetColumnFilters: vi.fn(),
	} as unknown as Table<unknown>;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DataTableToolbar", () => {
	it("renders search input with default placeholder", () => {
		const table = createMockTable();
		render(<DataTableToolbar table={table} />);
		expect(
			screen.getByPlaceholderText(DEFAULT_PLACEHOLDER),
		).toBeInTheDocument();
	});

	it("renders search input with custom placeholder", () => {
		const table = createMockTable();
		render(
			<DataTableToolbar table={table} searchPlaceholder={CUSTOM_PLACEHOLDER} />,
		);
		expect(screen.getByPlaceholderText(CUSTOM_PLACEHOLDER)).toBeInTheDocument();
	});

	it("shows current global filter value in search input", () => {
		const table = createMockTable({ globalFilter: "alice" });
		render(<DataTableToolbar table={table} />);
		expect(screen.getByDisplayValue("alice")).toBeInTheDocument();
	});

	it("calls setGlobalFilter on search input change", async () => {
		const user = userEvent.setup();
		const table = createMockTable();
		render(<DataTableToolbar table={table} />);

		await user.type(screen.getByPlaceholderText(DEFAULT_PLACEHOLDER), "bob");
		expect(table.setGlobalFilter).toHaveBeenCalled();
	});

	it("renders children", () => {
		const table = createMockTable();
		render(
			<DataTableToolbar table={table}>
				<button type="button">Custom Filter</button>
			</DataTableToolbar>,
		);
		expect(screen.getByText("Custom Filter")).toBeInTheDocument();
	});

	it("shows reset button when column filters are active", () => {
		const table = createMockTable({
			columnFilters: [{ id: "status", value: "active" }],
		});
		render(<DataTableToolbar table={table} />);
		expect(screen.getByText(RESET_LABEL)).toBeInTheDocument();
	});

	it("hides reset button when no column filters are active", () => {
		const table = createMockTable({ columnFilters: [] });
		render(<DataTableToolbar table={table} />);
		expect(screen.queryByText(RESET_LABEL)).not.toBeInTheDocument();
	});

	it("calls resetColumnFilters on reset button click", async () => {
		const user = userEvent.setup();
		const table = createMockTable({
			columnFilters: [{ id: "status", value: "active" }],
		});
		render(<DataTableToolbar table={table} />);

		await user.click(screen.getByText(RESET_LABEL));
		expect(table.resetColumnFilters).toHaveBeenCalledOnce();
	});

	it("applies custom className", () => {
		const table = createMockTable();
		const { container } = render(
			<DataTableToolbar table={table} className="my-toolbar" />,
		);
		expect(container.firstChild).toHaveClass("my-toolbar");
	});
});
