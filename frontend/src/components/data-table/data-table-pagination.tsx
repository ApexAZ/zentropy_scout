"use client";

/**
 * Pagination controls for DataTable.
 *
 * REQ-012 §13.3: Page selector with per-page options 20/50/100.
 *
 * Renders page info, previous/next navigation, and a page-size
 * selector. Receives the TanStack table instance as a prop.
 */

import type { Table } from "@tanstack/react-table";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DataTablePaginationProps<TData> {
	table: Table<TData>;
	pageSizeOptions?: number[];
	className?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PAGE_SIZE_OPTIONS = [20, 50, 100];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DataTablePagination<TData>({
	table,
	pageSizeOptions = DEFAULT_PAGE_SIZE_OPTIONS,
	className,
}: DataTablePaginationProps<TData>) {
	const { pageIndex, pageSize } = table.getState().pagination;
	const pageCount = table.getPageCount();

	return (
		<nav
			aria-label="Table pagination"
			className={cn("flex items-center justify-between px-2", className)}
		>
			<p className="text-muted-foreground text-sm">
				Page {pageCount > 0 ? pageIndex + 1 : 0} of {pageCount}
			</p>
			<div className="flex items-center gap-2">
				<Select
					value={String(pageSize)}
					onValueChange={(value) => table.setPageSize(Number(value))}
				>
					<SelectTrigger className="w-[120px]" aria-label="Rows per page">
						<SelectValue />
					</SelectTrigger>
					<SelectContent>
						{pageSizeOptions.map((size) => (
							<SelectItem key={size} value={String(size)}>
								{size} per page
							</SelectItem>
						))}
					</SelectContent>
				</Select>
				<Button
					variant="outline"
					size="sm"
					onClick={() => table.previousPage()}
					disabled={!table.getCanPreviousPage()}
				>
					Previous
				</Button>
				<Button
					variant="outline"
					size="sm"
					onClick={() => table.nextPage()}
					disabled={!table.getCanNextPage()}
				>
					Next
				</Button>
			</div>
		</nav>
	);
}
