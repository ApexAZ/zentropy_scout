"use client";

/**
 * @fileoverview Funding packs management tab for the admin page.
 *
 * Layer: component
 * Feature: admin
 *
 * REQ-022 §11.2, §10.4: Funding pack definitions with price formatting,
 * grant amounts, and highlight labels.
 *
 * Coordinates with:
 * - lib/api/admin.ts: createPack, deletePack, fetchPacks for API calls
 * - lib/query-keys.ts: queryKeys for cache key management
 * - lib/toast.ts: showToast for success/error feedback
 * - components/ui/button.tsx: Button for add and delete actions
 * - components/ui/confirmation-dialog.tsx: ConfirmationDialog for delete confirmation
 * - components/ui/table.tsx: Table, TableBody, TableCell, TableHead, TableHeader, TableRow for layout
 * - components/admin/add-pack-dialog.tsx: AddPackDialog for pack creation form
 * - types/admin.ts: FundingPackCreateRequest, FundingPackItem types
 *
 * Called by / Used by:
 * - components/admin/admin-config-page.tsx: Packs tab content
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, Trash2 } from "lucide-react";

import { createPack, deletePack, fetchPacks } from "@/lib/api/admin";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import type { FundingPackCreateRequest, FundingPackItem } from "@/types/admin";

import { AddPackDialog } from "./add-pack-dialog";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Funding packs management — list, add, delete. */
export function PacksTab() {
	const queryClient = useQueryClient();
	const [addOpen, setAddOpen] = useState(false);
	const [deleteTarget, setDeleteTarget] = useState<FundingPackItem | null>(
		null,
	);

	// -----------------------------------------------------------------------
	// Queries
	// -----------------------------------------------------------------------

	const { data, isLoading, error, refetch } = useQuery({
		queryKey: queryKeys.adminPacks,
		queryFn: () => fetchPacks(),
	});

	// -----------------------------------------------------------------------
	// Mutations
	// -----------------------------------------------------------------------

	const createMut = useMutation({
		mutationFn: (body: FundingPackCreateRequest) => createPack(body),
		onSuccess: () => {
			void queryClient.invalidateQueries({
				queryKey: queryKeys.adminPacks,
			});
			showToast.success("Pack created");
			setAddOpen(false);
		},
		onError: () => {
			showToast.error("Failed to create pack");
		},
	});

	const deleteMut = useMutation({
		mutationFn: (id: string) => deletePack(id),
		onSuccess: () => {
			void queryClient.invalidateQueries({
				queryKey: queryKeys.adminPacks,
			});
			showToast.success("Pack deleted");
			setDeleteTarget(null);
		},
		onError: () => {
			showToast.error("Failed to delete pack");
		},
	});

	// -----------------------------------------------------------------------
	// Loading / Error
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div data-testid="packs-loading" className="flex justify-center py-12">
				<Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
			</div>
		);
	}

	if (error) {
		return (
			<div className="py-8 text-center">
				<p className="text-destructive mb-2">Failed to load packs.</p>
				<Button variant="outline" size="sm" onClick={() => void refetch()}>
					Retry
				</Button>
			</div>
		);
	}

	const items = data?.data ?? [];

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<div data-testid="packs-tab" className="space-y-4 pt-4">
			<div className="flex items-center justify-between">
				<p className="text-muted-foreground text-sm">
					{items.length} pack{items.length === 1 ? "" : "s"}
				</p>
				<Button variant="outline" size="sm" onClick={() => setAddOpen(true)}>
					<Plus className="mr-1 h-4 w-4" />
					Add Pack
				</Button>
			</div>

			{items.length === 0 ? (
				<p className="text-muted-foreground py-8 text-center text-sm">
					No packs configured yet.
				</p>
			) : (
				<Table>
					<TableHeader>
						<TableRow>
							<TableHead>Name</TableHead>
							<TableHead>Price</TableHead>
							<TableHead>Grant (¢)</TableHead>
							<TableHead>Highlight</TableHead>
							<TableHead>Active</TableHead>
							<TableHead className="text-right">Actions</TableHead>
						</TableRow>
					</TableHeader>
					<TableBody>
						{items.map((item) => (
							<TableRow key={item.id}>
								<TableCell className="font-medium">{item.name}</TableCell>
								<TableCell>{item.price_display}</TableCell>
								<TableCell>{item.grant_cents.toLocaleString()}</TableCell>
								<TableCell>
									{item.highlight_label ? (
										<span className="bg-warning text-warning-foreground rounded-full px-2 py-0.5 text-xs font-medium">
											{item.highlight_label}
										</span>
									) : (
										<span className="text-muted-foreground">—</span>
									)}
								</TableCell>
								<TableCell>
									<span
										className={
											item.is_active ? "text-success" : "text-muted-foreground"
										}
									>
										{item.is_active ? "Active" : "Inactive"}
									</span>
								</TableCell>
								<TableCell className="text-right">
									<Button
										variant="ghost"
										size="sm"
										aria-label="Delete"
										onClick={() => setDeleteTarget(item)}
									>
										<Trash2 className="h-4 w-4" />
									</Button>
								</TableCell>
							</TableRow>
						))}
					</TableBody>
				</Table>
			)}

			{/* Add Pack Dialog */}
			<AddPackDialog
				open={addOpen}
				onOpenChange={setAddOpen}
				isPending={createMut.isPending}
				onSubmit={(data) => createMut.mutate(data)}
			/>

			{/* Delete Confirmation */}
			<ConfirmationDialog
				open={deleteTarget !== null}
				onOpenChange={(open) => {
					if (!open) setDeleteTarget(null);
				}}
				title="Delete Pack?"
				description={`Are you sure you want to delete "${deleteTarget?.name}"? This cannot be undone.`}
				confirmLabel="Confirm"
				variant="destructive"
				loading={deleteMut.isPending}
				onConfirm={() => {
					if (deleteTarget) deleteMut.mutate(deleteTarget.id);
				}}
			/>
		</div>
	);
}
