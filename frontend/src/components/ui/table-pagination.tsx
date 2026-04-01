/**
 * @fileoverview Shared pagination controls for data tables.
 *
 * Layer: component
 * Feature: shared
 *
 * Extracted from usage-table.tsx and transaction-table.tsx
 * to eliminate duplicated pagination UI. Renders Previous/Next
 * buttons with page counter.
 *
 * Coordinates with:
 * - components/ui/button.tsx: Button for Previous and Next actions
 *
 * Called by / Used by:
 * - usage/transaction-table.tsx: pagination in transaction history table
 * - usage/purchase-table.tsx: pagination in purchase history table
 * - usage/usage-table.tsx: pagination in usage details table
 */

import { Button } from "@/components/ui/button";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TablePaginationProps {
	page: number;
	totalPages: number;
	onPageChange: (page: number) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TablePagination({
	page,
	totalPages,
	onPageChange,
}: Readonly<TablePaginationProps>) {
	if (totalPages <= 1) return null;

	return (
		<div className="mt-4 flex items-center justify-between">
			<p className="text-muted-foreground text-sm">
				Page {page} of {totalPages}
			</p>
			<div className="flex gap-2">
				<Button
					variant="outline"
					size="sm"
					disabled={page <= 1}
					onClick={() => onPageChange(page - 1)}
				>
					Previous
				</Button>
				<Button
					variant="outline"
					size="sm"
					disabled={page >= totalPages}
					onClick={() => onPageChange(page + 1)}
				>
					Next
				</Button>
			</div>
		</div>
	);
}

export type { TablePaginationProps };
