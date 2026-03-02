"use client";

/**
 * Task routing management tab.
 *
 * REQ-022 §11.2, §10.3: Per-provider routing table with task type to model
 * mapping. Add form with provider/task_type/model fields.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, Trash2 } from "lucide-react";

import { createRouting, deleteRouting, fetchRouting } from "@/lib/api/admin";
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
import type { TaskRoutingCreateRequest, TaskRoutingItem } from "@/types/admin";

import { AddRoutingDialog } from "./add-routing-dialog";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Task routing management — list, add, delete. */
export function RoutingTab() {
	const queryClient = useQueryClient();
	const [addOpen, setAddOpen] = useState(false);
	const [deleteTarget, setDeleteTarget] = useState<TaskRoutingItem | null>(
		null,
	);

	// -----------------------------------------------------------------------
	// Queries
	// -----------------------------------------------------------------------

	const { data, isLoading, error, refetch } = useQuery({
		queryKey: queryKeys.adminRouting,
		queryFn: () => fetchRouting(),
	});

	// -----------------------------------------------------------------------
	// Mutations
	// -----------------------------------------------------------------------

	const createMut = useMutation({
		mutationFn: (body: TaskRoutingCreateRequest) => createRouting(body),
		onSuccess: () => {
			void queryClient.invalidateQueries({
				queryKey: queryKeys.adminRouting,
			});
			showToast.success("Routing created");
			setAddOpen(false);
		},
		onError: () => {
			showToast.error("Failed to create routing");
		},
	});

	const deleteMut = useMutation({
		mutationFn: (id: string) => deleteRouting(id),
		onSuccess: () => {
			void queryClient.invalidateQueries({
				queryKey: queryKeys.adminRouting,
			});
			showToast.success("Routing deleted");
			setDeleteTarget(null);
		},
		onError: () => {
			showToast.error("Failed to delete routing");
		},
	});

	// -----------------------------------------------------------------------
	// Loading / Error
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div data-testid="routing-loading" className="flex justify-center py-12">
				<Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
			</div>
		);
	}

	if (error) {
		return (
			<div className="py-8 text-center">
				<p className="text-destructive mb-2">Failed to load routing.</p>
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
		<div data-testid="routing-tab" className="space-y-4 pt-4">
			<div className="flex items-center justify-between">
				<p className="text-muted-foreground text-sm">
					{items.length} routing entr{items.length === 1 ? "y" : "ies"}
				</p>
				<Button variant="outline" size="sm" onClick={() => setAddOpen(true)}>
					<Plus className="mr-1 h-4 w-4" />
					Add Routing
				</Button>
			</div>

			{items.length === 0 ? (
				<p className="text-muted-foreground py-8 text-center text-sm">
					No routing entries yet.
				</p>
			) : (
				<Table>
					<TableHeader>
						<TableRow>
							<TableHead>Provider</TableHead>
							<TableHead>Task Type</TableHead>
							<TableHead>Model</TableHead>
							<TableHead>Display Name</TableHead>
							<TableHead className="text-right">Actions</TableHead>
						</TableRow>
					</TableHeader>
					<TableBody>
						{items.map((item) => (
							<TableRow key={item.id}>
								<TableCell>{item.provider}</TableCell>
								<TableCell className="font-mono text-xs">
									{item.task_type}
								</TableCell>
								<TableCell className="font-mono text-xs">
									{item.model}
								</TableCell>
								<TableCell>
									{item.model_display_name ?? (
										<span className="text-muted-foreground">—</span>
									)}
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

			{/* Add Routing Dialog */}
			<AddRoutingDialog
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
				title="Delete Routing?"
				description={`Are you sure you want to delete routing for ${deleteTarget?.provider}/${deleteTarget?.task_type}?`}
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
