"use client";

/**
 * Checkbox column factory for DataTable row selection.
 *
 * REQ-012 §13.3: Multi-select with checkbox column.
 *
 * Usage:
 * ```tsx
 * const columns = [getSelectColumn<MyRow>(), ...myColumns];
 * ```
 */

import type { ColumnDef } from "@tanstack/react-table";

import { Checkbox } from "@/components/ui/checkbox";

/** Aria label for per-row selection checkboxes. Shared with DataTable mobile cards. */
export const SELECT_ROW_LABEL = "Select row";

/**
 * Creates a checkbox column definition for row selection.
 *
 * Header renders a select-all checkbox (page-aware with pagination).
 * Each cell renders a per-row checkbox.
 */
export function getSelectColumn<TData>(): ColumnDef<TData, unknown> {
	return {
		id: "select",
		header: ({ table }) => (
			<Checkbox
				checked={
					table.getIsAllPageRowsSelected() ||
					(table.getIsSomePageRowsSelected() && "indeterminate")
				}
				onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
				aria-label="Select all"
			/>
		),
		cell: ({ row }) => (
			<Checkbox
				checked={row.getIsSelected()}
				onCheckedChange={(value) => row.toggleSelected(!!value)}
				aria-label={SELECT_ROW_LABEL}
			/>
		),
		enableSorting: false,
		enableHiding: false,
	};
}
