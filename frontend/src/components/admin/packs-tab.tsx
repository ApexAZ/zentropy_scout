"use client";

/**
 * Credit packs management tab.
 *
 * REQ-022 §11.2, §10.4: Credit pack definitions with price formatting,
 * credit amounts, and highlight labels.
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
import type { CreditPackCreateRequest, CreditPackItem } from "@/types/admin";

import { AddPackDialog } from "./add-pack-dialog";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Credit packs management — list, add, delete. */
export function PacksTab() {
	const queryClient = useQueryClient();
	const [addOpen, setAddOpen] = useState(false);
	const [deleteTarget, setDeleteTarget] = useState<CreditPackItem | null>(null);

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
		mutationFn: (body: CreditPackCreateRequest) => createPack(body),
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
							<TableHead>Credits</TableHead>
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
								<TableCell>{item.credit_amount.toLocaleString()}</TableCell>
								<TableCell>
									{item.highlight_label ? (
										<span className="rounded bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
											{item.highlight_label}
										</span>
									) : (
										<span className="text-muted-foreground">—</span>
									)}
								</TableCell>
								<TableCell>
									<span
										className={
											item.is_active
												? "text-green-600"
												: "text-muted-foreground"
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
