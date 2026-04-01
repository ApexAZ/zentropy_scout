"use client";

/**
 * @fileoverview Sortable column header for DataTable.
 *
 * Layer: component
 * Feature: shared
 *
 * REQ-012 §13.3: Column sorting — click header to toggle asc/desc.
 *
 * Coordinates with:
 * - lib/utils.ts: cn for conditional class merging
 *
 * Called by / Used by:
 * - components/applications/application-columns.tsx: sortable column headers in application table
 * - components/dashboard/opportunities-table.tsx: sortable column headers in opportunities table
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
// Helpers
// ---------------------------------------------------------------------------

/** Renders the appropriate sort direction icon. */
function SortDirectionIcon({
	direction,
}: Readonly<{ direction: false | "asc" | "desc" }>) {
	if (direction === "asc") {
		return <ArrowUp data-testid="sort-asc" className="h-4 w-4" />;
	}
	if (direction === "desc") {
		return <ArrowDown data-testid="sort-desc" className="h-4 w-4" />;
	}
	return (
		<ArrowUpDown data-testid="sort-unsorted" className="h-4 w-4 opacity-50" />
	);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DataTableColumnHeader<TData, TValue>({
	column,
	title,
	className,
}: Readonly<DataTableColumnHeaderProps<TData, TValue>>) {
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
			<SortDirectionIcon direction={sorted} />
		</button>
	);
}
