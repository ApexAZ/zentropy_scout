"use client";
"use no memo";

/**
 * Generic data table with TanStack Table and responsive card fallback.
 *
 * REQ-012 §13.3: Table/List component with column definitions,
 * row click navigation, responsive card fallback, sorting,
 * column filtering, and global search.
 *
 * §3.3 covers the base table. §3.4 adds sorting, filtering, and toolbar.
 * §3.5–§3.6 add pagination and multi-select.
 */

import * as React from "react";
import {
	type ColumnDef,
	type ColumnFiltersState,
	type OnChangeFn,
	type PaginationState,
	type RowSelectionState,
	type SortingState,
	type Table as ReactTable,
	flexRender,
	getCoreRowModel,
	getFilteredRowModel,
	getPaginationRowModel,
	getSortedRowModel,
	useReactTable,
} from "@tanstack/react-table";

import { cn } from "@/lib/utils";
import { Checkbox } from "@/components/ui/checkbox";
import { SELECT_ROW_LABEL } from "./data-table-select-column";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DataTableProps<TData> {
	columns: ColumnDef<TData, unknown>[];
	data: TData[];
	onRowClick?: (row: TData) => void;
	renderCard?: (row: TData) => React.ReactNode;
	getRowId?: (row: TData) => string;
	emptyMessage?: string;
	className?: string;

	/** Controlled sorting state. */
	sorting?: SortingState;
	/** Callback when sorting changes (controlled mode). */
	onSortingChange?: OnChangeFn<SortingState>;

	/** Controlled column filter state. */
	columnFilters?: ColumnFiltersState;
	/** Callback when column filters change (controlled mode). */
	onColumnFiltersChange?: OnChangeFn<ColumnFiltersState>;

	/** Controlled global filter value (toolbar search). */
	globalFilter?: string;
	/** Callback when global filter changes (controlled mode). */
	onGlobalFilterChange?: OnChangeFn<string>;

	/** Controlled pagination state. Providing this enables client-side pagination. */
	pagination?: PaginationState;
	/** Callback when pagination changes (controlled mode). */
	onPaginationChange?: OnChangeFn<PaginationState>;
	/** Total page count for server-side pagination. Enables manual pagination mode. */
	pageCount?: number;

	/** Enable row selection via checkboxes. */
	enableRowSelection?: boolean;
	/** Controlled row selection state (keys are row IDs). */
	rowSelection?: RowSelectionState;
	/** Callback when row selection changes (controlled mode). */
	onRowSelectionChange?: OnChangeFn<RowSelectionState>;

	/** Render prop for toolbar — receives the table instance. */
	toolbar?: (table: ReactTable<TData>) => React.ReactNode;

	/** Returns additional CSS class(es) for a table row based on its data. */
	getRowClassName?: (row: TData) => string | undefined;

	/** Arbitrary metadata passed to cell renderers via table.options.meta. */
	// eslint-disable-next-line @typescript-eslint/no-explicit-any -- TanStack Table meta is typed as `any` by design
	meta?: Record<string, any>;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getAriaSortValue(header: {
	column: {
		getIsSorted: () => false | "asc" | "desc";
		getCanSort: () => boolean;
	};
}): "ascending" | "descending" | "none" | undefined {
	const sorted = header.column.getIsSorted();
	if (sorted === "asc") return "ascending";
	if (sorted === "desc") return "descending";
	if (header.column.getCanSort()) return "none";
	return undefined;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DataTable<TData>({
	columns,
	data,
	onRowClick,
	renderCard,
	getRowId,
	emptyMessage = "No results.",
	className,
	sorting,
	onSortingChange,
	columnFilters,
	onColumnFiltersChange,
	globalFilter,
	onGlobalFilterChange,
	pagination,
	onPaginationChange,
	pageCount,
	enableRowSelection = false,
	rowSelection,
	onRowSelectionChange,
	toolbar,
	getRowClassName,
	meta,
}: Readonly<DataTableProps<TData>>) {
	// Internal state for uncontrolled mode
	const [internalSorting, setInternalSorting] = React.useState<SortingState>(
		[],
	);
	const [internalColumnFilters, setInternalColumnFilters] =
		React.useState<ColumnFiltersState>([]);
	const [internalGlobalFilter, setInternalGlobalFilter] = React.useState("");
	const [internalPagination, setInternalPagination] =
		React.useState<PaginationState>({ pageIndex: 0, pageSize: 20 });
	const [internalRowSelection, setInternalRowSelection] =
		React.useState<RowSelectionState>({});

	// Pagination enabled when consumer provides pagination state or pageCount
	const enablePagination = pagination !== undefined || pageCount !== undefined;

	const table = useReactTable({
		data,
		columns,
		getRowId,
		getCoreRowModel: getCoreRowModel(),
		getSortedRowModel: getSortedRowModel(),
		getFilteredRowModel: getFilteredRowModel(),
		...(enablePagination &&
			pageCount === undefined && {
				getPaginationRowModel: getPaginationRowModel(),
			}),
		...(pageCount !== undefined && {
			manualPagination: true,
			pageCount,
		}),
		enableRowSelection,
		meta,
		state: {
			sorting: sorting ?? internalSorting,
			columnFilters: columnFilters ?? internalColumnFilters,
			globalFilter: globalFilter ?? internalGlobalFilter,
			...(enablePagination && {
				pagination: pagination ?? internalPagination,
			}),
			rowSelection: rowSelection ?? internalRowSelection,
		},
		onSortingChange: onSortingChange ?? setInternalSorting,
		onColumnFiltersChange: onColumnFiltersChange ?? setInternalColumnFilters,
		onGlobalFilterChange: onGlobalFilterChange ?? setInternalGlobalFilter,
		...(enablePagination && {
			onPaginationChange: onPaginationChange ?? setInternalPagination,
		}),
		onRowSelectionChange: onRowSelectionChange ?? setInternalRowSelection,
	});

	const hasCards = renderCard !== undefined;

	return (
		<div data-slot="data-table" className={cn(className)}>
			{/* Toolbar (render prop) */}
			{toolbar && <div data-slot="data-table-toolbar">{toolbar(table)}</div>}

			{/* Desktop: standard table (hidden on mobile when cards exist) */}
			<div
				data-slot="data-table-desktop"
				className={cn(hasCards && "hidden md:block")}
			>
				<Table>
					<TableHeader>
						{table.getHeaderGroups().map((headerGroup) => (
							<TableRow key={headerGroup.id}>
								{headerGroup.headers.map((header) => (
									<TableHead
										key={header.id}
										aria-sort={getAriaSortValue(header)}
									>
										{header.isPlaceholder
											? null
											: flexRender(
													header.column.columnDef.header,
													header.getContext(),
												)}
									</TableHead>
								))}
							</TableRow>
						))}
					</TableHeader>
					<TableBody>
						{table.getRowModel().rows.length > 0 ? (
							table.getRowModel().rows.map((row) => (
								<TableRow
									key={row.id}
									className={cn(
										onRowClick &&
											"focus-visible:ring-ring cursor-pointer focus-visible:ring-2 focus-visible:outline-none",
										getRowClassName?.(row.original),
									)}
									role={onRowClick ? "button" : undefined}
									tabIndex={onRowClick ? 0 : undefined}
									data-state={row.getIsSelected() ? "selected" : undefined}
									onClick={
										onRowClick ? () => onRowClick(row.original) : undefined
									}
									onKeyDown={
										onRowClick
											? (e) => {
													if (e.key === "Enter" || e.key === " ") {
														e.preventDefault();
														onRowClick(row.original);
													}
												}
											: undefined
									}
								>
									{row.getVisibleCells().map((cell) => (
										<TableCell key={cell.id}>
											{flexRender(
												cell.column.columnDef.cell,
												cell.getContext(),
											)}
										</TableCell>
									))}
								</TableRow>
							))
						) : (
							<TableRow>
								<TableCell
									colSpan={columns.length}
									className="h-24 text-center"
								>
									{emptyMessage}
								</TableCell>
							</TableRow>
						)}
					</TableBody>
				</Table>
			</div>

			{/* Mobile: card list (shown only on mobile when renderCard is provided) */}
			{hasCards && (
				<div
					data-slot="data-table-mobile"
					className="flex flex-col gap-3 md:hidden"
				>
					{table.getRowModel().rows.length > 0 ? (
						table.getRowModel().rows.map((row) => (
							<div
								key={getRowId?.(row.original) ?? row.id}
								className={cn(enableRowSelection && "flex items-start gap-2")}
							>
								{enableRowSelection && (
									<Checkbox
										checked={row.getIsSelected()}
										onCheckedChange={(value) => row.toggleSelected(!!value)}
										aria-label={SELECT_ROW_LABEL}
										className="mt-1"
									/>
								)}
								<div className={cn(enableRowSelection && "flex-1")}>
									{renderCard(row.original)}
								</div>
							</div>
						))
					) : (
						<p className="text-muted-foreground py-8 text-center text-sm">
							{emptyMessage}
						</p>
					)}
				</div>
			)}
		</div>
	);
}
