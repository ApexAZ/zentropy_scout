/**
 * @fileoverview DataTable component barrel export.
 *
 * Layer: lib/utility
 * Feature: shared
 *
 * Re-exports the DataTable component, column header, toolbar,
 * pagination, and select column for use across pages.
 *
 * Coordinates with:
 * - components/data-table/data-table.tsx: DataTable, DataTableProps re-export
 * - components/data-table/data-table-column-header.tsx: DataTableColumnHeader, DataTableColumnHeaderProps re-export
 * - components/data-table/data-table-pagination.tsx: DataTablePagination, DataTablePaginationProps re-export
 * - components/data-table/data-table-select-column.tsx: getSelectColumn, SELECT_ROW_LABEL re-export
 * - components/data-table/data-table-toolbar.tsx: DataTableToolbar, DataTableToolbarProps re-export
 * - components/data-table/toolbar-select.tsx: ToolbarSelect sibling (not re-exported — consumers import directly)
 *
 * Called by / Used by:
 * - (barrel index — consumers import individual files directly)
 */

export { DataTable, type DataTableProps } from "./data-table";
export {
	DataTableColumnHeader,
	type DataTableColumnHeaderProps,
} from "./data-table-column-header";
export {
	DataTablePagination,
	type DataTablePaginationProps,
} from "./data-table-pagination";
export { getSelectColumn, SELECT_ROW_LABEL } from "./data-table-select-column";
export {
	DataTableToolbar,
	type DataTableToolbarProps,
} from "./data-table-toolbar";
