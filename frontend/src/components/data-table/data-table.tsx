"use client";
/* eslint-disable react-hooks/incompatible-library -- useReactTable is safe; opt out of React Compiler memoization */
"use no memo";

/**
 * Generic data table with TanStack Table and responsive card fallback.
 *
 * REQ-012 §13.3: Table/List component with column definitions,
 * row click navigation, and responsive card fallback.
 *
 * This task (§3.3) covers the base table only. Sorting, filtering,
 * pagination, and multi-select are added in §3.4–§3.6.
 */

import {
	type ColumnDef,
	flexRender,
	getCoreRowModel,
	useReactTable,
} from "@tanstack/react-table";

import { cn } from "@/lib/utils";
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
}: DataTableProps<TData>) {
	const table = useReactTable({
		data,
		columns,
		getCoreRowModel: getCoreRowModel(),
	});

	const hasCards = renderCard !== undefined;

	return (
		<div data-slot="data-table" className={cn(className)}>
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
									<TableHead key={header.id}>
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
									)}
									role={onRowClick ? "button" : undefined}
									tabIndex={onRowClick ? 0 : undefined}
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
					{data.length > 0 ? (
						data.map((row, index) => (
							<div key={getRowId?.(row) ?? index}>{renderCard(row)}</div>
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
