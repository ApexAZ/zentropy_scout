"use client";

/**
 * @fileoverview Toolbar for DataTable with search input and filter reset.
 *
 * Layer: component
 * Feature: shared
 *
 * REQ-012 §13.3: Toolbar search across table data.
 * Accepts children for page-specific filter controls (e.g., status dropdown).
 *
 * Coordinates with:
 * - lib/utils.ts: cn for conditional class merging
 * - components/ui/button.tsx: Button for filter reset action
 * - components/ui/input.tsx: Input for global search field
 *
 * Called by / Used by:
 * - components/applications/applications-list.tsx: application list toolbar
 * - components/dashboard/applications-table.tsx: dashboard applications toolbar
 * - components/dashboard/opportunities-table.tsx: dashboard opportunities toolbar
 */

import type { Table } from "@tanstack/react-table";
import { X } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DataTableToolbarProps<TData> {
	table: Table<TData>;
	searchPlaceholder?: string;
	className?: string;
	children?: React.ReactNode;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DataTableToolbar<TData>({
	table,
	searchPlaceholder = "Search...",
	className,
	children,
}: Readonly<DataTableToolbarProps<TData>>) {
	const globalFilter = (table.getState().globalFilter as string) ?? "";
	const isFiltered = table.getState().columnFilters.length > 0;

	return (
		<div className={cn("flex items-center gap-2", className)}>
			<Input
				aria-label={searchPlaceholder}
				placeholder={searchPlaceholder}
				value={globalFilter}
				onChange={(e) => table.setGlobalFilter(e.target.value)}
				className="max-w-sm"
				maxLength={256}
			/>
			{children}
			{isFiltered && (
				<Button
					variant="ghost"
					className="px-2 lg:px-3"
					onClick={() => table.resetColumnFilters()}
				>
					Reset
					<X className="ml-2 h-4 w-4" />
				</Button>
			)}
		</div>
	);
}
