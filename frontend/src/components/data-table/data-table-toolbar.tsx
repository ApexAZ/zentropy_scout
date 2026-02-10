"use client";

/**
 * Toolbar for DataTable with search input and filter reset.
 *
 * REQ-012 §13.3: Toolbar search across table data.
 *
 * Accepts children for page-specific filter controls (e.g., status dropdown).
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
}: DataTableToolbarProps<TData>) {
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
