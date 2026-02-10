"use client";

/**
 * Sortable column header for DataTable.
 *
 * REQ-012 §13.3: Column sorting — click header to toggle asc/desc.
 *
 * Usage in column definitions:
 * ```tsx
 * { accessorKey: "name", header: ({ column }) => <DataTableColumnHeader column={column} title="Name" /> }
 * ```
 */

import type { Column } from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";

import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DataTableColumnHeaderProps<TData, TValue> {
	column: Column<TData, TValue>;
	title: string;
	className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DataTableColumnHeader<TData, TValue>({
	column,
	title,
	className,
}: DataTableColumnHeaderProps<TData, TValue>) {
	if (!column.getCanSort()) {
		return <div className={cn(className)}>{title}</div>;
	}

	const sorted = column.getIsSorted();

	return (
		<button
			type="button"
			className={cn(
				"hover:bg-accent hover:text-accent-foreground -ml-4 flex h-8 items-center gap-1 rounded-md px-4",
				className,
			)}
			onClick={() => column.toggleSorting()}
		>
			<span>{title}</span>
			{sorted === "asc" ? (
				<ArrowUp data-testid="sort-asc" className="h-4 w-4" />
			) : sorted === "desc" ? (
				<ArrowDown data-testid="sort-desc" className="h-4 w-4" />
			) : (
				<ArrowUpDown
					data-testid="sort-unsorted"
					className="h-4 w-4 opacity-50"
				/>
			)}
		</button>
	);
}
