"use client";

/**
 * Model registry management tab.
 *
 * REQ-022 §11.2: Table of registered models with add/edit/deactivate
 * controls. Uses TanStack Query for data fetching and mutations.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, Power, Trash2 } from "lucide-react";

import {
	createModel,
	deleteModel,
	fetchModels,
	updateModel,
} from "@/lib/api/admin";
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
import type {
	ModelRegistryCreateRequest,
	ModelRegistryItem,
} from "@/types/admin";

import { AddModelDialog } from "./add-model-dialog";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Model registry management — list, add, toggle, delete. */
export function ModelsTab() {
	const queryClient = useQueryClient();
	const [addOpen, setAddOpen] = useState(false);
	const [deleteTarget, setDeleteTarget] = useState<ModelRegistryItem | null>(
		null,
	);

	// -----------------------------------------------------------------------
	// Queries
	// -----------------------------------------------------------------------

	const { data, isLoading, error, refetch } = useQuery({
		queryKey: queryKeys.adminModels,
		queryFn: () => fetchModels(),
	});

	// -----------------------------------------------------------------------
	// Mutations
	// -----------------------------------------------------------------------

	const createMut = useMutation({
		mutationFn: (body: ModelRegistryCreateRequest) => createModel(body),
		onSuccess: () => {
			void queryClient.invalidateQueries({ queryKey: queryKeys.adminModels });
			showToast.success("Model created");
			setAddOpen(false);
		},
		onError: () => {
			showToast.error("Failed to create model");
		},
	});

	const toggleMut = useMutation({
		mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
			updateModel(id, { is_active }),
		onSuccess: () => {
			void queryClient.invalidateQueries({ queryKey: queryKeys.adminModels });
			showToast.success("Model updated");
		},
		onError: () => {
			showToast.error("Failed to update model");
		},
	});

	const deleteMut = useMutation({
		mutationFn: (id: string) => deleteModel(id),
		onSuccess: () => {
			void queryClient.invalidateQueries({ queryKey: queryKeys.adminModels });
			showToast.success("Model deleted");
			setDeleteTarget(null);
		},
		onError: () => {
			showToast.error("Failed to delete model");
		},
	});

	// -----------------------------------------------------------------------
	// Loading / Error
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div data-testid="models-loading" className="flex justify-center py-12">
				<Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
			</div>
		);
	}

	if (error) {
		return (
			<div className="py-8 text-center">
				<p className="text-destructive mb-2">Failed to load models.</p>
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
		<div data-testid="models-tab" className="space-y-4 pt-4">
			<div className="flex items-center justify-between">
				<p className="text-muted-foreground text-sm">
					{items.length} model{items.length !== 1 ? "s" : ""} registered
				</p>
				<Button variant="outline" size="sm" onClick={() => setAddOpen(true)}>
					<Plus className="mr-1 h-4 w-4" />
					Add Model
				</Button>
			</div>

			{items.length === 0 ? (
				<p className="text-muted-foreground py-8 text-center text-sm">
					No models registered yet.
				</p>
			) : (
				<Table>
					<TableHeader>
						<TableRow>
							<TableHead>Provider</TableHead>
							<TableHead>Model</TableHead>
							<TableHead>Display Name</TableHead>
							<TableHead>Type</TableHead>
							<TableHead>Status</TableHead>
							<TableHead className="text-right">Actions</TableHead>
						</TableRow>
					</TableHeader>
					<TableBody>
						{items.map((item) => (
							<TableRow key={item.id}>
								<TableCell>{item.provider}</TableCell>
								<TableCell className="font-mono text-xs">
									{item.model}
								</TableCell>
								<TableCell>{item.display_name}</TableCell>
								<TableCell>{item.model_type}</TableCell>
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
										aria-label="Toggle active"
										onClick={() =>
											toggleMut.mutate({
												id: item.id,
												is_active: !item.is_active,
											})
										}
									>
										<Power className="h-4 w-4" />
									</Button>
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

			{/* Add Model Dialog */}
			<AddModelDialog
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
				title="Delete Model?"
				description={`Are you sure you want to delete "${deleteTarget?.display_name}"? This cannot be undone.`}
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
