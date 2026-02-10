/**
 * DataTable component barrel export.
 *
 * Re-exports the DataTable component, column header, toolbar,
 * pagination, and select column for use across pages.
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
